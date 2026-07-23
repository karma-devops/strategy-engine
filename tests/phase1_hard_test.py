"""
Hard-test all phase 1 functionality in strategy-engine.
Run with:
  source venv/bin/activate && \
  INSTANCE_SECRET_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") \
  DASHBOARD_USERNAME=operator DASHBOARD_PASSWORD=operator AGENT_API_KEY=test_api_key \
  DRY_RUN=true python3 tests/phase1_hard_test.py
"""
import os
import time
import sys
import base64

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("DRY_RUN", "true")

API_KEY = os.environ.get("AGENT_API_KEY", "test_api_key")
UI_USER = os.environ.get("DASHBOARD_USERNAME", "operator")
UI_PASS = os.environ.get("DASHBOARD_PASSWORD", "operator")
BASIC = base64.b64encode(f"{UI_USER}:{UI_PASS}".encode()).decode()
API_HEADERS = {"X-API-Key": API_KEY}
UI_HEADERS = {"Authorization": f"Basic {BASIC}"}

# compile all Python files first
print("[1/8] py_compile all .py files...")
import py_compile
import glob
files = (
    glob.glob("*.py")
    + glob.glob("api/*.py")
    + glob.glob("app/*.py")
    + glob.glob("core/*.py")
    + glob.glob("engine/*.py")
    + glob.glob("instances/*.py")
    + glob.glob("withdrawal/*.py")
)
for f in files:
    py_compile.compile(f, doraise=True)
print("  OK:", len(files), "files compiled")

# Fernet encryption
print("[2/8] Fernet encrypt/decrypt per-instance key...")
from instances.models import Instance
inst = Instance(slug="t-fernet", name="Fernet Test", token="FARTCOIN", strategy_id="strategy_v1_3")
inst.set_private_key("0xdeadbeef")
assert inst.get_private_key() == "0xdeadbeef"
print("  OK")

# default fleet seeding
print("[3/8] Default fleet seeding...")
from instances.manager import seed_default_fleet
from instances.models import SessionLocal, Instance
# Use the app's real DB path (import-time engine is already bound there)
seeded = seed_default_fleet()
# DEFAULT_FLEET defines 2 engines (engine-1, engine-2) per the
# "seed engine-1 only / 2-engine default fleet" decision (BACKLOG #32/#53).
assert len(seeded) == 2, f"expected 2 seeded, got {len(seeded)}"
slugs = [s for _, s in seeded]
assert slugs == ["engine-1", "engine-2"], slugs
print("  OK:", slugs)

# API tests via TestClient
print("[4/8] API smoke tests...")
from main import app
from fastapi.testclient import TestClient
client = TestClient(app)

r = client.get("/health")
assert r.status_code == 200 and r.json()["status"] == "ok", r.json()
print("  /health OK")

r = client.get("/api/v2/instances", headers=API_HEADERS)
assert r.status_code == 200
assert len(r.json()["instances"]) == 2
print("  /api/v2/instances OK")

r = client.get("/api/v2/instances/active", headers=API_HEADERS)
assert r.status_code == 200 and r.json()["ok"] is True
assert len(r.json()["instances"]) == 0
print("  /api/v2/instances/active OK (empty)")

r = client.get("/api/v2/strategies", headers=API_HEADERS)
assert r.status_code == 200 and len(r.json()["strategies"]) >= 2
print("  /api/v2/strategies OK")

r = client.get("/api/v2/presets/fleet", headers=API_HEADERS)
assert r.status_code == 200 and len(r.json()["fleet"]) == 2
print("  /api/v2/presets/fleet OK")

r = client.get("/api/v2/withdrawals/calculate", headers=API_HEADERS)
assert r.status_code == 200 and "balance" in r.json()
print("  /api/v2/withdrawals/calculate OK")

# start / stop
print("[5/8] Engine start/stop API...")
r = client.post("/api/v2/instances/engine-1/start", headers=API_HEADERS)
assert r.status_code == 200 and r.json()["ok"] is True, r.json()
print("  start OK")

time.sleep(1)
r = client.get("/api/v2/instances/active", headers=API_HEADERS)
assert r.json()["ok"] is True and len(r.json()["instances"]) == 1
assert r.json()["instances"][0]["slug"] == "engine-1"
print("  active list after start OK")

r = client.get("/api/v2/instances/engine-1/signals", headers=API_HEADERS)
assert r.status_code == 200
print("  signals endpoint OK (count:", len(r.json()["signals"]), ")")

r = client.post("/api/v2/instances/engine-1/stop", headers=API_HEADERS)
assert r.status_code == 200 and r.json()["ok"] is True, r.json()
print("  stop OK")

time.sleep(0.5)
r = client.get("/api/v2/instances/active", headers=API_HEADERS)
assert len(r.json()["instances"]) == 0
print("  active list after stop OK")

r = client.get("/api/v2/instances", headers=API_HEADERS)
inst = next(i for i in r.json()["instances"] if i["slug"] == "engine-1")
assert inst["status"] == "stopped"
print("  DB status persisted as stopped OK")

# UI routes render
print("[6/8] UI routes render...")
for path in ["/", "/instances/new", "/withdrawals"]:
    r = client.get(path, headers=UI_HEADERS)
    assert r.status_code == 200, f"{path} failed: {r.status_code}"
    print(f"  {path} OK")

# UI form create instance
print("[7/8] Create instance via UI form...")
form_data = {
    "slug": "manual-test",
    "name": "Manual Test Instance",
    "token": "BTC",
    "strategy_id": "strategy_v1_3",
    "mode": "Scalp",
    "profile": "aggressive_8_3",
    "timeframe": "15m",
    "leverage": "10",
    "max_position_pct": "0.50",
    "poll_interval_seconds": "30",
    "activation": "8",
    "offset": "3",
    "dry_run": "true",
}
r = client.post("/instances", data=form_data, follow_redirects=False, headers=UI_HEADERS)
assert r.status_code == 303 and r.headers["location"] == "/", r.status_code
print("  create instance redirect OK")

r = client.get("/api/v2/instances", headers=API_HEADERS)
inst = next((i for i in r.json()["instances"] if i["slug"] == "manual-test"), None)
assert inst is not None and inst["token"] == "BTC"
print("  instance persisted OK")

# per-instance credential with override
print("[8/8] Per-instance credential override...")
form_data2 = {
    "slug": "cred-test",
    "name": "Cred Test",
    "token": "ETH",
    "strategy_id": "strategy_v1_3",
    "mode": "Scalp",
    "profile": "aggressive_8_3",
    "timeframe": "15m",
    "leverage": "10",
    "max_position_pct": "0.50",
    "poll_interval_seconds": "30",
    "activation": "8",
    "offset": "3",
    "hyperliquid_private_key": "0xsecret123",
    "account_address": "0xabc",
    "withdrawal_address": "0xdef",
    "dry_run": "true",
}
r = client.post("/instances", data=form_data2, follow_redirects=False, headers=UI_HEADERS)
assert r.status_code == 303, r.status_code
print("  create with creds OK")

db = SessionLocal()
inst2 = db.query(Instance).filter(Instance.slug == "cred-test").first()
assert inst2 is not None
assert inst2.account_address == "0xabc"
assert inst2.withdrawal_address == "0xdef"
assert inst2.get_private_key() == "0xsecret123"
print("  encrypted private key round-trip OK")
db.close()

print("\n✅ ALL PHASE 1 HARD TESTS PASSED")
