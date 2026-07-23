#!/usr/bin/env python3
"""
PULS·R Live Strategy Worker — standalone MVP tester.
Port 9999. Basic auth operator:operator. Live only.
"""
import os, sys, json, time, threading, asyncio, secrets
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, Request, Depends, HTTPException, Response
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from core.exchange import HyperLiquidClient
from core.market_data import HyperLiquidMarketData
from core.position_sizer import PositionSizer
from engine.registry import STRATEGIES

# ── Config ──
PORT = int(os.getenv("WORKER_PORT", "9999"))
USERNAME = os.getenv("DASHBOARD_USERNAME", "operator")
PASSWORD = os.getenv("DASHBOARD_PASSWORD", "operator")
os.environ["DRY_RUN"] = "false"  # Worker is always live — no dry run

# ── State ──
state = {
    "token": "WIF",
    "timeframe": "15m",
    "strategy_id": "strategy_v1_3",
    "leverage": 5,
    "running": False,
    "last_signal": None,
    "last_signal_time": None,
    "position_side": None,
    "account_value": None,
    "logs": [],
    "equity_history": [],  # Populated by strategy_loop for adaptive compounding
    "strategy_config": {},  # Per-instance parameter overrides from DB
}
loop_thread = None
loop_stop = threading.Event()
sse_queues = []

# ── Auth ──
def check_auth(cre):
    if not (secrets.compare_digest(cre.username.encode(), USERNAME.encode()) and
            secrets.compare_digest(cre.password.encode(), PASSWORD.encode())):
        raise HTTPException(401, "Unauthorized", headers={"WWW-Authenticate": "Basic"})

def auth_dep(request: Request):
    import base64
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Basic "):
        raise HTTPException(401, "Unauthorized", headers={"WWW-Authenticate": "Basic"})
    try:
        decoded = base64.b64decode(auth[6:]).decode()
        username, password = decoded.split(":", 1)
    except Exception:
        raise HTTPException(401, "Bad credentials")
    if not (secrets.compare_digest(username.encode(), USERNAME.encode()) and
            secrets.compare_digest(password.encode(), PASSWORD.encode())):
        raise HTTPException(401, "Unauthorized")
    return username

# ── Logging ──
def log(level, msg):
    ts = datetime.utcnow().strftime("%H:%M:%S")
    entry = {"time": ts, "level": level, "msg": msg}
    state["logs"].insert(0, entry)
    if len(state["logs"]) > 200:
        state["logs"].pop()
    # Append to dated logfile
    try:
        logdir = os.path.join(os.path.dirname(__file__), "..", "data", "logs")
        os.makedirs(logdir, exist_ok=True)
        logfile = os.path.join(logdir, f"worker_{datetime.utcnow().strftime('%Y-%m-%d')}.log")
        with open(logfile, "a") as f:
            f.write(f"{datetime.utcnow().isoformat()} [{level.upper()}] {msg}\n")
    except Exception:
        pass  # Never let file logging crash the loop
    # Push to SSE queues
    for q in list(sse_queues):
        try:
            q.put_nowait(entry)
        except:
            sse_queues.remove(q)

# ── Strategy loop (full runner logic: SL/TP/trailing/trend/time/reversal) ──
def strategy_loop():
    md = HyperLiquidMarketData()
    ex = HyperLiquidClient()

    active_trade = None
    prev_fast_ema = None
    prev_medm_ema = None
    equity_history = []
    poll = 3
    last_candle_time = None  # Track last candle close for bar counter
    last_entry_bar_time = None  # Pine: bar_index > lastEntryBar (one entry per bar)
    last_good_account_value = None  # For anomalous snapshot filtering

    def derive_side(position):
        if not position:
            return None
        szi = float(position.get("szi", 0))
        if szi > 0: return "LONG"
        if szi < 0: return "SHORT"
        return None

    def evaluate_exit(signal_result, active_trade, position, bar_high, bar_low):
        """Neutral consumer exit evaluation. Reads from exit_config only."""
        ec = signal_result.get("exit_config", {}) or {}
        side = active_trade["side"]
        bars_in_trade = active_trade["bars_in_trade"]

        # 1. Stop-loss: candle H/L touches strategy stop level
        if side == "LONG":
            sl = ec.get("stop_loss_long")
            if sl is not None and bar_low <= float(sl):
                return "Stop Loss"
        elif side == "SHORT":
            sl = ec.get("stop_loss_short")
            if sl is not None and bar_high >= float(sl):
                return "Stop Loss"

        # 2. Trailing stop (reads all params from exit_config)
        # Pine: strategy.exit(trail_points=act, trail_offset=off) — no grace period
        mintick = float(active_trade.get("mintick", 0.00001))
        trail_act = float(ec.get("trail_activation", 0))
        trail_off = float(ec.get("trail_offset", 0))
        if not active_trade.get("trail_active") and trail_act > 0:
            if side == "LONG":
                if bar_high >= active_trade["entry_price"] + trail_act * mintick:
                    active_trade["trail_active"] = True
            else:
                if bar_low <= active_trade["entry_price"] - trail_act * mintick:
                    active_trade["trail_active"] = True
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

        # 3. Take-profit (only if strategy declares it)
        tp_long = ec.get("take_profit_long")
        tp_short = ec.get("take_profit_short")
        if side == "LONG" and tp_long is not None and bar_high >= float(tp_long):
            return "Take Profit"
        if side == "SHORT" and tp_short is not None and bar_low <= float(tp_short):
            return "Take Profit"

        # 4. EMA-cross trend reversal (bar-to-bar)
        curr_f = ec.get("fast_ema")
        curr_m = ec.get("medm_ema")
        if prev_fast_ema is not None and prev_medm_ema is not None and curr_f is not None and curr_m is not None:
            if side == "LONG" and prev_fast_ema >= prev_medm_ema and curr_f < curr_m:
                return "Trend Change"
            if side == "SHORT" and prev_fast_ema <= prev_medm_ema and curr_f > curr_m:
                return "Trend Change"

        # 5. Time-based exit (if strategy declares it)
        use_time_exit = ec.get("use_time_exit", False)
        if use_time_exit:
            max_bars = ec.get("time_exit_bars")
            if max_bars and bars_in_trade >= max_bars:
                return "Time Exit"

        return None

    log("info", f"Worker started: {state['token']} {state['timeframe']} {state['strategy_id']}")

    while not loop_stop.is_set():
        try:
            token = state["token"]
            tf = state["timeframe"]
            lev = state["leverage"]
            max_pos = state.get("max_pos", 0.97)

            # Get strategy instance (re-instantiate if config changed)
            strategy_cls = STRATEGIES.get(state["strategy_id"])
            if not strategy_cls:
                log("error", f"Strategy {state['strategy_id']} not found")
                time.sleep(poll)
                continue
            # Apply strategy_config overrides (per-instance params from DB)
            config = state.get("strategy_config", {})
            strategy = strategy_cls(**config) if config else strategy_cls()

            # Fetch candles for signal generation (not for bar counter - live uses time-based calc)
            df = md.get_candles(token, tf, bars=200)
            if df is None or df.empty:
                log("warn", f"No candles for {token}")
                time.sleep(poll)
                continue

            # Calculate bars_in_trade from elapsed time (live mode - no OHLC dependency)
            # Matches Pine's bar_index - entryBarIndex logic
            if active_trade:
                entry_dt = active_trade["entry_time"]
                elapsed_minutes = (datetime.utcnow() - entry_dt).total_seconds() / 60.0
                tf_minutes = {"5m": 5, "15m": 15, "30m": 30, "1h": 60, "4h": 240}.get(tf, 15)
                active_trade["bars_in_trade"] = int(elapsed_minutes / tf_minutes)

            # Generate signal
            result = strategy.generate_signals(df, symbol=token, equity_history=equity_history)
            direction = result.get("direction", "NEUTRAL")
            signal_val = result.get("signal", 0.0)
            metadata = result.get("metadata", {}) or {}

            # Store EMA values for cross detection - only on new bar close
            # Read from exit_config (receptacle), not metadata
            current_bar_time = df["timestamp"].iloc[-1] if "timestamp" in df.columns else None
            if current_bar_time is not None and current_bar_time != last_candle_time:
                ec_ema = result.get("exit_config", {}) or {}
                prev_fast_ema = ec_ema.get("fast_ema")
                prev_medm_ema = ec_ema.get("medm_ema")
                last_candle_time = current_bar_time

            # Sync position from exchange (source of truth)
            position = ex.get_position(token)
            current_side = derive_side(position)
            state["position_side"] = current_side

            # Reconcile active_trade with exchange position
            if current_side is None and active_trade is not None and active_trade != "PENDING":
                # Position gone but we think we're in a trade — clear it
                log("info", f"Position closed externally — clearing active trade")
                active_trade = None
            elif current_side is None and active_trade == "PENDING":
                # Order may not have filled yet — skip reconciliation this tick
                pass
            elif current_side and active_trade is None:
                # Adopt existing position (e.g. after restart)
                entry_px = float(position.get("entryPx", 0)) if position else 0.0
                adopt_size = abs(float(position.get("szi", 0))) if position else 0.0
                adopt_mark = float(position.get("markPx", 0)) if position else 0.0
                # Read SL/TP from current signal's exit_config
                ec_adopt = result.get("exit_config", {}) or {}
                active_trade = {
                    "side": current_side,
                    "entry_time": datetime.utcnow(),
                    "bars_in_trade": 0,
                    "entry_price": entry_px,
                    "best_price": adopt_mark or entry_px,
                    "trail_active": False,
                    "mintick": float(ec_adopt.get("mintick", detect_mintick(df=df, token=token))) if "exit_config" in result else detect_mintick(df=df, token=token),
                    "size": adopt_size,
                    "stop_loss": float(ec_adopt.get("stop_loss_long" if current_side == "LONG" else "stop_loss_short", 0)),
                    "take_profit": float(ec_adopt.get("take_profit_long" if current_side == "LONG" else "take_profit_short", 0)),
                }
                log("trade", f"ADOPTED {current_side} {token} @ {entry_px:.6f} SL={active_trade['stop_loss']:.6f} TP={active_trade['take_profit']:.6f}")
            elif current_side and active_trade and active_trade != "PENDING" and current_side != active_trade["side"]:
                # Side flipped externally — adopt new side
                entry_px = float(position.get("entryPx", 0)) if position else 0.0
                adopt_size = abs(float(position.get("szi", 0))) if position else 0.0
                adopt_mark = float(position.get("markPx", 0)) if position else 0.0
                # Read SL/TP from current signal's exit_config
                ec_adopt = result.get("exit_config", {}) or {}
                active_trade = {
                    "side": current_side,
                    "entry_time": datetime.utcnow(),
                    "bars_in_trade": 0,
                    "entry_price": entry_px,
                    "best_price": adopt_mark or entry_px,
                    "trail_active": False,
                    "mintick": float(ec_adopt.get("mintick", detect_mintick(df=df, token=token))) if "exit_config" in result else detect_mintick(df=df, token=token),
                    "size": adopt_size,
                    "stop_loss": float(ec_adopt.get("stop_loss_long" if current_side == "LONG" else "stop_loss_short", 0)),
                    "take_profit": float(ec_adopt.get("take_profit_long" if current_side == "LONG" else "take_profit_short", 0)),
                }
                log("trade", f"Side flipped → ADOPTED {current_side} {token} @ {entry_px:.6f} SL={active_trade['stop_loss']:.6f} TP={active_trade['take_profit']:.6f}")

            # Log signal with account value
            account_value = ex.get_account_value() or 0.0
            # Filter anomalous snapshots (same as runner.py P11)
            if last_good_account_value is not None and last_good_account_value > 0:
                ratio = account_value / last_good_account_value if last_good_account_value > 0 else 1.0
                if ratio < 0.5 or ratio > 2.0:
                    log("warn", f"Skipping anomalous account snapshot: ${account_value:.2f} vs last ${last_good_account_value:.2f} (ratio={ratio:.2f})")
                else:
                    last_good_account_value = account_value
            else:
                if account_value > 0:
                    last_good_account_value = account_value
            # Equity history: only append on trade close (matches Pine closedtrades)
            # NOT every tick - that corrupts the adaptive compounding with noise.
            state["account_value"] = round(account_value, 4)
            state["last_signal"] = {"signal": round(signal_val, 2), "direction": direction, "meta": {k: v for k, v in metadata.items() if k in ("adx", "fast_ema", "medm_ema", "slow_sma", "fan_up_trend", "fan_dn_trend", "stop_loss_long", "stop_loss_short", "take_profit_long", "take_profit_short", "engine_mode", "is_strategy_cold", "in_warmup")}}
            state["last_signal_time"] = datetime.utcnow().isoformat()
            reasoning = []
            if "adx" in metadata: reasoning.append(f"adx={metadata['adx']:.1f}")
            if metadata.get("fan_up_trend"): reasoning.append("fan=up")
            elif metadata.get("fan_dn_trend"): reasoning.append("fan=down")
            if metadata.get("bullish_pin_bar"): reasoning.append("pin=bull")
            elif metadata.get("bearish_pin_bar"): reasoning.append("pin=bear")
            state_label = "IN TRADE" if active_trade and active_trade != "PENDING" else ("PENDING" if active_trade == "PENDING" else "IDLE")
            log("signal", f"{token} {direction} sig={signal_val:.2f} | {state_label} | acct=${account_value:.2f}" + (f" | {' | '.join(reasoning)}" if reasoning else ""))

            # Determine desired side
            desired_side = None
            if direction == "BUY": desired_side = "LONG"
            elif direction == "SELL": desired_side = "SHORT"

            # ── Entry logic: only enter when flat (no active/pending trade) ──
            if active_trade is None and desired_side:
                # Pine: bar_index > lastEntryBar — one entry per bar
                current_bar_time = df["timestamp"].iloc[-1] if "timestamp" in df.columns else None
                if last_entry_bar_time is not None and current_bar_time == last_entry_bar_time:
                    pass  # Same bar — Pine prevents re-entry
                else:
                    # Synchronous re-entry guard: mark pending BEFORE async market_open
                    # prevents the 3s poll race from double-entering (BUG-001)
                    active_trade = "PENDING"
                    account_value = ex.get_account_value()
                    if account_value and account_value > 0:
                        notional = PositionSizer.notional_from_free_balance(account_value, lev, max_pos)
                        if notional > 0:
                            log("trade", f"OPEN {desired_side} {token} ${notional:.2f} {lev}x")
                            open_result = ex.market_open(token, side=desired_side.lower(), size_usd=notional, leverage=lev)
                            if open_result:
                                # Re-fetch position to get actual entry price
                                position = ex.get_position(token)
                                entry_px = float(position.get("entryPx", 0)) if position else 0.0
                                # Get mintick from HL API markPx precision (authoritative)
                                from engine.registry import detect_mintick
                                mintick = detect_mintick(df=df, token=token)
                                # Read trail params from exit_config (receptacle)
                                ec = result.get("exit_config", {}) or {}
                                active_trade = {
                                    "side": desired_side,
                                    "entry_time": datetime.utcnow(),
                                    "bars_in_trade": 0,
                                    "entry_price": entry_px,
                                    "best_price": entry_px,
                                    "trail_active": False,
                                    "mintick": mintick,
                                }
                                log("info", f"ENTRY {desired_side} @ {entry_px:.6f} | SL={ec.get('stop_loss_long' if desired_side == 'LONG' else 'stop_loss_short')} TP={ec.get('take_profit_long' if desired_side == 'LONG' else 'take_profit_short')}")
                                last_entry_bar_time = current_bar_time
                            else:
                                log("error", f"Open failed for {token}")
                                active_trade = None  # Clear PENDING guard on failure
                        else:
                            log("warn", f"Insufficient balance to open {desired_side}")
                            active_trade = None  # Clear PENDING guard on failure
                    else:
                        log("warn", f"No account value available")
                        active_trade = None  # Clear PENDING guard on failure

            # ── Exit logic: full evaluation when in a trade ──
            elif active_trade is not None and active_trade != "PENDING":
                bar_high = float(df["high"].iloc[-1])
                bar_low = float(df["low"].iloc[-1])
                exit_reason = evaluate_exit(result, active_trade, position, bar_high, bar_low)
                if exit_reason:
                    log("trade", f"CLOSE {token} ({active_trade['side']}) — {exit_reason}")
                    close_result = ex.market_close(token)
                    if close_result:
                        # Estimate exit cost for P&L tracking
                        entry_px = active_trade.get("entry_price", 0)
                        trade_size = active_trade.get("size", 0) or abs(float(position.get("szi", 0))) if position else 0
                        exit_price = float(position.get("markPx", 0)) if position else 0
                        if trade_size > 0 and entry_px > 0 and exit_price > 0:
                            notional = trade_size * exit_price
                            side_mult = 1.0 if active_trade["side"] == "LONG" else -1.0
                            pnl = side_mult * (exit_price - entry_px) * trade_size
                            exit_cost = notional * 0.0007  # taker fee both sides estimate
                            log("info", f"Trade P&L: ${pnl:.4f} (entry={entry_px:.6f} exit={exit_price:.6f} size={trade_size:.4f} cost=${exit_cost:.4f})")
                        active_trade = None
                        # Append realized equity to history (matches Pine closedtrades behavior)
                        # Pine: equityCurve updates only when strategy.closedtrades > lastClosedTrades
                        post_close_value = ex.get_account_value() or account_value
                        if post_close_value > 0:
                            equity_history.append(post_close_value)
                            if len(equity_history) > 100:  # MAX_EQUITY_HISTORY = 100
                                equity_history = equity_history[-100:]
                            state["equity_history"] = equity_history
                    else:
                        log("error", f"Close failed for {token}")

        except Exception as e:
            log("error", f"Loop error: {e}")

        for _ in range(poll):
            if loop_stop.is_set():
                break
            time.sleep(1)

    log("info", "Worker stopped")
    state["running"] = False

# ── App ──
app = FastAPI(title="PULS·R Worker")

@app.get("/", response_class=HTMLResponse)
async def index(username: str = Depends(auth_dep)):
    return PAGE_HTML

@app.get("/api/state")
async def get_state(username: str = Depends(auth_dep)):
    # Return state without logs or full equity_history (too large for JSON)
    resp = {k: v for k, v in state.items() if k not in ("logs", "equity_history")}
    eq_hist = state.get("equity_history", [])
    resp["equity_history_len"] = len(eq_hist)
    resp["equity_history_last"] = eq_hist[-1] if eq_hist else None
    return JSONResponse(resp)

@app.get("/api/settings")
async def get_settings(username: str = Depends(auth_dep)):
    """Return current worker configuration (read-only snapshot)."""
    return JSONResponse({
        "token": state.get("token"),
        "timeframe": state.get("timeframe"),
        "strategy_id": state.get("strategy_id"),
        "leverage": state.get("leverage"),
        "max_position_pct": state.get("max_pos", 0.97),
        "running": state.get("running", False),
        "account_value": state.get("account_value"),
        "position_side": state.get("position_side"),
        "equity_history_len": len(state.get("equity_history", [])),
    })

@app.post("/api/config")
async def set_config(request: Request, username: str = Depends(auth_dep)):
    body = await request.json()
    for key in ("token", "timeframe", "strategy_id", "leverage"):
        if key in body:
            state[key] = body[key]
    state["max_pos"] = float(body.get("max_position_pct", 0.97))
    if "strategy_config" in body:
        state["strategy_config"] = body["strategy_config"]
    log("info", f"Config updated: {state['token']} {state['timeframe']} {state['strategy_id']} lev={state['leverage']}x")
    return {"ok": True, "state": {k: v for k, v in state.items() if k != "logs"}}

@app.get("/api/strategy-config")
async def get_strategy_config(username: str = Depends(auth_dep)):
    """Return current strategy parameter overrides."""
    strategy_id = state.get("strategy_id", "strategy_v1_3")
    config = state.get("strategy_config", {})
    # If config is empty, return defaults from the strategy class
    if not config:
        strategy_cls = STRATEGIES.get(strategy_id)
        if strategy_cls and hasattr(strategy_cls, "get_default_config"):
            config = strategy_cls.get_default_config()
    return JSONResponse({"ok": True, "strategy_id": strategy_id, "config": config})

@app.put("/api/strategy-config")
async def set_strategy_config(request: Request, username: str = Depends(auth_dep)):
    """Update strategy parameter overrides. Merges with existing config."""
    body = await request.json()
    current = state.get("strategy_config", {})
    current.update(body)
    state["strategy_config"] = current
    log("info", f"Strategy config updated: {len(current)} parameters")
    return JSONResponse({"ok": True, "strategy_id": state.get("strategy_id"), "config": current})

@app.post("/api/start")
async def start_worker(username: str = Depends(auth_dep)):
    global loop_thread, loop_stop
    if state["running"]:
        return {"ok": False, "msg": "Already running"}
    loop_stop = threading.Event()
    loop_thread = threading.Thread(target=strategy_loop, daemon=True)
    state["running"] = True
    loop_thread.start()
    return {"ok": True, "msg": "Started"}

@app.post("/api/stop")
async def stop_worker(username: str = Depends(auth_dep)):
    global loop_stop
    if not state["running"]:
        return {"ok": False, "msg": "Not running"}
    loop_stop.set()
    state["running"] = False
    return {"ok": True, "msg": "Stop signal sent"}

@app.get("/stream")
async def stream(request: Request, username: str = Depends(auth_dep)):
    import queue
    q = queue.Queue()
    sse_queues.append(q)
    # Send existing logs first
    for entry in state["logs"][:50]:
        q.put_nowait(entry)

    async def gen():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    entry = q.get_nowait()
                    yield f"data: {json.dumps(entry)}\n\n"
                except:
                    yield f": keepalive\n\n"
                    await asyncio.sleep(1)
        finally:
            if q in sse_queues:
                sse_queues.remove(q)

    return StreamingResponse(gen(), media_type="text/event-stream")

# ── HTML ──
PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PULS·R Worker</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: #0a0a0a; color: #e5e5e5; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', monospace; font-size: 14px; }
.container { max-width: 900px; margin: 0 auto; padding: 20px; }
h1 { font-size: 18px; margin-bottom: 16px; color: #089981; letter-spacing: -0.5px; }
.config-bar { display: flex; gap: 12px; align-items: end; margin-bottom: 16px; flex-wrap: wrap; background: #141414; padding: 16px; border-radius: 8px; border: 1px solid #222; }
.field { display: flex; flex-direction: column; gap: 4px; }
.field label { font-size: 10px; text-transform: uppercase; color: #666; letter-spacing: 0.5px; }
.field input, .field select { background: #0a0a0a; color: #e5e5e5; border: 1px solid #333; border-radius: 4px; padding: 8px 10px; font-size: 13px; font-family: monospace; }
.field input:focus, .field select:focus { outline: 1px solid #089981; }
.btn { padding: 8px 20px; border-radius: 4px; border: none; font-size: 13px; font-weight: 600; cursor: pointer; font-family: inherit; }
.btn-start { background: #089981; color: #fff; }
.btn-start:hover { background: #0ab483; }
.btn-stop { background: #f23645; color: #fff; }
.btn-stop:hover { background: #ff4655; }
.btn-save { background: #333; color: #e5e5e5; }
.btn-save:hover { background: #444; }
.btn:disabled { opacity: 0.4; cursor: not-allowed; }
.status { display: flex; gap: 16px; align-items: center; margin-bottom: 12px; font-size: 12px; color: #888; }
.status .dot { width: 8px; height: 8px; border-radius: 50; background: #444; }
.status .dot.running { background: #089981; animation: pulse 1.5s ease-in-out infinite; }
.status .dot.stopped { background: #f23645; }
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }
.console { background: #0d0d0d; border: 1px solid #222; border-radius: 8px; padding: 12px; height: 500px; overflow-y: auto; font-family: 'SF Mono', 'Cascadia Code', monospace; font-size: 12px; line-height: 1.6; }
.log-line { white-space: pre-wrap; word-break: break-all; }
.log-line .ts { color: #555; }
.log-line .lvl-signal { color: #089981; }
.log-line .lvl-trade { color: #f0b90b; }
.log-line .lvl-error { color: #f23645; }
.log-line .lvl-warn { color: #f0b90b; }
.log-line .lvl-info { color: #888; }
</style>
</head>
<body>
<div class="container">
<h1>📡 PULS·R Live Strategy Worker</h1>
<div class="config-bar">
    <div class="field"><label>Token</label><input id="token" type="text" value="WIF" style="width:80px;"></div>
    <div class="field"><label>Timeframe</label><select id="timeframe" style="width:70px;"><option value="5m">5m</option><option value="15m" selected>15m</option><option value="30m">30m</option><option value="1h">1h</option><option value="4h">4h</option></select></div>
    <div class="field"><label>Strategy</label><select id="strategy" style="width:140px;"><option value="strategy_v1_3">Scalp v1.3</option><option value="strategy_v1">Swing v1</option><option value="strategy_v6_1">PRO v6.1</option></select></div>
    <div class="field"><label>Leverage</label><input id="leverage" type="number" value="1" min="1" max="50" style="width:60px;"></div>
    <div class="field"><label>Max Pos %</label><input id="maxpos" type="number" value="97" min="1" max="100" step="0.1" style="width:70px;"></div>
    <button class="btn btn-save" onclick="saveConfig()">Save</button>
    <button class="btn btn-start" id="btn-start" onclick="startWorker()">▶ Start</button>
    <button class="btn btn-stop" id="btn-stop" onclick="stopWorker()" disabled>■ Stop</button>
</div>
<div class="status">
    <span class="dot stopped" id="status-dot"></span>
    <span id="status-text">Stopped</span>
    <span>·</span>
    <span id="last-signal">No signal yet</span>
</div>
<div id="strategy-params" style="display:none;background:#141414;border:1px solid #222;border-radius:8px;padding:16px;margin-bottom:12px;">
    <h3 style="font-size:13px;color:#089981;margin-bottom:12px;letter-spacing:-0.3px;">Strategy Parameters</h3>
    <div id="params-grid" style="display:grid;grid-template-columns:1fr 1fr;gap:8px;"></div>
    <button class="btn btn-save" onclick="saveParams()" style="margin-top:12px;">Save Parameters</button>
</div>
<div class="console" id="console"></div>
</div>
<script>
const API_BASE = location.origin;
const auth = btoa('operator:operator');

async function api(path, method='GET', body=null) {
    const opts = { method, headers: { 'Authorization': 'Basic ' + auth, 'Content-Type': 'application/json' } };
    if (body) opts.body = JSON.stringify(body);
    const r = await fetch(API_BASE + path, opts);
    return r.json();
}

function addLog(entry) {
    const c = document.getElementById('console');
    const line = document.createElement('div');
    line.className = 'log-line';
    const ts = entry.time || new Date().toTimeString().slice(0,8);
    line.innerHTML = '<span class="ts">[' + ts + ']</span> <span class="lvl-' + (entry.level||'info') + '">' + (entry.msg||'') + '</span>';
    c.appendChild(line);
    c.scrollTop = c.scrollHeight;
    while (c.childElementCount > 200) c.removeChild(c.firstChild);
}

async function saveConfig() {
    const body = {
        token: document.getElementById('token').value.toUpperCase(),
        timeframe: document.getElementById('timeframe').value,
        strategy_id: document.getElementById('strategy').value,
        leverage: parseInt(document.getElementById('leverage').value) || 1,
        max_position_pct: (parseFloat(document.getElementById('maxpos').value) || 97) / 100,
    };
    const r = await api('/api/config', 'POST', body);
    if (r.ok) addLog({level:'info', msg:'Config saved: ' + body.token + ' ' + body.timeframe + ' ' + body.strategy_id});
}

async function startWorker() {
    await saveConfig();
    const r = await api('/api/start', 'POST');
    if (r.ok) {
        document.getElementById('btn-start').disabled = true;
        document.getElementById('btn-stop').disabled = false;
        document.getElementById('status-dot').className = 'dot running';
        document.getElementById('status-text').textContent = 'Running';
    }
}

async function stopWorker() {
    const r = await api('/api/stop', 'POST');
    if (r.ok) {
        document.getElementById('btn-start').disabled = false;
        document.getElementById('btn-stop').disabled = true;
        document.getElementById('status-dot').className = 'dot stopped';
        document.getElementById('status-text').textContent = 'Stopped';
    }
}

// SSE
const es = new EventSource(API_BASE + '/stream');
es.onmessage = ev => {
    try {
        const entry = JSON.parse(ev.data);
        if (entry.msg) {
            addLog(entry);
            if (entry.level === 'signal') {
                document.getElementById('last-signal').textContent = entry.msg;
            }
        }
    } catch {}
};

// Initial state
api('/api/state').then(s => {
    if (s.token) document.getElementById('token').value = s.token;
    if (s.timeframe) document.getElementById('timeframe').value = s.timeframe;
    if (s.strategy_id) document.getElementById('strategy').value = s.strategy_id;
    if (s.leverage) document.getElementById('leverage').value = s.leverage;
    if (s.running) {
        document.getElementById('btn-start').disabled = true;
        document.getElementById('btn-stop').disabled = false;
        document.getElementById('status-dot').className = 'dot running';
        document.getElementById('status-text').textContent = 'Running';
    }
});

// Strategy parameters
let currentParams = {};

async function loadParams() {
    const sid = document.getElementById('strategy').value;
    try {
        const r = await fetch(API_BASE + '/api/v2/strategies/' + encodeURIComponent(sid) + '/parameters', { headers: { 'X-API-Key': auth ? btoa ? '' : '' } } });
        if (!r.ok) throw new Error('Failed');
        const data = await r.json();
        if (!data.ok) return;
        const params = data.parameters || [];
        if (params.length === 0) { document.getElementById('strategy-params').style.display = 'none'; return; }
        // Get current config
        const cfg = await api('/api/strategy-config');
        currentParams = cfg.config || data.defaults || {};
        // Render form
        const grid = document.getElementById('params-grid');
        grid.innerHTML = '';
        params.forEach(p => {
            const val = currentParams[p.name] !== undefined ? currentParams[p.name] : p.default;
            let input;
            if (p.type === 'bool') {
                input = `<input type="checkbox" data-param="${p.name}" ${val ? 'checked' : ''} style="width:auto;">`;
            } else if (p.type === 'select') {
                input = `<select data-param="${p.name}" style="width:100%;">${(p.options||[]).map(o => `<option value="${o}" ${o===val?'selected':''}>${o}</option>`).join('')}</select>`;
            } else {
                input = `<input type="number" data-param="${p.name}" value="${val}" step="${p.step||1}" min="${p.min||''}" max="${p.max||''}" style="width:100%;">`;
            }
            grid.innerHTML += `<div style="display:flex;flex-direction:column;gap:2px;"><label style="font-size:10px;text-transform:uppercase;color:#666;letter-spacing:0.5px;">${p.label||p.name}</label>${input}</div>`;
        });
        document.getElementById('strategy-params').style.display = 'block';
    } catch(e) {
        document.getElementById('strategy-params').style.display = 'none';
    }
}

async function saveParams() {
    const inputs = document.querySelectorAll('[data-param]');
    const config = {};
    inputs.forEach(el => {
        const name = el.dataset.param;
        if (el.type === 'checkbox') config[name] = el.checked;
        else if (el.type === 'number') config[name] = parseFloat(el.value);
        else config[name] = el.value;
    });
    const r = await api('/api/strategy-config', 'PUT', config);
    if (r.ok) addLog({level:'info', msg:'Strategy config saved: ' + Object.keys(config).length + ' params'});
}

// Load params on strategy change
document.getElementById('strategy').addEventListener('change', loadParams);
loadParams();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)