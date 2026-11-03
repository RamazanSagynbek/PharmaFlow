"""REST API: pharmacies, stock, orders, totes, events and simulation control."""
import random

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models import EventLog, Order, OrderStatus, Pharmacy, Product, Tote, ToteStatus
from app.schemas import (
    EventOut,
    OrderIn,
    OrderOut,
    OrderSummaryOut,
    PharmacyOut,
    ProductStockOut,
    SimControl,
    ToteDetailOut,
    ToteItemOut,
    ToteOut,
)
from app.services.fulfillment import complete_tote
from app.services.orders import LineRequest, OrderError, create_order
from app.sim.runner import SimulationRunner

router = APIRouter(prefix="/api")


def get_runner(request: Request) -> SimulationRunner:
    return request.app.state.runner


# ------------------------------------------------------------------ master data

@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/pharmacies", response_model=list[PharmacyOut])
def list_pharmacies(db: Session = Depends(get_db)):
    return db.scalars(select(Pharmacy).order_by(Pharmacy.code)).all()


@router.get("/stock", response_model=list[ProductStockOut])
def list_stock(db: Session = Depends(get_db)):
    """Products with their batches (series, expiry, on hand, reserved)."""
    return db.scalars(select(Product).options(selectinload(Product.batches)).order_by(Product.sku)).all()


# ------------------------------------------------------------------ orders

@router.post("/orders", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
def post_order(body: OrderIn, response: Response, db: Session = Depends(get_db)):
    """Receive a replenishment order (from 1C). Re-sending the same `external_id` returns the existing order."""
    try:
        order, created = create_order(
            db, body.pharmacy_code, [LineRequest(line.sku, line.qty) for line in body.lines], body.external_id,
        )
    except OrderError as e:
        raise HTTPException(422, str(e)) from e
    if not created:
        response.status_code = status.HTTP_200_OK
    return order


@router.get("/orders", response_model=list[OrderSummaryOut])
def list_orders(
    status_: OrderStatus | None = Query(None, alias="status"),
    limit: int = Query(50, le=500),
    db: Session = Depends(get_db),
):
    query = (select(Order).options(selectinload(Order.lines), selectinload(Order.totes),
                                   selectinload(Order.pharmacy))
             .order_by(Order.id.desc()).limit(limit))
    if status_:
        query = query.where(Order.status == status_)
    return [
        OrderSummaryOut(
            id=o.id, external_id=o.external_id, status=o.status, created_at=o.created_at,
            shipped_at=o.shipped_at, pharmacy_code=o.pharmacy.code,
            lines_count=len(o.lines), totes_count=len(o.totes),
        )
        for o in db.scalars(query)
    ]


@router.get("/orders/{order_id}", response_model=OrderOut)
def get_order(order_id: int, db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "order not found")
    return order


@router.post("/demo/orders", response_model=list[OrderSummaryOut], status_code=status.HTTP_201_CREATED)
def generate_demo_orders(count: int = Query(5, ge=1, le=50), db: Session = Depends(get_db)):
    """Generate random replenishment orders (stand-in for 1C until the integration is built)."""
    pharmacies = db.scalars(select(Pharmacy.code)).all()
    skus = db.scalars(select(Product.sku)).all()
    created = []
    for _ in range(count):
        lines = [LineRequest(sku, random.randint(1, 15)) for sku in random.sample(skus, random.randint(2, 10))]
        order, _ = create_order(db, random.choice(pharmacies), lines)
        created.append(OrderSummaryOut(
            id=order.id, external_id=order.external_id, status=order.status,
            created_at=order.created_at, shipped_at=order.shipped_at,
            pharmacy_code=order.pharmacy.code, lines_count=len(order.lines),
            totes_count=len(order.totes),
        ))
    return created


# ------------------------------------------------------------------ totes & events

@router.get("/totes", response_model=list[ToteOut])
def list_totes(
    status_: ToteStatus | None = Query(None, alias="status"),
    limit: int = Query(100, le=1000),
    db: Session = Depends(get_db),
):
    query = select(Tote).order_by(Tote.id.desc()).limit(limit)
    if status_:
        query = query.where(Tote.status == status_)
    return db.scalars(query).all()


def _tote_by_barcode(db: Session, barcode: str) -> Tote:
    tote = db.scalar(select(Tote).where(Tote.barcode == barcode))
    if tote is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "tote not found")
    return tote


@router.get("/totes/{barcode}", response_model=ToteDetailOut)
def get_tote(barcode: str, db: Session = Depends(get_db)):
    tote = _tote_by_barcode(db, barcode)
    items = [
        ToteItemOut(
            sku=i.batch.product.sku, product_name=i.batch.product.name, is_rx=i.batch.product.is_rx,
            is_cold=i.batch.product.is_cold, batch_series=i.batch.series, batch_expiry=i.batch.expiry,
            qty=i.qty, zone=i.zone, picked=i.picked,
        )
        for i in tote.items
    ]
    pharmacy = tote.order.pharmacy
    return ToteDetailOut(
        **ToteOut.model_validate(tote).model_dump(),
        pharmacy_code=pharmacy.code, pharmacy_name=pharmacy.name, items=items,
    )


@router.post("/totes/{barcode}/resolve", response_model=ToteOut)
def resolve_rejected_tote(barcode: str, db: Session = Depends(get_db)):
    """Operator checked a rejected tote by hand and delivered it to its dock."""
    tote = _tote_by_barcode(db, barcode)
    if tote.status != ToteStatus.REJECTED:
        raise HTTPException(status.HTTP_409_CONFLICT, "only rejected totes can be resolved")
    complete_tote(db, tote)
    db.add(EventLog(tote_barcode=barcode, type="resolved", zone="dock",
                    message="Оператор вручную доставил лоток в док"))
    db.commit()
    return tote


@router.get("/events", response_model=list[EventOut])
def list_events(barcode: str | None = None, limit: int = Query(100, le=1000), db: Session = Depends(get_db)):
    query = select(EventLog).order_by(EventLog.id.desc()).limit(limit)
    if barcode:
        query = query.where(EventLog.tote_barcode == barcode)
    return db.scalars(query).all()


# ------------------------------------------------------------------ metrics & simulation

@router.get("/metrics")
def metrics(db: Session = Depends(get_db), runner: SimulationRunner = Depends(get_runner)):
    orders = dict(db.execute(select(Order.status, func.count()).group_by(Order.status)).all())
    totes = dict(db.execute(select(Tote.status, func.count()).group_by(Tote.status)).all())
    snapshot = runner.sim.snapshot()
    return {
        "orders": {s.value: orders.get(s, 0) for s in OrderStatus},
        "totes": {s.value: totes.get(s, 0) for s in ToteStatus},
        "simulation": {k: snapshot[k] for k in ("t", "queues", "utilization", "stats", "throughput_per_hour")},
        "running": runner.running,
    }


@router.get("/sim/state")
def sim_state(runner: SimulationRunner = Depends(get_runner)):
    return {"running": runner.running, "speed": runner.speed, **runner.sim.snapshot()}


@router.post("/sim/start")
def sim_start(runner: SimulationRunner = Depends(get_runner)):
    runner.start()
    return {"running": True}


@router.post("/sim/stop")
def sim_stop(runner: SimulationRunner = Depends(get_runner)):
    runner.stop()
    return {"running": False}


@router.post("/sim/speed")
def sim_speed(body: SimControl, runner: SimulationRunner = Depends(get_runner)):
    runner.speed = body.speed
    return {"speed": runner.speed}
