"""Domain model of the pharmacy network and the distribution warehouse."""
from datetime import UTC, date, datetime
from enum import StrEnum

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


def _enum(cls):
    """Store enum *values* ("auto") as plain strings, portable across databases."""
    return Enum(cls, native_enum=False, values_callable=lambda e: [m.value for m in e], length=20)


class PickZone(StrEnum):
    AUTO = "auto"      # zone 2: automatic vertical dispensers (A-frame)
    MANUAL = "manual"  # zone 3: manual picking of slow movers, bulky and cold-chain items


class OrderStatus(StrEnum):
    ALLOCATED = "allocated"      # stock reserved, totes created
    IN_PROGRESS = "in_progress"  # at least one tote is on the conveyor
    SHIPPED = "shipped"          # all totes packed at the dock
    EXCEPTION = "exception"      # a tote went to the reject lane, needs an operator
    UNFULFILLED = "unfulfilled"  # nothing could be allocated


class ToteStatus(StrEnum):
    CREATED = "created"
    IN_PROCESS = "in_process"
    PACKED = "packed"
    REJECTED = "rejected"


class Pharmacy(Base):
    __tablename__ = "pharmacies"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    address: Mapped[str] = mapped_column(String(200))
    dock: Mapped[int]  # shipping dock of this pharmacy's delivery route


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    gtin: Mapped[str] = mapped_column(String(14))
    pick_zone: Mapped[PickZone] = mapped_column(_enum(PickZone))
    is_rx: Mapped[bool] = mapped_column(default=False)    # prescription only
    is_cold: Mapped[bool] = mapped_column(default=False)  # +2..+8 °C cold chain

    batches: Mapped[list["Batch"]] = relationship(back_populates="product")


class Batch(Base):
    """A production series of a product with its own expiry date (needed for FEFO and recalls)."""

    __tablename__ = "batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    series: Mapped[str] = mapped_column(String(30))
    expiry: Mapped[date] = mapped_column(Date)
    qty_on_hand: Mapped[int] = mapped_column(default=0)
    qty_reserved: Mapped[int] = mapped_column(default=0)

    product: Mapped[Product] = relationship(back_populates="batches")

    @property
    def available(self) -> int:
        return self.qty_on_hand - self.qty_reserved


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    external_id: Mapped[str | None] = mapped_column(String(40), unique=True)  # document number in 1C
    pharmacy_id: Mapped[int] = mapped_column(ForeignKey("pharmacies.id"))
    status: Mapped[OrderStatus] = mapped_column(_enum(OrderStatus))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    pharmacy: Mapped[Pharmacy] = relationship()
    lines: Mapped[list["OrderLine"]] = relationship(back_populates="order", cascade="all, delete-orphan")
    totes: Mapped[list["Tote"]] = relationship(back_populates="order", cascade="all, delete-orphan")


class OrderLine(Base):
    __tablename__ = "order_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    qty_ordered: Mapped[int]
    qty_allocated: Mapped[int] = mapped_column(default=0)

    order: Mapped[Order] = relationship(back_populates="lines")
    product: Mapped[Product] = relationship()


class Tote(Base):
    """A plastic tote travelling on the conveyor, identified by its barcode."""

    __tablename__ = "totes"

    id: Mapped[int] = mapped_column(primary_key=True)
    barcode: Mapped[str] = mapped_column(String(20), unique=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    status: Mapped[ToteStatus] = mapped_column(_enum(ToteStatus))
    location: Mapped[str] = mapped_column(String(20), default="start")
    dock: Mapped[int]
    recirculations: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    packed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    order: Mapped[Order] = relationship(back_populates="totes")
    items: Mapped[list["ToteItem"]] = relationship(back_populates="tote", cascade="all, delete-orphan")


class ToteItem(Base):
    __tablename__ = "tote_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    tote_id: Mapped[int] = mapped_column(ForeignKey("totes.id"))
    order_line_id: Mapped[int] = mapped_column(ForeignKey("order_lines.id"))
    batch_id: Mapped[int] = mapped_column(ForeignKey("batches.id"))
    qty: Mapped[int]
    zone: Mapped[PickZone] = mapped_column(_enum(PickZone))
    picked: Mapped[bool] = mapped_column(default=False)

    tote: Mapped[Tote] = relationship(back_populates="items")
    order_line: Mapped[OrderLine] = relationship()
    batch: Mapped[Batch] = relationship()


class EventLog(Base):
    """Audit trail of everything that happened to totes (scans, picks, packing)."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    sim_time: Mapped[float] = mapped_column(default=0.0)
    tote_barcode: Mapped[str] = mapped_column(String(20), index=True)
    type: Mapped[str] = mapped_column(String(30))
    zone: Mapped[str] = mapped_column(String(20))
    message: Mapped[str] = mapped_column(String(200), default="")
