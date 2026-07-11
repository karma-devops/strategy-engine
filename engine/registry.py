"""
Strategy registry for strategy-engine.
"""

from engine.v1_3 import EngineV1_3Strategy
from engine.v1 import EngineV1Strategy


STRATEGIES = {
    "engine_v1_3": EngineV1_3Strategy,
    "engine_v1": EngineV1Strategy,
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
        "leverage": 10,
        "max_position_pct": 0.20,
        "poll_interval_seconds": 30,
    },
    {
        "slug": "engine-2",
        "name": "HYPE Scalp v1.3",
        "token": "HYPE",
        "strategy_id": "engine_v1_3",
        "mode": "Scalp",
        "profile": "aggressive_8_3",
        "timeframe": "15m",
        "leverage": 10,
        "max_position_pct": 0.20,
        "poll_interval_seconds": 30,
    },
    {
        "slug": "engine-3",
        "name": "WIF Scalp v1.3",
        "token": "WIF",
        "strategy_id": "engine_v1_3",
        "mode": "Scalp",
        "profile": "aggressive_8_3",
        "timeframe": "15m",
        "leverage": 10,
        "max_position_pct": 0.15,
        "poll_interval_seconds": 30,
    },
    {
        "slug": "engine-4",
        "name": "AAVE Scalp v1.3",
        "token": "AAVE",
        "strategy_id": "engine_v1_3",
        "mode": "Scalp",
        "profile": "aggressive_8_3",
        "timeframe": "15m",
        "leverage": 10,
        "max_position_pct": 0.15,
        "poll_interval_seconds": 30,
    },
    {
        "slug": "engine-5",
        "name": "kPEPE Swing v1",
        "token": "kPEPE",
        "strategy_id": "engine_v1",
        "mode": "Swing",
        "profile": "sniper_36_12",
        "timeframe": "1h",
        "leverage": 5,
        "max_position_pct": 0.20,
        "poll_interval_seconds": 300,
    },
    {
        "slug": "engine-6",
        "name": "SOL Swing v1",
        "token": "SOL",
        "strategy_id": "engine_v1",
        "mode": "Swing",
        "profile": "sniper_36_12",
        "timeframe": "1h",
        "leverage": 5,
        "max_position_pct": 0.10,
        "poll_interval_seconds": 300,
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
    return {}


def get_default_fleet() -> list:
    """Return the 6-engine default fleet spec."""
    return [dict(p) for p in DEFAULT_FLEET]
