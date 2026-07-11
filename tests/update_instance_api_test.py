"""
Test updating an instance via PUT /api/v2/instances/{slug}.
"""
import os

os.environ["DATABASE_URL"] = "sqlite:///data/test_update_instance.db"
os.environ["INSTANCE_SECRET_KEY"] = __import__("cryptography.fernet").fernet.Fernet.generate_key().decode()
os.environ["DRY_RUN"] = "true"
os.environ["DASHBOARD_USERNAME"] = "operator"
os.environ["DASHBOARD_PASSWORD"] = "operator"
os.environ["AGENT_API_KEY"] = "testkey"

from main import app
from fastapi.testclient import TestClient
from instances.manager import seed_default_fleet
from instances.models import Base, engine


def main():
    for f in ["data/test_update_instance.db", "data/test_update_instance.db-wal", "data/test_update_instance.db-shm"]:
        if os.path.exists(f):
            os.remove(f)

    Base.metadata.create_all(bind=engine)
    seed_default_fleet()

    client = TestClient(app)

    # Update engine-1 settings
    r = client.put(
        "/api/v2/instances/engine-1",
        json={"leverage": 15, "max_position_pct": 0.85, "poll_interval_seconds": 45},
        headers={"X-API-Key": "testkey"},
    )
    assert r.status_code == 200, f"PUT failed: {r.status_code} {r.text}"
    data = r.json()
    assert data["ok"], data
    print(f"Update response: {data['message']}")

    # Verify changes
    r = client.get("/api/v2/instances", headers={"X-API-Key": "testkey"})
    inst = next(i for i in r.json()["instances"] if i["slug"] == "engine-1")
    assert inst["leverage"] == 15, inst
    assert inst["max_position_pct"] == 0.85, inst
    assert inst["poll_interval_seconds"] == 45, inst
    print("Instance update verified: OK")

    # Cleanup
    for f in ["data/test_update_instance.db", "data/test_update_instance.db-wal", "data/test_update_instance.db-shm"]:
        if os.path.exists(f):
            os.remove(f)
    print("PUT instance update test: PASSED")


if __name__ == "__main__":
    main()
