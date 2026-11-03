"""Discrete-time simulation of the automated pharmacy warehouse (digital twin).

Conveyor layout::

    [1 START] --> [2 AUTO / A-frame] --> [3 MANUAL picking] --> [4 SORTER scanner] --> [DOCK n]
                                                                   |    ^
                                                                   v    |  no-read: recirculation loop
                                                                [REJECT lane]

Each tote is a small state machine. Zones are shared resources with limited
capacity (one A-frame, N pickers, one packing station per dock), so queues and
bottlenecks appear naturally. The engine is pure Python with no database or I/O,
which keeps it deterministic and easy to unit-test.
"""
import random
from collections import deque
from dataclasses import asdict, dataclass, field
from enum import StrEnum

from app.barcode import is_valid_tote_barcode


class Stage(StrEnum):
    QUEUED = "queued"              # waiting to be put on the conveyor
    TO_AUTO = "to_auto"
    AUTO_WAIT = "auto_wait"
    AUTO_PICK = "auto_pick"
    TO_MANUAL = "to_manual"
    MANUAL_WAIT = "manual_wait"
    MANUAL_PICK = "manual_pick"
    TO_SORTER = "to_sorter"
    RECIRCULATING = "recirculating"
    TO_DOCK = "to_dock"
    DOCK_WAIT = "dock_wait"
    PACKING = "packing"
    PACKED = "packed"
    REJECTED = "rejected"


ZONE_OF_STAGE = {
    Stage.QUEUED: "start",
    Stage.TO_AUTO: "start",
    Stage.AUTO_WAIT: "auto",
    Stage.AUTO_PICK: "auto",
    Stage.TO_MANUAL: "auto",
    Stage.MANUAL_WAIT: "manual",
    Stage.MANUAL_PICK: "manual",
    Stage.TO_SORTER: "manual",
    Stage.RECIRCULATING: "sorter",
    Stage.TO_DOCK: "sorter",
    Stage.DOCK_WAIT: "dock",
    Stage.PACKING: "dock",
    Stage.PACKED: "dock",
    Stage.REJECTED: "reject",
}

TIMED_STAGES = {
    Stage.TO_AUTO, Stage.AUTO_PICK, Stage.TO_MANUAL, Stage.MANUAL_PICK,
    Stage.TO_SORTER, Stage.RECIRCULATING, Stage.TO_DOCK, Stage.PACKING,
}


@dataclass
class SimConfig:
    induction_interval: float = 4.0   # s between totes put on the belt
    travel_to_auto: float = 5.0
    travel_to_manual: float = 6.0
    travel_to_sorter: float = 8.0
    travel_to_dock: float = 6.0
    recirculation_time: float = 20.0  # loop back to the scanner after a no-read
    auto_overhead: float = 2.0        # A-frame: positioning
    auto_per_unit: float = 0.3        # A-frame: ejecting one pack
    manual_per_line: float = 6.0      # picker walks to a shelf location
    manual_per_unit: float = 0.5
    manual_workers: int = 2
    packing_time: float = 10.0
    noread_rate: float = 0.03
    max_recirculations: int = 2
    max_substep: float = 0.5          # numerical resolution of step()


@dataclass
class SimTote:
    barcode: str
    order_id: int
    dock: int
    auto_units: int
    manual_lines: int
    manual_units: int
    stage: Stage = Stage.QUEUED
    remaining: float = 0.0
    duration: float = 0.0
    recirculations: int = 0

    @property
    def zone(self) -> str:
        return ZONE_OF_STAGE[self.stage]

    @property
    def progress(self) -> float:
        if self.stage not in TIMED_STAGES or self.duration <= 0:
            return 0.0
        return round(1 - self.remaining / self.duration, 3)


@dataclass
class SimEvent:
    t: float
    type: str
    barcode: str
    zone: str
    detail: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class SimStats:
    inducted: int = 0
    packed: int = 0
    rejected: int = 0
    no_reads: int = 0
    units_auto: int = 0
    units_manual: int = 0
    auto_busy_time: float = 0.0
    manual_busy_time: float = 0.0  # summed over all pickers


class WarehouseSim:
    def __init__(self, config: SimConfig | None = None, docks: list[int] | None = None,
                 rng: random.Random | None = None):
        self.cfg = config or SimConfig()
        self.rng = rng or random.Random()
        self.t = 0.0
        self.stats = SimStats()
        self.totes: dict[str, SimTote] = {}

        self._induction: deque[SimTote] = deque()
        self._next_induction = 0.0
        self._auto_queue: deque[SimTote] = deque()
        self._auto_busy: SimTote | None = None
        self._manual_queue: deque[SimTote] = deque()
        self._manual_busy: list[SimTote] = []
        self._dock_queues: dict[int, deque[SimTote]] = {d: deque() for d in (docks or [1, 2, 3, 4])}
        self._dock_busy: dict[int, SimTote | None] = {d: None for d in self._dock_queues}
        self._events: list[SimEvent] = []

    # ---------------------------------------------------------------- public API

    def add_tote(self, tote: SimTote) -> None:
        if tote.barcode in self.totes:
            return
        if tote.dock not in self._dock_queues:
            self._dock_queues[tote.dock] = deque()
            self._dock_busy[tote.dock] = None
        tote.stage = Stage.QUEUED
        self.totes[tote.barcode] = tote
        self._induction.append(tote)

    def step(self, dt: float) -> list[SimEvent]:
        """Advance simulated time by `dt` seconds and return what happened."""
        self._events = []
        remaining = dt
        while remaining > 1e-9:
            h = min(self.cfg.max_substep, remaining)
            self._substep(h)
            remaining -= h
        return self._events

    def run_until_idle(self, max_time: float = 36_000, dt: float = 1.0) -> list[SimEvent]:
        """Run until every tote is packed or rejected (used by tests and the CLI demo)."""
        events: list[SimEvent] = []
        deadline = self.t + max_time
        while self.active_count and self.t < deadline:
            events.extend(self.step(dt))
        return events

    @property
    def active_count(self) -> int:
        return len(self.totes)

    def snapshot(self) -> dict:
        elapsed = max(self.t, 1e-9)
        return {
            "t": round(self.t, 1),
            "totes": [
                {
                    "barcode": t.barcode, "order_id": t.order_id, "stage": t.stage.value,
                    "zone": t.zone, "progress": t.progress, "dock": t.dock,
                    "recirculations": t.recirculations,
                }
                for t in self.totes.values()
            ],
            "queues": {
                "start": len(self._induction),
                "auto": len(self._auto_queue),
                "manual": len(self._manual_queue),
                "docks": {d: len(q) for d, q in self._dock_queues.items()},
            },
            "utilization": {
                "auto": round(self.stats.auto_busy_time / elapsed, 3),
                "manual": round(self.stats.manual_busy_time / (elapsed * self.cfg.manual_workers), 3),
            },
            "stats": asdict(self.stats),
            "throughput_per_hour": round(self.stats.packed / elapsed * 3600, 1) if self.t > 0 else 0.0,
        }

    # ---------------------------------------------------------------- internals

    def _emit(self, type_: str, tote: SimTote, **detail) -> None:
        self._events.append(SimEvent(round(self.t, 2), type_, tote.barcode, tote.zone, detail))

    def _start(self, tote: SimTote, stage: Stage, duration: float) -> None:
        tote.stage, tote.duration, tote.remaining = stage, duration, duration

    def _substep(self, h: float) -> None:
        self.t += h
        if self._auto_busy:
            self.stats.auto_busy_time += h
        self.stats.manual_busy_time += h * len(self._manual_busy)

        # 1. Induction: one tote at a time onto the belt
        if self._induction and self.t >= self._next_induction:
            tote = self._induction.popleft()
            self._start(tote, Stage.TO_AUTO, self.cfg.travel_to_auto)
            self._next_induction = self.t + self.cfg.induction_interval
            self.stats.inducted += 1
            self._emit("inducted", tote)

        # 2. Advance every timed activity
        finished = []
        for tote in list(self.totes.values()):
            if tote.stage in TIMED_STAGES:
                tote.remaining -= h
                if tote.remaining <= 1e-9:
                    finished.append(tote)
        for tote in finished:
            self._on_timer_done(tote)

        # 3. Hand free resources to queued totes
        self._dispatch()

    def _on_timer_done(self, tote: SimTote) -> None:
        cfg = self.cfg
        match tote.stage:
            case Stage.TO_AUTO:
                if tote.auto_units:
                    tote.stage = Stage.AUTO_WAIT
                    self._auto_queue.append(tote)
                else:
                    self._emit("auto_skipped", tote)
                    self._start(tote, Stage.TO_MANUAL, cfg.travel_to_manual)
            case Stage.AUTO_PICK:
                self._auto_busy = None
                self.stats.units_auto += tote.auto_units
                self._emit("auto_done", tote, units=tote.auto_units)
                self._start(tote, Stage.TO_MANUAL, cfg.travel_to_manual)
            case Stage.TO_MANUAL:
                if tote.manual_lines:
                    tote.stage = Stage.MANUAL_WAIT
                    self._manual_queue.append(tote)
                else:
                    self._emit("manual_skipped", tote)
                    self._start(tote, Stage.TO_SORTER, cfg.travel_to_sorter)
            case Stage.MANUAL_PICK:
                self._manual_busy.remove(tote)
                self.stats.units_manual += tote.manual_units
                self._emit("manual_done", tote, lines=tote.manual_lines, units=tote.manual_units)
                self._start(tote, Stage.TO_SORTER, cfg.travel_to_sorter)
            case Stage.TO_SORTER | Stage.RECIRCULATING:
                self._scan(tote)
            case Stage.TO_DOCK:
                tote.stage = Stage.DOCK_WAIT
                self._dock_queues[tote.dock].append(tote)
            case Stage.PACKING:
                self._dock_busy[tote.dock] = None
                tote.stage = Stage.PACKED
                self.stats.packed += 1
                self._emit("packed", tote, dock=tote.dock)
                del self.totes[tote.barcode]

    def _scan(self, tote: SimTote) -> None:
        """Sorter scanner + diverter logic, the same decision a PLC would make."""
        no_read = self.rng.random() < self.cfg.noread_rate or not is_valid_tote_barcode(tote.barcode)
        if not no_read:
            self._emit("scanned", tote, dock=tote.dock)
            self._start(tote, Stage.TO_DOCK, self.cfg.travel_to_dock)
            return

        self.stats.no_reads += 1
        if tote.recirculations < self.cfg.max_recirculations:
            tote.recirculations += 1
            self._start(tote, Stage.RECIRCULATING, self.cfg.recirculation_time)
            self._emit("no_read", tote, attempt=tote.recirculations)
        else:
            tote.stage = Stage.REJECTED
            self.stats.rejected += 1
            self._emit("rejected", tote, attempts=tote.recirculations + 1)
            del self.totes[tote.barcode]

    def _dispatch(self) -> None:
        cfg = self.cfg
        if self._auto_busy is None and self._auto_queue:
            tote = self._auto_queue.popleft()
            self._auto_busy = tote
            self._start(tote, Stage.AUTO_PICK, cfg.auto_overhead + cfg.auto_per_unit * tote.auto_units)
            self._emit("auto_start", tote, units=tote.auto_units)

        while len(self._manual_busy) < cfg.manual_workers and self._manual_queue:
            tote = self._manual_queue.popleft()
            self._manual_busy.append(tote)
            duration = cfg.manual_per_line * tote.manual_lines + cfg.manual_per_unit * tote.manual_units
            self._start(tote, Stage.MANUAL_PICK, duration)
            self._emit("manual_start", tote, lines=tote.manual_lines)

        for dock, queue in self._dock_queues.items():
            if self._dock_busy[dock] is None and queue:
                tote = queue.popleft()
                self._dock_busy[dock] = tote
                self._start(tote, Stage.PACKING, cfg.packing_time)
                self._emit("packing_start", tote, dock=dock)
