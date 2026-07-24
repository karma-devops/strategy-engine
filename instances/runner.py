"""
Single strategy instance runner.
Polls candles, generates signal, executes trades, records state.
Runner is created stopped; manager must call .start() explicitly.
"""

import time
import threading
import traceback
from datetime import datetime, timezone
from typing import Optional, Tuple

from sqlalchemy.orm import sessionmaker

from config import config
from strategies.registry import get_strategy, detect_mintick
from core.market_data import market_data
from core.exchange import get_hyperliquid_client
from core.position_sizer import PositionSizer
from instances.events import event_bus, add_log
from instances.models import (
    engine,
    Signal,
    Trade,
    PositionSnapshot,
    AccountSnapshot,
    Instance,
)

Session = sessionmaker(bind=engine)


class InstanceRunner:
    # PITFALL: Stale HL client in daemon threads (2026-07-17)
    #
    # The runner's self._hl (HyperLiquidClient) is created once in __init__ and
    # reused for the entire lifetime of the daemon thread. The underlying
    # hyperliquid Info object holds an HTTP session that can go stale after
    # hours of continuous polling — get_position() returns None despite a live
    # position existing on the exchange.
    #
    # Symptoms:
    #   - HL shows a live position (e.g. LONG 186.1 FARTCOIN)
    #   - _sync_position creates correct PositionSnapshot rows (it got data
    #     from a fresh client on a successful tick)
    #   - But _update_position_cache writes None to the Instance model because
    #     the same tick's hl.get_position() returned None from the stale client
    #   - Dashboard shows no position even though HL has one
    #
    # The old fallback (lines 135-147) created a fresh HyperLiquidClient but
    # passed private_key=None, which fell through to global env credentials —
    # WRONG for per-instance credential isolation. This silently queried the
    # wrong account or returned None again.
    #
    # Fix: _refresh_hl_client() creates a fresh client using the instance's
    # resolved credentials (per-instance encrypted keys, NOT global env), and
    # replaces self._hl so all subsequent calls in the same tick also use it.
    # A retry counter (_stale_position_retries) forces a refresh after 3
    # consecutive None results while _active_trade says we should have a
    # position.
    #
    # Lesson: HTTP client sessions in long-lived daemon threads MUST be
    # refreshed periodically. Never trust a singleton client to stay alive
    # forever in a thread that polls every 30 seconds for days.

    def __init__(self, instance):
        self.instance = instance
        self.id = instance.slug
        self._thread = None
        self._stop_event = threading.Event()
        self._last_signal = None
        self._last_executed_side: Optional[str] = None
        self._active_trade: Optional[dict] = None  # side, entry_signal_id, entry_time, bars_in_trade
        self._prev_fast_ema: Optional[float] = None
        self._prev_medm_ema: Optional[float] = None
        self._last_bar_time: Optional[object] = None  # track bar close for EMA cross
        self._last_entry_bar_time: Optional[object] = None  # Pine: bar_index > lastEntryBar
        self._last_entry_attempt_ts: float = 0.0  # Idempotency P0: epoch sec of last entry attempt (60s cooldown)
        self._stale_position_retries: int = 0  # consecutive None ticks while in trade
        self._consecutive_errors: int = 0  # circuit breaker: consecutive tick exceptions
        self._hl = get_hyperliquid_client(instance)

        # Paper Trading state simulation
        self._paper_balance = float(instance.start_balance) if (instance.start_balance and instance.start_balance > 0) else 100.0  # E4: paper baseline 100 (matches backtest), operator directive
        self._equity_history: list = [self._paper_balance] if instance.dry_run else []  # closed-trade equity values

    def _refresh_hl_client(self):
        """Create a fresh HyperLiquidClient using the instance's resolved credentials.

        This replaces self._hl with a new client, which creates a new HTTP session
        (new Info/Exchange objects). Called when the existing client returns stale
        results — None from get_position() when a position should exist.

        Uses instance.get_resolved_hl_credentials() so per-instance encrypted keys
        are used, NOT global env fallback (the old bug).
        """
        try:
            # Re-read instance from DB to get fresh credential references
            db = Session()
            try:
                inst = db.query(Instance).filter(Instance.slug == self.id).first()
            finally:
                db.close()
            if inst:
                self._hl = get_hyperliquid_client(inst)
                add_log(
                    f"[{self.instance.token}] Refreshed HL client (stale connection recovery)",
                    "info", dry_run=self.instance.dry_run,
                )
            else:
                # Fallback: re-create with current instance object
                self._hl = get_hyperliquid_client(self.instance)
        except Exception as e:
            add_log(
                f"[{self.instance.token}] HL client refresh failed: {e}",
                "error", dry_run=self.instance.dry_run,
            )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------
    def _loop(self):
        # D2: auto-restart resilience. If the loop dies from an unexpected
        # exception OUTSIDE the per-tick try/except (e.g. HL client hard crash,
        # DB connection drop), automatically restart up to MAX_RESTARTS times
        # with exponential backoff — UNLESS the operator explicitly stopped us.
        MAX_RESTARTS = 5
        restarts = 0
        while not self._stop_event.is_set():
            try:
                self._run_once()
            except Exception as e:
                if self._stop_event.is_set():
                    break
                restarts += 1
                add_log(
                    f"[RUNNER {self.id}] CRASH (restart {restarts}/{MAX_RESTARTS}): {e}",
                    "error", dry_run=self.instance.dry_run,
                )
                print(f"[RUNNER {self.id}] CRASH (restart {restarts}/{MAX_RESTARTS}): {e}")
                import traceback
                traceback.print_exc()
                if restarts >= MAX_RESTARTS:
                    add_log(
                        f"[RUNNER {self.id}] Exhausted restarts — marking error",
                        "error", dry_run=self.instance.dry_run,
                    )
                    self._persist_status(self.instance, "error")
                    break
                # Exponential backoff: 2s, 4s, 8s, 16s
                backoff = min(2 ** restarts, 30)
                self._stop_event.wait(backoff)
                if self._stop_event.is_set():
                    break

    def _run_once(self):
        print(f"[RUNNER {self.id}] Started for {self.instance.token}")
        add_log(f"[RUNNER {self.id}] Started for {self.instance.token}", "info", dry_run=self.instance.dry_run)

        strategy_class = get_strategy(self.instance.strategy_id)
        if not strategy_class:
            print(f"[RUNNER {self.id}] Unknown strategy {self.instance.strategy_id}")
            add_log(f"Unknown strategy {self.instance.strategy_id}", "error", dry_run=self.instance.dry_run)
            self.instance.status = "error"
            self._persist_status(self.instance, "error")
            return

        # Apply per-instance strategy config overrides from DB (Pine input.* equivalent)
        strategy_config = getattr(self.instance, 'strategy_config', None) or {}
        strategy = strategy_class(**strategy_config) if strategy_config else strategy_class()
        hl = self._hl

        CIRCUIT_TRIP_THRESHOLD = 5  # consecutive tick errors before tripping

        while not self._stop_event.is_set():
            try:
                self._tick(strategy, hl)
                # Successful tick — reset breaker
                self._consecutive_errors = 0
            except Exception as e:
                self._consecutive_errors += 1
                print(f"[RUNNER {self.id}] Tick error ({self._consecutive_errors}/{CIRCUIT_TRIP_THRESHOLD}): {e}")
                traceback.print_exc()
                add_log(
                    f"Tick error in {self.instance.token} "
                    f"({self._consecutive_errors}/{CIRCUIT_TRIP_THRESHOLD}): {e}",
                    "error", dry_run=self.instance.dry_run,
                )
                # Circuit breaker: too many consecutive failures — stop hammering
                # a broken exchange/DB and surface the fault instead of looping forever.
                if self._consecutive_errors >= CIRCUIT_TRIP_THRESHOLD:
                    add_log(
                        f"[RUNNER {self.id}] CIRCUIT BREAKER TRIPPED after "
                        f"{self._consecutive_errors} consecutive errors — marking error",
                        "error", dry_run=self.instance.dry_run,
                    )
                    self.instance.status = "error"
                    self._persist_status(self.instance, "error")
                    break
            self._stop_event.wait(self.instance.poll_interval_seconds)

        print(f"[RUNNER {self.id}] Stopped")
        add_log(f"[RUNNER {self.id[:8]}] Stopped for {self.instance.token}", "info", dry_run=self.instance.dry_run)

    def _tick(self, strategy, hl):
        db = Session()
        try:
            # BUG #6: kill-switch check BEFORE any order logic.
            # A kill triggered mid-tick must not let the current tick place orders.
            # Lazy import avoids circular import (killswitch → manager → runner).
            from api.killswitch import is_global_killed
            if is_global_killed(db):
                add_log(
                    f"[RUNNER {self.id}] Kill switch active — skipping tick (no orders)",
                    "warn", dry_run=self.instance.dry_run,
                )
                return

            # Fetch candles
            df = market_data.get_candles(
                self.instance.token,
                timeframe=self.instance.timeframe,
                bars=100,
            )
            if df.empty:
                add_log(f"[RUNNER {self.id}] No candles for {self.instance.token}", "warn", dry_run=self.instance.dry_run)
                return

            # Generate signal
            result = strategy.generate_signals(df, symbol=self.instance.token, equity_history=self._equity_history)
            direction = result.get("direction", "NEUTRAL")
            signal_val = result.get("signal", 0.0)
            metadata = result.get("metadata", {}) or {}

            # Store current EMA values for next-tick cross detection.
            # Only update prev values when a new bar has closed (not every poll).
            # This matches Pine's bar-by-bar ta.crossunder/crossover behavior.
            # Read from exit_config (receptacle), not metadata.
            current_bar_time = df["timestamp"].iloc[-1] if "timestamp" in df.columns else None
            if current_bar_time is not None and current_bar_time != self._last_bar_time:
                # New bar detected - update prev EMA values from exit_config
                ec_ema = result.get("exit_config", {}) or {}
                self._prev_fast_ema = ec_ema.get("fast_ema")
                self._prev_medm_ema = ec_ema.get("medm_ema")
                self._last_bar_time = current_bar_time
                # Increment bars_in_trade only on new bar (not every poll)
                if self._active_trade:
                    self._active_trade["bars_in_trade"] += 1

            # Sync position from exchange (source of truth).
            # PITFALL: self._hl's HTTP session goes stale in long-running daemon
            # threads. get_position() returns None despite a live position on HL.
            # We track consecutive None results and force-refresh the client after
            # 3 stale ticks while _active_trade says we should have a position.
            position = hl.get_position(self.instance.token)
            if position is None and hl.has_credentials:
                # Stale client detected — refresh and retry with correct credentials.
                # OLD BUG: the fallback here used private_key=None, which fell
                # through to global env creds — wrong for per-instance isolation.
                self._stale_position_retries += 1
                if self._stale_position_retries >= 3 and self._active_trade:
                    # 3 consecutive None ticks while we track an active trade.
                    # The HL client is almost certainly stale. Replace it entirely.
                    self._refresh_hl_client()
                    hl = self._hl  # use the fresh client for the rest of this tick
                # Immediate retry with fresh credentials (even if < 3 retries,
                # a single None while has_credentials is worth probing)
                try:
                    position = hl.get_position(self.instance.token)
                except Exception:
                    pass
                # If still None after retry, log it
                if position is None and self._active_trade:
                    add_log(
                        f"[{self.instance.token}] Position None despite active trade "
                        f"(stale retries: {self._stale_position_retries})",
                        "warn", dry_run=self.instance.dry_run,
                    )
            else:
                # Position found — reset stale counter
                self._stale_position_retries = 0
            current_side = self._derive_side(position)
            trade_active = bool(current_side)

            # Reconcile local active-trade tracker with exchange position
            if current_side is None and self._active_trade is not None:
                # Position was closed externally / by TP/SL/trailing
                self._close_active_trade(db, position, "exit")
                self._active_trade = None
            elif current_side and self._active_trade is None:
                # Position exists but we didn't track entry (e.g. restart) — adopt it
                adopt_entry_cost = 0.0
                if position:
                    try:
                        adopt_entry_cost = abs(float(position.get("szi", 0))) * float(position.get("entryPx", 0)) * 0.00035
                    except Exception:
                        adopt_entry_cost = 0.0
                # Adopt position with current signal's exit_config for SL/TP
                ec = result.get("exit_config", {}) or {}
                adopt_size = abs(float(position.get("szi", 0))) if position else 0.0
                adopt_mintick = detect_mintick(df=df, token=self.instance.token) if position else 0.00001
                self._active_trade = {
                    "side": current_side,
                    "entry_signal_id": None,
                    "entry_time": datetime.now(timezone.utc),
                    "bars_in_trade": 0,
                    "entry_cost": adopt_entry_cost,
                    "entry_price": float(position.get("entryPx", 0)) if position else 0.0,
                    "size": adopt_size,
                    "best_price": float(position.get("markPx", 0)) or float(position.get("entryPx", 0)) if position else 0.0,
                    "trail_active": False,
                    "mintick": adopt_mintick,
                    "stop_loss": ec.get("stop_loss_long") if current_side == "LONG" else ec.get("stop_loss_short"),
                    "take_profit": ec.get("take_profit_long") if current_side == "LONG" else ec.get("take_profit_short"),
                }
                add_log(
                    f"[{self.instance.token}] ADOPTED POS {current_side} "
                    f"{adopt_size:.4f}@{float(position.get('entryPx', 0)):.6f} | "
                    f"SL={self._active_trade['stop_loss']} TP={self._active_trade['take_profit']}",
                    "trade", dry_run=self.instance.dry_run,
                )
            elif current_side and self._active_trade and current_side != self._active_trade["side"]:
                # Side flipped externally — adopt new side with current signal's exit_config
                adopt_entry_cost = 0.0
                if position:
                    try:
                        adopt_entry_cost = abs(float(position.get("szi", 0))) * float(position.get("entryPx", 0)) * 0.00035
                    except Exception:
                        adopt_entry_cost = 0.0
                ec = result.get("exit_config", {}) or {}
                adopt_size = abs(float(position.get("szi", 0))) if position else 0.0
                adopt_mintick = detect_mintick(df=df, token=self.instance.token) if position else 0.00001
                self._active_trade = {
                    "side": current_side,
                    "entry_signal_id": None,
                    "entry_time": datetime.now(timezone.utc),
                    "bars_in_trade": 0,
                    "entry_cost": adopt_entry_cost,
                    "entry_price": float(position.get("entryPx", 0)) if position else 0.0,
                    "size": adopt_size,
                    "best_price": float(position.get("markPx", 0)) or float(position.get("entryPx", 0)) if position else 0.0,
                    "trail_active": False,
                    "mintick": adopt_mintick,
                    "stop_loss": ec.get("stop_loss_long") if current_side == "LONG" else ec.get("stop_loss_short"),
                    "take_profit": ec.get("take_profit_long") if current_side == "LONG" else ec.get("take_profit_short"),
                }

            # Persist position snapshot
            self._sync_position(db, position, current_side)

            # Record account snapshot with real withdrawable
            account_value = hl.get_account_value()
            withdrawable = hl.get_withdrawable()
            self._record_account(db, account_value, withdrawable)

            # Build reasoning text
            reasoning_parts = []
            if "adx" in metadata:
                reasoning_parts.append(f"adx={metadata['adx']:.1f}")
            if metadata.get("fan_up_trend"):
                reasoning_parts.append("fan=up")
            elif metadata.get("fan_dn_trend"):
                reasoning_parts.append("fan=down")
            if metadata.get("bull_pierce"):
                reasoning_parts.append("pierce=bull")
            elif metadata.get("bear_pierce"):
                reasoning_parts.append("pierce=bear")
            if metadata.get("bullish_pin_bar"):
                reasoning_parts.append("pin=bull")
            elif metadata.get("bearish_pin_bar"):
                reasoning_parts.append("pin=bear")
            reasoning_text = " | ".join(reasoning_parts) if reasoning_parts else None

            # Decide if this signal should execute
            desired_side = None
            if direction == "BUY":
                desired_side = "LONG"
            elif direction == "SELL":
                desired_side = "SHORT"

            executed = False
            entry_cost = 0.0

            # PineScript semantics: enter only from flat; exit via stop/TP/trailing/time/reversal
            # Guard: a stuck "PENDING" sentinel from a prior failed open must not
            # permanently block entry — clear it at the top of each flat evaluation.
            if self._active_trade == "PENDING":
                self._active_trade = None
            if self._active_trade is None:
                # Flat: enter on a fresh entry signal
                # Pine: bar_index > lastEntryBar — one entry per bar
                current_bar_time = df["timestamp"].iloc[-1] if "timestamp" in df.columns else None
                if desired_side and (self._last_entry_bar_time is None or current_bar_time != self._last_entry_bar_time):
                    # Idempotency P0: 60s cooldown after ANY entry attempt
                    # (incl. failed/aborted opens) so a stalled HL fill or
                    # API lag cannot trigger a duplicate entry on the next poll.
                    if time.time() - self._last_entry_attempt_ts < 60.0:
                        add_log(f"[{self.instance.token}] ENTRY skipped — {60.0 - (time.time() - self._last_entry_attempt_ts):.0f}s entry cooldown active", "debug", dry_run=self.instance.dry_run)
                    else:
                        # X1/X2 FIX: set a synchronous PENDING sentinel BEFORE calling
                        # _execute_open so a subsequent non-blocking poll (3s interval)
                        # cannot re-enter on a stale signal before the first fill commits.
                        # Universal entry gate: read the strategy's declared
                        # entry_config.trigger (neutral receiver, same pattern as
                        # exit_config). Falls back to legacy top-level
                        # valid_trigger_* keys for engines not yet emitting
                        # entry_config. No coupling to strategy-internal names.
                        ec_entry = result.get("entry_config", {}) or {}
                        pin_ok = bool(ec_entry.get("trigger"))
                        if not pin_ok:
                            # backward-compat: legacy engines emit valid_trigger_*
                            pin_ok = bool(
                                (desired_side == "LONG" and result.get("valid_trigger_bull"))
                                or (desired_side == "SHORT" and result.get("valid_trigger_bear"))
                            )
                        if not pin_ok:
                            if desired_side == "LONG":
                                add_log(f"[{self.instance.token}] ENTRY skipped - no bullish pin/trigger", "debug", dry_run=self.instance.dry_run)
                            else:
                                add_log(f"[{self.instance.token}] ENTRY skipped - no bearish pin/trigger", "debug", dry_run=self.instance.dry_run)
                        else:
                            self._last_entry_attempt_ts = time.time()  # Idempotency P0: stamp attempt
                            self._active_trade = "PENDING"  # X1 sentinel - blocks re-entry on next poll
                        executed, entry_cost = self._execute_open(db, hl, desired_side, account_value, position, result)
                        if executed:
                            # Strategy exit_config is read at exit time (neutral receiver)
                            ec = result.get("exit_config", {}) or {}
                            entry_px = float(position.get("entryPx", 0)) if position else 0.0
                            # Detect mintick from HL API markPx precision (authoritative)
                            mintick = detect_mintick(df=df, token=self.instance.token)
                            # BUG-A fix: `notional` was never assigned in _tick scope -> NameError
                            # on first valid entry signal. Derive it here (same source as _execute_open/
                            # reversal block) so size is computed from the actual account balance.
                            notional = PositionSizer.notional_from_free_balance(
                                account_value, self.instance.leverage, self.instance.max_position_pct
                            ) if account_value and account_value > 0 else 0.0
                            self._active_trade = {
                                "side": desired_side,
                                "entry_signal_id": None,
                                "entry_time": datetime.now(timezone.utc),
                                "bars_in_trade": 0,
                                "entry_cost": entry_cost,
                                "entry_price": entry_px,
                                "size": (notional / entry_px) if entry_px else 0.0,
                                "best_price": entry_px,
                                "trail_active": False,
                                "mintick": mintick,
                                "stop_loss": ec.get("stop_loss_long") if desired_side == "LONG" else ec.get("stop_loss_short"),
                                "take_profit": ec.get("take_profit_long") if desired_side == "LONG" else ec.get("take_profit_short"),
                            }
                            add_log(
                                f"[{self.instance.token}] ENTRY {desired_side} @ {entry_px:.6f} | "
                                f"SL={self._active_trade['stop_loss']} TP={self._active_trade['take_profit']}",
                                "trade", dry_run=self.instance.dry_run,
                            )
                            trade_active = True
                            self._last_entry_bar_time = current_bar_time
                        else:
                            # Open failed — reset to None for retry on next poll
                            self._active_trade = None
            else:
                # In a trade: check exit conditions
                # Pass current bar H/L for stop-loss evaluation
                bar_high = float(df["high"].iloc[-1])
                bar_low = float(df["low"].iloc[-1])
                exit_reason = self._evaluate_exit(result, self._active_trade, position, bar_high, bar_low)
                if exit_reason:
                    closed, exit_cost = self._execute_close(db, hl, self._active_trade["side"], position, exit_reason)
                    if closed:
                        recorded_entry_cost = self._active_trade.get("entry_cost", 0.0)
                        # Equity history: append post-close account value (matches Pine closedtrades)
                        # Pine: closedEquity = strategy.equity - strategy.openprofit (on trade close)
                        post_close_value = hl.get_account_value() or account_value
                        if post_close_value > 0:
                            self._equity_history.append(post_close_value)
                            if len(self._equity_history) > 100:  # MAX_EQUITY_HISTORY
                                self._equity_history = self._equity_history[-100:]
                        self._close_active_trade(db, position, exit_reason, entry_cost=recorded_entry_cost, exit_cost=exit_cost)
                        self._active_trade = None
                        trade_active = current_side is not None
                        executed = True

                        # PineScript reversal: if exit reason is trend change and
                        # the current signal is opposite, re-enter same tick.
                        if exit_reason in ("Trend Change", "Reversal Signal") and desired_side and desired_side != current_side:
                            # Refresh position — should be None after close
                            position = hl.get_position(self.instance.token)
                            if position is None:
                                self._last_entry_attempt_ts = time.time()  # Idempotency P0: stamp reversal re-entry
                                opened, entry_cost_rev = self._execute_open(db, hl, desired_side, account_value, position, result)
                                if opened:
                                    entry_px = float(position.get("entryPx", 0)) if position else 0.0
                                    # Re-read position after open to get actual entry price
                                    position = hl.get_position(self.instance.token)
                                    entry_px = float(position.get("entryPx", 0)) if position else 0.0
                                    ec = result.get("exit_config", {}) or {}
                                    mintick = detect_mintick(df=df, token=self.instance.token)
                                    notional_rev = PositionSizer.notional_from_free_balance(
                                        account_value, self.instance.leverage, self.instance.max_position_pct
                                    ) if account_value and account_value > 0 else 0.0
                                    self._active_trade = {
                                        "side": desired_side,
                                        "entry_signal_id": None,
                                        "entry_time": datetime.now(timezone.utc),
                                        "bars_in_trade": 0,
                                        "entry_cost": notional_rev * 0.00035 if notional_rev else 0.0,
                                        "entry_price": entry_px,
                                        "size": (notional_rev / entry_px) if entry_px else 0.0,
                                        "best_price": entry_px,
                                        "trail_active": False,
                                        "mintick": mintick,
                                        "stop_loss": ec.get("stop_loss_long") if desired_side == "LONG" else ec.get("stop_loss_short"),
                                        "take_profit": ec.get("take_profit_long") if desired_side == "LONG" else ec.get("take_profit_short"),
                                    }
                                    add_log(
                                        f"[{self.instance.token}] RE-ENTRY {desired_side} @ {entry_px:.6f} (reversal from {exit_reason}) | "
                                        f"SL={self._active_trade['stop_loss']} TP={self._active_trade['take_profit']}",
                                        "trade", dry_run=self.instance.dry_run,
                                    )
                                    trade_active = True

            # bars_in_trade now incremented on new bar close (above), not every poll

            # Update instance position cache AFTER reconcile/adopt so
            # adopted positions are reflected in the dashboard in real-time.
            # If position is None but we have an active trade (HL API thread issue),
            # use tracked _active_trade data so the dashboard still shows the position.
            if position is None and self._active_trade:
                at = self._active_trade
                self._update_position_cache_from_tracked(at)
            else:
                self._update_position_cache(position, current_side)

            # Record signal AFTER execution so trade_active/executed are accurate
            signal_row = Signal(
                instance_id=self.id,
                direction=direction,
                signal=signal_val,
                trade_active=trade_active,
                executed=executed,
                metadata_json=metadata,
                reasoning_text=reasoning_text,
                dry_run=self.instance.dry_run,
            )
            db.add(signal_row)
            db.commit()
            if self._active_trade and self._active_trade["entry_signal_id"] is None:
                self._active_trade["entry_signal_id"] = signal_row.id
            self._last_signal = signal_row

            # Log signal + state
            state_label = "IN TRADE" if trade_active else "IDLE"
            add_log(
                f"[{self.instance.token}] {direction} signal (strength={signal_val:.2f}) | {state_label}",
                "signal" if direction != "NEUTRAL" else "info", dry_run=self.instance.dry_run,
            )
            if reasoning_text:
                add_log(f"[{self.instance.token}] reasoning: {reasoning_text}", "info", dry_run=self.instance.dry_run)

            # Persist position snapshot
            self._sync_position(db, position, current_side)

            # Emit event for UI
            event_bus.emit(
                {
                    "type": "signal",
                    "instance_id": self.id,
                    "token": self.instance.token,
                    "direction": direction,
                    "signal": signal_val,
                    "trade_active": trade_active,
                    "executed": executed,
                    "metadata": metadata,
                }
            )

            # Update instance status
            # FIX: do NOT db.merge(self.instance) — that re-persists the stale
            # in-memory dry_run (and other operator config) every tick, clobbering
            # a LIVE/PAPER change made via PUT while the engine is running.
            # Instead, reload the row and copy ONLY runner-owned fields.
            db_inst = db.query(Instance).filter(Instance.slug == self.id).first()
            if db_inst is not None:
                db_inst.status = "running"
                db_inst.updated_at = datetime.now(timezone.utc)
                # runner-owned position cache (preserve operator dry_run/strategy/etc.)
                for _f in ("position_side", "position_size", "entry_price", "mark_price",
                           "unrealized_pnl", "unrealized_pnl_pct", "liquidation_price",
                           "last_signal", "last_signal_strength", "last_reasoning"):
                    if hasattr(self.instance, _f):
                        setattr(db_inst, _f, getattr(self.instance, _f))
                db.commit()
            else:
                self.instance.status = "running"
                self.instance.updated_at = datetime.now(timezone.utc)
                db.merge(self.instance)
                db.commit()

        finally:
            db.close()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _update_position_cache_from_tracked(self, at: dict):
        """Fallback: update Instance cache from tracked _active_trade data
        when HL API returns None inside the daemon thread."""
        db = Session()
        try:
            inst = db.query(Instance).filter(Instance.slug == self.id).first()
            if not inst:
                return
            inst.position_side = at.get("side")
            inst.position_size = float(at.get("size", 0))
            inst.entry_price = float(at.get("entry_price", 0))
            inst.mark_price = float(at.get("best_price", 0)) or inst.entry_price
            inst.unrealized_pnl = 0.0  # unknown without live position
            inst.unrealized_pnl_pct = 0.0
            db.commit()
        except Exception as e:
            print(f"[WARN] _update_position_cache_from_tracked failed: {e}")
        finally:
            db.close()

    def _derive_side(self, position):
        if not position:
            return None
        szi = float(position.get("szi", 0))
        if szi > 0:
            return "LONG"
        if szi < 0:
            return "SHORT"
        return None

    # ------------------------------------------------------------------
    # Position sync
    # ------------------------------------------------------------------
    def _update_position_cache(self, position, current_side):
        """Update the Instance row with live position fields for API/UI display.

        When position is None due to HL API failure (not confirmed flat),
        do NOT clear the cache — leave existing values so the dashboard
        keeps showing the last known position state.
        """
        db = Session()
        try:
            inst = db.query(Instance).filter(Instance.slug == self.id).first()
            if not inst:
                return
            if position:
                szi = float(position.get("szi", 0))
                inst.position_side = current_side
                inst.position_size = abs(szi)
                inst.entry_price = float(position.get("entryPx", 0))
                inst.mark_price = float(position.get("markPx", 0)) if "markPx" in position else inst.entry_price
                inst.unrealized_pnl = float(position.get("unrealizedPnl", 0))
                inst.unrealized_pnl_pct = float(position.get("returnOnEquity", 0)) * 100
                add_log(
                    f"[{self.instance.token}] Position cache: {current_side} {abs(szi)} @ {inst.entry_price:.6f} pnl=${inst.unrealized_pnl:.4f}",
                    "info", dry_run=self.instance.dry_run,
                )
            elif current_side is None:
                # Position is None — could be API failure or genuinely flat.
                # Only clear if we have no active trade (confirmed flat).
                # If _active_trade exists, keep the cache as-is (HL API issue).
                if not self._active_trade:
                    inst.position_side = None
                    inst.position_size = 0.0
                    inst.entry_price = 0.0
                    inst.mark_price = 0.0
                    inst.unrealized_pnl = 0.0
                    inst.unrealized_pnl_pct = 0.0
            db.commit()
        finally:
            db.close()

    def _sync_position(self, db, position, current_side):
        """Sync position from HL exchange to DB — update both snapshot AND Instance model.

        PITFALL: When position is None but _active_trade says we have a position,
        this is likely a stale HL client (not a genuine flat). Do NOT clear the
        Instance model in that case — _update_position_cache_from_tracked will
        preserve the last known position data instead. Only clear when we're
        genuinely flat (no active trade, no position on exchange).
        """
        # Update Instance model fields (read by dashboard/frontend)
        inst = db.query(Instance).filter(Instance.slug == self.id).first()
        if inst:
            if not position or not current_side:
                # Only clear position fields if we're genuinely flat (no tracked trade).
                # If _active_trade exists, position=None is likely a stale client,
                # not a genuine flat — keep existing values for dashboard display.
                if not self._active_trade:
                    inst.position_side = None
                    inst.position_size = 0.0
                    inst.entry_price = 0.0
                    inst.unrealized_pnl = 0.0
                    inst.unrealized_pnl_pct = 0.0
                    inst.liquidation_price = 0.0
                    inst.stop_loss = None
                    inst.take_profit = None
            else:
                szi = float(position.get("szi", 0))
                entry_px = float(position.get("entryPx", 0))
                # HL doesn't always include markPx; compute from positionValue / szi
                raw_mark = float(position.get("markPx", 0)) if position.get("markPx") else 0.0
                pos_val = float(position.get("positionValue", 0)) if position.get("positionValue") else 0.0
                if raw_mark > 0:
                    mark_px = raw_mark
                elif pos_val > 0 and abs(szi) > 0:
                    mark_px = pos_val / abs(szi)
                else:
                    mark_px = entry_px
                pnl = float(position.get("unrealizedPnl", 0))
                pnl_pct = float(position.get("returnOnEquity", 0)) * 100
                liq_px = float(position.get("liquidationPx", 0)) if position.get("liquidationPx") else 0.0

                inst.position_side = current_side
                inst.position_size = abs(szi)
                inst.entry_price = entry_px
                inst.mark_price = mark_px
                inst.unrealized_pnl = pnl
                inst.unrealized_pnl_pct = pnl_pct
                inst.liquidation_price = liq_px

                # Save SL/TP from tracked trade (if active)
                if self._active_trade:
                    inst.stop_loss = self._active_trade.get("stop_loss")
                    inst.take_profit = self._active_trade.get("take_profit")

                # Also save snapshot for history
                snap = PositionSnapshot(
                    instance_id=self.id,
                    side=current_side,
                    size=abs(szi),
                    entry_price=entry_px,
                    mark_price=mark_px,
                    unrealized_pnl_usd=pnl,
                    unrealized_pnl_pct=pnl_pct,
                )
                db.add(snap)
            db.commit()

    # ------------------------------------------------------------------
    # Trade execution
    # ------------------------------------------------------------------
    def _execute_open(
        self,
        db,
        hl,
        desired_side: str,
        account_value: float,
        position,
        signal_result: dict,
    ) -> Tuple[bool, float]:
        """Open a new position when flat. Mirrors PineScript strategy.entry."""
        # Bug #7 fix: removed redundant max_notional / min() check.
        # notional_from_free_balance already computes the same formula
        # (balance * leverage * max_position_pct). The guard below is kept
        # as an early bail for zero/negative values.
        max_notional = account_value * self.instance.leverage * self.instance.max_position_pct
        if max_notional <= 0:
            add_log(f"[{self.instance.token}] Position limit blocks {desired_side}: no notional allowance", "warn", dry_run=self.instance.dry_run)
            return False, 0.0

        notional = PositionSizer.notional_from_free_balance(
            account_value,
            self.instance.leverage,
            self.instance.max_position_pct,
        )
        if notional <= 0:
            add_log(f"[RUNNER {self.id}] Insufficient balance to open {desired_side}", "warn", dry_run=self.instance.dry_run)
            return False, 0.0

        # Bug #1 fix: generate cloid once so retries get the same id
        # (retry_with_backoff re-enters market_open on failure, and without
        # a stable cloid each retry would create a different order)
        open_cloid = hl._make_cloid(self.instance.token, "open",
                                     stable_id=str(int(time.time() * 1000)))

        open_result = hl.market_open(
            self.instance.token,
            side=desired_side.lower(),
            size_usd=notional,
            leverage=self.instance.leverage,
            cloid=open_cloid,
        )
        entry_cost = notional * 0.00035  # taker fee estimate
        dr = getattr(hl, "dry_run", False)
        add_log(
            f"[{self.instance.token}] {'[DRY RUN] ' if dr else ''}OPEN {desired_side} ${notional:.2f} "
            f"cost=${entry_cost:.4f} (ok={open_result is not None})",
            "trade", dry_run=self.instance.dry_run,
        )
        event_bus.emit(
            {
                "type": "trade",
                "instance_id": self.id,
                "token": self.instance.token,
                "action": "OPEN",
                "side": desired_side,
                "notional": notional,
            }
        )
        # D2(a): record a dedicated OPEN row so the trades table has the entry
        # lifecycle (entry time/size/side) before close. exit_price NULL until
        # _close_active_trade writes its own close-row. user_id for multi-tenant.
        # size/entry_price are filled by the close-row (D1) once HL returns the
        # real fill; this row captures the open event + side + entry cost.
        if open_result is not None:
            open_trade = Trade(
                instance_id=self.id,
                user_id=self.instance.user_id,
                side=desired_side,
                size=0.0,
                entry_price=None,
                exit_price=None,
                pnl_usd=0.0,
                pnl_pct=0.0,
                entry_cost=entry_cost,
                exit_cost=0.0,
                price_diff=0.0,
                signal_id=None,
                dry_run=self.instance.dry_run,
            )
            db.add(open_trade)
            db.commit()
        return open_result is not None, entry_cost

    def _execute_close(
        self,
        db,
        hl,
        current_side: str,
        position,
        exit_reason: str,
    ) -> Tuple[bool, float]:
        """Close the active position. Mirrors PineScript strategy.close_all."""
        # Estimate exit cost from current notional before closing.
        # Bug #2/#4 fix: three-tier fallback so exit_cost never stays $0.
        # Tier 1: live position from exchange (most accurate)
        # Tier 2: tracked _active_trade dict (adopted/reconciled positions)
        # Tier 3: recorded entry_cost from _active_trade as last resort
        notional = 0.0
        if position:
            mark_px = float(position.get("markPx", 0)) or float(position.get("entryPx", 0))
            szi = float(position.get("szi", 0))
            notional = abs(szi) * mark_px
        elif self._active_trade:
            mark_px = float(self._active_trade.get("best_price", 0)) or float(self._active_trade.get("entry_price", 0))
            notional = abs(self._active_trade.get("size", 0)) * mark_px
        # Tier 3: if notional is still 0, use entry_cost as a floor estimate
        if notional <= 0 and self._active_trade and self._active_trade.get("entry_cost", 0) > 0:
            notional = self._active_trade["entry_cost"] / 0.00035  # reverse the fee to get rough notional
            add_log(
                f"[RUNNER {self.id}] exit_cost fallback: using entry_cost ${self._active_trade['entry_cost']:.4f} "
                f"→ estimated notional ${notional:.2f}",
                "warn", dry_run=self.instance.dry_run,
            )
        exit_cost = notional * 0.00035  # taker fee estimate

        # Bug #1 fix: generate cloid once so retries get the same id
        close_cloid = hl._make_cloid(self.instance.token, "close",
                                      stable_id=str(int(time.time() * 1000)))

        close_result = hl.market_close(self.instance.token, cloid=close_cloid)
        dr = getattr(hl, "dry_run", False)
        add_log(
            f"[{self.instance.token}] {'[DRY RUN] ' if dr else ''}CLOSE {current_side} reason={exit_reason} "
            f"cost=${exit_cost:.4f} (ok={close_result is not None})",
            "trade", dry_run=self.instance.dry_run,
        )
        event_bus.emit(
            {
                "type": "trade",
                "instance_id": self.id,
                "token": self.instance.token,
                "action": "CLOSE",
                "side": current_side,
            }
        )
        return close_result is not None, exit_cost

    def _close_active_trade(self, db, position, reason: str, entry_cost: float = 0.0, exit_cost: float = 0.0):
        """Record the closing trade row and position snapshot after exit.

        Falls back to self._active_trade data when position is None (HL already
        cleared the position) so the Trade record is never lost.
        Queries HL user_fills for the actual exit price and closed PnL.
        """
        # Prefer live position data; fall back to tracked active trade
        if position:
            entry_px = float(position.get("entryPx", 0))
            mark_px = float(position.get("markPx", 0)) if "markPx" in position else entry_px
            pnl = float(position.get("unrealizedPnl", 0))
            pnl_pct = float(position.get("returnOnEquity", 0)) * 100
            szi = float(position.get("szi", 0))
            side = "LONG" if szi > 0 else "SHORT"
            size = abs(szi)
        elif self._active_trade:
            # HL already cleared the position — use tracked data + query fills
            at = self._active_trade
            entry_px = float(at.get("entry_price", 0))
            mark_px = float(at.get("best_price", 0)) or entry_px
            size = float(at.get("size", 0))
            side = at.get("side", "LONG")
            pnl = 0.0
            pnl_pct = 0.0

            if self.instance.dry_run:
                # Direct mathematical calculation for paper trading
                raw_pnl = (mark_px - entry_px) / entry_px if entry_px > 0 else 0.0
                if side == "SHORT":
                    raw_pnl = -raw_pnl
                pnl_pct = raw_pnl * self.instance.leverage * 100
                pnl = (size * entry_px) * raw_pnl * self.instance.leverage - (entry_cost + exit_cost)
            else:
                # Query HL user_fills for the actual exit price and closed PnL
                try:
                    from core.exchange import hl_client as _global_hl
                    fills = _global_hl._info.user_fills(_global_hl._query_address())
                    token_fills = [f for f in fills if f.get("coin") == self.instance.token]
                    if token_fills:
                        last_fill = token_fills[-1]
                        fill_px = float(last_fill.get("px", 0))
                        fill_pnl = float(last_fill.get("closedPnl", 0))
                        if fill_px > 0:
                            mark_px = fill_px
                        if fill_pnl != 0:
                            pnl = fill_pnl
                        add_log(
                            f"[{self.instance.token}] Exit fill from HL: px={fill_px:.6f} pnl=${fill_pnl:.4f}",
                            "info", dry_run=self.instance.dry_run,
                        )
                except Exception as e:
                    print(f"[WARN] Could not fetch exit fill from HL: {e}")
        else:
            add_log(f"[{self.instance.token}] Trade closed: {reason} (no position data)", "info")
            return

        if self.instance.dry_run:
            self._paper_balance += pnl
            self._equity_history.append(self._paper_balance)
            if len(self._equity_history) > 100:
                self._equity_history = self._equity_history[-100:]

        trade = Trade(
            instance_id=self.id,
            user_id=self.instance.user_id,  # D1/FE-1: attribute trade to owning user (multi-tenant)
            side=side,
            size=size,
            entry_price=entry_px,
            exit_price=mark_px,
            pnl_usd=pnl,
            pnl_pct=pnl_pct,
            entry_cost=entry_cost,
            exit_cost=exit_cost,
            price_diff=(mark_px - entry_px),
            dry_run=self.instance.dry_run,
        )
        db.add(trade)
        db.commit()
        add_log(f"[{self.instance.token}] Trade closed: {reason} | {side} {size:.4f} PnL=${pnl:.4f}", "info", dry_run=self.instance.dry_run)

    def _evaluate_exit(
        self,
        signal_result: dict,
        active_trade: dict,
        position,
        bar_high: float = 0.0,
        bar_low: float = 0.0,
    ) -> Optional[str]:
        """
        Evaluate exit conditions mirroring PineScript.
        Reads from exit_config (strategy-declared exits) only.
        No fabricated exits. Neutral consumer.

        Pine exit order:
            1. Stop Loss     - strategy.exit(stop=)
            2. Trailing Stop - strategy.exit(trail_points, trail_offset)
            3. Take Profit   - strategy.exit(limit=) if useFixedTP (v1.3 only)
            4. Trend Change  - ta.crossunder/crossover → strategy.close_all()
            5. Time Exit     - if use_time_exit and engine_mode == Scalp (v1.3 only)

        NOT evaluated (not in any PineScript):
            - Full fan alignment against position (fabricated, removed)
            - Reversal signal / opposite entry (fabricated, removed)
        """
        ec = signal_result.get("exit_config", {}) or {}
        side = active_trade["side"]
        bars_in_trade = active_trade["bars_in_trade"]

        # 1. Stop-loss: candle high/low touches static entry stop level from active_trade
        sl = active_trade.get("stop_loss")
        if sl is not None:
            if side == "LONG" and bar_low <= float(sl):
                return "Stop Loss"
            elif side == "SHORT" and bar_high >= float(sl):
                return "Stop Loss"

        # 2. Trailing stop — EXACT PineScript semantics.
        # Pine: strategy.exit(trail_points=activeActivation, trail_offset=activeOffset)
        #   - trail_points  = TRAILING DISTANCE (stop sits trail_points ticks below running peak)
        #   - trail_offset  = ACTIVATION MOVE (price must travel this far from entry before trailing engages)
        # Pine trails from entry (calc_on_every_tick=true); no extra gate beyond trail_offset.
        mintick = float(active_trade.get("mintick", 0.00001))
        # NOTE: v1_3 emits exit_config.trail_activation == Pine's trail_points (distance)
        #       and exit_config.trail_offset    == Pine's trail_offset (activation move).
        trail_dist = float(ec.get("trail_activation", 0))   # distance (Pine trail_points)
        trail_act_move = float(ec.get("trail_offset", 0))   # activation move (Pine trail_offset)
        if trail_dist > 0:
            # Track running peak from entry (Pine trails the highest-high since entry).
            if side == "LONG":
                if bar_high > active_trade.get("best_price", 0):
                    active_trade["best_price"] = bar_high
                # Activation: price must move trail_act_move ticks beyond entry first.
                activated = (bar_high >= active_trade["entry_price"] + trail_act_move * mintick)
                if activated:
                    trail_stop = active_trade["best_price"] - trail_dist * mintick
                    if bar_low <= trail_stop:
                        return "Trailing Stop"
            else:  # SHORT
                if bar_low < active_trade.get("best_price", float("inf")):
                    active_trade["best_price"] = bar_low
                activated = (bar_low <= active_trade["entry_price"] - trail_act_move * mintick)
                if activated:
                    trail_stop = active_trade["best_price"] + trail_dist * mintick
                    if bar_high >= trail_stop:
                        return "Trailing Stop"

        # 3. Take-profit: candle high/low touches static entry take-profit level from active_trade
        tp = active_trade.get("take_profit")
        if tp is not None:
            if side == "LONG" and bar_high >= float(tp):
                return "Take Profit"
            elif side == "SHORT" and bar_low <= float(tp):
                return "Take Profit"

        # 4. EMA-cross trend reversal (bar-to-bar, not poll-to-poll)
        prev_f = self._prev_fast_ema
        prev_m = self._prev_medm_ema
        curr_f = ec.get("fast_ema")
        curr_m = ec.get("medm_ema")
        if prev_f is not None and prev_m is not None and curr_f is not None and curr_m is not None:
            if side == "LONG" and prev_f >= prev_m and curr_f < curr_m:
                return "Trend Change"
            if side == "SHORT" and prev_f <= prev_m and curr_f > curr_m:
                return "Trend Change"

        # 5. Time-based exit (if strategy declares it)
        use_time_exit = ec.get("use_time_exit", False)
        if use_time_exit:
            max_bars = ec.get("time_exit_bars")
            if max_bars and bars_in_trade >= max_bars:
                return "Time Exit"

        return None

    def _execute_flip(
        self,
        db,
        hl,
        current_side: Optional[str],
        desired_side: str,
        account_value: float,
        position,
    ) -> bool:
        """Legacy flip helper (kept for API compatibility)."""
        if current_side:
            self._execute_close(db, hl, current_side, position, "legacy_flip")
        opened, _ = self._execute_open(db, hl, desired_side, account_value, position, {})
        return opened

    # ------------------------------------------------------------------
    # Account snapshot
    # ------------------------------------------------------------------
    def _record_account(self, db, account_value: float, withdrawable: float):
        if self.instance.dry_run:
            account_value = self._paper_balance
            withdrawable = self._paper_balance

        # B2: record every tick (no anomaly filter). The >50% swing skip
        # created visual gaps in the pulse graph — operator directive: gaps are
        # the bug, not the wild value. source stamps this row so the pulse/KPI
        # (B4) can filter perp-native vs total consistently.
        snap = AccountSnapshot(
            instance_id=self.id,
            user_id=self.instance.user_id,
            account_value=account_value,
            withdrawable=withdrawable,
            dry_run=self.instance.dry_run,
            source="paper" if self.instance.dry_run else "perp",
        )
        db.add(snap)
        db.commit()

    # ------------------------------------------------------------------
    # Status persistence
    # ------------------------------------------------------------------
    def _persist_status(self, instance, status: str):
        """Persist only the runner status to the DB.

        Uses a fresh query by slug and writes ONLY the status column. This
        prevents a stale in-memory instance object (loaded before a PUT
        changed timeframe/leverage/dry_run) from clobbering operator-set fields.
        """
        db = Session()
        try:
            db_inst = db.query(Instance).filter(Instance.slug == instance.slug).first()
            if db_inst is None:
                return
            db_inst.status = status
            db.commit()
        finally:
            db.close()
