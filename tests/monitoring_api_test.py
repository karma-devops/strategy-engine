"""
Monitoring API end-to-end test.
Run with:
  source venv/bin/activate && \
  INSTANCE_SECRET_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") \
  DASHBOARD_USERNAME=operator DASHBOARD_PASSWORD=operator AGENT_API_KEY=test_api_key \
  DATABASE_URL=sqlite:///data/test_monitoring.db \
  DRY_RUN=true \
  PYTHONPATH=/workspace/projects/strategy-engine \
  python3 tests/monitoring_api_test.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DRY_RUN", "true")

from main import app
from fastapi.testclient import TestClient

API_KEY = os.environ.get("AGENT_API_KEY", "test_api_key")
API_HEADERS = {"X-API-Key": API_KEY}


def main():
    client = TestClient(app)

    print("[1] Seed fleet")
    from instances.manager import seed_default_fleet
    seed_default_fleet()
    r = client.get("/api/v2/instances", headers=API_HEADERS)
    assert r.status_code == 200
    print(f"  {len(r.json()['instances'])} instances")

    print("[2] Refresh scores")
    r = client.post("/api/v2/monitoring/scores/refresh", json={"days": 30}, headers=API_HEADERS)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["ok"] is True
    print(f"  {len(data['scores'])} scores computed")

    print("[3] Get scores")
    r = client.get("/api/v2/monitoring/scores", headers=API_HEADERS)
    assert r.status_code == 200
    assert r.json()["ok"] is True
    print(f"  {len(r.json()['scores'])} score rows")

    print("[4] Refresh rotation recommendations")
    r = client.post("/api/v2/monitoring/rotation/refresh", headers=API_HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    print(f"  {len(data['recommendations'])} recommendations")

    print("[5] Evaluate alerts")
    r = client.post("/api/v2/alerts/evaluate", headers=API_HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    print(f"  {data['created']} alerts created")

    print("[6] List alerts")
    r = client.get("/api/v2/alerts", headers=API_HEADERS)
    assert r.status_code == 200
    alerts = r.json()["alerts"]
    print(f"  {len(alerts)} alert rows")

    if alerts:
        alert_id = alerts[0]["id"]
        print("[7] Dismiss first alert")
        r = client.post(f"/api/v2/alerts/{alert_id}/dismiss", headers=API_HEADERS)
        assert r.status_code == 200
        assert r.json()["ok"] is True
        print("  dismissed")

    print("[8] Testing pool list")
    r = client.get("/api/v2/testing-pool", headers=API_HEADERS)
    assert r.status_code == 200
    assert r.json()["ok"] is True
    print(f"  {len(r.json()['assets'])} pool assets")

    print("\n✅ MONITORING API TEST PASSED")


if __name__ == "__main__":
    main()
