"""
Multi-instance manager: start/stop/restart per-token strategy runners.
"""

import threading
from typing import Dict

from sqlalchemy.orm import sessionmaker

from config import config
from engine.registry import DEFAULT_FLEET
from instances.models import engine, Instance
from instances.runner import InstanceRunner, event_bus

Session = sessionmaker(bind=engine)


class InstanceManager:
    def __init__(self):
        self._runners: Dict[str, InstanceRunner] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def load_instances(self):
        """Load instances from DB but do NOT start them automatically."""
        db = Session()
        try:
            instances = db.query(Instance).all()
            for inst in instances:
                # Ensure any previously running instance is marked stopped on boot
                if inst.status == "running":
                    inst.status = "stopped"
                    self._persist_status(inst)
        finally:
            db.close()

    def start(self):
        """No-op for startup; instances are started manually via start_instance."""
        self.load_instances()

    def shutdown(self):
        with self._lock:
            for runner in self._runners.values():
                runner.stop()
            self._runners.clear()

    def stop(self):
        """Alias for shutdown."""
        self.shutdown()

    # ------------------------------------------------------------------
    # Control
    # ------------------------------------------------------------------
    def start_instance(self, instance: Instance) -> bool:
        with self._lock:
            if instance.slug in self._runners:
                return True
            # Respect kill states
            if instance.status == "killed":
                print(f"[MANAGER] Refusing to start {instance.slug}: instance is killed")
                return False
            db = Session()
            try:
                from instances.models import KillSwitchState
                global_state = db.query(KillSwitchState).filter(KillSwitchState.scope == "global").first()
                if global_state and global_state.active:
                    print(f"[MANAGER] Refusing to start {instance.slug}: global kill switch active")
                    return False
            finally:
                db.close()
            runner = InstanceRunner(instance)
            runner.start()
            self._runners[instance.slug] = runner
            instance.status = "running"
            self._persist_status(instance)
            return True

    def stop_instance(self, instance_id: str) -> bool:
        with self._lock:
            runner = self._runners.pop(instance_id, None)
            if not runner:
                return False
            runner.stop()
            self._persist_status(runner.instance, "stopped")
            return True

    def stop_instance_by_slug(self, slug: str) -> bool:
        """Stop a runner by slug; also updates DB status even if no runner exists."""
        with self._lock:
            runner = self._runners.pop(slug, None)
            if runner:
                runner.stop()
            db = Session()
            try:
                inst = db.query(Instance).filter(Instance.slug == slug).first()
                if inst and inst.status == "running":
                    inst.status = "stopped"
                    db.commit()
            finally:
                db.close()
            return True

    def stop_all(self):
        """Stop every running engine."""
        with self._lock:
            slugs = list(self._runners.keys())
            for slug in slugs:
                self.stop_instance(slug)

    def restart_instance(self, instance_id: str) -> bool:
        with self._lock:
            runner = self._runners.get(instance_id)
            if not runner:
                return False
            inst = runner.instance
            runner.stop()
            runner.start()
            inst.status = "running"
            self._persist_status(inst)
            return True

    def get_runner(self, instance_id: str) -> InstanceRunner:
        with self._lock:
            return self._runners.get(instance_id)

    def list_runners(self) -> Dict[str, InstanceRunner]:
        with self._lock:
            return dict(self._runners)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _persist_status(self, instance: Instance, status: str = None):
        db = Session()
        try:
            if status:
                instance.status = status
            db.merge(instance)
            db.commit()
        finally:
            db.close()


# Singleton manager
manager = InstanceManager()


def seed_default_instance():
    """Create the default FARTCOIN v1.3 instance if DB is empty."""
    db = Session()
    try:
        if db.query(Instance).first():
            return
        defaults = config.DEFAULT_INSTANCE
        inst = Instance(
            slug="engine-1",
            name=defaults["name"],
            token=defaults["token"],
            strategy_id=defaults["strategy_id"],
            mode=defaults["mode"],
            profile=defaults["profile"],
            timeframe=defaults["timeframe"],
            leverage=defaults["leverage"],
            max_position_pct=defaults["max_position_pct"],
            poll_interval_seconds=defaults["poll_interval_seconds"],
            dry_run=defaults["dry_run"],
            enabled=True,
            status="stopped",
        )
        db.add(inst)
        db.commit()
        print(f"[MANAGER] Seeded default instance {inst.slug} for {inst.token}")
        return inst
    finally:
        db.close()


def seed_default_fleet():
    """Ensure the 6-engine default fleet exists. Upsert missing presets and stop all."""
    db = Session()
    try:
        created_or_updated = []
        existing = {i.slug: i for i in db.query(Instance).all()}
        for preset in DEFAULT_FLEET:
            inst = existing.get(preset["slug"])
            if inst is None:
                inst = Instance(
                    slug=preset["slug"],
                    name=preset["name"],
                    token=preset["token"],
                    strategy_id=preset["strategy_id"],
                    mode=preset["mode"],
                    profile=preset["profile"],
                    timeframe=preset["timeframe"],
                    leverage=preset["leverage"],
                    max_position_pct=preset["max_position_pct"],
                    poll_interval_seconds=preset["poll_interval_seconds"],
                    dry_run=True,
                    enabled=True,
                    status="stopped",
                )
                db.add(inst)
                created_or_updated.append(("created", inst.slug))
            else:
                # Ensure fleet metadata stays aligned; preserve credentials/status
                inst.name = preset["name"]
                inst.token = preset["token"]
                inst.strategy_id = preset["strategy_id"]
                inst.mode = preset["mode"]
                inst.profile = preset["profile"]
                inst.timeframe = preset["timeframe"]
                inst.leverage = preset["leverage"]
                inst.max_position_pct = preset["max_position_pct"]
                inst.poll_interval_seconds = preset["poll_interval_seconds"]
                if inst.status not in ("running", "killed"):
                    inst.status = "stopped"
                created_or_updated.append(("synced", inst.slug))
        db.commit()
        for action, slug in created_or_updated:
            print(f"[MANAGER] {action} fleet instance {slug}")
        return created_or_updated
    finally:
        db.close()
