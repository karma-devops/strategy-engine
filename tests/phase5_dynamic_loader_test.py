"""Track 5.6/5.7/5.3 hard test — dynamic strategy loader + detect_mintick relocation.

Verifies:
  - strategies/registry.py dynamically resolves all built-ins from subdirs
  - aliases still resolve
  - detect_mintick re-exported from core/ works
  - engines/registry (fleet) still imports
Run: venv/bin/python3 tests/phase5_dynamic_loader_test.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategies.registry import (
    STRATEGIES,
    list_strategies,
    get_strategy,
    get_presets,
    detect_mintick,
)
from core.detect_mintick import detect_mintick as core_dm
from engines.registry import get_default_fleet


def test_loader():
    keys = list_strategies()
    assert "strategy_v1_3" in keys, "strategy_v1_3 missing"
    assert "strategy_v1" in keys, "strategy_v1 missing"
    assert "strategy_v6_1" in keys, "strategy_v6_1 missing"
    # resolved from subdirs, not top-level flat files
    for slug in ("strategy_v1_3", "strategy_v1", "strategy_v6_1"):
        cls = get_strategy(slug)
        assert cls is not None, f"{slug} resolved to None"
        assert cls.__module__ == f"strategies.{slug}.{slug.split('_')[-1]}" or cls.__module__.startswith(
            f"strategies.{slug}."
        ), f"{slug} not loaded from subdir: {cls.__module__}"
    # alias
    assert get_strategy("engine_v1_3") is get_strategy("strategy_v1_3"), "alias broken"
    # presets
    assert get_presets("strategy_v1_3")["default"]["mode"] == "Scalp"
    # detect_mintick re-export identity
    assert detect_mintick is core_dm, "detect_mintick not re-exported from core"
    # engines fleet
    assert len(get_default_fleet()) == 2
    print("PASS: phase5 dynamic loader + detect_mintick relocation")


if __name__ == "__main__":
    test_loader()
