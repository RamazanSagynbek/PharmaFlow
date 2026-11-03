import os

# In-memory SQLite by default; CI also runs the suite against PostgreSQL via PF_TEST_DATABASE_URL.
os.environ["PF_DATABASE_URL"] = os.environ.get("PF_TEST_DATABASE_URL", "sqlite://")
os.environ["PF_SIM_AUTOSTART"] = "false"
os.environ["PF_SIM_LOOP"] = "false"  # tests drive the simulation with runner.tick()

import random  # noqa: E402
from datetime import date  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.seed import seed  # noqa: E402

TODAY = date(2026, 11, 1)


@pytest.fixture
def db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        seed(session, today=TODAY, rng=random.Random(1))
        yield session


@pytest.fixture
def client(db):
    from app.main import app

    with TestClient(app) as c:
        yield c
