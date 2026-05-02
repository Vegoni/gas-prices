"""
FastAPI application entry point.

This file wires everything together:
- Creates the FastAPI app
- Sets up database tables on startup
- Includes API routes
- (Later) starts the background scheduler for auto-ingestion

Run with:  uvicorn app.main:app --reload
The --reload flag watches for file changes — great during development.
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.models.database import init_db
from app.api.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup/shutdown lifecycle.

    Code before 'yield' runs at startup.
    Code after 'yield' runs at shutdown.

    WHY use lifespan instead of @app.on_event?
    on_event is deprecated in newer FastAPI. The lifespan context manager
    is the modern replacement — cleaner and supports async cleanup.
    """
    # Startup: create tables if they don't exist
    print("Initializing database...")
    await init_db()
    print("Database ready.")
    yield
    # Shutdown: nothing to clean up yet
    print("Shutting down.")


app = FastAPI(
    title="Gas Price Dashboard API",
    description="Track U.S. gasoline and diesel prices from EIA data",
    version="0.1.0",
    lifespan=lifespan,
)

_default_origins = "http://localhost:3000,http://localhost:5173"
_origins = [o.strip() for o in os.getenv("CORS_ALLOW_ORIGINS", _default_origins).split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routes
app.include_router(router, prefix="/api")
