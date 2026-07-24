# strategy_v1

**Class:** `EngineV1Strategy`
**File:** `strategy_v1/v1.py`
**Origin:** PineScript → Python (pynescript translation)

## What it does
Swing-mode variant. Emits `entry_config`; declares exits via `generate_signals()`.

## Parameters
See `EngineV1Strategy.get_parameters()` at runtime. Defaults pre-fill first render;
saved `config.yaml` owns the value after save.

## Fidelity score
- **Status:** TBD — Track 5.9.

## Notes
- `strategy_id` = `strategy_v1`. Legacy `engine_v1` alias resolves via `ALIASES`.
