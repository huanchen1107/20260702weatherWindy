import urllib.request
import urllib.parse
import json
import csv
import sqlite3
import ssl
import os

url = "https://opendata.cwa.gov.tw/fileapi/v1/opendataapi/O-A0001-001?downloadType=WEB&format=JSON"
CSV_FILE = "weather.csv"
DB_FILE = "weather.db"
TABLE_NAME = "weather"

class AuthStrippingRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Create redirect request using default behavior
        new_req = super().redirect_request(req, fp, code, msg, headers, newurl)
        # Parse hostnames to compare them
        orig_host = urllib.parse.urlparse(req.full_url).hostname
        new_host = urllib.parse.urlparse(newurl).hostname
        # If target host is different, strip Authorization header to prevent S3 authentication errors
        if orig_host != new_host:
            for key in list(new_req.headers.keys()):
                if key.lower() == 'authorization':
                    del new_req.headers[key]
        return new_req

def parse_float(val):
    if val is None:
        return None
    try:
        f = float(val)
        # CWA uses -99, -99.0, -999, etc. to represent missing values
        if f <= -99.0:
            return None
        return f
    except ValueError:
        return None

def parse_int(val):
    if val is None:
        return None
    try:
        i = int(val)
        if i <= -99:
            return None
        return i
    except ValueError:
        # Try float conversion first then int
        try:
            f = float(val)
            if f <= -99.0:
                return None
            return int(f)
        except ValueError:
            return None

def get_east_asian_width_length(text):
    """Helper to calculate display width of text containing Chinese characters."""
    import unicodedata
    width = 0
    for char in text:
        if unicodedata.east_asian_width(char) in ('F', 'W', 'A'):
            width += 2
        else:
            width += 1
    return width

def pad_text(text, width):
    if text is None:
        text = ""
    text_len = get_east_asian_width_length(text)
    padding = max(0, width - text_len)
    return text + (" " * padding)

def load_env(env_path=".env"):
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    os.environ[key] = value

def load_token_from_db(db_path="token.db"):
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.execute("SELECT key, value FROM secrets")
            for key, value in cursor.fetchall():
                if key not in os.environ:
                    os.environ[key] = value
            conn.close()
        except Exception as e:
            print(f"Warning: Failed to load token.db: {e}")

def main():
    # Load API token from environment / .env file / token.db
    load_env()
    load_token_from_db()
    token = os.environ.get("CWA_API_TOKEN")
    if not token:
        print("Error: CWA_API_TOKEN not found in environment variables or .env file.")
        return

    print("Fetching data from CWA API using Authorization header...")
    req = urllib.request.Request(
        url, 
        headers={
            'User-Agent': 'Mozilla/5.0',
            'Authorization': token
        }
    )
    context = ssl._create_unverified_context()
    opener = urllib.request.build_opener(
        AuthStrippingRedirectHandler(),
        urllib.request.HTTPSHandler(context=context)
    )
    
    try:
        with opener.open(req) as response:
            raw_data = json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"Error fetching data: {e}")
        return
        
    stations = raw_data.get("cwaopendata", {}).get("dataset", {}).get("Station", [])
    print(f"Successfully fetched {len(stations)} stations from API.")
    
    parsed_stations = []
    
    for station in stations:
        station_name = station.get("StationName")
        station_id = station.get("StationId")
        obs_time = station.get("ObsTime", {}).get("DateTime")
        
        geo_info = station.get("GeoInfo", {})
        altitude = parse_float(geo_info.get("StationAltitude"))
        county_name = geo_info.get("CountyName")
        town_name = geo_info.get("TownName")
        county_code = geo_info.get("CountyCode")
        town_code = geo_info.get("TownCode")
        
        # WGS84 Coordinates
        latitude = None
        longitude = None
        coordinates = geo_info.get("Coordinates", [])
        for coord in coordinates:
            if coord.get("CoordinateName") == "WGS84":
                latitude = parse_float(coord.get("StationLatitude"))
                longitude = parse_float(coord.get("StationLongitude"))
                break
        if latitude is None and len(coordinates) > 0:
            latitude = parse_float(coordinates[0].get("StationLatitude"))
            longitude = parse_float(coordinates[0].get("StationLongitude"))
            
        weather_element = station.get("WeatherElement", {})
        weather = weather_element.get("Weather")
        precipitation = parse_float(weather_element.get("Now", {}).get("Precipitation"))
        wind_direction = parse_float(weather_element.get("WindDirection"))
        wind_speed = parse_float(weather_element.get("WindSpeed"))
        air_temperature = parse_float(weather_element.get("AirTemperature"))
        relative_humidity = parse_int(weather_element.get("RelativeHumidity"))
        air_pressure = parse_float(weather_element.get("AirPressure"))
        
        # Daily extreme temps
        daily_extreme = weather_element.get("DailyExtreme", {})
        daily_high_temp = parse_float(daily_extreme.get("DailyHigh", {}).get("TemperatureInfo", {}).get("AirTemperature"))
        daily_high_time = daily_extreme.get("DailyHigh", {}).get("TemperatureInfo", {}).get("Occurred_at", {}).get("DateTime")
        if daily_high_time == "-99":
            daily_high_time = None
            
        daily_low_temp = parse_float(daily_extreme.get("DailyLow", {}).get("TemperatureInfo", {}).get("AirTemperature"))
        daily_low_time = daily_extreme.get("DailyLow", {}).get("TemperatureInfo", {}).get("Occurred_at", {}).get("DateTime")
        if daily_low_time == "-99":
            daily_low_time = None
            
        row = {
            "station_name": station_name,
            "station_id": station_id,
            "observation_time": obs_time,
            "latitude": latitude,
            "longitude": longitude,
            "altitude": altitude,
            "county_name": county_name,
            "town_name": town_name,
            "county_code": county_code,
            "town_code": town_code,
            "weather": weather,
            "precipitation": precipitation,
            "wind_direction": wind_direction,
            "wind_speed": wind_speed,
            "temperature": air_temperature,
            "relative_humidity": relative_humidity,
            "air_pressure": air_pressure,
            "daily_high_temperature": daily_high_temp,
            "daily_high_time": daily_high_time,
            "daily_low_temperature": daily_low_temp,
            "daily_low_time": daily_low_time
        }
        parsed_stations.append(row)
        
    # Write to CSV with utf-8-sig BOM (so Excel displays Chinese characters properly)
    headers = [
        "station_name", "station_id", "observation_time", "latitude", "longitude", "altitude",
        "county_name", "town_name", "county_code", "town_code", "weather", "precipitation",
        "wind_direction", "wind_speed", "temperature", "relative_humidity", "air_pressure",
        "daily_high_temperature", "daily_high_time", "daily_low_temperature", "daily_low_time"
    ]
    
    print(f"Writing to CSV: {CSV_FILE}...")
    with open(CSV_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(parsed_stations)
    print(f"Successfully saved CSV to {os.path.abspath(CSV_FILE)}")
    
    # Write to SQLite Database
    print(f"Writing to SQLite: {DB_FILE}...")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Create Table
    cursor.execute(f"DROP TABLE IF EXISTS {TABLE_NAME}")
    create_table_query = f"""
    CREATE TABLE {TABLE_NAME} (
        station_name TEXT,
        station_id TEXT PRIMARY KEY,
        observation_time TEXT,
        latitude REAL,
        longitude REAL,
        altitude REAL,
        county_name TEXT,
        town_name TEXT,
        county_code TEXT,
        town_code TEXT,
        weather TEXT,
        precipitation REAL,
        wind_direction REAL,
        wind_speed REAL,
        temperature REAL,
        relative_humidity INTEGER,
        air_pressure REAL,
        daily_high_temperature REAL,
        daily_high_time TEXT,
        daily_low_temperature REAL,
        daily_low_time TEXT
    )
    """
    cursor.execute(create_table_query)
    
    # Insert data
    insert_query = f"""
    INSERT INTO {TABLE_NAME} (
        station_name, station_id, observation_time, latitude, longitude, altitude,
        county_name, town_name, county_code, town_code, weather, precipitation,
        wind_direction, wind_speed, temperature, relative_humidity, air_pressure,
        daily_high_temperature, daily_high_time, daily_low_temperature, daily_low_time
    ) VALUES (
        :station_name, :station_id, :observation_time, :latitude, :longitude, :altitude,
        :county_name, :town_name, :county_code, :town_code, :weather, :precipitation,
        :wind_direction, :wind_speed, :temperature, :relative_humidity, :air_pressure,
        :daily_high_temperature, :daily_high_time, :daily_low_temperature, :daily_low_time
    )
    """
    cursor.executemany(insert_query, parsed_stations)
    conn.commit()
    
    # Verify count
    cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}")
    count = cursor.fetchone()[0]
    print(f"Successfully saved {count} records to table '{TABLE_NAME}' in {os.path.abspath(DB_FILE)}\n")
    
    # Fetch sample data to demonstrate database content
    cursor.execute(f"""
        SELECT station_name, county_name, temperature, weather, precipitation 
        FROM {TABLE_NAME} 
        WHERE temperature IS NOT NULL 
        LIMIT 5
    """)
    rows = cursor.fetchall()
    
    print("Database Verification - Sample Records:")
    headers_view = f"| {pad_text('Station', 12)} | {pad_text('County', 12)} | {pad_text('Temp (°C)', 10)} | {pad_text('Weather', 10)} | {pad_text('Rain (mm)', 10)} |"
    divider = "-" * len(headers_view)
    print(divider)
    print(headers_view)
    print(divider)
    for row in rows:
        name = row[0]
        county = row[1]
        temp = f"{row[2]:.1f}" if row[2] is not None else "N/A"
        weath = row[3] if row[3] is not None else "N/A"
        rain = f"{row[4]:.1f}" if row[4] is not None else "N/A"
        print(f"| {pad_text(name, 12)} | {pad_text(county, 12)} | {pad_text(temp, 10)} | {pad_text(weath, 10)} | {pad_text(rain, 10)} |")
    print(divider)
    
    conn.close()

if __name__ == "__main__":
    main()
