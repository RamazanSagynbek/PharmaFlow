"""PharmaFlow WMS: FastAPI application."""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import models  # noqa: F401  (register tables)
from app.api import routes, ws
from app.config import settings
from app.db import Base, SessionLocal, engine
from app.seed import seed
from app.sim.engine import SimConfig
from app.sim.runner import SimulationRunner

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed(db)
    runner = SimulationRunner(
        SessionLocal,
        SimConfig(
            noread_rate=settings.scanner_noread_rate,
            max_recirculations=settings.max_recirculations,
            manual_workers=settings.manual_workers,
        ),
        speed=settings.sim_speed,
        tick_seconds=settings.sim_tick_seconds,
        broadcast=ws.manager.broadcast,
    )
    app.state.runner = runner
    if settings.sim_autostart:
        runner.start()
    if settings.sim_loop:
        runner.start_loop()
    yield
    await runner.shutdown()


app = FastAPI(
    title="PharmaFlow WMS",
    version="0.1.0",
    description="Система управления автоматизированным аптечным складом: "
                "приём заказов аптек, FEFO-резервирование, лотки со штрихкодами, "
                "симуляция конвейера (автомат, ручной отбор, сортировка, доки).",
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(routes.router)
app.include_router(ws.router)

# HMI (built React app). Mounted last so /api and /ws keep priority.
HMI_DIR = Path(__file__).parent / "static"
if (HMI_DIR / "index.html").exists():
    app.mount("/", StaticFiles(directory=HMI_DIR, html=True), name="hmi")
