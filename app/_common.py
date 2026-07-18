"""
Common Pure Helpers — No DB Access

Authority: Z1 (route split)

This module contains PURE helper functions used across all routers:
- `_safe_tojson`: JSON serialization with Undefined tolerance (fixes P9 500 bug)
- `_inject_theme`: Reads theme from cookie, validates, returns string
- `_read_source`: Reads file from source directory
- `_instances_by_mode`: Filters instances by live/paper/backtest mode

NO DATABASE ACCESS — these functions are pure (no SessionLocal, no queries).
"""

from jinja2 import Undefined
import json
import os


#=== JSON Utilities ===#
def _safe_tojson(o):
    """Jinja 'tojson' filter that tolerates missing context vars.
    
    Jinja passes jinja2.Undefined for variables absent from render context.
    The previous lambda did json.dumps(o) directly, which raised TypeError
    on Undefined and 500'd any template referencing an undefined var
    (e.g. engine_detail.html -> paper_trades). Here we coerce Undefined to
    None so the page still renders with an empty/fallback value.
    """
    if isinstance(o, Undefined):
        return json.dumps(None)
    try:
        return json.dumps(o)
    except TypeError:
        return json.dumps(str(o))


#=== Theme Helper ===#
def _inject_theme(request):
    """Read theme from cookie, falling back to DB-stored preference.
    
    Args:
        request: FastAPI Request object
        
    Returns:
        str: Theme name ('pulsr', 'hyperfluid', or 'portrait')
    """
    theme = request.cookies.get("pulsr-theme") or "pulsr"
    # Validate
    if theme not in ("pulsr", "hyperfluid", "portrait"):
        theme = "pulsr"
    return theme


#=== File Utilities ===#
def _read_source(path):
    """Read file from source directory.
    
    Args:
        path (str): Relative path from source directory
        
    Returns:
        str: File contents, or None if file not found
    """
    try:
        base = os.path.dirname(os.path.abspath(__file__))
        full_path = os.path.join(base, "..", path)
        with open(full_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


#=== Instance Filter Helpers ===#
def _instances_by_mode(instances, mode):
    """Filter instances by mode (live, paper, backtest).
    
    Args:
        instances: List of Instance query results
        mode (str): 'live', 'paper', or 'backtest'
        
    Returns:
        List[Instance]: Filtered instances
    """
    if mode == "live":
        return [i for i in instances if not i.dry_run]
    elif mode == "paper":
        return [i for i in instances if i.dry_run]
    elif mode == "backtest":
        return []  # Backtest instances are ephemeral, not stored in DB
    else:
        return instances


#=== Export ===#
__all__ = [
    "_safe_tojson",
    "_inject_theme", 
    "_read_source",
    "_instances_by_mode",
]
