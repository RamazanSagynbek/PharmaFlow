"""Stock allocation rules.

* FEFO (First Expired, First Out): the batch with the nearest expiry date ships first.
* Batches whose remaining shelf life is shorter than `min_shelf_days` are never shipped.
* Allocations are packed into totes of limited capacity; automatic-zone items go
  first so the A-frame dispenses into an empty tote and the picker tops it up.
"""
from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import date, timedelta
from typing import Any, Protocol

from app.models import PickZone


class BatchLike(Protocol):
    id: Any
    expiry: date

    @property
    def available(self) -> int: ...


@dataclass(frozen=True)
class Allocation:
    line: Any       # OrderLine
    batch: Any      # Batch
    qty: int
    zone: PickZone


def fefo_allocate(
    batches: Iterable[BatchLike], qty: int, today: date, min_shelf_days: int
) -> list[tuple[BatchLike, int]]:
    """Return (batch, qty) picks covering up to `qty` units, nearest expiry first."""
    cutoff = today + timedelta(days=min_shelf_days)
    eligible = sorted(
        (b for b in batches if b.expiry >= cutoff and b.available > 0),
        key=lambda b: (b.expiry, b.id or 0),
    )
    picks: list[tuple[BatchLike, int]] = []
    remaining = qty
    for batch in eligible:
        if remaining == 0:
            break
        take = min(batch.available, remaining)
        picks.append((batch, take))
        remaining -= take
    return picks


def pack_into_totes(allocations: Iterable[Allocation], capacity: int) -> list[list[Allocation]]:
    """First-fit packing by units; an allocation larger than the free space is split."""
    if capacity <= 0:
        raise ValueError("tote capacity must be positive")

    ordered = sorted(allocations, key=lambda a: a.zone != PickZone.AUTO)  # stable: AUTO first
    totes: list[list[Allocation]] = []
    current: list[Allocation] = []
    free = capacity
    for alloc in ordered:
        qty = alloc.qty
        while qty > 0:
            if free == 0:
                totes.append(current)
                current, free = [], capacity
            take = min(qty, free)
            current.append(replace(alloc, qty=take))
            qty -= take
            free -= take
    if current:
        totes.append(current)
    return totes
