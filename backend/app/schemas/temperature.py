from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Dict, Any, Optional

class StationTemperature(BaseModel):
    station_id: str = Field(..., description="Unique CWA station identifier")
    station_name: str = Field(..., description="Name of the weather station")
    county: Optional[str] = Field(None, description="County name, e.g. 花蓮縣")
    town: Optional[str] = Field(None, description="Town/district name, e.g. 秀林鄉")
    
    lat: float = Field(..., description="WGS84 station latitude")
    lon: float = Field(..., description="WGS84 station longitude")
    altitude_m: Optional[float] = Field(None, description="Station altitude in meters")
    
    observed_at: datetime = Field(..., description="Observation timestamp")
    temperature_c: float = Field(..., description="Air temperature in Celsius")
    
    humidity_percent: Optional[float] = Field(None, description="Relative humidity percentage")
    pressure_hpa: Optional[float] = Field(None, description="Air pressure in hPa")
    wind_speed_mps: Optional[float] = Field(None, description="Wind speed in meters per second")
    wind_direction_deg: Optional[float] = Field(None, description="Wind direction in degrees")
    precipitation_mm: Optional[float] = Field(None, description="Rain precipitation in mm")
    weather: Optional[str] = Field(None, description="Weather description, e.g. 晴, 多雲")
    
    # Daily Extreme High/Low
    daily_high_temperature: Optional[float] = Field(None, description="Daily extreme high temperature")
    daily_high_time: Optional[datetime] = Field(None, description="Time of daily high temperature")
    daily_low_temperature: Optional[float] = Field(None, description="Daily extreme low temperature")
    daily_low_time: Optional[datetime] = Field(None, description="Time of daily low temperature")

class LatestTemperatureResponse(BaseModel):
    source: str = "CWA"
    updated_at: datetime
    count: int
    stations: List[StationTemperature]

class GeoJSONGeometry(BaseModel):
    type: str = "Point"
    coordinates: List[float]  # [lon, lat]

class GeoJSONFeature(BaseModel):
    type: str = "Feature"
    geometry: GeoJSONGeometry
    properties: Dict[str, Any]

class GeoJSONFeatureCollection(BaseModel):
    type: str = "FeatureCollection"
    features: List[GeoJSONFeature]
