"""
Asset testing pool stub for strategy-engine.
Assets can be promoted/failed after backtest + forward-test validation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from instances.models import Instance, Backtest


POOL_ASSETS = [
    {"token": "BONK", "timeframes": ["15m", "1h"], "status": "testing"},
    {"token": "POPCAT", "timeframes": ["15m"], "status": "ready"},
    {"token": "MOG", "timeframes": ["1h"], "status": "testing"},
    {"token": "BRETT", "timeframes": ["15m"], "status": "failed"},
]


def list_pool(db: Session) -> list[dict[str, Any]]:
    """Return testing pool assets with latest backtest summary if any."""
    results = []
    for asset in POOL_ASSETS:
        bt = (
            db.query(Backtest)
            .filter(Backtest.token == asset["token"])
            .order_by(Backtest.created_at.desc())
            .first()
        )
        results.append({
            **asset,
            "last_backtest": {
                "id": bt.id,
                "return_pct": bt.total_return_pct,
                "total_trades": bt.total_trades,
                "status": bt.status,
            } if bt else None,
        })
    return results


def promote_asset(token: str) -> dict[str, Any]:
    # BUG #13: no-op by design — pool assets are not persisted to DB.
    # This only signals the operator; status is not stored.
    return {
        "ok": True,
        "persisted": False,
        "message": f"Asset {token} promoted to production candidate. Operator must create instance manually.",
    }


def fail_asset(token: str, reason: str = "") -> dict[str, Any]:
    # BUG #13: no-op by design — pool assets are not persisted to DB.
    return {
        "ok": True,
        "persisted": False,
        "message": f"Asset {token} marked failed. Reason: {reason or 'No reason provided.'}",
    }
