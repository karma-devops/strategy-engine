"""
Smoke test for GET /api/v2/withdrawals/calculate with no HL credentials.
"""
import os

os.environ["INSTANCE_SECRET_KEY"] = __import__("cryptography.fernet").fernet.Fernet.generate_key().decode()
os.environ["DASHBOARD_USERNAME"] = "operator"
os.environ["DASHBOARD_PASSWORD"] = "testpass"
os.environ["AGENT_API_KEY"] = "testkey"
# Explicitly NOT setting HYPER_LIQUID_ETH_PRIVATE_KEY or ACCOUNT_ADDRESS
os.environ["DRY_RUN"] = "true"
os.environ["DATABASE_URL"] = "sqlite:///data/test_withdrawals_calc.db"

from fastapi.testclient import TestClient
from main import app


def main():
    for f in ["data/test_withdrawals_calc.db", "data/test_withdrawals_calc.db-wal", "data/test_withdrawals_calc.db-shm"]:
        if os.path.exists(f):
            os.remove(f)

    client = TestClient(app)
    resp = client.get("/api/v2/withdrawals/calculate", headers={"X-API-Key": "testkey"})
    print("GET /withdrawals/calculate:", resp.status_code, resp.json())
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["credentials_present"] is False
    assert body["balance"] == 0.0
    assert body["manual_50"]["amount"] == 0.0
    assert "No HyperLiquid credentials configured" in body["manual_50"]["reason"]

    for f in ["data/test_withdrawals_calc.db", "data/test_withdrawals_calc.db-wal", "data/test_withdrawals_calc.db-shm"]:
        if os.path.exists(f):
            os.remove(f)
    print("GET /api/v2/withdrawals/calculate graceful-no-creds test: PASSED")


if __name__ == "__main__":
    main()
