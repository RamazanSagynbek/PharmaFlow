"""State changes of totes and orders caused by warehouse events."""
from sqlalchemy.orm import Session

from app.models import OrderStatus, PickZone, Tote, ToteStatus, utcnow


def mark_zone_picked(tote: Tote, zone: PickZone) -> None:
    for item in tote.items:
        if item.zone == zone:
            item.picked = True


def complete_tote(db: Session, tote: Tote) -> None:
    """Tote packed at the dock: reserved stock physically leaves the warehouse."""
    if tote.status == ToteStatus.PACKED:
        return
    for item in tote.items:
        item.picked = True
        item.batch.qty_on_hand -= item.qty
        item.batch.qty_reserved -= item.qty
    tote.status = ToteStatus.PACKED
    tote.location = "dock"
    tote.packed_at = utcnow()
    refresh_order_status(tote)


def reject_tote(tote: Tote) -> None:
    """Barcode unreadable after all recirculations: tote goes to the reject lane."""
    tote.status = ToteStatus.REJECTED
    tote.location = "reject"
    refresh_order_status(tote)


def refresh_order_status(tote: Tote) -> None:
    order = tote.order
    statuses = {t.status for t in order.totes}
    if statuses == {ToteStatus.PACKED}:
        order.status = OrderStatus.SHIPPED
        order.shipped_at = utcnow()
    elif ToteStatus.REJECTED in statuses:
        order.status = OrderStatus.EXCEPTION
    elif statuses & {ToteStatus.IN_PROCESS, ToteStatus.PACKED}:
        order.status = OrderStatus.IN_PROGRESS
