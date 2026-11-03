"""Connects the in-memory simulator with the database and live clients.

Every tick: pick up newly created totes from the DB, advance the simulation,
write the resulting events back (tote location, picked items, stock movements,
order status) and broadcast a snapshot over WebSocket.
"""
import asyncio
import logging
from collections.abc import Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload, sessionmaker

from app.models import EventLog, OrderStatus, Pharmacy, PickZone, Tote, ToteStatus
from app.services.fulfillment import (
    complete_tote,
    mark_zone_picked,
    refresh_order_status,
    reject_tote,
)
from app.sim.engine import SimConfig, SimEvent, SimTote, WarehouseSim

log = logging.getLogger(__name__)

Broadcaster = Callable[[dict], Awaitable[None]]

_MESSAGES = {
    "inducted": "Лоток поставлен на конвейер",
    "auto_start": "Автомат-дозатор начал отбор",
    "auto_done": "Автоматический отбор завершён",
    "auto_skipped": "Нет позиций для автомата, проезд",
    "manual_start": "Сборщик начал ручной отбор",
    "manual_done": "Ручной отбор завершён",
    "manual_skipped": "Нет позиций для ручного отбора, проезд",
    "scanned": "Штрихкод считан, направлен в док",
    "no_read": "Штрихкод не считан, повторный круг",
    "rejected": "Штрихкод не считан, лоток ушёл в зону брака",
    "packing_start": "Упаковка в коробку",
    "packed": "Упаковано, готово к отгрузке",
}


class SimulationRunner:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        config: SimConfig | None = None,
        speed: float = 5.0,
        tick_seconds: float = 0.2,
        broadcast: Broadcaster | None = None,
    ):
        self.session_factory = session_factory
        self.config = config or SimConfig()
        self.speed = speed
        self.tick_seconds = tick_seconds
        self.broadcast = broadcast
        self.running = False
        self._task: asyncio.Task | None = None
        with session_factory() as db:
            docks = sorted(set(db.scalars(select(Pharmacy.dock))))
            self._requeue_interrupted(db)
        self.sim = WarehouseSim(self.config, docks=docks or None)

    # ------------------------------------------------------------ sync core

    def tick(self, sim_seconds: float) -> list[SimEvent]:
        with self.session_factory() as db:
            self._load_new_totes(db)
            events = self.sim.step(sim_seconds)
            self._persist(db, events)
            db.commit()
        return events

    def _requeue_interrupted(self, db: Session) -> None:
        """After a restart the in-memory state is gone: put unfinished totes back to the start."""
        for tote in db.scalars(select(Tote).where(Tote.status == ToteStatus.IN_PROCESS)):
            tote.status, tote.location = ToteStatus.CREATED, "start"
        db.commit()

    def _load_new_totes(self, db: Session) -> None:
        new = db.scalars(
            select(Tote).where(Tote.status == ToteStatus.CREATED)
            .options(selectinload(Tote.items)).order_by(Tote.id)
        ).all()
        for tote in new:
            auto = [i for i in tote.items if i.zone == PickZone.AUTO]
            manual = [i for i in tote.items if i.zone == PickZone.MANUAL]
            self.sim.add_tote(SimTote(
                barcode=tote.barcode, order_id=tote.order_id, dock=tote.dock,
                auto_units=sum(i.qty for i in auto),
                manual_lines=len(manual), manual_units=sum(i.qty for i in manual),
            ))
            tote.status = ToteStatus.IN_PROCESS
            if tote.order.status == OrderStatus.ALLOCATED:
                tote.order.status = OrderStatus.IN_PROGRESS

    def _persist(self, db: Session, events: list[SimEvent]) -> None:
        if not events:
            return
        barcodes = {e.barcode for e in events}
        totes = {t.barcode: t for t in db.scalars(select(Tote).where(Tote.barcode.in_(barcodes)))}
        for event in events:
            tote = totes.get(event.barcode)
            if tote is None:
                continue
            tote.location = event.zone
            match event.type:
                case "auto_done":
                    mark_zone_picked(tote, PickZone.AUTO)
                case "manual_done":
                    mark_zone_picked(tote, PickZone.MANUAL)
                case "no_read":
                    tote.recirculations = event.detail.get("attempt", tote.recirculations)
                case "packed":
                    complete_tote(db, tote)
                case "rejected":
                    reject_tote(tote)
                case "inducted":
                    refresh_order_status(tote)
            db.add(EventLog(
                sim_time=event.t, tote_barcode=event.barcode, type=event.type,
                zone=event.zone, message=_MESSAGES.get(event.type, event.type),
            ))

    # ------------------------------------------------------------ async loop

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self.running = False
        if self._task:
            await self._task
            self._task = None

    async def _loop(self) -> None:
        while self.running:
            try:
                events = await asyncio.to_thread(self.tick, self.tick_seconds * self.speed)
                if self.broadcast:
                    await self.broadcast({
                        "type": "tick",
                        "snapshot": self.sim.snapshot(),
                        "events": [e.as_dict() for e in events],
                    })
            except Exception:  # keep the warehouse running, but make the failure visible
                log.exception("simulation tick failed")
            await asyncio.sleep(self.tick_seconds)
