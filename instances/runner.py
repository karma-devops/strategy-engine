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
from engine.registry import get_strategy, detect_mintick
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
        self._equity_history: list = []  # closed-trade equity values for adaptive strategy
        self._hl = get_hyperliquid_client(instance)

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

        while not self._stop_event.is_set():
            try:
                self._tick(strategy, hl)
            except Exception as e:
                print(f"[RUNNER {self.id}] Tick error: {e}")
                traceback.print_exc()
                add_log(f"Tick error in {self.instance.token}: {e}", "error", dry_run=self.instance.dry_run)
            self._stop_event.wait(self.instance.poll_interval_seconds)

        print(f"[RUNNER {self.id}] Stopped")
        add_log(f"[RUNNER {self.id[:8]}] Stopped for {self.instance.token}", "info", dry_run=self.instance.dry_run)

    def _tick(self, strategy, hl):
        db = Session()
        try:
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

            # Sync position from exchange (source of truth)
            position = hl.get_position(self.instance.token)
            if position is None and hl.has_credentials:
                # Runner's HL client may have a stale HTTP connection in the
                # daemon thread. Create a fresh Info query to bypass it.
                try:
                    from core.exchange import HyperLiquidClient
                    _fresh = HyperLiquidClient(
                        private_key=None,  # falls back to config env
                        account_address=self.instance.get_account_address(),
                        dry_run=self.instance.dry_run,
                    )
                    position = _fresh.get_position(self.instance.token)
                except Exception:
                    pass
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
            if self._active_trade is None:
                # Flat: enter on a fresh entry signal
                # Pine: bar_index > lastEntryBar — one entry per bar
                current_bar_time = df["timestamp"].iloc[-1] if "timestamp" in df.columns else None
                if desired_side and (self._last_entry_bar_time is None or current_bar_time != self._last_entry_bar_time):
                    executed, entry_cost = self._execute_open(db, hl, desired_side, account_value, position, result)
                    if executed:
                        # Strategy exit_config is read at exit time (neutral receiver)
                        ec = result.get("exit_config", {}) or {}
                        entry_px = float(position.get("entryPx", 0)) if position else 0.0
                        # Detect mintick from HL API markPx precision (authoritative)
                        mintick = detect_mintick(df=df, token=self.instance.token)
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
        if not position or not current_side:
            return

        szi = float(position.get("szi", 0))
        entry_px = float(position.get("entryPx", 0))
        mark_px = float(position.get("markPx", 0)) if "markPx" in position else entry_px
        pnl = float(position.get("unrealizedPnl", 0))
        pnl_pct = float(position.get("returnOnEquity", 0)) * 100

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

        trade = Trade(
            instance_id=self.id,
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

        # 1. Stop-loss: candle high/low touches strategy stop level
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
        # Filter anomalous snapshots: HL API can return wild values during
        # position transitions (margin held/released) that produce fake drawdowns.
        # Skip recording if value swings >50% from last known good value.
        if hasattr(self, "_last_good_account_value") and self._last_good_account_value > 0:
            ratio = account_value / self._last_good_account_value
            if ratio < 0.5 or ratio > 2.0:
                add_log(
                    f"[{self.instance.token}] Skipping anomalous account snapshot: "
                    f"${account_value:.2f} vs last ${self._last_good_account_value:.2f} (ratio={ratio:.2f})",
                    "warn", dry_run=self.instance.dry_run,
                )
                return
        # Record good values
        if account_value > 0:
            self._last_good_account_value = account_value
        snap = AccountSnapshot(
            instance_id=self.id,
            account_value=account_value,
            withdrawable=withdrawable,
            dry_run=self.instance.dry_run,
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
