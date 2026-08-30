import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .routes import test_runs, flaky_tests
from .services.vector_store import client
from .database import init_db

init_db()

app = FastAPI(
    title="Flaky Test Detector API",
    description="Backend for ingesting test run data, detecting flaky tests, and providing AI-powered root cause analysis.",
    version="1.0.0",
)

# CORS – allow all or configured origins
_raw_origins = os.getenv("ALLOWED_ORIGINS", "*")
if _raw_origins == "*":
    origins = ["*"]
else:
    origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(test_runs.router)
app.include_router(flaky_tests.router)

# Mount /data directory for static sample JSON files if present
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
data_dir = os.path.join(backend_dir, "data")
if os.path.exists(data_dir):
    app.mount("/data", StaticFiles(directory=data_dir), name="data")

# Serve dashboard.html at root / and /dashboard.html
@app.get("/", include_in_schema=False)
@app.get("/dashboard.html", include_in_schema=False)
async def serve_dashboard():
    dashboard_path = os.path.join(backend_dir, "dashboard.html")
    if not os.path.exists(dashboard_path):
        dashboard_path = os.path.abspath(os.path.join(backend_dir, "..", "dashboard.html"))
    if os.path.exists(dashboard_path):
        return FileResponse(dashboard_path)
    return {"message": "Flaky Test Detector API is running. Go to /docs for API documentation."}

@app.get("/health", tags=["system"])
async def health_check():
    try:
        client.get_collections()
        return {"status": "ok", "qdrant": "connected"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Qdrant connection failure: {str(e)}")

