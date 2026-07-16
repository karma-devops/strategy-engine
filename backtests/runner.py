"""
Historical backtest runner for strategy-engine.

Simulates trades on OHLCV data using an engine strategy. No HyperLiquid
orders are sent. Market orders are assumed to fill at the close of the
candle that produced the signal.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd

from core.market_data import HyperLiquidMarketData
from engine.registry import get_strategy
from instances.models import CandleCache, SessionLocal


# Estimated trading costs for HyperLiquid perps (taker-heavy scalp/swing).
MAKER_FEE = 0.0001   # 0.01% (HL maker)
TAKER_FEE = 0.00045  # 0.045% (HL taker for perps)


@dataclass
class BacktestTrade:
    entry_bar: int
    entry_time: datetime
    entry_price: float
    side: str  # LONG or SHORT
    exit_bar: int | None = None
    exit_time: datetime | None = None
    exit_price: float | None = None
    pnl_pct: float = 0.0
    pnl_usd: float = 0.0
    bars_held: int = 0
    qty: float = 0.0
    position_size: float = 0.0
    stop_loss_price: float | None = None
    trail_activation: float = 0.0
    trail_offset: float = 0.0
    best_price: float = 0.0
    trail_active: bool = False
    trail_stop_price: float | None = None


@dataclass
class BacktestResult:
    id: str
    instance_slug: str
    token: str
    strategy_id: str
    timeframe: str
    mode: str
    profile: str
    activation: int
    offset: int
    leverage: int
    start_date: datetime
    end_date: datetime
    initial_capital: float
    final_capital: float
    total_return_pct: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    max_drawdown_pct: float = 0.0
    total_trades: int = 0
    sharpe_ratio: float = 0.0
    trades: list[BacktestTrade] = field(default_factory=list)
    equity_curve: list[dict] = field(default_factory=list)
    error_message: str | None = None
    status: str = "done"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "instance_slug": self.instance_slug,
            "token": self.token,
            "strategy_id": self.strategy_id,
            "timeframe": self.timeframe,
            "mode": self.mode,
            "profile": self.profile,
            "activation": self.activation,
            "offset": self.offset,
            "leverage": self.leverage,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "initial_capital": self.initial_capital,
            "final_capital": self.final_capital,
            "total_return_pct": self.total_return_pct,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "max_drawdown_pct": self.max_drawdown_pct,
            "total_trades": self.total_trades,
            "sharpe_ratio": self.sharpe_ratio,
            "trades": [
                {
                    "entry_bar": t.entry_bar,
                    "entry_time": t.entry_time.isoformat() if t.entry_time else None,
                    "entry_price": t.entry_price,
                    "side": t.side,
                    "exit_bar": t.exit_bar,
                    "exit_time": t.exit_time.isoformat() if t.exit_time else None,
                    "exit_price": t.exit_price,
                    "pnl_pct": t.pnl_pct,
                    "pnl_usd": t.pnl_usd,
                    "bars_held": t.bars_held,
                    "qty": t.qty,
                    "position_size": t.position_size,
                    "stop_loss_price": t.stop_loss_price,
                }
                for t in self.trades
            ],
            "equity_curve": self.equity_curve,
            "error_message": self.error_message,
            "status": self.status,
        }


def _calculate_metrics(equity_curve: list[float], trades: list[BacktestTrade]) -> dict:
    """Compute return, drawdown, win rate, profit factor, sharpe."""
    initial = equity_curve[0] if equity_curve else 1.0
    final = equity_curve[-1] if equity_curve else initial
    total_return_pct = ((final / initial) - 1.0) * 100.0 if initial > 0 else 0.0

    # Max drawdown
    peak = initial
    max_dd = 0.0
    for eq in equity_curve:
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd

    # Win rate / profit factor
    wins = [t for t in trades if t.pnl_usd > 0]
    losses = [t for t in trades if t.pnl_usd <= 0]
    win_rate = (len(wins) / len(trades) * 100.0) if trades else 0.0
    gross_profit = sum(t.pnl_usd for t in wins)
    gross_loss = abs(sum(t.pnl_usd for t in losses))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0.0)

    # Sharpe-ish: mean daily return / std daily return * sqrt(periods)
    sharpe = 0.0
    if len(equity_curve) > 1:
        returns = [(equity_curve[i] / equity_curve[i - 1]) - 1.0 for i in range(1, len(equity_curve))]
        if len(returns) > 1:
            mean_ret = np.mean(returns)
            std_ret = np.std(returns, ddof=1)
            if std_ret > 0:
                sharpe = (mean_ret / std_ret) * np.sqrt(len(returns))

    return {
        "total_return_pct": total_return_pct,
        "max_drawdown_pct": max_dd * 100.0,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "sharpe_ratio": sharpe,
    }


def _build_signal_series(df: pd.DataFrame, strategy, symbol: str, equity_history: list = None) -> list[dict]:
    """Run strategy over a sliding window to produce one signal per bar.

    Passes equity_history from the main loop so adaptive compounding
    activates as trades close during the backtest.
    """
    if equity_history is None:
        equity_history = []
    signals = []
    ema_slow = getattr(strategy, 'ema_slow_len', None) or getattr(strategy, 'SMA_SLOW', 50)
    atr_per = getattr(strategy, 'atr_period', None) or getattr(strategy, 'ATR_VALU', 14)
    min_rows = max(ema_slow, atr_per) + 5
    for i in range(min_rows, len(df)):
        window = df.iloc[: i + 1].copy()
        result = strategy.generate_signals(window, symbol=symbol, equity_history=list(equity_history))
        signals.append(result)
    return signals




def _save_candles_to_cache(df: pd.DataFrame, token: str, timeframe: str):
    """Save fetched OHLCV candles to DB cache for future use."""
    try:
        db = SessionLocal()
        for _, row in df.iterrows():
            ts = row["timestamp"]
            existing = db.query(CandleCache).filter(
                CandleCache.token == token,
                CandleCache.timeframe == timeframe,
                CandleCache.timestamp == ts,
            ).first()
            if not existing:
                db.add(CandleCache(
                    token=token, timeframe=timeframe, timestamp=ts,
                    open=float(row["open"]), high=float(row["high"]),
                    low=float(row["low"]), close=float(row["close"]),
                    volume=float(row.get("volume", 0)),
                ))
        db.commit()
        db.close()
    except Exception as e:
        print(f"[BACKTEST] Candle cache save failed: {e}")


def _load_cached_candles(token: str, timeframe: str, start_date, end_date) -> pd.DataFrame | None:
    """Load cached candles for a date range. Returns None if insufficient data."""
    try:
        db = SessionLocal()
        rows = db.query(CandleCache).filter(
            CandleCache.token == token,
            CandleCache.timeframe == timeframe,
            CandleCache.timestamp >= start_date,
            CandleCache.timestamp <= end_date,
        ).order_by(CandleCache.timestamp).all()
        db.close()
        if len(rows) < 30:
            return None
        import pandas as pd2
        data = [{
            "timestamp": r.timestamp, "open": r.open, "high": r.high,
            "low": r.low, "close": r.close, "volume": r.volume,
        } for r in rows]
        return pd2.DataFrame(data)
    except Exception:
        return None



def _generate_intra_bar_ticks(open_p: float, high: float, low: float, close: float, n_ticks: int = 28) -> list[float]:
    """Generate n synthetic intra-bar ticks via Brownian bridge from open to close,
    ensuring high and low are touched."""
    if n_ticks <= 1:
        return [close]
    if n_ticks == 4:
        # Basic: O, H, L, C in order
        return [open_p, high, low, close]
    
    # Brownian bridge: random walk from open to close, touching high and low
    rng = np.random.default_rng()
    ticks = []
    # Split into 4 segments: O→H, H→L, L→C, with remaining ticks distributed
    # Place high at ~25% and low at ~75% of the bar
    high_idx = max(1, n_ticks // 4)
    low_idx = min(n_ticks - 2, (3 * n_ticks) // 4)
    
    segments = []
    # Segment 1: open → high
    for i in range(high_idx):
        frac = (i + 1) / high_idx
        ticks.append(open_p + (high - open_p) * frac + rng.normal(0, abs(high - open_p) * 0.1))
    # Segment 2: high → low
    for i in range(low_idx - high_idx):
        frac = (i + 1) / (low_idx - high_idx)
        ticks.append(high + (low - high) * frac + rng.normal(0, abs(low - high) * 0.1))
    # Segment 3: low → close
    remaining = n_ticks - low_idx - 1
    for i in range(remaining):
        frac = (i + 1) / (remaining + 1)
        ticks.append(low + (close - low) * frac + rng.normal(0, abs(close - low) * 0.1))
    ticks.append(close)
    
    # Clamp to [low, high] range
    ticks = [max(low, min(high, t)) for t in ticks]
    # Ensure first = open, last = close
    if ticks:
        ticks[0] = open_p
        ticks[-1] = close
    return ticks


def _check_trailing_stop_on_ticks(position: BacktestTrade, ticks: list[float], mintick: float, leverage: int, equity: float) -> tuple[bool, float, float]:
    """Evaluate trailing stop on intra-bar ticks. Returns (hit, exit_price, pnl_usd)."""
    for tick_price in ticks:
        if position.side == "LONG":
            if tick_price > position.best_price:
                position.best_price = tick_price
            if not position.trail_active:
                activation_price = position.entry_price + position.trail_activation * mintick
                if tick_price >= activation_price:
                    position.trail_active = True
            if position.trail_active:
                trail_stop = position.best_price - position.trail_offset * mintick
                position.trail_stop_price = trail_stop
                if trail_stop > position.stop_loss_price and tick_price <= trail_stop:
                    exit_cost = position.qty * trail_stop * TAKER_FEE
                    raw_pnl = (trail_stop - position.entry_price) / position.entry_price
                    pnl_usd = position.position_size * raw_pnl * leverage - exit_cost
                    return True, trail_stop, pnl_usd
            # Also check stop-loss on ticks
            if position.stop_loss_price is not None and tick_price <= position.stop_loss_price:
                exit_cost = position.qty * position.stop_loss_price * TAKER_FEE
                raw_pnl = (position.stop_loss_price - position.entry_price) / position.entry_price
                pnl_usd = position.position_size * raw_pnl * leverage - exit_cost
                return True, position.stop_loss_price, pnl_usd
        elif position.side == "SHORT":
            if position.best_price == 0 or tick_price < position.best_price:
                position.best_price = tick_price
            if not position.trail_active:
                activation_price = position.entry_price - position.trail_activation * mintick
                if tick_price <= activation_price:
                    position.trail_active = True
            if position.trail_active:
                trail_stop = position.best_price + position.trail_offset * mintick
                position.trail_stop_price = trail_stop
                if trail_stop < position.stop_loss_price and tick_price >= trail_stop:
                    exit_cost = position.qty * trail_stop * TAKER_FEE
                    raw_pnl = (position.entry_price - trail_stop) / position.entry_price
                    pnl_usd = position.position_size * raw_pnl * leverage - exit_cost
                    return True, trail_stop, pnl_usd
            if position.stop_loss_price is not None and tick_price >= position.stop_loss_price:
                exit_cost = position.qty * position.stop_loss_price * TAKER_FEE
                raw_pnl = (position.stop_loss_price - position.entry_price) / position.entry_price
                pnl_usd = position.position_size * raw_pnl * leverage - exit_cost
                return True, position.stop_loss_price, pnl_usd
    return False, 0.0, 0.0



def run_backtest(
    instance_slug: str,
    token: str,
    strategy_id: str,
    timeframe: str,
    mode: str,
    profile: str,
    activation: int = 8,
    offset: int = 3,
    leverage: int = 1,
    days: int = 30,
    initial_capital: float = 100.0,
    risk_per_trade_pct: float = 97.0,
    market_data: HyperLiquidMarketData | None = None,
    use_saved_ohlcv: pd.DataFrame | None = None,
    tick_mode: int = 1,  # 1=OHLC only, 4=basic O/H/L/C, 28=Brownian bridge
) -> BacktestResult:
    """Run a historical backtest and return a BacktestResult."""
    backtest_id = str(uuid.uuid4())
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    result = BacktestResult(
        id=backtest_id,
        instance_slug=instance_slug,
        token=token,
        strategy_id=strategy_id,
        timeframe=timeframe,
        mode=mode,
        profile=profile,
        activation=activation,
        offset=offset,
        leverage=leverage,
        start_date=start_date,
        end_date=end_date,
        initial_capital=initial_capital,
        final_capital=initial_capital,
    )

    strategy_cls = get_strategy(strategy_id)
    if not strategy_cls:
        result.status = "error"
        result.error_message = f"Unknown strategy_id: {strategy_id}"
        return result

    strategy = strategy_cls()

    try:
        if use_saved_ohlcv is not None and not use_saved_ohlcv.empty:
            df = use_saved_ohlcv.copy()
        else:
            # Try cached candles first (enables backtests beyond HL 60-day API limit)
            cached = _load_cached_candles(token, timeframe, start_date, end_date)
            if cached is not None and len(cached) >= 30:
                # Merge cache with fresh data for any newer candles
                md = market_data or HyperLiquidMarketData()
                bars_needed = int((days * 24 * 60) / _minutes_for_timeframe(timeframe)) + 50
                fresh = md.get_candles(symbol=token, timeframe=timeframe, bars=bars_needed)
                if not fresh.empty:
                    # Save fresh candles to cache for future use
                    _save_candles_to_cache(fresh, token, timeframe)
                    # Combine: use cached for old data, fresh for new
                    df = pd.concat([cached, fresh]).drop_duplicates(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
                else:
                    df = cached
            else:
                md = market_data or HyperLiquidMarketData()
                bars_needed = int((days * 24 * 60) / _minutes_for_timeframe(timeframe)) + 50
                df = md.get_candles(symbol=token, timeframe=timeframe, bars=bars_needed)
                # Save fetched candles to cache for future use
                if not df.empty:
                    _save_candles_to_cache(df, token, timeframe)

        if df.empty or len(df) < 50:
            result.status = "error"
            result.error_message = f"Insufficient OHLCV data for {token} ({timeframe})"
            return result

        # Restrict to requested date range
        df = df[(df["timestamp"] >= start_date) & (df["timestamp"] <= end_date)].copy()
        if len(df) < 30:
            result.status = "error"
            result.error_message = f"Not enough candles in date range for {token}"
            return result

        # Resolve indicator length attributes (v1.3 uses ema_slow_len, v1 uses SMA_SLOW)
        ema_slow = getattr(strategy, 'ema_slow_len', None) or getattr(strategy, 'SMA_SLOW', 50)
        atr_per = getattr(strategy, 'atr_period', None) or getattr(strategy, 'ATR_VALU', 14)
        min_rows = max(ema_slow, atr_per) + 5

        # Detect mintick from candle data (HL tick size varies per asset)
        mintick = _detect_mintick(df)

        equity = initial_capital
        equity_curve = [{"time": df["timestamp"].iloc[0].isoformat(), "equity": equity}]
        position: BacktestTrade | None = None
        trades: list[BacktestTrade] = []
        equity_history: list[float] = []

        # Track previous bar EMA values for trend reversal detection
        prev_fast_ema = None
        prev_medm_ema = None

        for i in range(len(df)):
            candle = df.iloc[i]
            ts = candle["timestamp"]
            close = float(candle["close"])
            high = float(candle["high"])
            low = float(candle["low"])

            # Generate signal for this bar (if enough warmup data)
            direction = "NEUTRAL"
            sig = None
            sig_metadata = {}
            if i >= min_rows:
                window = df.iloc[: i + 1].copy()
                sig = strategy.generate_signals(window, symbol=token, equity_history=list(equity_history))
                direction = sig.get("direction", "NEUTRAL") if sig else "NEUTRAL"
                sig_metadata = sig.get("metadata", {}) if sig else {}

            # Trend reversal close (Pine: ta.crossunder/crossover fastEMA vs medmEMA)
            # Read EMA values from exit_config (neutral receiver)
            ec_current = sig.get("exit_config", {}) or {} if sig else {}
            if position is not None and prev_fast_ema is not None and prev_medm_ema is not None:
                curr_fast = ec_current.get("fast_ema")
                curr_medm = ec_current.get("medm_ema")
                if curr_fast is not None and curr_medm is not None:
                    trend_reversal = False
                    # crossunder: fast was above medm, now below → close LONG
                    if position.side == "LONG" and prev_fast_ema >= prev_medm_ema and curr_fast < curr_medm:
                        trend_reversal = True
                    # crossover: fast was below medm, now above → close SHORT
                    elif position.side == "SHORT" and prev_fast_ema <= prev_medm_ema and curr_fast > curr_medm:
                        trend_reversal = True

                    if trend_reversal:
                        exit_cost = position.qty * close * TAKER_FEE
                        if position.side == "LONG":
                            raw_pnl = (close - position.entry_price) / position.entry_price
                        else:
                            raw_pnl = (position.entry_price - close) / position.entry_price
                        pnl_pct = raw_pnl * leverage * 100
                        pnl_usd = position.position_size * raw_pnl * leverage - exit_cost
                        position.exit_bar = i
                        position.exit_time = ts
                        position.exit_price = close
                        position.pnl_pct = pnl_pct
                        position.pnl_usd = pnl_usd
                        position.bars_held = i - position.entry_bar
                        trades.append(position)
                        equity += pnl_usd
                        equity_history.append(equity)
                        position = None

            # Update prev EMA values for next bar (from exit_config)
            if ec_current.get("fast_ema") is not None:
                prev_fast_ema = ec_current.get("fast_ema")
                prev_medm_ema = ec_current.get("medm_ema")

            # Check stop-loss hit (using candle high/low)
            if position is not None and position.stop_loss_price is not None:
                sl = position.stop_loss_price
                hit = False
                if position.side == "LONG" and low <= sl:
                    hit = True
                elif position.side == "SHORT" and high >= sl:
                    hit = True

                if hit:
                    exit_price = sl
                    exit_cost = position.qty * exit_price * TAKER_FEE
                    if position.side == "LONG":
                        raw_pnl = (exit_price - position.entry_price) / position.entry_price
                    else:
                        raw_pnl = (position.entry_price - exit_price) / position.entry_price
                    pnl_pct = raw_pnl * leverage * 100
                    pnl_usd = position.position_size * raw_pnl * leverage - exit_cost
                    position.exit_bar = i
                    position.exit_time = ts
                    position.exit_price = exit_price
                    position.pnl_pct = pnl_pct
                    position.pnl_usd = pnl_usd
                    position.bars_held = i - position.entry_bar
                    trades.append(position)
                    equity += pnl_usd
                    equity_history.append(equity)
                    position = None

            # Intra-bar tick evaluation for trailing stop (tick_mode > 1)
            if position is not None and position.trail_activation > 0 and tick_mode > 1:
                tick_prices = _generate_intra_bar_ticks(float(candle["open"]), high, low, close, tick_mode)
                hit, exit_px, pnl_usd_val = _check_trailing_stop_on_ticks(position, tick_prices, mintick, leverage, equity)
                if hit:
                    position.exit_bar = i
                    position.exit_time = ts
                    position.exit_price = exit_px
                    position.pnl_pct = (pnl_usd_val / position.position_size * 100) if position.position_size > 0 else 0.0
                    position.pnl_usd = pnl_usd_val
                    position.bars_held = i - position.entry_bar
                    trades.append(position)
                    equity += pnl_usd_val
                    equity_history.append(equity)
                    position = None

            # Check trailing stop (Pine: trail_points/trail_offset) - OHLC mode
            # Activates after price moves activation ticks in favor,
            # then trails at offset ticks behind best price.
            if position is not None and position.trail_activation > 0 and tick_mode == 1:
                tick_size = mintick  # detected per-asset from HL candle data

                if position.side == "LONG":
                    # Track best price (highest high)
                    if high > position.best_price:
                        position.best_price = high
                    # Activate trailing stop once price moves activation ticks above entry
                    if not position.trail_active:
                        activation_price = position.entry_price + position.trail_activation * tick_size
                        if high >= activation_price:
                            position.trail_active = True
                    # If active, compute and check trail stop
                    if position.trail_active:
                        trail_stop = position.best_price - position.trail_offset * tick_size
                        position.trail_stop_price = trail_stop
                        # Only exit if trail stop is above initial stop-loss
                        if trail_stop > position.stop_loss_price and low <= trail_stop:
                            exit_price = trail_stop
                            exit_cost = position.qty * exit_price * TAKER_FEE
                            raw_pnl = (exit_price - position.entry_price) / position.entry_price
                            pnl_pct = raw_pnl * leverage * 100
                            pnl_usd = position.position_size * raw_pnl * leverage - exit_cost
                            position.exit_bar = i
                            position.exit_time = ts
                            position.exit_price = exit_price
                            position.pnl_pct = pnl_pct
                            position.pnl_usd = pnl_usd
                            position.bars_held = i - position.entry_bar
                            trades.append(position)
                            equity += pnl_usd
                            equity_history.append(equity)
                            position = None

                elif position.side == "SHORT":
                    # Track best price (lowest low)
                    if position.best_price == 0 or low < position.best_price:
                        position.best_price = low
                    # Activate trailing stop once price moves activation ticks below entry
                    if not position.trail_active:
                        activation_price = position.entry_price - position.trail_activation * tick_size
                        if low <= activation_price:
                            position.trail_active = True
                    # If active, compute and check trail stop
                    if position.trail_active:
                        trail_stop = position.best_price + position.trail_offset * tick_size
                        position.trail_stop_price = trail_stop
                        # Only exit if trail stop is below initial stop-loss
                        if trail_stop < position.stop_loss_price and high >= trail_stop:
                            exit_price = trail_stop
                            exit_cost = position.qty * exit_price * TAKER_FEE
                            raw_pnl = (position.entry_price - exit_price) / position.entry_price
                            pnl_pct = raw_pnl * leverage * 100
                            pnl_usd = position.position_size * raw_pnl * leverage - exit_cost
                            position.exit_bar = i
                            position.exit_time = ts
                            position.exit_price = exit_price
                            position.pnl_pct = pnl_pct
                            position.pnl_usd = pnl_usd
                            position.bars_held = i - position.entry_bar
                            trades.append(position)
                            equity += pnl_usd
                            equity_history.append(equity)
                            position = None

            # Enter new position if flat and signal is directional
            if position is None and direction in ("BUY", "SELL"):
                side = "LONG" if direction == "BUY" else "SHORT"

                # Read all exit params from strategy exit_config (neutral receiver)
                ec = sig.get("exit_config", {}) or {}
                sl = ec.get("stop_loss_long") if side == "LONG" else ec.get("stop_loss_short")
                tp = ec.get("take_profit_long") if side == "LONG" else ec.get("take_profit_short")
                trail_act = float(ec.get("trail_activation", 0))
                trail_off = float(ec.get("trail_offset", 0))
                use_time_exit = ec.get("use_time_exit", False)
                time_exit_bars = ec.get("time_exit_bars")

                # Fallback: compute stop-loss from ATR if exit_config didn't declare one
                if not sl:
                    atr_val = sig_metadata.get("atr", close * 0.01)
                    atr_mult = sig_metadata.get("atr_mult_use", 1.8)
                    if side == "LONG":
                        sl = low - atr_val * atr_mult
                    else:
                        sl = high + atr_val * atr_mult

                # Risk-based position sizing (matches Pine calcSize)
                # qtyRisk = riskAmount / riskPerShare
                # qtyMax = floor(equity * 0.97 / close)
                # qty = min(qtyRisk, qtyMax)
                risk_per_share = abs(close - sl)
                risk_per_share = max(risk_per_share, mintick * 10)
                risk_amount = equity * (risk_per_trade_pct / 100.0)
                qty_risk = risk_amount / risk_per_share if risk_per_share > 0 else 0
                qty_max = int(equity * 0.97 / close) if close > 0 else 0
                qty = min(qty_risk, qty_max)
                qty = max(qty, 0)

                position_size = qty * close
                entry_cost = qty * close * TAKER_FEE

                position = BacktestTrade(
                    entry_bar=i,
                    entry_time=ts,
                    entry_price=close,
                    side=side,
                    qty=qty,
                    position_size=position_size,
                    stop_loss_price=sl,
                    trail_activation=trail_act,
                    trail_offset=trail_off,
                    best_price=close,
                    trail_active=False,
                )
                # Charge entry cost to equity
                equity -= entry_cost

            equity_curve.append({"time": ts.isoformat(), "equity": equity})

        # Close any open position at last candle
        if position is not None:
            last = df.iloc[-1]
            close = float(last["close"])
            ts = last["timestamp"]
            exit_cost = position.qty * close * TAKER_FEE
            if position.side == "LONG":
                raw_pnl = (close - position.entry_price) / position.entry_price
            else:
                raw_pnl = (position.entry_price - close) / position.entry_price
            pnl_pct = raw_pnl * leverage * 100
            pnl_usd = position.position_size * raw_pnl * leverage - exit_cost
            position.exit_bar = len(df) - 1
            position.exit_time = ts
            position.exit_price = close
            position.pnl_pct = pnl_pct
            position.pnl_usd = pnl_usd
            position.bars_held = (len(df) - 1) - position.entry_bar
            trades.append(position)
            equity += pnl_usd
            equity_curve[-1]["equity"] = equity
            equity_history.append(equity)

        metrics = _calculate_metrics([pt["equity"] for pt in equity_curve], trades)

        result.final_capital = equity
        result.total_return_pct = metrics["total_return_pct"]
        result.max_drawdown_pct = metrics["max_drawdown_pct"]
        result.win_rate = metrics["win_rate"]
        result.profit_factor = metrics["profit_factor"]
        result.sharpe_ratio = metrics["sharpe_ratio"]
        result.total_trades = len(trades)
        result.trades = trades
        result.equity_curve = equity_curve
        result.status = "done"
        return result

    except Exception as e:
        result.status = "error"
        result.error_message = str(e)
        return result


def _detect_mintick(df: pd.DataFrame) -> float:
    """Detect the minimum price tick from candle data.

    Sorts all unique price values (close, open, high, low) and finds
    the smallest non-zero difference — that's the exchange's tick size.
    Falls back to 0.00001 if detection fails.
    """
    try:
        all_prices = set()
        for col in ("close", "open", "high", "low"):
            if col in df.columns:
                all_prices.update(df[col].dropna().unique())
        sorted_prices = sorted(all_prices)
        if len(sorted_prices) < 2:
            return 0.00001
        diffs = [sorted_prices[i + 1] - sorted_prices[i] for i in range(len(sorted_prices) - 1)]
        mintick = min(d for d in diffs if d > 0)
        return float(mintick)
    except Exception:
        pass
    return 0.00001


def _minutes_for_timeframe(timeframe: str) -> int:
    """Convert HyperLiquid-style timeframe string to minutes."""
    if timeframe.endswith("m"):
        return int(timeframe[:-1])
    if timeframe.endswith("h"):
        return int(timeframe[:-1]) * 60
    if timeframe.endswith("d"):
        return int(timeframe[:-1]) * 24 * 60
    return 15
