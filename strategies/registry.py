"""
Strategy registry for strategy-engine.

TERMINOLOGY (keep these distinct):
  - STRATEGY  = the trading logic/signal class (e.g. v1.3, v1, v6.1). Lives in
                strategies/{slug}/<file>.py.
  - ENGINE    = a running Instance that executes a Strategy against HyperLiquid
                (see instances/runner.py). An Instance has a strategy_id.

Track 5.3 (2026-07-24): the registry now DISCOVERS strategies dynamically by
scanning strategies/{slug}/ for a BaseStrategy subclass via importlib. The
legacy hardcoded dict below remains as the SEED (canonical built-ins); the
loader overlays any discovered subdir strategy on top, so built-ins and
file-based strategies coexist. Public names are unchanged so callers
(instances/runner.py, api/*, app/routes.py, testing/runner.py,
backtests/runner.py, scripts/worker.py) don't break.

detect_mintick is re-exported from core/ (moved in Track 5.7).
"""
import importlib
import inspect
import pkgutil
from pathlib import Path

from strategies.base import BaseStrategy

# Re-export detect_mintick from core/ (moved there in Track 5.7 — it is a
# strategy-support helper, not registry logic). Kept here so existing importers
# (`instances/runner.py`, `api/strategies.py`, `scripts/worker.py`) need no change.
from core.detect_mintick import detect_mintick  # noqa: E402,F401


# ---------------------------------------------------------------------------
# Seed registry — canonical built-in strategies (kept for backward compat).
# Imported directly so they resolve even if subdir discovery is disabled.
# ---------------------------------------------------------------------------
from strategies.strategy_v1_3.v1_3 import EngineV1_3Strategy  # noqa: E402
from strategies.strategy_v1.v1 import EngineV1Strategy  # noqa: E402
from strategies.strategy_v6_1.v6_1 import EngineV6_1Strategy  # noqa: E402

_SEED_STRATEGIES = {
    "strategy_v1_3": EngineV1_3Strategy,
    "strategy_v1": EngineV1Strategy,
    "strategy_v6_1": EngineV6_1Strategy,
}

# Backward-compat aliases → canonical key. DO NOT remove (existing DB rows use these).
ALIASES = {
    "engine_v1_3": "strategy_v1_3",
    "engine_v1": "strategy_v1",
    "engine_v6_1": "strategy_v6_1",
}


def _discover_subdir_strategies() -> dict:
    """Scan strategies/{slug}/ for BaseStrategy subclasses.

    Returns {slug: class}. A subdir strategy overrides a seed entry with the
    same slug. The class's module name (strategy_id) is derived from the subdir
    name; the discovered class is registered under that slug.
    """
    found = {}
    strategies_root = Path(__file__).resolve().parent
    for sub in strategies_root.iterdir():
        if not sub.is_dir():
            continue
        if sub.name.startswith("_") or sub.name in ("__pycache__",):
            continue
        # find the first .py file that defines a BaseStrategy subclass
        py_files = sorted(sub.glob("*.py"))
        for pf in py_files:
            if pf.name.startswith("_") or pf.name == "base.py":
                continue
            module_name = f"strategies.{sub.name}.{pf.stem}"
            try:
                mod = importlib.import_module(module_name)
            except Exception:
                # a broken strategy subdir must not take down the whole registry
                continue
            for _, obj in inspect.getmembers(mod, inspect.isclass):
                if (
                    issubclass(obj, BaseStrategy)
                    and obj is not BaseStrategy
                    and obj.__module__ == module_name
                ):
                    found[sub.name] = obj
                    break
    return found


# STRATEGIES = seed overlaid with discovered subdir strategies.
STRATEGIES = dict(_SEED_STRATEGIES)
STRATEGIES.update(_discover_subdir_strategies())


def list_strategies() -> list:
    # Canonical keys only — no alias duplicates.
    return list(STRATEGIES.keys())


def _resolve_strategy_id(strategy_id: str) -> str:
    """Map a (possibly legacy) strategy_id to its canonical registry key."""
    if strategy_id in STRATEGIES:
        return strategy_id
    return ALIASES.get(strategy_id, strategy_id)


def get_strategy(strategy_id: str):
    return STRATEGIES.get(_resolve_strategy_id(strategy_id))


def get_presets(strategy_id: str) -> dict:
    """Return preset configs for a strategy (UI-facing; kept as static map).

    TODO (1.7 / future): derive from strategy.get_default_config() once all
    built-ins expose presets uniformly. Kept static to avoid breaking the
    engine settings panel during the dynamic-loader refactor.
    """
    canonical = _resolve_strategy_id(strategy_id)
    if canonical == "strategy_v1_3":
        return {
            "default": {
                "mode": "Scalp",
                "profile": "aggressive_8_3",
                "timeframe": "15m",
                "activation": 8,
                "offset": 3,
            }
        }
    if canonical == "strategy_v1":
        return {
            "sniper_36_12": {
                "mode": "Swing",
                "profile": "sniper_36_12",
                "timeframe": "1h",
                "activation": 36,
                "offset": 12,
            }
        }
    if canonical == "strategy_v6_1":
        return {
            "default": {
                "mode": "Scalp",
                "profile": "manual_18_6",
                "timeframe": "15m",
                "activation": 18,
                "offset": 6,
            }
        }
    return {}


def register_uploaded_strategy(strategy_id: str, strategy_cls) -> None:
    """Register an uploaded/cloned strategy in the runtime registry."""
    STRATEGIES[strategy_id] = strategy_cls


def unregister_uploaded_strategy(strategy_id: str) -> None:
    """Remove an uploaded/cloned strategy from the runtime registry."""
    canonical = _resolve_strategy_id(strategy_id)
    if canonical in STRATEGIES and canonical not in _SEED_STRATEGIES:
        del STRATEGIES[canonical]
