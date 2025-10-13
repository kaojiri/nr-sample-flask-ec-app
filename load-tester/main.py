"""
Load Testing Automation - Main Application
"""
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import logging
from pathlib import Path

from config import settings
from api import router as api_router
from worker_pool import worker_pool
from load_test_manager import LoadTestManager

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Load Testing Automation",
    description="Automated load testing for Flask EC application",
    version="1.0.0"
)

# Create necessary directories
Path("logs").mkdir(exist_ok=True)
Path("data").mkdir(exist_ok=True)
Path("static").mkdir(exist_ok=True)
Path("templates").mkdir(exist_ok=True)

# Setup templates
templates = Jinja2Templates(directory="templates")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include API routes
app.include_router(api_router, prefix="/api")

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page"""
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "load-tester"}

@app.on_event("startup")
async def startup_event():
    """Application startup event"""
    logger.info("Load Testing Automation service starting up...")
    logger.info(f"Target application URL: {settings.target_app_url}")
    logger.info(f"Log level: {settings.log_level}")
    
    # Initialize load test manager with worker pool
    import load_test_manager as ltm_module
    ltm_module.load_test_manager = LoadTestManager(worker_pool)
    logger.info("Load test manager initialized")
    
    # Initialize scheduler
    from scheduler import initialize_scheduler
    def get_load_test_manager():
        return ltm_module.load_test_manager
    
    scheduler = initialize_scheduler(get_load_test_manager)
    await scheduler.start_scheduler()
    logger.info("Load test scheduler initialized and started")

@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event"""
    logger.info("Load Testing Automation service shutting down...")
    
    # Stop scheduler
    from scheduler import get_scheduler
    scheduler = get_scheduler()
    if scheduler:
        await scheduler.stop_scheduler()
        logger.info("Load test scheduler stopped")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)