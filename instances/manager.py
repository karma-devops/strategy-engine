"""
Multi-instance manager: start/stop/restart per-token strategy runners.
"""

import threading
from typing import Dict

from sqlalchemy.orm import sessionmaker

from config import config
from strategies.registry import DEFAULT_FLEET
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
    def load_instances(self, auto_resume: bool = True):
        """Load instances from DB.

        D2: if auto_resume is True (default), any instance that was `running`
        before the last shutdown is automatically restarted on boot — UNLESS
        it is killed or the global kill switch is active. This prevents a
        server restart from silently leaving live engines dead.

        If auto_resume is False, previously-running instances are marked
        `stopped` (legacy behavior).
        """
        db = Session()
        try:
            instances = db.query(Instance).all()
            for inst in instances:
                if inst.status == "running":
                    if not auto_resume:
                        inst.status = "stopped"
                        self._persist_status(inst)
                        continue
                    # D2: attempt to resume. Kill states are checked inside
                    # start_instance() (refuses if killed / global kill active).
                    try:
                        self.start_instance(inst)
                        add_log_safe(
                            f"[MANAGER] Auto-resumed {inst.slug} on boot (D2)",
                            "info", dry_run=inst.dry_run,
                        )
                    except Exception as e:
                        print(f"[MANAGER] Auto-resume failed for {inst.slug}: {e}")
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
        """Stop a runner and/or clear a zombie DB status.

        If the in-memory runner is gone (e.g. thread crashed), the API call
        still falls back to resetting the DB status to stopped so the UI
        and CLI don't trust a dead engine.
        """
        with self._lock:
            runner = self._runners.pop(instance_id, None)
            if runner:
                # B7 fix: close the open position on the exchange
                # BEFORE stopping the thread, so a stopped engine never
                # leaves an unmanaged position.
                # Only for live (dry_run=False) instances — paper/backtest
                # never open real positions.
                inst = runner.instance
                if inst and not inst.dry_run and inst.position_side:
                    try:
                        from core.exchange import get_hyperliquid_client
                        client = get_hyperliquid_client(inst)
                        client.market_close(inst.token)
                        print(f"[MANAGER] B7: closed live position for {instance_id} ({inst.token}) before stop")
                    except Exception as e:
                        print(f"[MANAGER] B7: failed to close position for {instance_id}: {e}")
                runner.stop()
                self._persist_status(runner.instance, "stopped")
                return True
            # Fallback: runner thread is gone but DB still says running (zombie)
            db = Session()
            try:
                inst = db.query(Instance).filter(Instance.slug == instance_id).first()
                if inst and inst.status == "running":
                    inst.status = "stopped"
                    db.commit()
            finally:
                db.close()
            return True

    def stop_instance_by_slug(self, slug: str) -> bool:
        """Alias that guarantees DB status is cleared."""
        return self.stop_instance(slug)

    def stop_all(self):
        """Stop every running engine."""
        with self._lock:
            slugs = list(self._runners.keys())
            for slug in slugs:
                self.stop_instance(slug)

    def close_all_positions(self):
        """Close open positions on the exchange for all running instances.

        Used by the global kill switch so engaging it flattens exposure
        instead of leaving positions open and unmanaged.
        """
        from core.exchange import get_hyperliquid_client
        with self._lock:
            for slug, runner in list(self._runners.items()):
                try:
                    inst = runner.instance
                    client = get_hyperliquid_client(inst)
                    result = client.market_close(inst.token)
                    print(f"[MANAGER] Kill switch closed position for {slug} ({inst.token}): {result is not None}")
                except Exception as e:
                    print(f"[MANAGER] Failed to close position for {slug}: {e}")

    def restart_instance(self, instance_id: str) -> bool:
        with self._lock:
            runner = self._runners.get(instance_id)
            if not runner:
                return False
            inst = runner.instance
            # BUG #5: check kill state before restarting
            # Lazy import avoids circular import (killswitch → manager)
            from api.killswitch import is_instance_killed, is_global_killed
            db = Session()
            try:
                if inst.status == "killed" or is_instance_killed(db, inst.slug) or is_global_killed(db):
                    add_log_safe(f"[MANAGER] Restart blocked — {inst.slug} is killed", "warn", dry_run=inst.dry_run)
                    return False
            finally:
                db.close()
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
        """Persist only the runner status to the DB.

        Uses a fresh query by slug and writes ONLY the status column so a
        stale in-memory instance object (e.g. one loaded before a PUT flipped
        dry_run) cannot clobber operator-set fields like dry_run back to their
        old value.
        """
        db = Session()
        try:
            db_inst = db.query(Instance).filter(Instance.slug == instance.slug).first()
            if db_inst is None:
                return
            if status:
                db_inst.status = status
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
        from instances.models import get_or_seed_operator
        operator = get_or_seed_operator(db)
        created_or_updated = []
        existing = {i.slug: i for i in db.query(Instance).all()}
        for preset in DEFAULT_FLEET:
            inst = existing.get(preset["slug"])
            if inst is None:
                inst = Instance(
                    slug=preset["slug"],
                    user_id=operator.id,
                    name=preset["name"],
                    token=preset["token"],
                    strategy_id=preset["strategy_id"],
                    mode=preset["mode"],
                    profile=preset["profile"],
                    timeframe=preset["timeframe"],
                    leverage=preset["leverage"],
                    max_position_pct=preset["max_position_pct"],
                    poll_interval_seconds=preset["poll_interval_seconds"],
                    dry_run=operator.default_dry_run,  # default to Paper (per user setting)
                    enabled=True,
                    status="stopped",
                )
                db.add(inst)
                created_or_updated.append(("created", inst.slug))
            else:
                # Ensure fleet metadata stays aligned for NEW fields; preserve
                # operator-edited fields (timeframe, leverage, max_position_pct, etc.)
                # so UI changes survive a server restart.
                inst.name = preset["name"]
                inst.token = preset["token"]
                inst.strategy_id = preset["strategy_id"]
                inst.mode = preset["mode"]
                inst.profile = preset["profile"]
                # DO NOT overwrite operator-edited config across fleet sync
                # inst.timeframe = preset["timeframe"]
                # inst.leverage = preset["leverage"]
                # inst.max_position_pct = preset["max_position_pct"]
                # inst.poll_interval_seconds = preset["poll_interval_seconds"]
                if inst.user_id is None:
                    inst.user_id = operator.id
                # NOTE: do NOT overwrite inst.dry_run here — preserve operator's DB setting
                # (e.g. dry_run=True forced for safe testing) across fleet syncs.
                if inst.status not in ("running", "killed"):
                    inst.status = "stopped"
                created_or_updated.append(("synced", inst.slug))
        db.commit()
        for action, slug in created_or_updated:
            print(f"[MANAGER] {action} fleet instance {slug}")
        return created_or_updated
    finally:
        db.close()


def add_log_safe(msg: str, level: str, dry_run: bool = False):
    """Best-effort log helper that never raises (used during boot)."""
    try:
        from instances.logger import add_log
        add_log(msg, level, dry_run=dry_run)
    except Exception:
        pass
