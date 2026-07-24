# strategy_v6_1

**Class:** `EngineV6_1Strategy`
**File:** `strategy_v6_1/v6_1.py`
**Origin:** PineScript → Python (pynescript translation)

## What it does
Scalp-mode variant with manual profile default. Emits `entry_config`; declares exits
via `generate_signals()`.

## Parameters
See `EngineV6_1Strategy.get_parameters()` at runtime. Defaults pre-fill first render;
saved `config.yaml` owns the value after save.

## Fidelity score
- **Status:** TBD — Track 5.9.

## Notes
- `strategy_id` = `strategy_v6_1`. Legacy `engine_v6_1` alias resolves via `ALIASES`.
