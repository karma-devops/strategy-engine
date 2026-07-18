"""
Smoke test for POST /api/v2/signals/{slug}.
Uses a fresh temp DB and TestClient.
"""
import os

os.environ["INSTANCE_SECRET_KEY"] = __import__("cryptography.fernet").fernet.Fernet.generate_key().decode()
os.environ["DASHBOARD_USERNAME"] = "operator"
os.environ["DASHBOARD_PASSWORD"] = "testpass"
os.environ["AGENT_API_KEY"] = "testkey"
os.environ["DRY_RUN"] = "true"
os.environ["DATABASE_URL"] = "sqlite:///data/test_post_signals.db"

from fastapi.testclient import TestClient
from main import app
from instances.models import engine, Signal
from sqlalchemy.orm import sessionmaker


def main():
    for f in ["data/test_post_signals.db", "data/test_post_signals.db-wal", "data/test_post_signals.db-shm"]:
        if os.path.exists(f):
            os.remove(f)

    client = TestClient(app)

    # Create an instance to target
    create_payload = {
        "slug": "engine-test",
        "name": "Test Engine",
        "token": "DOGE",
        "strategy_id": "engine_v1_3",
    }
    create_resp = client.post("/api/v2/instances", json=create_payload, headers={"X-API-Key": "testkey"})
    print("POST /instances:", create_resp.status_code, create_resp.json())
    assert create_resp.status_code == 200
    assert create_resp.json()["ok"] is True

    # Inject a signal
    signal_payload = {
        "direction": "BUY",
        "signal": 0.85,
        "metadata": {"test": True, "source": "api"},
        "reasoning": "test injection",
        "trade_active": False,
        "executed": False,
    }
    resp = client.post("/api/v2/signals/engine-test", json=signal_payload, headers={"X-API-Key": "testkey"})
    print("POST /signals/engine-test:", resp.status_code, resp.json())
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert resp.json()["signal"]["direction"] == "BUY"

    # Bad direction should fail validation (422)
    bad = dict(signal_payload, direction="HOLD")
    resp2 = client.post("/api/v2/signals/engine-test", json=bad, headers={"X-API-Key": "testkey"})
    print("POST bad direction:", resp2.status_code)
    assert resp2.status_code == 422

    # Unknown instance should return 200 ok=False
    resp3 = client.post("/api/v2/signals/unknown", json=signal_payload, headers={"X-API-Key": "testkey"})
    print("POST unknown instance:", resp3.status_code, resp3.json())
    assert resp3.status_code == 200
    assert resp3.json()["ok"] is False

    # Verify DB
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        rows = db.query(Signal).filter(Signal.instance_id == "engine-test").all()
        assert len(rows) == 1
        assert rows[0].direction == "BUY"
        print("DB verification: 1 signal stored for engine-test")
    finally:
        db.close()

    for f in ["data/test_post_signals.db", "data/test_post_signals.db-wal", "data/test_post_signals.db-shm"]:
        if os.path.exists(f):
            os.remove(f)
    print("POST /api/v2/signals/{slug} test: PASSED")


if __name__ == "__main__":
    main()
