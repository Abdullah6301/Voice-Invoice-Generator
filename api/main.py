"""
Invoice Generator API – Main FastAPI Application
Entry point for the REST API and web dashboard.
"""

import os
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from loguru import logger

from backend.config import settings
from database.connection import db_manager
from ai_engine.dataset_matcher import dataset_matcher
from api.routes import voice, invoices, customers, dataset, contractors, dashboard, conversation


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    # Startup
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    await db_manager.initialize()
    await dataset_matcher.load_dataset(db_manager)
    logger.info("Application ready")
    yield
    # Shutdown
    logger.info("Shutting down application")


app = FastAPI(
    title=settings.APP_NAME,
    description="AI-Powered Smart Invoice System for Construction",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# Static files and templates
frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=str(frontend_dir / "static")), name="static")

# Mount invoice output directory for PDF downloads
invoice_dir = Path(settings.INVOICE_OUTPUT_DIR)
invoice_dir.mkdir(parents=True, exist_ok=True)
app.mount("/invoices/output", StaticFiles(directory=str(invoice_dir)), name="invoice_files")

# Register API routes
app.include_router(voice.router, prefix="/api", tags=["Voice"])
app.include_router(conversation.router, prefix="/api", tags=["Conversation"])
app.include_router(invoices.router, prefix="/api", tags=["Invoices"])
app.include_router(customers.router, prefix="/api", tags=["Customers"])
app.include_router(dataset.router, prefix="/api", tags=["Dataset"])
app.include_router(contractors.router, prefix="/api", tags=["Contractors"])
app.include_router(dashboard.router, tags=["Dashboard"])
