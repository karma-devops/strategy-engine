"""
Backtest API end-to-end test.
Run with:
  source venv/bin/activate && \
  INSTANCE_SECRET_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") \
  DASHBOARD_USERNAME=operator DASHBOARD_PASSWORD=operator AGENT_API_KEY=test_api_key \
  DATABASE_URL=sqlite:///data/test_backtest.db \
  DRY_RUN=true \
  PYTHONPATH=/workspace/projects/strategy-engine \
  python3 tests/backtest_api_test.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DRY_RUN", "true")

from main import app
from fastapi.testclient import TestClient
from instances.manager import seed_default_fleet

API_KEY = os.environ.get("AGENT_API_KEY", "test_api_key")
API_HEADERS = {"X-API-Key": API_KEY}


def main():
    client = TestClient(app)

    print("[1] Ensure default fleet exists")
    seed_default_fleet()
    r = client.get("/api/v2/instances", headers=API_HEADERS)
    assert r.status_code == 200
    data = r.json()
    print(f"  Found {len(data.get('instances', []))} instances")
    assert any(i["slug"] == "engine-1" for i in data.get("instances", [])), "engine-1 not found"

    print("[2] POST /api/v2/backtests/run for engine-1 (FARTCOIN 15m, last 7 days)")
    payload = {"instance_slug": "engine-1", "days": 7, "initial_capital": 1000.0}
    r = client.post("/api/v2/backtests/run", json=payload, headers=API_HEADERS)
    print(f"  status: {r.status_code}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True, body
    backtest = body["backtest"]
    assert "id" in backtest
    assert backtest["token"] == "FARTCOIN"
    assert backtest["strategy_id"] == "translation-test"
    print(f"  backtest id: {backtest['id']}")
    print(f"  status: {backtest['status']}")
    if backtest["status"] == "done":
        print(f"  total_trades: {backtest['total_trades']}")
        print(f"  total_return_pct: {backtest['total_return_pct']:.4f}")
        print(f"  max_drawdown_pct: {backtest['max_drawdown_pct']:.4f}")
        print(f"  win_rate: {backtest['win_rate']:.2f}")
        print(f"  profit_factor: {backtest['profit_factor']:.4f}")
    else:
        print(f"  error_message: {backtest.get('error_message')}")

    print("[3] GET /api/v2/backtests")
    r = client.get("/api/v2/backtests?instance_slug=engine-1", headers=API_HEADERS)
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert len(r.json()["backtests"]) >= 1
    print(f"  listed {len(r.json()['backtests'])} backtest(s)")

    print("[4] GET /api/v2/backtests/{id}")
    bid = backtest["id"]
    r = client.get(f"/api/v2/backtests/{bid}", headers=API_HEADERS)
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert r.json()["backtest"]["id"] == bid
    print("  fetch by id OK")

    print("\n✅ BACKTEST API TEST PASSED")


if __name__ == "__main__":
    main()
