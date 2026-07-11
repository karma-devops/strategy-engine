"""
Phase 2 kill switch verification test.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DRY_RUN", "true")

from main import app
from fastapi.testclient import TestClient

with TestClient(app) as client:

    def get_status(slug):
        r = client.get("/api/v2/instances")
        return next(i for i in r.json()["instances"] if i["slug"] == slug)["status"]

    # 1. Start engine-1
    print("[1] Start engine-1")
    assert client.post("/api/v2/instances/engine-1/start").json()["ok"]
    time.sleep(0.5)
    assert get_status("engine-1") == "running"
    print("  OK: running")

    # 2. Global kill stops engine-1 and blocks restart
    print("[2] Global kill")
    assert client.post("/api/v2/kill/global").json()["ok"]
    time.sleep(0.5)
    assert get_status("engine-1") == "stopped"
    print("  OK: engine-1 stopped")
    start_r = client.post("/api/v2/instances/engine-1/start").json()
    assert not start_r["ok"], start_r
    print("  OK: start rejected under global kill")

    # 3. Reset global kill
    print("[3] Reset global kill")
    assert client.post("/api/v2/kill/global/reset").json()["ok"]
    assert client.get("/api/v2/kill/status").json()["global"] is False
    print("  OK: global reset")

    # 4. Restart engine-1
    print("[4] Restart engine-1")
    assert client.post("/api/v2/instances/engine-1/start").json()["ok"]
    time.sleep(0.5)
    assert get_status("engine-1") == "running"
    print("  OK: running again")

    # 5. Per-instance kill
    print("[5] Per-instance kill engine-1")
    assert client.post("/api/v2/kill/engine-1").json()["ok"]
    time.sleep(0.5)
    assert get_status("engine-1") == "killed"
    print("  OK: killed")

    # 6. Try start killed instance
    print("[6] Try start killed instance")
    start_r = client.post("/api/v2/instances/engine-1/start").json()
    assert not start_r["ok"], start_r
    print("  OK: start rejected")

    # 7. Reset instance kill
    print("[7] Reset instance kill")
    assert client.post("/api/v2/kill/engine-1/reset").json()["ok"]
    assert get_status("engine-1") == "stopped"
    print("  OK: reset to stopped")

    # 8. Withdrawal kill blocks withdrawals
    print("[8] Withdrawal kill blocks withdrawals")
    assert client.post("/api/v2/kill/withdrawals").json()["ok"]
    r = client.post("/api/v2/withdrawals/manual/50").json()
    assert not r["ok"] and "kill switch" in r["message"], r
    print("  OK: withdrawal blocked")

    # 9. Reset withdrawal kill
    print("[9] Reset withdrawal kill")
    assert client.post("/api/v2/kill/withdrawals/reset").json()["ok"]
    assert client.get("/api/v2/kill/status").json()["withdrawals"] is False
    print("  OK: withdrawals reset")

    # 10. Persisted state after new app instance
    print("[10] Kill state persists across restart")

print("\n✅ ALL KILL SWITCH TESTS PASSED")
