"""Order intake: validation, idempotency, stock reservation and tote creation."""
from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.barcode import make_tote_barcode
from app.config import settings
from app.models import (
    Batch,
    Order,
    OrderLine,
    OrderStatus,
    Pharmacy,
    Product,
    Tote,
    ToteItem,
    ToteStatus,
)
from app.services.allocation import Allocation, fefo_allocate, pack_into_totes


class OrderError(ValueError):
    pass


@dataclass
class LineRequest:
    sku: str
    qty: int


def create_order(
    db: Session,
    pharmacy_code: str,
    lines: list[LineRequest],
    external_id: str | None = None,
    today: date | None = None,
) -> tuple[Order, bool]:
    """Create and allocate an order. Returns (order, created).

    Idempotent by `external_id`: 1C may resend the same document after a network
    error, and the warehouse must not pick it twice.
    """
    if external_id:
        existing = db.scalar(select(Order).where(Order.external_id == external_id))
        if existing:
            return existing, False

    pharmacy = db.scalar(select(Pharmacy).where(Pharmacy.code == pharmacy_code))
    if pharmacy is None:
        raise OrderError(f"unknown pharmacy: {pharmacy_code}")
    if not lines:
        raise OrderError("order has no lines")

    skus = {line.sku for line in lines}
    products = {p.sku: p for p in db.scalars(select(Product).where(Product.sku.in_(skus)))}
    unknown = skus - products.keys()
    if unknown:
        raise OrderError(f"unknown sku: {', '.join(sorted(unknown))}")

    # Merge duplicate SKUs so each product is one line
    merged: dict[str, int] = {}
    for line in lines:
        if line.qty <= 0:
            raise OrderError(f"quantity must be positive for {line.sku}")
        merged[line.sku] = merged.get(line.sku, 0) + line.qty

    order = Order(external_id=external_id, pharmacy=pharmacy, status=OrderStatus.ALLOCATED)
    order.lines = [OrderLine(product=products[sku], qty_ordered=qty) for sku, qty in merged.items()]
    db.add(order)
    db.flush()

    allocate(db, order, today or date.today())
    db.commit()
    return order, True


def allocate(db: Session, order: Order, today: date) -> None:
    allocations: list[Allocation] = []
    for line in order.lines:
        batches = db.scalars(select(Batch).where(Batch.product_id == line.product_id)).all()
        picks = fefo_allocate(batches, line.qty_ordered, today, settings.min_shelf_days)
        for batch, qty in picks:
            batch.qty_reserved += qty
            allocations.append(Allocation(line=line, batch=batch, qty=qty, zone=line.product.pick_zone))
        line.qty_allocated = sum(qty for _, qty in picks)

    if not allocations:
        order.status = OrderStatus.UNFULFILLED
        return

    sequence = db.scalar(select(func.max(Tote.id))) or 0
    for group in pack_into_totes(allocations, settings.tote_capacity):
        sequence += 1
        tote = Tote(
            barcode=make_tote_barcode(sequence),
            status=ToteStatus.CREATED,
            location="start",
            dock=order.pharmacy.dock,
        )
        tote.items = [
            ToteItem(order_line=a.line, batch=a.batch, qty=a.qty, zone=a.zone) for a in group
        ]
        order.totes.append(tote)
    order.status = OrderStatus.ALLOCATED
