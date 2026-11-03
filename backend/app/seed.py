"""Demo data: a pharmacy chain in Almaty and a warehouse assortment.

GTIN codes are generated (prefix 487 = GS1 Kazakhstan) and are not real product codes.
"""
import random
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.barcode import gs1_check_digit
from app.models import Batch, Pharmacy, PickZone, Product

PHARMACIES = [
    ("APT-001", "Аптека №1 «Медеу»", "пр. Достык, 105", 1),
    ("APT-002", "Аптека №2 «Самал»", "мкр. Самал-2, 58", 1),
    ("APT-003", "Аптека №3 «Алатау»", "пр. Абая, 150", 2),
    ("APT-004", "Аптека №4 «Бостандык»", "ул. Тимирязева, 42", 2),
    ("APT-005", "Аптека №5 «Ауэзов»", "мкр. Жетысу-2, 70", 3),
    ("APT-006", "Аптека №6 «Алмалы»", "ул. Толе би, 59", 3),
    ("APT-007", "Аптека №7 «Турксиб»", "ул. Сейфуллина, 31", 4),
    ("APT-008", "Аптека №8 «Наурызбай»", "мкр. Шугыла, 12", 4),
]

A, M = PickZone.AUTO, PickZone.MANUAL
# (name, zone, is_rx, is_cold)
PRODUCTS = [
    ("Парацетамол 500 мг, таб. №10", A, False, False),
    ("Ибупрофен 200 мг, таб. №20", A, False, False),
    ("Ацетилсалициловая кислота 100 мг, таб. №30", A, False, False),
    ("Цетиризин 10 мг, таб. №10", A, False, False),
    ("Лоратадин 10 мг, таб. №10", A, False, False),
    ("Омепразол 20 мг, капс. №30", A, False, False),
    ("Дротаверин 40 мг, таб. №20", A, False, False),
    ("Лоперамид 2 мг, капс. №10", A, False, False),
    ("Амброксол 30 мг, таб. №20", A, False, False),
    ("Панкреатин 25 ЕД, таб. №20", A, False, False),
    ("Амоксициллин 500 мг, капс. №16", A, True, False),
    ("Азитромицин 500 мг, таб. №3", A, True, False),
    ("Метформин 850 мг, таб. №60", A, True, False),
    ("Аторвастатин 20 мг, таб. №30", A, True, False),
    ("Лизиноприл 10 мг, таб. №30", A, True, False),
    ("Амлодипин 5 мг, таб. №30", A, True, False),
    ("Бисопролол 5 мг, таб. №30", A, True, False),
    ("Флуконазол 150 мг, капс. №1", A, True, False),
    ("Ципрофлоксацин 500 мг, таб. №10", A, True, False),
    ("Витамин D3 2000 МЕ, капс. №60", A, False, False),
    ("Активированный уголь 250 мг, таб. №50", M, False, False),
    ("Ксилометазолин 0,1%, спрей назальный 10 мл", M, False, False),
    ("Хлоргексидин 0,05%, раствор 100 мл", M, False, False),
    ("Натрия хлорид 0,9%, раствор 200 мл", M, False, False),
    ("Диклофенак 1%, гель 50 г", M, False, False),
    ("Валерианы экстракт 20 мг, таб. №50", M, False, False),
    ("Нитроглицерин 0,5 мг, таб. №40", M, True, False),
    ("Инсулин гларгин 100 ЕД/мл, шприц-ручка 3 мл", M, True, True),
    ("Эноксапарин 4000 анти-Ха МЕ, шприц 0,4 мл №10", M, True, True),
    ("Вакцина против гриппа, шприц 0,5 мл", M, True, True),
]


def _gtin(n: int) -> str:
    body = f"487{n:09d}"
    return body + str(gs1_check_digit(body))


def seed(db: Session, today: date | None = None, rng: random.Random | None = None) -> bool:
    """Fill an empty database. Returns False if data already exists."""
    if db.scalar(select(Pharmacy.id).limit(1)) is not None:
        return False
    today = today or date.today()
    rng = rng or random.Random(42)

    db.add_all(Pharmacy(code=c, name=n, address=a, dock=d) for c, n, a, d in PHARMACIES)

    for i, (name, zone, is_rx, is_cold) in enumerate(PRODUCTS, start=1):
        product = Product(sku=f"MED-{i:04d}", name=name, gtin=_gtin(i), pick_zone=zone,
                          is_rx=is_rx, is_cold=is_cold)
        # 2-3 batches with different expiry dates; the first one sometimes expires
        # too soon to ship, which demonstrates the minimum shelf-life rule.
        for b in range(rng.randint(2, 3)):
            days = rng.choice([45, 200, 400, 700]) if b == 0 else rng.randint(150, 900)
            product.batches.append(Batch(
                series=f"{rng.randint(100000, 999999)}",
                expiry=today + timedelta(days=days),
                qty_on_hand=rng.randint(80, 600),
            ))
        db.add(product)
    db.commit()
    return True
