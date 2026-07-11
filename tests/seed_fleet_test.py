"""
Functional test for seed_default_fleet() upsert behavior.
Uses a fresh temporary SQLite DB and DRY_RUN=true.
"""
import os
import time

from instances.manager import seed_default_fleet, manager
from instances.models import engine, Instance
from sqlalchemy.orm import sessionmaker


def main():
    Session = sessionmaker(bind=engine)
    db = Session()

    # 1. Fresh DB must create 6 instances
    result = seed_default_fleet()
    print("First seed result:", result)

    instances = db.query(Instance).order_by(Instance.slug).all()
    print(f"Instance count after first seed: {len(instances)}")
    slugs = [i.slug for i in instances]
    expected = ["engine-1", "engine-2", "engine-3", "engine-4", "engine-5", "engine-6"]
    assert slugs == expected, f"Expected {expected}, got {slugs}"
    for inst in instances:
        print(f"  {inst.slug}: token={inst.token} strategy={inst.strategy_id} status={inst.status}")

    engine1 = db.query(Instance).filter(Instance.slug == "engine-1").first()
    assert engine1 is not None
    print("engine-1 exists: True")

    # 2. Re-seed on non-empty DB must be no-op (sync only)
    result2 = seed_default_fleet()
    print("Second seed result:", result2)
    instances2 = db.query(Instance).order_by(Instance.slug).all()
    assert len(instances2) == 6
    assert all(action == "synced" for action, _ in result2)
    print("Re-seed on non-empty DB: all synced, no duplicates")

    # 3. Start engine-1 path (dry-run; may error on HL connection but should register)
    manager.load_instances()
    started = manager.start_instance(engine1)
    print("start_instance(engine-1) returned:", started)
    time.sleep(0.5)
    runner = manager.get_runner("engine-1")
    print("runner registered:", runner is not None)
    if runner:
        print("runner is_running:", runner.is_running())
    manager.stop_instance_by_slug("engine-1")
    manager.shutdown()

    db.close()
    print("seed_default_fleet() functional test: PASSED")


if __name__ == "__main__":
    main()
