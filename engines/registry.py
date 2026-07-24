"""Engine registry — saved engine DEFINITIONS (the user-facing var/param layer).

Distinct from:
  - strategies/registry.py  -> logic catalog (strategy classes).
  - instances/manager.py    -> deployed runs (engine def + live config).

Seeded with the default fleet (migrated from strategies/registry.DEFAULT_FLEET,
Track 5.2, 2026-07-24). New engine defs are added by cloning/editing via UI/API
and persist as instances/{slug}/config.yaml (Track 5.11).
"""
from copy import deepcopy
from typing import Optional


# Seed engine definitions — the "default fleet".
# Each def binds a strategy_id to default user-facing vars/params.
ENGINE_DEFS = [
    {
        "slug": "engine-1",
        "name": "FARTCOIN Scalp v1.3",
        "token": "FARTCOIN",
        "strategy_id": "strategy_v1_3",
        "mode": "Scalp",
        "profile": "aggressive_8_3",
        "timeframe": "15m",
        "leverage": 1,
        "max_position_pct": 0.97,
        "poll_interval_seconds": 3,
    },
    {
        "slug": "engine-2",
        "name": "HYPE Paper v1.3",
        "token": "HYPE",
        "strategy_id": "strategy_v1_3",
        "mode": "Scalp",
        "profile": "aggressive_8_3",
        "timeframe": "15m",
        "leverage": 5,
        "max_position_pct": 0.97,
        "poll_interval_seconds": 3,
    },
]


def get_engine_defs() -> list:
    """Return a deep copy of all saved engine definitions."""
    return [deepcopy(d) for d in ENGINE_DEFS]


def get_engine_def(slug: str) -> Optional[dict]:
    """Return a named engine def by slug, or None."""
    for d in ENGINE_DEFS:
        if d["slug"] == slug:
            return deepcopy(d)
    return None


def get_default_fleet() -> list:
    """Back-compat: return the seed fleet spec used to bootstrap instances."""
    return get_engine_defs()
