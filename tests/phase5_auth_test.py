"""
Phase 5 auth verification test.
Run with:
  source venv/bin/activate && \
  DASHBOARD_USERNAME=operator DASHBOARD_PASSWORD=operator AGENT_API_KEY=test_api_key \
  INSTANCE_SECRET_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") \
  DRY_RUN=true python3 tests/phase5_auth_test.py
"""
import os
import sys
import base64

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DRY_RUN", "true")

from main import app
from fastapi.testclient import TestClient

client = TestClient(app)

API_KEY = os.environ.get("AGENT_API_KEY", "test_api_key")
UI_USER = os.environ.get("DASHBOARD_USERNAME", "operator")
UI_PASS = os.environ.get("DASHBOARD_PASSWORD", "operator")
BASIC = base64.b64encode(f"{UI_USER}:{UI_PASS}".encode()).decode()

print("[1] Public static /health should remain open")
r = client.get("/health")
assert r.status_code == 200, r.status_code
print("  OK")

print("[2] UI routes auth enforcement")
# / is the PUBLIC landing page (no auth required)
r = client.get("/")
assert r.status_code == 200, f"/ should be public, got {r.status_code}"
print("  / OK (public)")
# These routes require Basic Auth
for path in ["/instances/new", "/withdrawals"]:
    assert client.get(path).status_code == 401, path
    r = client.get(path, headers={"Authorization": f"Basic {BASIC}"})
    assert r.status_code == 200, f"{path} -> {r.status_code}"
    print(f"  {path} OK")

print("[3] API read endpoints require X-API-Key")
for path in ["/api/v2/instances", "/api/v2/strategies", "/api/v2/kill/status"]:
    assert client.get(path).status_code == 403, path
    r = client.get(path, headers={"X-API-Key": API_KEY})
    assert r.status_code == 200, f"{path} -> {r.status_code}"
    print(f"  {path} OK")

print("[4] API write endpoints require X-API-Key")
r = client.post("/api/v2/instances/engine-1/start")
assert r.status_code == 403, r.status_code
r = client.post("/api/v2/instances/engine-1/start", headers={"X-API-Key": API_KEY})
assert r.status_code == 200, r.status_code
print("  start OK")

print("[5] Wrong API key rejected")
r = client.get("/api/v2/instances", headers={"X-API-Key": "bad-key"})
assert r.status_code == 403, r.status_code
print("  OK")

print("[6] Wrong Basic password rejected")
bad_basic = base64.b64encode(b"operator:wrong").decode()
r = client.get("/", headers={"Authorization": f"Basic {bad_basic}"})
assert r.status_code == 401, r.status_code
print("  OK")

print("\n✅ ALL AUTH TESTS PASSED")
