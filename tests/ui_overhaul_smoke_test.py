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

    # Basic auth helper
    r = client.get("/", auth=("operator", "testpass"))
    assert r.status_code == 200, f"dashboard status {r.status_code}"
    assert "Pulse Graph" in r.text, "missing Pulse Graph header"
    assert "Fleet" in r.text, "missing Fleet header"
    assert "Global Logs" in r.text, "missing Global Logs header"
    print("Dashboard renders: OK")

    r = client.get("/static/style.css")
    assert r.status_code == 200, "style.css missing"
    assert "--panel" in r.text, "missing CSS variables"
    print("CSS serves: OK")

    r = client.get("/static/app.js")
    assert r.status_code == 200, "app.js missing"
    assert "drawPulse" in r.text, "missing drawPulse function"
    print("JS serves: OK")

    # Cleanup
    for f in ["data/test_ui_overhaul.db", "data/test_ui_overhaul.db-wal", "data/test_ui_overhaul.db-shm"]:
        if os.path.exists(f):
            os.remove(f)
    print("UI overhaul smoke test: PASSED")


if __name__ == "__main__":
    main()
