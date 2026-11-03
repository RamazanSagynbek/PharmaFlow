from sqlalchemy import select

from app.models import Batch, Order, Product, Tote


def first_auto_and_manual_sku(client):
    stock = client.get("/api/stock").json()
    auto = next(p["sku"] for p in stock if p["pick_zone"] == "auto")
    manual = next(p["sku"] for p in stock if p["pick_zone"] == "manual")
    return auto, manual


def run_sim(client, seconds: float = 600):
    runner = client.app.state.runner
    for _ in range(int(seconds)):
        runner.tick(1.0)


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_seed_data_available(client):
    assert len(client.get("/api/pharmacies").json()) == 8
    assert len(client.get("/api/stock").json()) == 30


def test_create_order_reserves_stock_and_creates_totes(client, db):
    auto, manual = first_auto_and_manual_sku(client)
    r = client.post("/api/orders", json={"pharmacy_code": "APT-003",
                                         "lines": [{"sku": auto, "qty": 50}, {"sku": manual, "qty": 4}]})
    assert r.status_code == 201
    order = r.json()
    assert order["status"] == "allocated"
    assert len(order["totes"]) == 2               # 54 units, capacity 40
    assert all(t["dock"] == 2 for t in order["totes"])  # APT-003 ships from dock 2

    product = db.scalar(select(Product).where(Product.sku == auto))
    db.expire_all()
    assert sum(b.qty_reserved for b in product.batches) == 50


def test_order_is_idempotent_by_external_id(client, db):
    auto, _ = first_auto_and_manual_sku(client)
    body = {"external_id": "1C-ЗК-000001", "pharmacy_code": "APT-001", "lines": [{"sku": auto, "qty": 5}]}
    first = client.post("/api/orders", json=body)
    second = client.post("/api/orders", json=body)
    assert first.status_code == 201 and second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert len(db.scalars(select(Order)).all()) == 1


def test_validation_errors(client):
    r = client.post("/api/orders", json={"pharmacy_code": "NOPE", "lines": [{"sku": "MED-0001", "qty": 1}]})
    assert r.status_code == 422 and "unknown pharmacy" in r.json()["detail"]
    r = client.post("/api/orders", json={"pharmacy_code": "APT-001", "lines": [{"sku": "XXX", "qty": 1}]})
    assert r.status_code == 422 and "unknown sku" in r.json()["detail"]
    r = client.post("/api/orders", json={"pharmacy_code": "APT-001", "lines": [{"sku": "MED-0001", "qty": 0}]})
    assert r.status_code == 422


def test_full_flow_order_is_shipped_and_stock_leaves(client, db):
    client.app.state.runner.sim.cfg.noread_rate = 0
    auto, manual = first_auto_and_manual_sku(client)
    before = {b.id: b.qty_on_hand for b in db.scalars(select(Batch))}

    order_id = client.post("/api/orders", json={
        "pharmacy_code": "APT-007", "lines": [{"sku": auto, "qty": 12}, {"sku": manual, "qty": 3}],
    }).json()["id"]
    run_sim(client)

    order = client.get(f"/api/orders/{order_id}").json()
    assert order["status"] == "shipped"
    assert all(t["status"] == "packed" and t["location"] == "dock" for t in order["totes"])

    db.expire_all()
    after = {b.id: (b.qty_on_hand, b.qty_reserved) for b in db.scalars(select(Batch))}
    shipped = sum(before[i] - on_hand for i, (on_hand, _) in after.items())
    assert shipped == 15
    assert all(reserved == 0 for _, reserved in after.values())

    barcode = order["totes"][0]["barcode"]
    events = [e["type"] for e in client.get("/api/events", params={"barcode": barcode, "limit": 50}).json()]
    assert "scanned" in events and "packed" in events


def test_rejected_tote_can_be_resolved_by_operator(client, db):
    runner = client.app.state.runner
    runner.sim.cfg.noread_rate = 1.0
    auto, _ = first_auto_and_manual_sku(client)
    order_id = client.post("/api/orders", json={"pharmacy_code": "APT-001",
                                                "lines": [{"sku": auto, "qty": 3}]}).json()["id"]
    run_sim(client)

    order = client.get(f"/api/orders/{order_id}").json()
    assert order["status"] == "exception"
    barcode = order["totes"][0]["barcode"]
    assert client.get(f"/api/totes/{barcode}").json()["status"] == "rejected"

    assert client.post(f"/api/totes/{barcode}/resolve").status_code == 200
    assert client.get(f"/api/orders/{order_id}").json()["status"] == "shipped"
    assert client.post(f"/api/totes/{barcode}/resolve").status_code == 409


def test_demo_orders_and_metrics(client):
    created = client.post("/api/demo/orders", params={"count": 3}).json()
    assert len(created) == 3
    m = client.get("/api/metrics").json()
    assert sum(m["orders"].values()) == 3
    assert m["totes"]["created"] >= 3


def test_tote_detail_lists_batches(client, db):
    auto, _ = first_auto_and_manual_sku(client)
    order = client.post("/api/orders", json={"pharmacy_code": "APT-002",
                                             "lines": [{"sku": auto, "qty": 2}]}).json()
    detail = client.get(f"/api/totes/{order['totes'][0]['barcode']}").json()
    assert detail["items"][0]["sku"] == auto
    assert detail["items"][0]["batch_series"]


def test_restart_requeues_unfinished_totes(client, db):
    auto, _ = first_auto_and_manual_sku(client)
    client.post("/api/orders", json={"pharmacy_code": "APT-001", "lines": [{"sku": auto, "qty": 2}]})
    client.app.state.runner.tick(1.0)  # tote taken into the simulation
    db.expire_all()
    assert db.scalar(select(Tote)).status == "in_process"

    from app.db import SessionLocal
    from app.sim.runner import SimulationRunner
    SimulationRunner(SessionLocal)  # new process after a crash
    db.expire_all()
    assert db.scalar(select(Tote)).status == "created"


def test_websocket_sends_snapshot(client):
    with client.websocket_connect("/ws") as ws:
        msg = ws.receive_json()
    assert msg["type"] == "hello"
    assert "queues" in msg["snapshot"]


def test_paused_conveyor_still_shows_new_totes(client):
    runner = client.app.state.runner
    assert not runner.running
    auto, _ = first_auto_and_manual_sku(client)
    client.post("/api/orders", json={"pharmacy_code": "APT-001", "lines": [{"sku": auto, "qty": 2}]})
    runner.tick(0.0)  # what the loop does while STOP is pressed
    totes = runner.sim.snapshot()["totes"]
    assert len(totes) == 1 and totes[0]["stage"] == "queued"
    msg = runner.state_message()
    assert msg["running"] is False and "speed" in msg


def test_start_stop_endpoints(client):
    assert client.post("/api/sim/start").json() == {"running": True}
    assert client.app.state.runner.running
    assert client.post("/api/sim/stop").json() == {"running": False}


def test_tote_detail_has_product_and_pharmacy(client):
    _, manual = first_auto_and_manual_sku(client)
    order = client.post("/api/orders", json={"pharmacy_code": "APT-004",
                                             "lines": [{"sku": manual, "qty": 1}]}).json()
    detail = client.get(f"/api/totes/{order['totes'][0]['barcode']}").json()
    assert detail["pharmacy_code"] == "APT-004"
    assert detail["items"][0]["product_name"]
