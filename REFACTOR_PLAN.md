# Strategy Engine Refactor Plan — Pine Fidelity Restoration

> **Goal:** Make the Python execution path match the Pine Script v1.3 exactly.
> Remove all fabricated deviations. Restore dual-mode support (Swing + Scalp).
> Make strategy parameters configurable from the UI.

---

## Part 1: Strategy Layer Refactor (`engine/v1_3.py`)

### 1.1 Restore Dual-Mode Support (Swing + Scalp)

**Current (lines 36-42):** Mode hardcoded to Scalp only.
```python
self.engine_mode = "Scalp"
self.active_activation = 8
self.active_offset = 3
self.allowed_modes = {"Scalp"}
self.allowed_profiles = {(8, 3)}
```

**Pine (lines 36, 217-257):** Mode is user-selectable. Risk profiles are checkboxes.
Pine defaults: `engineMode = 'Swing'`, `enableScalpDefault = true` (10/4).

**Refactor:**
```python
def __init__(self, name="Eve Engine v1.3", engine_mode="Swing",
             risk_profile="Scalp Default (10/4)", **kwargs):
    super().__init__(name)
    self.engine_mode = engine_mode  # "Swing" or "Scalp"
    self.is_swing_mode = engine_mode == "Swing"
    self.is_scalp_mode = engine_mode == "Scalp"

    # Risk profile → trail params (Pine lines 237-257)
    PROFILES = {
        "Swing Sniper (36/12)": (36, 12),
        "Swing Trend (36/18)": (36, 18),
        "Swing Conservative (48/18)": (48, 18),
        "Scalp Default (10/4)": (10, 4),
        "Scalp Aggressive (8/3)": (8, 3),
        "Scalp Conservative (12/5)": (12, 5),
    }
    self.active_activation, self.active_offset = PROFILES.get(
        risk_profile, (36, 12) if self.is_swing_mode else (10, 4)
    )
    self.risk_profile = risk_profile
```

### 1.2 Mode-Aware Indicator Lengths

**Current (lines 47-50):** Hardcoded to Scalp values (4/9/25).
```python
self.ema_fast_len = 4
self.ema_medm_len = 9
self.ema_slow_len = 25
```

**Pine (lines 281-283):** Mode-aware.
```python
ema_fast_use = isSwingMode ? 6 : 4
ema_medm_use = isSwingMode ? 18 : 9
ema_slow_use = isSwingMode ? 50 : 25
```

**Refactor:**
```python
self.ema_fast_len = 6 if self.is_swing_mode else 4
self.ema_medm_len = 18 if self.is_swing_mode else 9
self.ema_slow_len = 50 if self.is_swing_mode else 25
```

### 1.3 Mode-Aware ATR Multiplier Base

**Current (line 56):** `self.atr_mult_base = 1.3` (scalp only).

**Pine (line 117):** `atr_mult_base = isSwingMode ? 1.8 : 1.3`

**Refactor:**
```python
self.atr_mult_base = 1.8 if self.is_swing_mode else 1.3
```

### 1.4 Mode-Aware Momentum Threshold

**Current (line 65):** `self.momentum_thresh = 28` (hardcoded scalp).

**Pine (lines 48, 302-303):** Input default 18, mode override: Swing=18, Scalp=28.
```pine
momentumThresh = input.int(18, ...)
adxDefault = isSwingMode ? 18 : 28
momentumThreshFinal = momentumThresh > 0 ? momentumThresh : adxDefault
```

**Refactor:**
```python
self.momentum_thresh = 18  # Pine input default
# Mode-aware override (Pine line 302)
self.momentum_thresh_mode = 18 if self.is_swing_mode else 28
```

In `generate_signals()`:
```python
momentum_thresh_final = self.momentum_thresh if self.momentum_thresh > 0 else self.momentum_thresh_mode
```

### 1.5 Mode-Aware Pin Bar Ratios

**Current (lines 475-476):** Hardcoded 0.70/0.30 (scalp).

**Pine (lines 314-315):**
```python
pinBarWickRatio = isSwingMode ? 0.66 : 0.70
pinBarBodyRatio = isSwingMode ? 0.34 : 0.30
```

**Refactor:**
```python
pin_bar_wick_ratio = 0.66 if self.is_swing_mode else 0.70
pin_bar_body_ratio = 0.34 if self.is_swing_mode else 0.30
```

### 1.6 Mode-Aware Volume Multiplier

**Current (line 91):** `self.volume_multiplier = 1.3` (scalp only).

**Pine (line 342):** `volumeMultiplier_use = isScalpMode ? 1.3 : 1.0`

**Refactor:**
```python
self.volume_multiplier = 1.3 if self.is_scalp_mode else 1.0
```

### 1.7 Remove `trail_exit_grace_seconds` from exit_config

**Current (line 654):** `"trail_exit_grace_seconds": 90`

**Pine:** No such concept. `strategy.exit()` is active immediately.

**Refactor:** Remove from exit_config dict. Remove grace logic from worker and runner.

### 1.8 Add `get_parameters()` to BaseStrategy

**New in `engine/base.py`:**
```python
class BaseStrategy:
    @classmethod
    def get_parameters(cls) -> list[dict]:
        """Declare configurable parameters for UI rendering."""
        return []

    @classmethod
    def get_default_config(cls) -> dict:
        """Return default parameter values."""
        params = cls.get_parameters()
        return {p["name"]: p["default"] for p in params}
```

**In `engine/v1_3.py`:**
```python
@classmethod
def get_parameters(cls) -> list[dict]:
    return [
        {"name": "engine_mode", "label": "Engine Mode", "type": "select",
         "options": ["Swing", "Scalp"], "default": "Swing", "group": "Configuration"},
        {"name": "risk_profile", "label": "Risk Profile", "type": "select",
         "options": [
             "Swing Sniper (36/12)", "Swing Trend (36/18)", "Swing Conservative (48/18)",
             "Scalp Default (10/4)", "Scalp Aggressive (8/3)", "Scalp Conservative (12/5)"
         ], "default": "Scalp Default (10/4)", "group": "Risk Management"},
        {"name": "risk_per_trade_pct", "label": "Risk % Per Trade", "type": "float",
         "min": 50.0, "max": 100.0, "step": 1.0, "default": 97.0, "group": "Risk Management"},
        {"name": "atr_mult_input", "label": "Stop Loss Base (x ATR)", "type": "float",
         "min": 0.5, "max": 3.0, "step": 0.1, "default": 1.8, "group": "Risk Management"},
        {"name": "atr_mult_guard", "label": "Stop Loss Guard (x ATR)", "type": "float",
         "min": 0.5, "max": 2.0, "step": 0.1, "default": 0.9, "group": "Risk Management"},
        {"name": "growth_target_x", "label": "Hyper-Growth Target (x)", "type": "float",
         "min": 1.1, "step": 0.5, "default": 50.0, "group": "Hyper-Growth Protocol"},
        {"name": "momentum_thresh", "label": "Momentum Threshold (ADX)", "type": "int",
         "min": 10, "max": 40, "default": 18, "group": "Hyper-Growth Protocol"},
        {"name": "use_momentum", "label": "Exploit Momentum Entry?", "type": "bool",
         "default": True, "group": "Hyper-Growth Protocol"},
        {"name": "use_fixed_tp", "label": "Use Fixed Take-Profit?", "type": "bool",
         "default": False, "group": "Scalp Features"},
        {"name": "tp_multiplier", "label": "TP Multiplier (x ATR)", "type": "float",
         "min": 1.0, "max": 5.0, "step": 0.1, "default": 1.5, "group": "Scalp Features"},
        {"name": "use_time_exit", "label": "Use Time-Based Exit?", "type": "bool",
         "default": False, "group": "Scalp Features"},
        {"name": "max_bars_in_trade", "label": "Max Bars In Trade", "type": "int",
         "min": 5, "max": 100, "default": 20, "group": "Scalp Features"},
        {"name": "use_volume_confirm", "label": "Require Volume Confirmation?", "type": "bool",
         "default": False, "group": "Filters"},
        {"name": "volume_lookback", "label": "Volume SMA Length", "type": "int",
         "min": 5, "max": 100, "default": 20, "group": "Filters"},
        {"name": "trade_direction", "label": "Trade Direction", "type": "select",
         "options": ["Both", "Long Only", "Short Only"], "default": "Both", "group": "Filters"},
    ]
```

---

## Part 2: Worker Equity History Fix (`scripts/worker.py`)

### 2.1 Only Append to equity_history on Trade Close (Not Every Tick)

**Current (worker.py lines 296-300):**
```python
if account_value > 0:
    equity_history.append(account_value)
    if len(equity_history) > 500:
        equity_history = equity_history[-500:]
```

**Pine (lines 77-84):** Only on `strategy.closedtrades > lastClosedTrades`.
```python
if strategy.closedtrades > lastClosedTrades:
    closedEquity = strategy.equity - strategy.openprofit
    if not na(closedEquity) and closedEquity > 0:
        array.push(equityCurve, closedEquity)
        if array.size(equityCurve) > MAX_EQUITY_HISTORY:
            array.shift(equityCurve)
    lastClosedTrades := strategy.closedtrades
```

**Refactor:** Remove the per-tick append. Add equity_history.append on trade close:
```python
# After successful close (line ~378, after active_trade = None):
if close_result:
    # ... existing P&L estimation ...
    # Append realized equity to history (matches Pine closedtrades behavior)
    realized_equity = account_value  # current account value after close
    if realized_equity > 0:
        equity_history.append(realized_equity)
        if len(equity_history) > MAX_EQUITY_HISTORY:  # 100, not 500
            equity_history = equity_history[-MAX_EQUITY_HISTORY:]
    active_trade = None
```

Remove the per-tick equity_history append (lines 296-300).

### 2.2 Remove trail_exit_grace_seconds

**Current (worker.py lines 132-133, 145, 152):**
```python
trail_grace = float(ec.get("trail_exit_grace_seconds", 0))
in_grace = trail_grace > 0 and ...
if not in_grace:
    trail_stop = ...
```

**Refactor:** Remove grace check. Trail is active immediately after activation:
```python
if active_trade.get("trail_active"):
    if side == "LONG":
        if bar_high > active_trade.get("best_price", 0):
            active_trade["best_price"] = bar_high
        trail_stop = active_trade["best_price"] - trail_off * mintick
        if bar_low <= trail_stop:
            return "Trailing Stop"
    else:
        if bar_low < active_trade.get("best_price", float("inf")):
            active_trade["best_price"] = bar_low
        trail_stop = active_trade["best_price"] + trail_off * mintick
        if bar_high >= trail_stop:
            return "Trailing Stop"
```

### 2.3 Enforce One-Entry-Per-Bar (Pine `bar_index > lastEntryBar`)

**Current:** Worker re-enters on next poll (3s later) if signal persists.

**Pine (line 362):** `bar_index > lastEntryBar` — one entry per bar.

**Refactor:** Track `last_entry_bar_time`. Only enter if current bar timestamp differs:
```python
# After successful entry (line ~348):
last_entry_bar_time = current_bar_time

# Before entry (line ~320):
if active_trade is None and desired_side:
    if last_entry_bar_time is not None and current_bar_time == last_entry_bar_time:
        pass  # Same bar — Pine prevents re-entry
    else:
        active_trade = "PENDING"
        # ... existing entry logic ...
```

### 2.4 Use Live Mark Price for Trail Instead of Candle H/L

**Current (worker.py line 361-362):**
```python
bar_high = float(df["high"].iloc[-1])
bar_low = float(df["low"].iloc[-1])
```

This uses the *current incomplete candle's* H/L, which changes every poll.

**Better approach:** Use the live mark price from the exchange position:
```python
# Get live mark price from position
mark_price = float(position.get("markPx", 0)) if position else float(df["close"].iloc[-1])

# Use mark_price for trail best_price tracking + trail stop check
# This approximates calc_on_every_tick — each poll sees the current price
```

However, this changes the trailing stop from candle-based to tick-based. This is actually **closer to Pine's `calc_on_every_tick=true`**. The trade-off: we lose the ability to catch wicks (which Pine's tick engine would see), but we avoid the current bug where the candle H/L includes momentary spikes that already reverted.

**Decision:** Use mark price for trail check. Keep candle H/L for stop-loss and take-profit (those are bar-level orders in Pine).

---

## Part 3: Runner Equity History Fix (`instances/runner.py`)

### 3.1 Runner Already Appends on Trade Close (Mostly Correct)

**Current (runner.py lines 278-283):**
```python
if not hasattr(self, "_equity") or self._equity <= 0:
    self._equity = account_value
realized_pnl = float(position.get("unrealizedPnl", 0)) if position else 0.0
self._equity = max(0.0, self._equity + realized_pnl)
self._equity_history.append(self._equity)
```

**Issue:** Uses `unrealizedPnl` from the position *before* close (not actual realized PnL).
Also computes `self._equity` from `account_value` (live balance) + `unrealizedPnl` — this is close but not exact.

**Pine:** `closedEquity = strategy.equity - strategy.openprofit` — equity minus open profit = realized equity.

**Refactor:** Use `account_value` directly after close as the realized equity:
```python
# After close_result confirmed:
realized_equity = hl.get_account_value()  # post-close account value
if realized_equity > 0:
    self._equity_history.append(realized_equity)
    if len(self._equity_history) > self.MAX_EQUITY_HISTORY:  # 100
        self._equity_history = self._equity_history[-self.MAX_EQUITY_HISTORY:]
```

### 3.2 Remove trail_exit_grace_seconds (Same as Worker)

**Current (runner.py lines 602-603, 615, 622):** Same grace logic.

**Refactor:** Remove. Same code change as worker.

### 3.3 Enforce One-Entry-Per-Bar

**Current:** No bar-level entry guard in runner.

**Refactor:** Add `self._last_entry_bar_time` tracking, same as worker.

---

## Part 4: Remove `trail_exit_grace_seconds` from Strategy

**v1_3.py line 654:** Remove from exit_config dict.
```python
# REMOVE this line:
"trail_exit_grace_seconds": 90,
```

---

## Part 5: Strategy Parameter API + UI

### 5.1 API Endpoints

**`GET /api/v2/strategies/{id}/parameters`** — returns parameter schema:
```python
@app.get("/api/v2/strategies/{strategy_id}/parameters")
async def get_strategy_parameters(strategy_id: str, user=Depends(auth_dep)):
    strategy_cls = get_strategy(strategy_id)
    if not strategy_cls:
        raise HTTPException(404)
    return {"parameters": strategy_cls.get_parameters()}
```

**`PUT /api/v2/instances/{slug}/strategy-config`** — saves per-instance overrides:
```python
@app.put("/api/v2/instances/{slug}/strategy-config")
async def update_strategy_config(slug: str, body: dict, user=Depends(auth_dep)):
    inst = db.query(Instance).filter(Instance.slug == slug).first()
    if not inst:
        raise HTTPException(404)
    inst.strategy_config = body  # JSON column on Instance
    db.commit()
    return {"ok": True}
```

### 5.2 Instance Model — Add strategy_config Column

```python
# instances/models.py — add to Instance model:
strategy_config = Column(JSON, default=dict)  # per-instance parameter overrides
```

### 5.3 Runner/Worker — Apply Config When Instantiating Strategy

```python
# runner.py line 80:
config = self.instance.strategy_config or {}
strategy = strategy_class(**config)

# worker.py line 198:
config = state.get("strategy_config", {})
strategy = strategy_cls(state["strategy_id"], **config)
```

### 5.4 Engine Detail Page — Dynamic Settings Panel

**`engine_detail.html`:** Settings modal fetches parameters from API and renders fields dynamically:

```javascript
async function loadStrategyParams() {
    const resp = await fetch(`/api/v2/strategies/${strategyId}/parameters`);
    const { parameters } = await resp.json();
    const container = document.getElementById('strategy-params');
    container.innerHTML = parameters.map(p => renderField(p)).join('');
}

function renderField(p) {
    if (p.type === 'select') {
        return `<label>${p.label}<select name="${p.name}">
            ${p.options.map(o => `<option value="${o}">${o}</option>`).join('')}
        </select></label>`;
    } else if (p.type === 'bool') {
        return `<label><input type="checkbox" name="${p.name}"> ${p.label}</label>`;
    } else {
        return `<label>${p.label}<input type="number" name="${p.name}"
            min="${p.min||''}" max="${p.max||''}" step="${p.step||''}" value="${p.default}"></label>`;
    }
}
```

---

## Part 6: Strategy Studio Flow Improvements

### 6.1 Clone Endpoint
```
POST /api/v2/strategies/{id}/clone → creates new DB row with status="draft"
```

### 6.2 Upload Python Directly
Add tab in `strategy_upload.html`: "Paste Pine" | "Paste Python"
Python tab saves `python_source` directly, `pine_source = null`, `status="active"`.

### 6.3 Backtest from Studio
"Backtest this strategy" button → redirect to `/app/testing/historical?strategy={id}`

### 6.4 Paper Trade from Studio
"Paper Trade" button → creates instance with `dry_run=true`, `strategy_id={id}`

---

## Implementation Order

| Phase | Files | What | Verify |
|-------|-------|------|--------|
| 1 | `engine/base.py` | Add `get_parameters()` + `get_default_config()` | Unit test |
| 2 | `engine/v1_3.py` | Restore dual-mode, mode-aware params, remove grace, add `get_parameters()` | Smoke test |
| 3 | `scripts/worker.py` | Fix equity_history (trade-close only), remove grace, one-entry-per-bar, mark price trail | Live test paper |
| 4 | `instances/runner.py` | Same fixes as worker, apply strategy_config | Backtest + live test |
| 5 | `instances/models.py` | Add `strategy_config` JSON column to Instance | Migration test |
| 6 | `api/instances.py` + `api/strategies.py` | Add parameters + strategy-config endpoints | API test |
| 7 | `app/routes.py` | Pass strategy_config to engine detail, wire parameters | Browser test |
| 8 | `engine_detail.html` | Dynamic settings panel from strategy parameters | Browser test |
| 9 | `strategy_upload.html` | Add Python upload tab | Browser test |
| 10 | `api/strategies.py` | Clone endpoint | API test |