"""
Smoke test for the overhauled dashboard UI.
Starts the FastAPI app with a fresh test DB and verifies key UI routes render.
"""
import os

os.environ["INSTANCE_SECRET_KEY"] = __import__("cryptography.fernet").fernet.Fernet.generate_key().decode()
os.environ["DASHBOARD_USERNAME"] = "operator"
os.environ["DASHBOARD_PASSWORD"] = "testpass"
os.environ["AGENT_API_KEY"] = "testkey"
os.environ["DRY_RUN"] = "true"
os.environ["DATABASE_URL"] = "sqlite:///data/test_ui_overhaul.db"

from main import app
from fastapi.testclient import TestClient


def main():
    client = TestClient(app)
    for f in ["data/test_ui_overhaul.db", "data/test_ui_overhaul.db-wal", "data/test_ui_overhaul.db-shm"]:
        if os.path.exists(f):
            os.remove(f)

    # Root is the public landing page
    r = client.get("/", auth=("operator", "testpass"))
    assert r.status_code == 200, f"landing status {r.status_code}"
    assert "PULS" in r.text, "missing brand on landing"
    print("Landing renders: OK")

    r = client.get("/static/style.css")
    assert r.status_code == 200, "style.css missing"
    assert "--bg-0" in r.text, "missing CSS variables"
    print("CSS serves: OK")

    # Server-rendered dashboard (Option B) — no SPA app.js
    r = client.get("/app/dashboard", auth=("operator", "testpass"))
    assert r.status_code == 200, f"dashboard status {r.status_code}"
    assert "Account Value" in r.text, "missing Account Value KPI"
    assert "Fleet" in r.text, "missing Fleet header"
    assert "lightweight-charts" in r.text, "missing equity chart lib"
    print("Server-rendered dashboard: OK")

    r = client.get("/app/backtests", auth=("operator", "testpass"))
    assert r.status_code == 200, f"backtests status {r.status_code}"
    assert "Run Backtest" in r.text, "missing backtest form"
    print("Server-rendered backtests: OK")

    # Cleanup
    for f in ["data/test_ui_overhaul.db", "data/test_ui_overhaul.db-wal", "data/test_ui_overhaul.db-shm"]:
        if os.path.exists(f):
            os.remove(f)
    print("UI overhaul smoke test: PASSED")


if __name__ == "__main__":
    main()
