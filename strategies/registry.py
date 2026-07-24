"""
Strategy registry for strategy-engine.

TERMINOLOGY (keep these distinct):
  - STRATEGY  = the trading logic/signal class (e.g. v1.3, v1, v6.1). Lives in
                strategies/{slug}/<file>.py.
  - ENGINE    = a running Instance that executes a Strategy against HyperLiquid
                (see instances/runner.py). An Instance has a strategy_id.

Track 5.3 (2026-07-24): the registry DISCOVERS strategies dynamically by
scanning strategies/{slug}/ for a BaseStrategy subclass via importlib. The
prior hardcoded SEED dict (EngineV1_3Strategy / EngineV1Strategy /
EngineV6_1Strategy) was removed in Track 5 legacy-removal (2026-07-24)
— the legacy strategy_v1_3 / strategy_v1 / strategy_v6_1 dirs were
moved to backups/legacy-strategies/, so the seed must stay empty or the
whole module raises ModuleNotFoundError at import. STRATEGIES is now
populated by _discover_subdir_strategies() alone. Public names unchanged
so callers (instances/runner.py, api/*, app/routes.py, testing/runner.py,
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
# Seed registry — EMPTY by design (Track 5 legacy removal, 2026-07-24).
# All strategies are now discovered dynamically from strategies/{slug}/ via
# _discover_subdir_strategies() below. The prior hardcoded seed imported
# EngineV1_3Strategy / EngineV1Strategy / EngineV6_1Strategy from the
# legacy strategy_v1_3 / strategy_v1 / strategy_v6_1 dirs — those dirs
# were moved to backups/legacy-strategies/ and must NOT be imported here,
# or the whole registry module raises ModuleNotFoundError at import time.
# ---------------------------------------------------------------------------
_SEED_STRATEGIES = {}


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


# STRATEGIES = discovered subdir strategies only (seed is empty post-legacy-removal).
# Dynamic loader is the sole source of truth now.
STRATEGIES = _discover_subdir_strategies()


def list_strategies() -> list:
    # Canonical keys only — no alias duplicates.
    return list(STRATEGIES.keys())


def _resolve_strategy_id(strategy_id: str) -> str:
    """Map a (possibly legacy) strategy_id to its canonical registry key.

    As of Track 5 legacy removal (2026-07-24) all strategies are
    slug-discovered; there are no backward-compat aliases. This now
    resolves only to a live key or returns the id unchanged.
    """
    if strategy_id in STRATEGIES:
        return strategy_id
    return strategy_id


def get_strategy(strategy_id: str):
    return STRATEGIES.get(_resolve_strategy_id(strategy_id))


def get_presets(strategy_id: str) -> dict:
    """Return preset configs for a strategy (UI-facing; kept as static map).

    Track 5 legacy removal (2026-07-24): the hardcoded v1_3 / v1 /
    v6_1 preset blocks were removed with the legacy strategies. Presets
    should now be derived per-strategy via strategy.get_default_config()
    (TODO 1.7). Until every discovered strategy exposes that uniformly,
    this returns {} and the UI falls back to the strategy's own defaults.
    """
    canonical = _resolve_strategy_id(strategy_id)
    # No static presets remain post-legacy-removal; callers fall back to
    # the discovered strategy's get_default_config()/get_parameters().
    _ = canonical  # resolved for forward-compat callers
    return {}


def register_uploaded_strategy(strategy_id: str, strategy_cls) -> None:
    """Register an uploaded/cloned strategy in the runtime registry."""
    STRATEGIES[strategy_id] = strategy_cls


def unregister_uploaded_strategy(strategy_id: str) -> None:
    """Remove an uploaded/cloned strategy from the runtime registry."""
    canonical = _resolve_strategy_id(strategy_id)
    if canonical in STRATEGIES and canonical not in _SEED_STRATEGIES:
        del STRATEGIES[canonical]


def clone_strategy(slug: str, new_slug: str) -> Path:
    """Clone a strategy subdir into a new, self-contained, editable copy.

    Mirrors clone_instance_config (5.13) but for STRATEGY code: the clone is a
    full copy of strategies/{slug}/ -> strategies/{new_slug}/ (strategy .py,
    .pine, -doc.md, origins) so the user can edit the copy's logic. The clone
    is git-tracked and loads via the same dynamic discovery that found the
    source. After a successful copy we also register it in the runtime
    STRATEGIES dict so callers see it without a process restart.

    Args:
        slug: source strategy slug (must exist on disk under strategies/).
        new_slug: target slug; must be a valid slug (alnum/_/-) and not collide.

    Returns the new strategy dir Path.

    Raises:
        ValueError: invalid/colliding slug, or source missing.
        FileExistsError: target already exists.
    """
    import re
    import shutil

    if not re.fullmatch(r"[A-Za-z0-9_-]+", new_slug):
        raise ValueError(f"new_slug must match [A-Za-z0-9_-]+, got {new_slug!r}")
    if new_slug == slug:
        raise ValueError("new_slug must differ from source slug")
    if slug not in STRATEGIES:
        raise ValueError(f"source strategy {slug!r} not found in registry")

    strategies_root = Path(__file__).resolve().parent
    src = strategies_root / slug
    dst = strategies_root / new_slug
    if not src.is_dir():
        raise ValueError(f"source strategy dir missing: {src}")
    if dst.exists():
        raise FileExistsError(f"target already exists: {dst}")

    shutil.copytree(src, dst)

    # Best-effort: reassign an in-code class identity so the clone is
    # distinguishable at runtime. Many strategies expose a `strategy_id`
    # attribute or use it in config logging; rewrite occurrences of the
    # source slug token inside .py files. This is cosmetic — discovery keys
    # on the subdir name, not the in-code id.
    for pf in dst.glob("*.py"):
        if pf.name.startswith("_") or pf.name == "base.py":
            continue
        try:
            text = pf.read_text()
        except Exception:
            continue
        if slug in text:
            pf.write_text(text.replace(slug, new_slug))

    # Register in runtime registry (import the cloned module to get the class).
    try:
        module_name = f"strategies.{new_slug}.strategy"
        # drop any prior cached module so a fresh import is forced
        sys_mod = __import__("sys").modules
        sys_mod.pop(module_name, None)
        mod = importlib.import_module(module_name)
        for _, obj in inspect.getmembers(mod, inspect.isclass):
            if (
                issubclass(obj, BaseStrategy)
                and obj is not BaseStrategy
                and obj.__module__ == module_name
            ):
                STRATEGIES[new_slug] = obj
                break
    except Exception:
        # copy succeeded; registration is best-effort (discovery picks it up
        # on next import / process restart regardless)
        pass

    return dst
