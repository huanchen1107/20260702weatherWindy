import time
import threading
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from backend.app.routers import temperature, health
from backend.app.services import temperature_service
from backend.app import config

app = FastAPI(
    title="CWA Weather Observation Visualization Service",
    description="Backend API and cache layer for displaying CWA temperature broadcasts on a Windy Map",
    version="1.0.0"
)

# Configure CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(temperature.router)
app.include_router(health.router)

# Serve Frontend SPA
@app.get("/")
async def serve_index():
    return FileResponse("frontend/index.html")

# Mount frontend files (css, js, images)
# Make sure frontend folder exists before mounting
import os
os.makedirs("frontend", exist_ok=True)
app.mount("/static", StaticFiles(directory="frontend"), name="static")

def background_cache_refresher():
    """
    Background worker thread that regularly updates the CWA data cache.
    """
    print("Background Worker: Started CWA cache refresh loop.")
    # Fetch immediately on start to populate cache
    try:
        temperature_service.refresh_cache()
    except Exception as e:
        print(f"Background Worker: Initial cache fetch failed: {e}")
        
    while True:
        # Sleep for the configured cache TTL (default 10 minutes)
        time.sleep(config.CACHE_TTL)
        print("Background Worker: Triggering hourly CWA cache refresh...")
        try:
            temperature_service.refresh_cache()
        except Exception as e:
            print(f"Background Worker: Scheduled cache refresh failed: {e}")

@app.on_event("startup")
def startup_event():
    # Start background scheduler thread
    refresher_thread = threading.Thread(target=background_cache_refresher, daemon=True)
    refresher_thread.start()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host=config.HOST, port=config.PORT, reload=config.DEBUG)
