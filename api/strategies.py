"""
Strategy metadata API.
"""

from fastapi import APIRouter, Request

from api.ratelimit import limiter, READ_LIMIT
from engine.registry import list_strategies, get_presets, get_default_fleet

router = APIRouter()


@router.get("/strategies")
@limiter.limit(READ_LIMIT)
def list_strategies_endpoint(request: Request):
    return {"ok": True, "strategies": list_strategies()}


@router.get("/strategies/{strategy_id}/presets")
@limiter.limit(READ_LIMIT)
def get_presets_endpoint(request: Request, strategy_id: str):
    return {"ok": True, "strategy_id": strategy_id, "presets": get_presets(strategy_id)}


@router.get("/presets/fleet")
@limiter.limit(READ_LIMIT)
def get_fleet_presets(request: Request):
    return {"ok": True, "fleet": get_default_fleet()}
