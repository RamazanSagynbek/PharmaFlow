"""API request / response models."""
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import OrderStatus, PickZone, ToteStatus


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class OrderLineIn(BaseModel):
    sku: str = Field(examples=["MED-0001"])
    qty: int = Field(gt=0, examples=[12])


class OrderIn(BaseModel):
    """Replenishment order, e.g. sent by 1C when a pharmacy's stock drops below minimum."""

    external_id: str | None = Field(default=None, max_length=40, examples=["1C-ЗК-000123"])
    pharmacy_code: str = Field(examples=["APT-001"])
    lines: list[OrderLineIn] = Field(min_length=1)


class PharmacyOut(ORM):
    id: int
    code: str
    name: str
    address: str
    dock: int


class BatchOut(ORM):
    id: int
    series: str
    expiry: date
    qty_on_hand: int
    qty_reserved: int
    available: int


class ProductOut(ORM):
    id: int
    sku: str
    name: str
    gtin: str
    pick_zone: PickZone
    is_rx: bool
    is_cold: bool


class ProductStockOut(ProductOut):
    batches: list[BatchOut]


class OrderLineOut(ORM):
    id: int
    product: ProductOut
    qty_ordered: int
    qty_allocated: int


class ToteItemOut(ORM):
    sku: str
    product_name: str
    is_rx: bool
    is_cold: bool
    batch_series: str
    batch_expiry: date
    qty: int
    zone: PickZone
    picked: bool


class ToteOut(ORM):
    id: int
    barcode: str
    order_id: int
    status: ToteStatus
    location: str
    dock: int
    recirculations: int
    packed_at: datetime | None


class ToteDetailOut(ToteOut):
    pharmacy_code: str
    pharmacy_name: str
    items: list[ToteItemOut]


class OrderOut(ORM):
    id: int
    external_id: str | None
    status: OrderStatus
    created_at: datetime
    shipped_at: datetime | None
    pharmacy: PharmacyOut
    lines: list[OrderLineOut]
    totes: list[ToteOut]


class OrderSummaryOut(ORM):
    id: int
    external_id: str | None
    status: OrderStatus
    created_at: datetime
    shipped_at: datetime | None
    pharmacy_code: str
    lines_count: int
    totes_count: int


class EventOut(ORM):
    ts: datetime
    sim_time: float
    tote_barcode: str
    type: str
    zone: str
    message: str


class SimControl(BaseModel):
    speed: float = Field(gt=0, le=100)
