"""detect_mintick — strategy support helper (moved from strategies/registry.py, Track 5.7).

Computes the minimum price tick for a token. Not registry logic — lives in core/.
"""
import requests


def detect_mintick(df=None, token: str = None) -> float:
    """Return the minimum price increment (tick size) for a token.

    Detects the minimum price tick (syminfo.mintick equivalent) from HL API.
    Uses the markPx string precision from metaAndAssetCtxs, which is the
    authoritative source of HL's price tick size.

    Falls back to L2 orderbook granularity, then candle data, then 0.00001.

    Do NOT use szDecimals - that's quantity decimals, not price tick size.
    """
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
            import pandas as pd
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
