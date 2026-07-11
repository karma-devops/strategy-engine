"""
Strategy registry for strategy-engine.
"""

from engine.v1_3 import EngineV1_3Strategy
from engine.v1 import EngineV1Strategy
from engine.v6_1 import EngineV6_1Strategy


STRATEGIES = {
    "engine_v1_3": EngineV1_3Strategy,
    "engine_v1": EngineV1Strategy,
    "engine_v6_1": EngineV6_1Strategy,
}


DEFAULT_FLEET = [
    {
        "slug": "engine-1",
        "name": "FARTCOIN Scalp v1.3",
        "token": "FARTCOIN",
        "strategy_id": "engine_v1_3",
        "mode": "Scalp",
        "profile": "aggressive_8_3",
        "timeframe": "15m",
        "leverage": 1,
        "max_position_pct": 0.97,
        "poll_interval_seconds": 30,
    },
]


def list_strategies() -> list:
    return list(STRATEGIES.keys())


def get_strategy(strategy_id: str):
    return STRATEGIES.get(strategy_id)


def get_presets(strategy_id: str) -> dict:
    if strategy_id == "engine_v1_3":
        return {
            "default": {
                "mode": "Scalp",
                "profile": "aggressive_8_3",
                "timeframe": "15m",
                "activation": 8,
                "offset": 3,
            }
        }
    if strategy_id == "engine_v1":
        return {
            "sniper_36_12": {
                "mode": "Swing",
                "profile": "sniper_36_12",
                "timeframe": "1h",
                "activation": 36,
                "offset": 12,
            }
        }
    if strategy_id == "engine_v6_1":
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


def get_default_fleet() -> list:
    """Return the default fleet spec (engine-1 only)."""
    return [dict(p) for p in DEFAULT_FLEET]
