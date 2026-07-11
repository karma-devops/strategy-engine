"""
Single strategy instance runner.
Polls candles, generates signal, executes trades, records state.
Runner is created stopped; manager must call .start() explicitly.
"""

import threading
import traceback
from datetime import datetime, timezone
from typing import Optional, Tuple

from sqlalchemy.orm import sessionmaker

from config import config
from engine.registry import get_strategy
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
        add_log(f"[RUNNER {self.id}] Started for {self.instance.token}", "info")

        strategy_class = get_strategy(self.instance.strategy_id)
        if not strategy_class:
            print(f"[RUNNER {self.id}] Unknown strategy {self.instance.strategy_id}")
            add_log(f"Unknown strategy {self.instance.strategy_id}", "error")
            self.instance.status = "error"
            self._persist_status(self.instance, "error")
            return

        strategy = strategy_class()
        hl = self._hl

        while not self._stop_event.is_set():
            try:
                self._tick(strategy, hl)
            except Exception as e:
                print(f"[RUNNER {self.id}] Tick error: {e}")
                traceback.print_exc()
                add_log(f"Tick error in {self.instance.token}: {e}", "error")
            self._stop_event.wait(self.instance.poll_interval_seconds)

        print(f"[RUNNER {self.id}] Stopped")
        add_log(f"[RUNNER {self.id[:8]}] Stopped for {self.instance.token}", "info")

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
                add_log(f"[RUNNER {self.id}] No candles for {self.instance.token}", "warn")
                return

            # Generate signal
            result = strategy.generate_signals(df, symbol=self.instance.token)
            direction = result.get("direction", "NEUTRAL")
            signal_val = result.get("signal", 0.0)
            metadata = result.get("metadata", {}) or {}

            # Sync position from exchange (source of truth)
            position = hl.get_position(self.instance.token)
            current_side = self._derive_side(position)
            trade_active = bool(current_side)

            # Update instance position cache
            self._update_position_cache(position, current_side)

            # Reconcile local active-trade tracker with exchange position
            if current_side is None and self._active_trade is not None:
                # Position was closed externally / by TP/SL/trailing
                self._close_active_trade(db, position, "exit")
                self._active_trade = None
            elif current_side and self._active_trade is None:
                # Position exists but we didn't track entry (e.g. restart) — adopt it
                self._active_trade = {
                    "side": current_side,
                    "entry_signal_id": None,
                    "entry_time": datetime.now(timezone.utc),
                    "bars_in_trade": 0,
                }
            elif current_side and self._active_trade and current_side != self._active_trade["side"]:
                # Side flipped externally — adopt new side
                self._active_trade = {
                    "side": current_side,
                    "entry_signal_id": None,
                    "entry_time": datetime.now(timezone.utc),
                    "bars_in_trade": 0,
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
                if desired_side:
                    executed, entry_cost = self._execute_open(db, hl, desired_side, account_value, position, result)
                    if executed:
                        self._active_trade = {
                            "side": desired_side,
                            "entry_signal_id": None,
                            "entry_time": datetime.now(timezone.utc),
                            "bars_in_trade": 0,
                            "entry_cost": entry_cost,
                        }
                        trade_active = True
            else:
                # In a trade: check exit conditions
                exit_reason = self._evaluate_exit(result, self._active_trade, position)
                if exit_reason:
                    closed, exit_cost = self._execute_close(db, hl, self._active_trade["side"], position, exit_reason)
                    if closed:
                        recorded_entry_cost = self._active_trade.get("entry_cost", 0.0)
                        self._close_active_trade(db, position, exit_reason, entry_cost=recorded_entry_cost, exit_cost=exit_cost)
                        self._active_trade = None
                        trade_active = current_side is not None
                        executed = True

            # Increment bars-in-trade counter
            if self._active_trade:
                self._active_trade["bars_in_trade"] += 1

            # Record signal AFTER execution so trade_active/executed are accurate
            signal_row = Signal(
                instance_id=self.id,
                direction=direction,
                signal=signal_val,
                trade_active=trade_active,
                executed=executed,
                metadata_json=metadata,
                reasoning_text=reasoning_text,
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
                "signal" if direction != "NEUTRAL" else "info",
            )
            if reasoning_text:
                add_log(f"[{self.instance.token}] reasoning: {reasoning_text}", "info")

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
        """Update the Instance row with live position fields for API/UI display."""
        db = Session()
        try:
            inst = db.query(Instance).filter(Instance.slug == self.id).first()
            if not inst:
                return
            inst.position_side = current_side
            if position:
                szi = float(position.get("szi", 0))
                inst.position_size = abs(szi)
                inst.entry_price = float(position.get("entryPx", 0))
                inst.mark_price = float(position.get("markPx", 0)) if "markPx" in position else inst.entry_price
                inst.unrealized_pnl = float(position.get("unrealizedPnl", 0))
                inst.unrealized_pnl_pct = float(position.get("returnOnEquity", 0)) * 100
            else:
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
        max_notional = account_value * self.instance.leverage * self.instance.max_position_pct
        if max_notional <= 0:
            add_log(f"[{self.instance.token}] Position limit blocks {desired_side}: no notional allowance", "warn")
            return False, 0.0

        notional = PositionSizer.notional_from_free_balance(
            account_value,
            self.instance.leverage,
            self.instance.max_position_pct,
        )
        if notional <= 0:
            add_log(f"[RUNNER {self.id}] Insufficient balance to open {desired_side}", "warn")
            return False, 0.0
        notional = min(notional, max_notional)

        open_result = hl.market_open(
            self.instance.token,
            side=desired_side.lower(),
            size_usd=notional,
            leverage=self.instance.leverage,
        )
        entry_cost = notional * 0.00035  # taker fee estimate
        add_log(
            f"[{self.instance.token}] OPEN {desired_side} ${notional:.2f} cost=${entry_cost:.4f} (ok={open_result is not None})",
            "trade",
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
        # Estimate exit cost from current notional before closing
        notional = 0.0
        if position:
            mark_px = float(position.get("markPx", 0)) or float(position.get("entryPx", 0))
            szi = float(position.get("szi", 0))
            notional = abs(szi) * mark_px
        exit_cost = notional * 0.00035  # taker fee estimate

        close_result = hl.market_close(self.instance.token)
        add_log(
            f"[{self.instance.token}] CLOSE {current_side} reason={exit_reason} cost=${exit_cost:.4f} (ok={close_result is not None})",
            "trade",
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
        """Record the closing trade row and position snapshot after exit."""
        if position:
            entry_px = float(position.get("entryPx", 0))
            mark_px = float(position.get("markPx", 0)) if "markPx" in position else entry_px
            pnl = float(position.get("unrealizedPnl", 0))
            pnl_pct = float(position.get("returnOnEquity", 0)) * 100
            szi = float(position.get("szi", 0))
            trade = Trade(
                instance_id=self.id,
                side="LONG" if szi > 0 else "SHORT",
                size=abs(szi),
                entry_price=entry_px,
                exit_price=mark_px,
                pnl_usd=pnl,
                pnl_pct=pnl_pct,
                entry_cost=entry_cost,
                exit_cost=exit_cost,
                price_diff=(mark_px - entry_px),
            )
            db.add(trade)
            db.commit()
        add_log(f"[{self.instance.token}] Trade closed: {reason}", "info")

    def _evaluate_exit(
        self,
        signal_result: dict,
        active_trade: dict,
        position,
    ) -> Optional[str]:
        """
        Evaluate exit conditions mirroring PineScript:
        - Trend reversal (EMA cross against position)
        - Time-based exit (scalp only, if enabled)
        - Future: stop-loss / take-profit / trailing activation-offset
        Returns exit reason string or None.
        """
        metadata = signal_result.get("metadata", {}) or {}
        direction = signal_result.get("direction", "NEUTRAL")
        side = active_trade["side"]
        bars_in_trade = active_trade["bars_in_trade"]

        # Trend reversal: fan/EMA cross against current position
        if side == "LONG" and metadata.get("fan_dn_trend"):
            return "Trend Change"
        if side == "SHORT" and metadata.get("fan_up_trend"):
            return "Trend Change"

        # Time-based exit (scalp only)
        engine_mode = metadata.get("engine_mode", "")
        use_time_exit = metadata.get("use_time_exit", False)
        max_bars = metadata.get("time_exit_bars")
        if engine_mode == "Scalp" and use_time_exit and max_bars and bars_in_trade >= max_bars:
            return "Time Exit"

        # Opposite entry signal while in trade acts as reversal close in this implementation
        if side == "LONG" and direction == "SELL":
            return "Reversal Signal"
        if side == "SHORT" and direction == "BUY":
            return "Reversal Signal"

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
        snap = AccountSnapshot(
            instance_id=self.id,
            account_value=account_value,
            withdrawable=withdrawable,
        )
        db.add(snap)
        db.commit()

    # ------------------------------------------------------------------
    # Status persistence
    # ------------------------------------------------------------------
    def _persist_status(self, instance, status: str):
        db = Session()
        try:
            instance.status = status
            db.merge(instance)
            db.commit()
        finally:
            db.close()
