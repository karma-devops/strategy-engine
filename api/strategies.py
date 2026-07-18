"""
Strategy metadata API.
"""

import re
from fastapi import APIRouter, Request

from api.ratelimit import limiter, READ_LIMIT, WRITE_LIMIT
from engine.registry import list_strategies, get_presets, get_default_fleet, get_strategy

router = APIRouter()


@router.get("/strategies")
@limiter.limit(READ_LIMIT)
def list_strategies_endpoint(request: Request):
    return {"ok": True, "strategies": list_strategies()}


@router.get("/strategies/{strategy_id}/parameters")
@limiter.limit(READ_LIMIT)
def get_strategy_parameters(request: Request, strategy_id: str):
    """Return parameter schema for UI rendering (Pine input.* equivalent)."""
    strategy_cls = get_strategy(strategy_id)
    if not strategy_cls:
        return {"ok": False, "error": f"Unknown strategy: {strategy_id}"}, 404
    return {
        "ok": True,
        "strategy_id": strategy_id,
        "parameters": strategy_cls.get_parameters(),
        "defaults": strategy_cls.get_default_config(),
    }


@router.get("/strategies/{strategy_id}/presets")
@limiter.limit(READ_LIMIT)
def get_presets_endpoint(request: Request, strategy_id: str):
    return {"ok": True, "strategy_id": strategy_id, "presets": get_presets(strategy_id)}


@router.get("/presets/fleet")
@limiter.limit(READ_LIMIT)
def get_fleet_presets(request: Request):
    return {"ok": True, "fleet": get_default_fleet()}


@router.post("/strategies/{strategy_id}/clone")
@limiter.limit(WRITE_LIMIT)
async def clone_strategy(request: Request, strategy_id: str):
    """Clone a strategy (built-in or uploaded). Creates a new Strategy row with
    parent_strategy_id linking back and auto-incremented version.
    Body: {"name": "My Custom Strategy", "description": "optional"}
    """
    import json
    from instances.models import engine as db_engine, Strategy
    from sqlalchemy.orm import Session

    body = await request.json()

    name = body.get("name", f"{strategy_id}-clone")
    description = body.get("description", "")

    # Slugify name for strategy_id
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    if not slug:
        slug = "cloned-strategy"

    with Session(db_engine) as db:
        # Check if source is a built-in strategy
        strategy_cls = get_strategy(strategy_id)

        if strategy_cls:
            # Built-in strategy: copy source code from registry
            import inspect
            try:
                pine_source = f"# Auto-cloned from built-in {strategy_id}\n# Original: {strategy_id}"
                python_source = inspect.getsource(strategy_cls)
            except Exception:
                pine_source = f"# Cloned from {strategy_id}"
                python_source = None

            # Check for existing clones to determine version
            existing = db.query(Strategy).filter(
                Strategy.parent_strategy_id == strategy_id
            ).order_by(Strategy.version.desc()).first()

            version = "1.0"
            if existing:
                try:
                    major, minor = existing.version.split('.')
                    version = f"{major}.{int(minor) + 1}"
                except Exception:
                    version = "1.1"

            new_id = f"{strategy_id}-{slug}-v{version}"

            # Ensure unique
            if db.query(Strategy).filter(Strategy.strategy_id == new_id).first():
                import uuid
                new_id = f"{strategy_id}-{slug}-v{version}-{uuid.uuid4().hex[:6]}"

            strat = Strategy(
                name=name,
                strategy_id=new_id,
                pine_source=pine_source,
                python_source=python_source,
                documentation=description,
                status="pending",
                parameters=strategy_cls.get_default_config(),
                parent_strategy_id=strategy_id,
                version=version,
            )
        else:
            # Uploaded strategy: copy from DB
            parent = db.query(Strategy).filter(Strategy.strategy_id == strategy_id).first()
            if not parent:
                return {"ok": False, "error": f"Strategy not found: {strategy_id}"}, 404

            existing = db.query(Strategy).filter(
                Strategy.parent_strategy_id == strategy_id
            ).order_by(Strategy.version.desc()).first()

            version = "1.0"
            if existing:
                try:
                    major, minor = existing.version.split('.')
                    version = f"{major}.{int(minor) + 1}"
                except Exception:
                    version = "1.1"

            new_id = f"{strategy_id}-{slug}-v{version}"
            if db.query(Strategy).filter(Strategy.strategy_id == new_id).first():
                import uuid
                new_id = f"{strategy_id}-{slug}-v{version}-{uuid.uuid4().hex[:6]}"

            strat = Strategy(
                name=name,
                strategy_id=new_id,
                pine_source=parent.pine_source,
                python_source=parent.python_source,
                documentation=description or parent.documentation,
                status="pending",
                parameters=parent.parameters or {},
                parent_strategy_id=strategy_id,
                version=version,
            )

        db.add(strat)
        db.commit()
        db.refresh(strat)

    return {
        "ok": True,
        "strategy_id": strat.strategy_id,
        "name": strat.name,
        "parent_strategy_id": strat.parent_strategy_id,
        "version": strat.version,
        "status": strat.status,
    }


@router.post("/strategies/{strategy_id}/activate")
@limiter.limit(WRITE_LIMIT)
def activate_strategy(request: Request, strategy_id: str):
    """Activate an uploaded/cloned strategy. Validates Python source compiles
    and has required methods, then registers in runtime STRATEGIES dict."""
    import json
    from instances.models import engine as db_engine, Strategy
    from engine.registry import register_uploaded_strategy
    from sqlalchemy.orm import Session

    with Session(db_engine) as db:
        strat = db.query(Strategy).filter(Strategy.strategy_id == strategy_id).first()
        if not strat:
            return {"ok": False, "error": f"Strategy not found: {strategy_id}"}, 404

        if not strat.python_source:
            return {"ok": False, "error": "No Python source to activate"}, 400

        # Validate: compiles
        try:
            compile(strat.python_source, f"<{strategy_id}>", "exec")
        except SyntaxError as e:
            return {"ok": False, "error": f"Syntax error: {e}"}, 400

        # Validate: has BaseStrategy subclass with generate_signals and get_parameters
        namespace = {"__builtins__": __builtins__}
        # Pre-load required base classes into namespace
        from engine.base import BaseStrategy
        from engine.registry import detect_mintick
        import pandas as pd
        import numpy as np
        namespace["BaseStrategy"] = BaseStrategy
        namespace["detect_mintick"] = detect_mintick
        namespace["pd"] = pd
        namespace["np"] = np
        try:
            exec(strat.python_source, namespace)
        except Exception as e:
            return {"ok": False, "error": f"Exec error: {e}"}, 400

        # Find the strategy class
        from engine.base import BaseStrategy
        strategy_cls = None
        for obj in namespace.values():
            if isinstance(obj, type) and issubclass(obj, BaseStrategy) and obj is not BaseStrategy:
                strategy_cls = obj
                break

        if not strategy_cls:
            return {"ok": False, "error": "No BaseStrategy subclass found"}, 400

        if not hasattr(strategy_cls, 'generate_signals') or not callable(getattr(strategy_cls, 'generate_signals')):
            return {"ok": False, "error": "Missing generate_signals method"}, 400

        # Register in runtime
        register_uploaded_strategy(strategy_id, strategy_cls)

        # Update status
        strat.status = "active"
        db.commit()

    return {"ok": True, "strategy_id": strategy_id, "status": "active"}