"""Track 5.8 hard test — pynescript install + core/translate helper.

Verifies:
  - pynescript imports in venv (installed 0.3.0)
  - pynescript.ast.parse parses Pine v5
  - core/translate.parse_pine + pine_to_struct extract indicators/inputs/functions
Run: venv/bin/python3 tests/phase5_pynescript_test.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pynescript
from core.translate import parse_pine, pine_to_struct


def test_pynescript():
    # pynescript 0.3.0 top-level module has no __version__ (it lives in __about__);
    # the real gate is that it imports and ast.parse works on Pine v5.
    assert hasattr(pynescript, "ast"), "pynescript.ast missing"
    from pynescript.__about__ import __version__ as pv
    assert pv == "0.3.0", pv
    pine = (
        "//@version=5\n"
        'indicator("My Strat", overlay=true)\n'
        'len1 = input.int(20, "Length")\n'
        "ema1 = ta.ema(close, len1)\n"
        "plot(ema1)\n"
        "f(x) => x * 2\n"
    )
    ast = parse_pine(pine)
    assert type(ast).__name__ == "Script"
    s = pine_to_struct(pine)
    assert s["indicators"] == ["indicator"], s["indicators"]
    assert any(i["kind"] == "int" and i["name"] == "len1" for i in s["inputs"]), s["inputs"]
    assert "f" in s["functions"]
    print("PASS: phase5 pynescript 0.3.0 + core/translate helper")


if __name__ == "__main__":
    test_pynescript()
