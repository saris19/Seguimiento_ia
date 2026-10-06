"""
Sistema de seguimiento de procesos con IA — FastAPI application entry point.

Run:  python run.py   (or: uvicorn app.main:app --reload)
Docs: http://127.0.0.1:8000/docs
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.ai.risk_model import get_model
from app.config import STATIC_DIR
from app.database import init_db, SessionLocal
from app.routers import processes, phases, general
from app.seed import seed_demo_data


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    get_model()  # train / warm up the risk model once
    if os.getenv("SEED_DEMO", "1") == "1":
        with SessionLocal() as db:
            seed_demo_data(db)
    yield


app = FastAPI(
    title="Sistema de seguimiento de procesos con IA",
    description="Plataforma que supervisa cada fase de un proceso con un motor de IA híbrido "
                "(reglas + modelo de riesgo) que valida, alerta y recomienda.",
    version="0.5.0",
    lifespan=lifespan,
)

app.include_router(general.router)
app.include_router(processes.router)
app.include_router(phases.router)

app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
