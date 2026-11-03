import random

from app.barcode import make_tote_barcode
from app.sim.engine import SimConfig, SimTote, Stage, WarehouseSim


def tote(n: int, dock: int = 1, auto: int = 10, manual_lines: int = 1, manual_units: int = 3) -> SimTote:
    return SimTote(make_tote_barcode(n), order_id=1, dock=dock, auto_units=auto,
                   manual_lines=manual_lines, manual_units=manual_units)


def make_sim(**cfg) -> WarehouseSim:
    return WarehouseSim(SimConfig(**cfg), docks=[1, 2, 3, 4], rng=random.Random(0))


def test_tote_goes_through_all_zones_in_order():
    sim = make_sim(noread_rate=0)
    sim.add_tote(tote(1))
    types = [e.type for e in sim.run_until_idle()]
    assert types == ["inducted", "auto_start", "auto_done", "manual_start", "manual_done",
                     "scanned", "packing_start", "packed"]
    assert sim.stats.packed == 1 and sim.active_count == 0


def test_zones_without_items_are_bypassed():
    sim = make_sim(noread_rate=0)
    sim.add_tote(tote(1, auto=0, manual_lines=2, manual_units=4))
    sim.add_tote(tote(2, auto=8, manual_lines=0, manual_units=0))
    types = [e.type for e in sim.run_until_idle()]
    assert "auto_skipped" in types and "manual_skipped" in types
    assert sim.stats.packed == 2


def test_tote_is_routed_to_its_pharmacy_dock():
    sim = make_sim(noread_rate=0)
    sim.add_tote(tote(1, dock=3))
    packed = [e for e in sim.run_until_idle() if e.type == "packed"]
    assert packed[0].detail["dock"] == 3


def test_unreadable_barcode_recirculates_then_rejects():
    sim = make_sim(noread_rate=1.0, max_recirculations=2)
    sim.add_tote(tote(1))
    events = sim.run_until_idle()
    types = [e.type for e in events]
    assert types.count("no_read") == 2
    assert types[-1] == "rejected"
    assert sim.stats.rejected == 1 and sim.stats.packed == 0


def test_corrupted_barcode_is_never_routed():
    sim = make_sim(noread_rate=0)
    bad = tote(1)
    bad.barcode = bad.barcode[:-1] + str((int(bad.barcode[-1]) + 1) % 10)
    sim.add_tote(bad)
    assert [e.type for e in sim.run_until_idle()][-1] == "rejected"


def test_single_a_frame_creates_a_queue():
    sim = make_sim(noread_rate=0, induction_interval=0.5, auto_per_unit=5.0)
    for n in range(1, 6):
        sim.add_tote(tote(n, auto=10))
    sim.step(20)
    stages = [t.stage for t in sim.totes.values()]
    assert stages.count(Stage.AUTO_PICK) == 1
    assert stages.count(Stage.AUTO_WAIT) >= 1


def test_manual_workers_limit_parallel_picking():
    sim = make_sim(noread_rate=0, induction_interval=0.5, manual_workers=2, manual_per_line=60)
    for n in range(1, 6):
        sim.add_tote(tote(n, auto=0, manual_lines=1))
    sim.step(40)
    stages = [t.stage for t in sim.totes.values()]
    assert stages.count(Stage.MANUAL_PICK) == 2


def test_all_totes_finish_and_snapshot_is_consistent():
    sim = WarehouseSim(SimConfig(noread_rate=0.1), docks=[1, 2, 3, 4], rng=random.Random(7))
    for n in range(1, 31):
        sim.add_tote(tote(n, dock=n % 4 + 1))
    sim.run_until_idle()
    snap = sim.snapshot()
    assert snap["stats"]["packed"] + snap["stats"]["rejected"] == 30
    assert snap["totes"] == []
    assert 0 < snap["utilization"]["auto"] <= 1
    assert snap["throughput_per_hour"] > 0


def test_adding_same_tote_twice_is_ignored():
    sim = make_sim()
    sim.add_tote(tote(1))
    sim.add_tote(tote(1))
    assert sim.active_count == 1
