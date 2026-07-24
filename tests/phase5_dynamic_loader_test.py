"""
Track 5.6/5.7/5.3 hard test — dynamic strategy loader + detect_mintick relocation.

Verifies:
  - strategies/registry.py dynamically resolves the translation-test slot from its subdir
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
    # Post legacy-removal: the only seeded slot is translation-test.
    assert "translation-test" in keys, "translation-test missing from registry"

    # resolved from subdir, not a top-level flat file
    cls = get_strategy("translation-test")
    assert cls is not None, "translation-test resolved to None"
    assert cls.__module__ == "strategies.translation-test.strategy", (
        f"translation-test not loaded from subdir: {cls.__module__}"
    )
    # it must be a BaseStrategy subclass (importable + contract-conforming)
    from strategies.base import BaseStrategy
    assert issubclass(cls, BaseStrategy), "translation-test is not a BaseStrategy subclass"

    # Presets are NOT hardcoded post-removal (get_presets returns empty map)
    assert get_presets("translation-test") == {}, "get_presets should be empty post-removal"

    # detect_mintick re-export identity
    assert detect_mintick is core_dm, "detect_mintick not re-exported from core"

    # engines fleet
    assert len(get_default_fleet()) == 2

    # Sanity: no legacy slugs should linger
    for stale in ("strategy_v1", "strategy_v1_3", "strategy_v6_1"):
        assert stale not in keys, f"stale legacy slug still present: {stale}"

    print("PASS: phase5 dynamic loader + detect_mintick relocation (post-removal)")


if __name__ == "__main__":
    test_loader()
