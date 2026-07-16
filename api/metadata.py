"""
Metadata API routes — token info, leverage limits, mintick, fees, system stats.
"""

import time
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from api.ratelimit import limiter, READ_LIMIT
from core.market_data import market_data
from instances.models import get_db, Instance, Trade
from config import config

router = APIRouter()

_start_time = time.time()


@router.get("/metadata")
@limiter.limit(READ_LIMIT)
def get_metadata(request: Request, token: str = None, query: str = None):
    """Return HyperLiquid universe metadata.

    If `token` is provided, return info for that token only.
    If `query` is provided, return tokens whose name starts with the query (case-insensitive).
    Otherwise return the full universe.
    """
    meta = market_data.get_meta()
    if not meta:
        return {"ok": True, "tokens": [], "count": 0}

    if token:
        info = meta.get(token, meta.get(token.upper()))
        if not info:
            return {"ok": False, "message": f"Token {token} not found"}
        return {"ok": True, "token": token.upper(), "info": info}

    if query:
        q = query.upper()
        matches = {k: v for k, v in meta.items() if k.startswith(q)}
        return {
            "ok": True,
            "tokens": list(matches.keys()),
            "count": len(matches),
            "results": [{"name": k, **v} for k, v in matches.items()],
        }

    return {
        "ok": True,
        "tokens": list(meta.keys()),
        "count": len(meta),
    }


@router.get("/metadata/{token}")
@limiter.limit(READ_LIMIT)
def get_token_metadata(request: Request, token: str):
    """Return metadata for a specific token."""
    meta = market_data.get_meta()
    if not meta:
        return {"ok": False, "message": "Metadata unavailable"}

    info = meta.get(token, meta.get(token.upper()))
    if not info:
        return {"ok": False, "message": f"Token {token} not found"}

    return {"ok": True, "token": token.upper(), "info": info}


@router.get("/stats")
@limiter.limit(READ_LIMIT)
def get_stats(request: Request, db: Session = Depends(get_db)):
    """Return system stats for the Settings page."""
    uptime_seconds = int(time.time() - _start_time)
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    uptime_str = f"{hours}h {minutes}m" if hours else f"{minutes}m {seconds}s"

    instances = db.query(Instance).all()
    running = [i for i in instances if i.status == "running"]
    trades = db.query(Trade).all()
    total_pnl = sum(t.pnl_usd for t in trades) if trades else 0.0

    return {
        "ok": True,
        "uptime": uptime_str,
        "version": "0.095",
        "dry_run": config.DRY_RUN,
        "running_instances": len(running),
        "total_instances": len(instances),
        "total_trades": len(trades),
        "total_pnl": total_pnl,
    }


@router.get("/tokens")
@limiter.limit(READ_LIMIT)
def get_tokens(request: Request, query: str = None):
    """Return all valid USDC perpetual tokens from HyperLiquid.

    Fetches universe metadata and spot+perp info from HL API.
    Only returns tokens that have a valid USDC perp market.
    Each token includes: name, szDecimals, markPx, dayNtlVlm, funding, openInterest, leverage.
    """
    # Get universe metadata (szDecimals per token)
    meta = market_data.get_meta()
    if not meta:
        return {"ok": False, "message": "Failed to fetch metadata from HyperLiquid", "tokens": [], "count": 0}

    # Get all asset contexts (mark price, volume, funding, OI)
    try:
        payload = {"type": "metaAndAssetCtxs"}
        data = market_data._post(payload)
        if not data or not isinstance(data, list) or len(data) < 2:
            return {"ok": False, "message": f"Failed to fetch asset contexts: data={type(data).__name__}", "tokens": [], "count": 0}
        # HL returns [meta_dict, asset_contexts_list]
        meta_dict = data[0] if isinstance(data[0], dict) else {}
        universe = meta_dict.get("universe", [])
        asset_ctxs = data[1] if isinstance(data[1], list) else []
    except Exception as e:
        return {"ok": False, "message": f"Exception fetching asset contexts: {e}", "tokens": [], "count": 0}

    # Build token list with rich data
    tokens = []
    for i, coin in enumerate(universe):
        name = coin.get("name", "")
        sz_decimals = coin.get("szDecimals", 0)
        ctx = asset_ctxs[i] if i < len(asset_ctxs) else {}
        mark_px = float(ctx.get("markPx", 0)) if ctx.get("markPx") else None
        day_ntl_vlm = float(ctx.get("dayNtlVlm", 0)) if ctx.get("dayNtlVlm") else None
        funding = float(ctx.get("funding", 0)) if ctx.get("funding") else None
        open_interest = float(ctx.get("openInterest", 0)) if ctx.get("openInterest") else None
        leverage = coin.get("maxLeverage", None)

        token_data = {
            "name": name,
            "szDecimals": sz_decimals,
            "markPx": mark_px,
            "dayNtlVlm": day_ntl_vlm,
            "funding": funding,
            "openInterest": open_interest,
            "maxLeverage": leverage,
            "isDelisted": coin.get("isDelisted", False),
        }
        # Filter out delisted tokens and tokens with zero volume
        if coin.get("isDelisted"):
            continue
        if day_ntl_vlm is not None and day_ntl_vlm > 0:
            tokens.append(token_data)

    # Sort by volume descending (most traded first)
    tokens.sort(key=lambda t: t.get("dayNtlVlm") or 0, reverse=True)

    # Filter by query if provided
    if query:
        q = query.upper()
        tokens = [t for t in tokens if t["name"].startswith(q)]

    return {
        "ok": True,
        "count": len(tokens),
        "tokens": tokens,
    }