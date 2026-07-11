"""
API routes for positions.
"""

from fastapi import APIRouter, Request

from api.ratelimit import limiter, READ_LIMIT
from instances.manager import manager
from core.exchange import hl_client

router = APIRouter()


@router.get("/instances/{instance_id}/position")
@limiter.limit(READ_LIMIT)
def get_position(request: Request, instance_id: str):
    runner = manager.get_runner(instance_id)
    if not runner:
        return {"ok": False, "message": "Instance not running"}
    pos = runner._hl.get_position(runner.instance.token)
    if not pos:
        return {"ok": True, "position": None}
    return {
        "ok": True,
        "position": {
            "coin": pos.get("coin"),
            "szi": float(pos.get("szi", 0)),
            "entryPx": float(pos.get("entryPx", 0)),
            "markPx": float(pos.get("markPx", 0)) if "markPx" in pos else None,
            "unrealizedPnl": float(pos.get("unrealizedPnl", 0)),
            "returnOnEquity": float(pos.get("returnOnEquity", 0)),
            "leverage": pos.get("leverage", {}).get("value") if isinstance(pos.get("leverage"), dict) else None,
        },
    }


@router.get("/positions")
@limiter.limit(READ_LIMIT)
def get_all_positions(request: Request):
    result = {}
    for runner in manager.list_runners().values():
        pos = runner._hl.get_position(runner.instance.token)
        if pos:
            result[runner.instance.token] = {
                "slug": runner.id,
                "coin": pos.get("coin"),
                "szi": float(pos.get("szi", 0)),
                "entryPx": float(pos.get("entryPx", 0)),
            }
    return {"ok": True, "positions": result}
