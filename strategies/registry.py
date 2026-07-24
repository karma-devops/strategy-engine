"""
Strategy registry for strategy-engine.

TERMINOLOGY (keep these distinct):
  - STRATEGY  = the trading logic/signal class (e.g. v1.3, v1, v6.1). Lives in engine/*.py.
  - ENGINE    = a running Instance that executes a Strategy against HyperLiquid
                (see instances/runner.py). An Instance has a strategy_id.

Naming:
  - Canonical registry keys use the "strategy_*" namespace (e.g. "strategy_v1_3").
  - Legacy "engine_*" keys (e.g. "engine_v1_3") are kept ONLY as backward-compat
    ALIASES so existing Instances whose strategy_id was seeded as "engine_v1_3"
    continue to resolve without a DB migration. ALIASES is consulted inside
    get_strategy() / get_presets() — the STRATEGIES dict itself contains ONLY
    canonical "strategy_*" keys, so iteration and listing never produce duplicates.
"""

from engine.v1_3 import EngineV1_3Strategy
from engine.v1 import EngineV1Strategy
from engine.v6_1 import EngineV6_1Strategy


# Canonical strategy registry — "strategy_*" keys only.
STRATEGIES = {
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


DEFAULT_FLEET = [
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


def get_default_fleet() -> list:
    """Return the default fleet spec (engine-1 only)."""
    return [dict(p) for p in DEFAULT_FLEET]


def register_uploaded_strategy(strategy_id: str, strategy_cls) -> None:
    """Register an uploaded/cloned strategy in the runtime registry."""
    STRATEGIES[strategy_id] = strategy_cls


def unregister_uploaded_strategy(strategy_id: str) -> None:
    """Remove an uploaded/cloned strategy from the runtime registry."""
    canonical = _resolve_strategy_id(strategy_id)
    if canonical in STRATEGIES and canonical not in ("strategy_v1_3", "strategy_v1", "strategy_v6_1"):
        del STRATEGIES[canonical]


def detect_mintick(df=None, token: str = None) -> float:
    """
    Detect the minimum price tick (syminfo.mintick equivalent) from HL API.
    Uses the markPx string precision from metaAndAssetCtxs, which is the
    authoritative source of HL's price tick size.

    Falls back to L2 orderbook granularity, then candle data, then 0.00001.

    Do NOT use szDecimals - that's quantity decimals, not price tick size.
    """
    import requests

    # Method 1: markPx decimal precision from metaAndAssetCtxs (authoritative)
    if token:
        try:
            resp = requests.post(
                "https://api.hyperliquid.xyz/info",
                headers={"Content-Type": "application/json"},
                json={"type": "metaAndAssetCtxs"},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                meta = data[0] if isinstance(data, list) and len(data) > 0 else {}
                ctxs = data[1] if isinstance(data, list) and len(data) > 1 else []
                for m, c in zip(meta.get("universe", []), ctxs):
                    if m.get("name") == token:
                        mark_px = c.get("markPx", "")
                        if "." in mark_px:
                            dec_places = len(mark_px.split(".")[1])
                        else:
                            dec_places = 0
                        return 10 ** (-dec_places)
        except Exception:
            pass

    # Method 2: L2 orderbook granularity (fallback)
    if token:
        try:
            resp = requests.post(
                "https://api.hyperliquid.xyz/info",
                headers={"Content-Type": "application/json"},
                json={"type": "l2Book", "coin": token},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                levels = data.get("levels", [])
                if levels and levels[0]:
                    bids = [float(l["px"]) for l in levels[0][:10]]
                    diffs = [abs(bids[i + 1] - bids[i]) for i in range(len(bids) - 1)]
                    pos_diffs = [d for d in diffs if d > 0]
                    if pos_diffs:
                        return float(min(pos_diffs))
        except Exception:
            pass

    # Method 3: candle data detection (last resort fallback)
    if df is not None:
        try:
            all_prices = set()
            for col in ("close", "open", "high", "low"):
                if col in df.columns:
                    all_prices.update(df[col].dropna().unique())
            sorted_prices = sorted(all_prices)
            if len(sorted_prices) >= 2:
                diffs = [sorted_prices[i + 1] - sorted_prices[i] for i in range(len(sorted_prices) - 1)]
                pos_diffs = [d for d in diffs if d > 0]
                if pos_diffs:
                    return float(min(pos_diffs))
        except Exception:
            pass

    return 0.00001
