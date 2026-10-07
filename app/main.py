"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import init_db
from app.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the database on startup."""
    init_db()
    yield


app = FastAPI(
    title="Bulk Certificate Generator",
    description=(
        "API for generating certificates in bulk for event participants. "
        "Submit a list of recipients, track progress, and download PDFs."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(router)


@app.get("/", tags=["health"])
def health_check():
    """Simple health-check endpoint."""
    return {"status": "ok", "service": "Bulk Certificate Generator"}
