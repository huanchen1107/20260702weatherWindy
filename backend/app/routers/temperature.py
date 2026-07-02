from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional
from backend.app.services import temperature_service
from backend.app.schemas.temperature import LatestTemperatureResponse, GeoJSONFeatureCollection

router = APIRouter(prefix="/api/temperature", tags=["temperature"])

@router.get("/latest", response_model=LatestTemperatureResponse)
async def get_latest_temperatures():
    """
    Returns latest parsed and normalized weather station records.
    """
    return temperature_service.get_latest_stations()

@router.get("/geojson", response_model=Dict[str, Any])
async def get_geojson_temperatures():
    """
    Returns weather station observations formatted in GeoJSON.
    Suitable for map overlays like Leaflet.
    """
    return temperature_service.get_latest_geojson()

@router.get("/stations/{station_id}")
async def get_station_detail(station_id: str):
    """
    Returns detailed current observations and daily extremes for a single station.
    """
    detail = temperature_service.get_station_detail(station_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Station with ID '{station_id}' not found.")
    return detail

@router.post("/refresh")
async def force_refresh_cache():
    """
    Manually forces the API to clear its current in-memory cache and re-fetch from CWA.
    """
    result = temperature_service.refresh_cache()
    if result.get("status") == "failed":
        raise HTTPException(status_code=500, detail=result.get("error"))
    return result
