import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .routes import test_runs, flaky_tests
from .services.vector_store import client
from .database import init_db

init_db()

app = FastAPI(
    title="Flaky Test Detector API",
    description="Backend for ingesting test run data, detecting flaky tests, and providing AI-powered root cause analysis.",
    version="1.0.0",
)

# CORS – set ALLOWED_ORIGINS as a comma-separated list in production
# e.g. ALLOWED_ORIGINS=https://your-dashboard.com,https://ci.your-company.com
_raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:8080")
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

@app.get("/health", tags=["system"])
async def health_check():
    try:
        client.get_collections()
        return {"status": "ok", "qdrant": "connected"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Qdrant connection failure: {str(e)}")
