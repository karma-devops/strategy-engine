"""
Live HyperLiquid smoke test:
- Starts engine-1 with live creds (DRY_RUN=true)
- Checks /api/v2/account and /api/v2/instances/active
- Verifies dashboard renders
"""
import os

# Set DATABASE_URL before any imports so instances.models.engine points here
os.environ["DATABASE_URL"] = "sqlite:///data/test_live_smoke.db"
os.environ["INSTANCE_SECRET_KEY"] = __import__("cryptography.fernet").fernet.Fernet.generate_key().decode()
os.environ["DRY_RUN"] = "true"
os.environ["DASHBOARD_USERNAME"] = "operator"
os.environ["DASHBOARD_PASSWORD"] = "operator"
os.environ["AGENT_API_KEY"] = "test_api_key"

# Remove any stale test DB before model import creates the engine
for f in ["data/test_live_smoke.db", "data/test_live_smoke.db-wal", "data/test_live_smoke.db-shm"]:
    if os.path.exists(f):
        os.remove(f)

from main import app
from fastapi.testclient import TestClient
from instances.manager import seed_default_fleet, manager
from instances.models import Instance, Base, engine
from sqlalchemy.orm import sessionmaker


def main():
    # Ensure tables exist on the correct engine
    Base.metadata.create_all(bind=engine)

    Session = sessionmaker(bind=engine)
    client = TestClient(app)

    # Seed default fleet
    seed_default_fleet()

    # Start engine-1 via manager singleton
    db = Session()
    try:
        instance = db.query(Instance).filter(Instance.slug == "engine-1").first()
        ok = manager.start_instance(instance)
        assert ok, "engine-1 start failed"
    finally:
        db.close()

    # API checks with X-API-Key
    r = client.get("/api/v2/instances/active", headers={"X-API-Key": "test_api_key"})
    assert r.status_code == 200, f"active instances failed: {r.status_code}"
    data = r.json()
    assert any(i["slug"] == "engine-1" for i in data.get("instances", [])), "engine-1 not active"
    print("Active instances: OK")

    r = client.get("/api/v2/account", headers={"X-API-Key": "test_api_key"})
    assert r.status_code == 200, f"account failed: {r.status_code}"
    data = r.json()
    assert data.get("account_value", 0) > 0, "account value missing"
    print(f"Account value from API: {data['account_value']} (live)")

    # UI dashboard renders with Basic Auth
    r = client.get("/", auth=("operator", "operator"))
    assert r.status_code == 200
    assert "Pulse Graph" in r.text
    print("Dashboard renders with live creds: OK")

    manager.stop_instance_by_slug("engine-1")

    # Cleanup
    for f in ["data/test_live_smoke.db", "data/test_live_smoke.db-wal", "data/test_live_smoke.db-shm"]:
        if os.path.exists(f):
            os.remove(f)
    print("Live smoke test: PASSED")


if __name__ == "__main__":
    main()
