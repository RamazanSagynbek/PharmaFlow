from dataclasses import dataclass
from datetime import date, timedelta

import pytest

from app.models import PickZone
from app.services.allocation import Allocation, fefo_allocate, pack_into_totes

TODAY = date(2026, 11, 1)


@dataclass
class FakeBatch:
    id: int
    expiry: date
    on_hand: int
    reserved: int = 0

    @property
    def available(self) -> int:
        return self.on_hand - self.reserved


def days(n: int) -> date:
    return TODAY + timedelta(days=n)


def test_fefo_takes_nearest_expiry_first():
    late, early = FakeBatch(1, days(500), 100), FakeBatch(2, days(200), 100)
    picks = fefo_allocate([late, early], 30, TODAY, min_shelf_days=90)
    assert picks == [(early, 30)]


def test_fefo_spans_several_batches():
    a, b = FakeBatch(1, days(200), 10), FakeBatch(2, days(300), 100)
    picks = fefo_allocate([b, a], 25, TODAY, min_shelf_days=90)
    assert picks == [(a, 10), (b, 15)]


def test_short_shelf_life_batch_is_never_shipped():
    expiring = FakeBatch(1, days(30), 100)
    fresh = FakeBatch(2, days(400), 100)
    picks = fefo_allocate([expiring, fresh], 10, TODAY, min_shelf_days=90)
    assert picks == [(fresh, 10)]


def test_reserved_stock_is_not_available():
    batch = FakeBatch(1, days(200), on_hand=50, reserved=45)
    assert fefo_allocate([batch], 10, TODAY, 90) == [(batch, 5)]


def test_shortage_returns_partial_allocation():
    batch = FakeBatch(1, days(200), 7)
    picks = fefo_allocate([batch], 20, TODAY, 90)
    assert sum(q for _, q in picks) == 7


def alloc(qty: int, zone: PickZone, line: str = "L") -> Allocation:
    return Allocation(line=line, batch="B", qty=qty, zone=zone)


def test_auto_items_are_packed_first():
    totes = pack_into_totes([alloc(5, PickZone.MANUAL, "m"), alloc(5, PickZone.AUTO, "a")], capacity=40)
    assert [a.line for a in totes[0]] == ["a", "m"]


def test_large_allocation_is_split_across_totes():
    totes = pack_into_totes([alloc(95, PickZone.AUTO)], capacity=40)
    assert [sum(a.qty for a in t) for t in totes] == [40, 40, 15]


def test_capacity_is_never_exceeded():
    allocations = [alloc(q, PickZone.AUTO if q % 2 else PickZone.MANUAL) for q in (13, 22, 7, 31, 5, 18)]
    totes = pack_into_totes(allocations, capacity=40)
    assert all(sum(a.qty for a in t) <= 40 for t in totes)
    assert sum(a.qty for t in totes for a in t) == sum(a.qty for a in allocations)


def test_invalid_capacity():
    with pytest.raises(ValueError):
        pack_into_totes([alloc(1, PickZone.AUTO)], capacity=0)
