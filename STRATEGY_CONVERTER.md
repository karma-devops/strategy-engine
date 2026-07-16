# Strategy Converter Contract

> **Working Prototype** — PULS-R Strategy Engine v1.0
> Date: 2026-07-14
> Status: ACTIVE — all 3 strategies (v1, v1.3, v6.1) comply

## Purpose

This document defines the contract between **strategy engines** (PineScript ports) and **receivers** (worker, runner, backtest). Any new strategy that follows this contract can be dropped into `engine/` and will work with all receivers without modification.

## The Golden Rule

> **Strategy declares. Receiver consumes. No hardcoded strategy-specifics in receivers.**

Receivers (worker.py, runner.py, backtests/runner.py) are universal ports. They read strategy values from the signal result dict. They do NOT import strategy classes, read presets, or hardcode activation/offset/mode values.

---

## Signal Result Contract

Every `generate_signals()` call returns a dict with these top-level keys:

```
{
    "token":        "***",                   # asset symbol
    "signal":       1.0 | -1.0 | 0.0,       # signal strength
    "direction":    "BUY" | "SELL" | "NEUTRAL",  # entry direction
    "metadata":     { ... },                # strategy internal state (display + risk)
    "exit_config":  { ... },                # exit levels (receiver reads these)
}
```

### entry (top-level fields)

The strategy declares WHEN to enter and WHAT direction:

| Field | Type | Values | Receiver Action |
|-------|------|--------|-----------------|
| `direction` | str | `"BUY"` | Open LONG |
| `direction` | str | `"SELL"` | Open SHORT |
| `direction` | str | `"NEUTRAL"` | Stay flat |
| `signal` | float | `1.0` / `-1.0` / `0.0` | Log/display only |

**No `entry_config` dict needed.** Direction + signal are top-level. The receiver decides position sizing, leverage, and execution mechanics — those are NOT strategy concerns.

### metadata (strategy internal state)

Used for display, logging, and risk-sizing fallbacks. Keys vary per strategy. Common fields:

```
{
    "adx":              float,   # ADX indicator value
    "fast_ema":         float,   # Fast EMA value
    "medm_ema":         float,   # Medium EMA value
    "slow_sma":         float,   # Slow SMA value
    "atr":              float,   # ATR value
    "atr_mult_use":     float,   # ATR multiplier for stop loss
    "fan_up_trend":     bool,    # EMA fan alignment (bullish)
    "fan_dn_trend":     bool,    # EMA fan alignment (bearish)
    "bullish_pin_bar":  bool,    # Pin bar pattern
    "bearish_pin_bar":  bool,
    "stop_loss_long":   float,   # Stop loss for long position
    "stop_loss_short":  float,   # Stop loss for short position
    "take_profit_long":  float,  # Take profit for long
    "take_profit_short": float,  # Take profit for short
    "engine_mode":      str,     # "Scalp" | "Trend" | "Swing"
    "is_strategy_cold": bool,    # Warmup period active
    "in_warmup":        bool,    # Still warming up
    "qty_long":         float,   # Pine calcSize quantity (long)
    "qty_short":        float,   # Pine calcSize quantity (short)
    "risk_profile":     str,     # Risk profile name
    "momentum_thresh_final": float,
    "volume_confirmed": bool,
    "use_fixed_tp":     bool,
    "use_time_exit":    bool,
    "time_exit_bars":   int,
    "active_activation": float,
    "active_offset":    float,
    ...
}
```

Receivers should NOT depend on specific metadata keys. Metadata is for display + optional fallbacks only.

### exit_config (receiver contract)

This is the formal contract. Receivers read ONLY from `exit_config` for all exit decisions. If a field is missing, the receiver skips that exit type (`.get()` returns None/0/False).

```
{
    # 1. Stop Loss (price levels)
    "stop_loss_long":     float | None,   # SL price for long positions
    "stop_loss_short":    float | None,   # SL price for short positions

    # 2. Trailing Stop
    "trail_activation":   float,          # Ticks to activate trailing
    "trail_offset":       float,          # Ticks behind best price
    "trail_exit_grace_seconds": float,    # Block trail exit for N seconds after entry (0 = no grace)

    # 3. Take Profit (optional, only if strategy uses fixed TP)
    "take_profit_long":   float | None,
    "take_profit_short":  float | None,

    # 4. Trend Change (EMA cross)
    "fast_ema":           float | None,   # Current fast EMA
    "medm_ema":           float | None,   # Current medium EMA
    # Receiver stores prev bar values, detects cross on bar close

    # 5. Time Exit
    "use_time_exit":      bool,           # Whether time exit is active
    "time_exit_bars":     int | None,     # Max bars in trade before exit

    # Internal (for display/fallback)
    "engine_mode":        str,            # "Scalp" | "Trend" | "Swing"
    "fan_up_trend":       bool,
    "fan_dn_trend":       bool,
}
```

---

## Receiver Exit Evaluation Order

Reivers evaluate exits in this fixed order. First match wins.

```
1. Stop Loss      → ec["stop_loss_long/short"] vs bar high/low
2. Trailing Stop  → ec["trail_activation"] activates, ec["trail_offset"] trails
                    → ec["trail_exit_grace_seconds"] blocks exit for N seconds after entry
3. Take Profit    → ec["take_profit_long/short"] vs bar high/low (if declared)
4. Trend Change   → EMA cross: prev fast vs medm → current fast vs medm
5. Time Exit      → ec["use_time_exit"] && bars_in_trade >= ec["time_exit_bars"]
```

**Removed exits (not in any PineScript):**
- ~~Reversal Signal~~ (fabricated, removed from all receivers)
- ~~Full Fan Alignment~~ (fabricated, removed)
- ~~Signal Reverses~~ (fabricated, removed from backtest)

---

## Receiver Entry Flow

```
1. Strategy returns direction = "BUY" | "SELL" | "NEUTRAL"
2. Receiver: if direction is directional AND no active trade:
   a. Get account value from exchange
   b. Calculate notional = PositionSizer(balance, leverage, max_pos_pct)
   c. Execute market_open(token, side, size_usd, leverage)
   d. Create active_trade dict with entry_price, mintick, best_price
3. If direction is NEUTRAL or already in trade: stay flat
```

**Receiver-owned (NOT strategy-declared):**
- `leverage` — from instance/config
- `max_position_pct` — from instance/config (default 0.97)
- `position_size` — PositionSizer math
- `poll_interval` — from instance/config (default 3s)

**Strategy-owned (declared in result):**
- `direction` — when to enter, what side
- `signal` — signal strength for display

---

## File Map

```
engine/
  base.py          → BaseStrategy abstract class
  v1_3.py          → Eve Engine v1.3 (Scalp) — emits exit_config
  v1.py            → Eve Engine v1 (Swing) — emits exit_config
  v6_1.py          → Engine v6.1 (Trend) — emits exit_config
  registry.py      → STRATEGIES dict + detect_mintick()

receivers/
  scripts/worker.py        → Live trading worker (port 9999)
  instances/runner.py      → PWA fleet runner (dev server)
  backtests/runner.py      → Historical backtest engine

execution/
  core/exchange.py         → HyperLiquidClient (market_open, market_close)
  core/market_data.py      → HyperLiquidMarketData (get_candles, get_position)
  core/position_sizer.py   → PositionSizer (notional_from_free_balance)
```

---

## How to Port a New Strategy

1. Create `engine/vN.py` extending `BaseStrategy`
2. Implement `generate_signals(df, symbol, equity_history)` → return dict with:
   - `direction`: "BUY" | "SELL" | "NEUTRAL"
   - `signal`: float
   - `metadata`: dict of internal state
   - `exit_config`: dict with all exit params your strategy uses
3. Register in `engine/registry.py` STRATEGIES dict
4. **Do NOT touch any receiver file.** If the receiver can't handle your exit, you're missing a field in `exit_config`.

### exit_config checklist for new strategies:

- [ ] `stop_loss_long` / `stop_loss_short` — price levels (or None if no SL)
- [ ] `trail_activation` — ticks to activate (0 if no trailing)
- [ ] `trail_offset` — ticks behind best price (0 if no trailing)
- [ ] `trail_exit_grace_seconds` — seconds to block trail exit after entry (0 for no grace)
- [ ] `take_profit_long` / `take_profit_short` — price levels (or None if no TP)
- [ ] `fast_ema` / `medm_ema` — current EMA values for trend change detection (or None)
- [ ] `use_time_exit` — bool
- [ ] `time_exit_bars` — int or None

If your strategy has a new exit type not covered above, add the field to `exit_config` and update the receiver's `evaluate_exit()` function to read it. The receiver change should be generic (read from `ec.get()`), not strategy-specific.

---

## Mintick Resolution

`detect_mintick(token=, df=)` in `engine/registry.py`:
1. HL API `metaAndAssetCtxs` → `markPx` string precision (authoritative)
2. Fallback: L2 orderbook price precision
3. Fallback: candle close price decimal count
4. Fallback: 0.00001

Mintick is stored on `active_trade["mintick"]` at entry time. Used by trailing stop tick calculations.

---

## Bars-in-Trade Tracking

Reivers track bars in trade differently:
- **Live (worker/runner):** `elapsed_minutes / timeframe_minutes` (time-based, no OHLC dependency)
- **Backtest:** `i - entry_bar` (bar index based)

Both feed into `bars_in_trade` which is compared against `exit_config["time_exit_bars"]`.

---

## EMA Cross Detection (Trend Change)

Reivers store `prev_fast_ema` and `prev_medm_ema` from the previous bar's `exit_config`. On each new bar:
- If `prev_fast >= prev_medm` and `curr_fast < curr_medm` → crossunder → close LONG
- If `prev_fast <= prev_medm` and `curr_fast > curr_medm` → crossover → close SHORT

EMA values are only updated on bar close (not every poll). This matches PineScript's bar-by-bar evaluation.

---

*This document is the canonical contract. When in doubt, check here. When adding new exit types, update this document first, then update receivers, then update strategies.*