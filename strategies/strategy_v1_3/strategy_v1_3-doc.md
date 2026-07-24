# strategy_v1_3

**Class:** `EngineV1_3Strategy`
**File:** `strategy_v1_3/v1_3.py`
**Origin:** PineScript → Python (pynescript translation, see `strategies/strategy_v1_3/*.pine` once exported)

## What it does
Scalp-mode EMA-fan strategy. Emits `entry_config` (universal trigger contract) consumed
neutrally by `instances/runner.py`. Declares exit params via `generate_signals()`.

## Parameters (keys it owns → populate engine settings panel)
See `EngineV1_3Strategy.get_parameters()` at runtime. Defaults pre-fill the input box on
first render; the saved `config.yaml` owns the value after save.

## Fidelity score (translated python vs origin pine)
- **Status:** TBD — to be produced by Track 5.9 fidelity mechanism (pynescript round-trip / AST diff).
- **Method:** not yet chosen.

## Notes
- `strategy_id` in the registry = `strategy_v1_3` (canonical). Legacy `engine_v1_3` alias
  resolves via `ALIASES` for existing DB rows.
