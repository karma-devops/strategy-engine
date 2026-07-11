"""
Smoke test for POST /api/v2/instances.
Uses a fresh temp DB and TestClient.
"""
import os

# Must set env BEFORE importing config/main
os.environ["INSTANCE_SECRET_KEY"] = __import__("cryptography.fernet").fernet.Fernet.generate_key().decode()
os.environ["DASHBOARD_USERNAME"] = "operator"
os.environ["DASHBOARD_PASSWORD"] = "testpass"
os.environ["AGENT_API_KEY"] = "testkey"
os.environ["DRY_RUN"] = "true"
os.environ["DATABASE_URL"] = "sqlite:///data/test_post_instances.db"

from fastapi.testclient import TestClient
from main import app
from instances.models import engine, Instance
from sqlalchemy.orm import sessionmaker


def main():
    # Fresh DB
    for f in ["data/test_post_instances.db", "data/test_post_instances.db-wal", "data/test_post_instances.db-shm"]:
        if os.path.exists(f):
            os.remove(f)

    client = TestClient(app)

    # Seed default fleet via app startup (lifespan should seed)
    # Actually main.py may not auto-seed; call endpoint directly after a GET
    list_resp = client.get("/api/v2/instances", headers={"X-API-Key": "testkey"})
    print("GET /instances:", list_resp.status_code, list_resp.json().get("ok"))

    payload = {
        "slug": "engine-test",
        "name": "Test Engine",
        "token": "DOGE",
        "strategy_id": "engine_v1_3",
        "mode": "Scalp",
        "profile": "aggressive_8_3",
        "timeframe": "15m",
        "leverage": 10,
        "max_position_pct": 0.15,
        "poll_interval_seconds": 60,
        "activation": 8,
        "offset": 3,
        "dry_run": True,
        "enabled": True,
    }
    resp = client.post("/api/v2/instances", json=payload, headers={"X-API-Key": "testkey"})
    print("POST /instances:", resp.status_code, resp.json())
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert resp.json()["instance"]["slug"] == "engine-test"

    # Duplicate should fail
    resp2 = client.post("/api/v2/instances", json=payload, headers={"X-API-Key": "testkey"})
    print("POST duplicate:", resp2.status_code, resp2.json())
    assert resp2.status_code == 200
    assert resp2.json()["ok"] is False

    # Unknown strategy should fail
    bad = dict(payload, slug="engine-bad", strategy_id="engine_v99")
    resp3 = client.post("/api/v2/instances", json=bad, headers={"X-API-Key": "testkey"})
    print("POST bad strategy:", resp3.status_code, resp3.json())
    assert resp3.status_code == 200
    assert resp3.json()["ok"] is False

    # Verify in DB
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        inst = db.query(Instance).filter(Instance.slug == "engine-test").first()
        assert inst is not None
        assert inst.token == "DOGE"
        print("DB verification: engine-test exists with token", inst.token)
    finally:
        db.close()

    # Cleanup
    for f in ["data/test_post_instances.db", "data/test_post_instances.db-wal", "data/test_post_instances.db-shm"]:
        if os.path.exists(f):
            os.remove(f)
    print("POST /api/v2/instances test: PASSED")


if __name__ == "__main__":
    main()
