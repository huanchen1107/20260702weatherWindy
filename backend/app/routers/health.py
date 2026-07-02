from fastapi import APIRouter
from typing import Dict, Any
from backend.app.services import temperature_service
from backend.app import config

router = APIRouter(tags=["health"])

@router.get("/api/health")
async def health_check() -> Dict[str, Any]:
    """
    Returns API status, in-memory cache status, station count, and last refresh timestamp.
    """
    cache_info = temperature_service.get_cache_info()
    return {
        "status": "ok" if cache_info["status"] != "empty" else "initializing",
        "cwa_cache_status": cache_info["status"],
        "cached_records_count": cache_info["count"],
        "cache_last_updated": cache_info["last_updated"],
        "latest_cwa_time": cache_info["latest_cwa_time"]
    }

@router.get("/api/config")
async def client_config() -> Dict[str, Any]:
    """
    Exposes safe config values (like Windy API Key) to the client application.
    """
    return {
        "windy_api_key": config.WINDY_API_KEY,
        "cwa_dataset_url": config.CWA_DATA_URL
    }
