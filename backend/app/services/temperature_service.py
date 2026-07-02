import threading
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from backend.app.services import cwa_client
from backend.app.schemas.temperature import StationTemperature
from backend.app import config

# Thread-safe in-memory cache
_cache_lock = threading.Lock()
_cached_stations: List[StationTemperature] = []
_last_updated: Optional[datetime] = None
_latest_cwa_time: Optional[datetime] = None
_cache_status: str = "empty"  # empty, fresh, stale

INVALID_VALUES = {"", "X", "NA", "null", "None", "-99", "-99.0", "-999", "-999.0", "-9999"}

def parse_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    val_str = str(val).strip()
    if val_str in INVALID_VALUES:
        return None
    try:
        f = float(val_str)
        if f <= -99.0:  # Safety fallback for double/negative indicators
            return None
        return f
    except ValueError:
        return None

def parse_int(val: Any) -> Optional[int]:
    if val is None:
        return None
    val_str = str(val).strip()
    if val_str in INVALID_VALUES:
        return None
    try:
        i = int(val_str)
        if i <= -99:
            return None
        return i
    except ValueError:
        try:
            f = float(val_str)
            if f <= -99.0:
                return None
            return int(f)
        except ValueError:
            return None

def parse_datetime(val: Any) -> Optional[datetime]:
    if val is None:
        return None
    val_str = str(val).strip()
    if val_str in INVALID_VALUES:
        return None
    try:
        return datetime.fromisoformat(val_str)
    except ValueError:
        return None

def normalize_station_data(raw_data: dict) -> List[StationTemperature]:
    """
    Parses the raw CWA API JSON structure into a list of StationTemperature models.
    """
    stations = raw_data.get("cwaopendata", {}).get("dataset", {}).get("Station", [])
    normalized = []
    
    for station in stations:
        try:
            station_name = station.get("StationName")
            station_id = station.get("StationId")
            obs_time_str = station.get("ObsTime", {}).get("DateTime")
            
            # 1. Validation Rules: Station ID, name, and time must exist
            if not station_id or not station_name or not obs_time_str:
                continue
                
            obs_time = parse_datetime(obs_time_str)
            if not obs_time:
                continue
                
            geo_info = station.get("GeoInfo", {})
            altitude = parse_float(geo_info.get("StationAltitude"))
            county_name = geo_info.get("CountyName")
            town_name = geo_info.get("TownName")
            
            # WGS84 Coordinates extraction
            lat, lon = None, None
            coordinates = geo_info.get("Coordinates", [])
            for coord in coordinates:
                if coord.get("CoordinateName") == "WGS84":
                    lat = parse_float(coord.get("StationLatitude"))
                    lon = parse_float(coord.get("StationLongitude"))
                    break
            
            # Fallback coordinate check
            if (lat is None or lon is None) and coordinates:
                lat = parse_float(coordinates[0].get("StationLatitude"))
                lon = parse_float(coordinates[0].get("StationLongitude"))
                
            # Validation Rules: Latitude & Longitude must exist and be valid
            if lat is None or lon is None:
                continue
                
            weather_element = station.get("WeatherElement", {})
            
            # Temperature validation
            temp = parse_float(weather_element.get("AirTemperature"))
            # Validation Rules: Temperature must exist and be in range -20 to 50
            if temp is None or temp < -20.0 or temp > 50.0:
                continue
                
            weather = weather_element.get("Weather")
            precipitation = parse_float(weather_element.get("Now", {}).get("Precipitation"))
            wind_direction = parse_float(weather_element.get("WindDirection"))
            wind_speed = parse_float(weather_element.get("WindSpeed"))
            relative_humidity = parse_int(weather_element.get("RelativeHumidity"))
            air_pressure = parse_float(weather_element.get("AirPressure"))
            
            # Daily extremes
            daily_extreme = weather_element.get("DailyExtreme", {})
            daily_high_temp = parse_float(daily_extreme.get("DailyHigh", {}).get("TemperatureInfo", {}).get("AirTemperature"))
            daily_high_time = parse_datetime(daily_extreme.get("DailyHigh", {}).get("TemperatureInfo", {}).get("Occurred_at", {}).get("DateTime"))
            
            daily_low_temp = parse_float(daily_extreme.get("DailyLow", {}).get("TemperatureInfo", {}).get("AirTemperature"))
            daily_low_time = parse_datetime(daily_extreme.get("DailyLow", {}).get("TemperatureInfo", {}).get("Occurred_at", {}).get("DateTime"))
            
            model = StationTemperature(
                station_id=station_id,
                station_name=station_name,
                county=county_name,
                town=town_name,
                lat=lat,
                lon=lon,
                altitude_m=altitude,
                observed_at=obs_time,
                temperature_c=temp,
                humidity_percent=relative_humidity,
                pressure_hpa=air_pressure,
                wind_speed_mps=wind_speed,
                wind_direction_deg=wind_direction,
                precipitation_mm=precipitation,
                weather=weather,
                daily_high_temperature=daily_high_temp,
                daily_high_time=daily_high_time,
                daily_low_temperature=daily_low_temp,
                daily_low_time=daily_low_time
            )
            normalized.append(model)
        except Exception as e:
            # Skip invalid records and log issue silently
            # print(f"Error parsing station {station.get('StationId')}: {e}")
            continue
            
    return normalized

def refresh_cache() -> dict:
    """
    Triggers fetching data from CWA API and updating the internal cache.
    Thread-safe.
    """
    global _cached_stations, _last_updated, _latest_cwa_time, _cache_status
    
    print("Temperature Service: Refreshing CWA Cache...")
    try:
        raw_data = cwa_client.fetch_raw_cwa_data()
        parsed_stations = normalize_station_data(raw_data)
        
        # Extract sent time for dataset update reference
        sent_time_str = raw_data.get("cwaopendata", {}).get("sent")
        sent_time = parse_datetime(sent_time_str) or datetime.now(timezone.utc)
        
        with _cache_lock:
            _cached_stations = parsed_stations
            _last_updated = datetime.now(timezone.utc)
            _latest_cwa_time = sent_time
            _cache_status = "fresh"
            
        print(f"Temperature Service: Cache updated successfully with {len(parsed_stations)} stations.")
        return {
            "status": "success",
            "count": len(parsed_stations),
            "updated_at": _last_updated.isoformat(),
            "latest_cwa_time": _latest_cwa_time.isoformat()
        }
    except Exception as e:
        print(f"Temperature Service Error: Failed to refresh cache: {e}")
        with _cache_lock:
            if _cached_stations:
                _cache_status = "stale"
            else:
                _cache_status = "empty"
                
        return {
            "status": "failed",
            "error": str(e),
            "cache_status": _cache_status
        }

def get_latest_stations() -> dict:
    """
    Returns latest parsed stations. Fetches from CWA API if cache is empty.
    """
    with _cache_lock:
        is_empty = len(_cached_stations) == 0
        
    if is_empty:
        refresh_cache()
        
    with _cache_lock:
        # Format list to dict matches schema
        updated_val = _last_updated or datetime.now(timezone.utc)
        obs_val = _latest_cwa_time or updated_val
        
        # Convert Pydantic objects to dicts
        return {
            "source": "CWA",
            "updated_at": obs_val.isoformat(),
            "cache_updated_at": updated_val.isoformat(),
            "cache_status": _cache_status,
            "count": len(_cached_stations),
            "stations": [s.model_dump() for s in _cached_stations]
        }

def get_latest_geojson() -> dict:
    """
    Returns latest CWA station temperatures in GeoJSON format.
    """
    stations_data = get_latest_stations()
    features = []
    
    for s in stations_data["stations"]:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [s["lon"], s["lat"]]
            },
            "properties": {
                "station_id": s["station_id"],
                "station_name": s["station_name"],
                "temperature_c": s["temperature_c"],
                "county": s["county"],
                "town": s["town"],
                "observed_at": s["observed_at"],
                "weather": s["weather"],
                "humidity_percent": s["humidity_percent"],
                "wind_speed_mps": s["wind_speed_mps"]
            }
        })
        
    return {
        "type": "FeatureCollection",
        "features": features
    }

def get_station_detail(station_id: str) -> Optional[dict]:
    """
    Returns the details of a single station.
    """
    stations_data = get_latest_stations()
    for s in stations_data["stations"]:
        if s["station_id"] == station_id:
            return s
    return None

def get_cache_info() -> dict:
    """
    Returns cache statistics.
    """
    with _cache_lock:
        return {
            "status": _cache_status,
            "count": len(_cached_stations),
            "last_updated": _last_updated.isoformat() if _last_updated else None,
            "latest_cwa_time": _latest_cwa_time.isoformat() if _latest_cwa_time else None
        }
