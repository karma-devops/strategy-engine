"""
Engine v6.1 — Full-fidelity translation of Engine v6 PRO Pine Script.

Unique features not in v1/v1.3:
- Dynamic risk multiplier with drawdown protection
- Peak protection override (hyper phase forces 1.0-1.2x risk even at peaks)
- Different pin bar detection (close vs open comparison, not wick/body ratio)
- ATR sensitivity switching (10 vs 14 based on acceleration)
- multAdaptive clamped to [1.0, 2.0] instead of [0.5, 3.0]
- bufferMult: hyper=0.0, normal=1.0 (safety buffer in max qty calc)
"""

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import pandas as pd
import numpy as np
from engine.base import BaseStrategy


class EngineV6_1Strategy(BaseStrategy):
    """
    Engine v6.1 PRO — full-fidelity Pine Script translation.

    - EMA fan (6/18/50), ATR (14), DMI/ADX
    - Adaptive equity compounding (5-layer, clamped [1.0, 2.0])
    - Dynamic risk multiplier with drawdown protection
    - Pin bar: close vs open comparison (not wick/body ratio)
    - ATR sensitivity: switches length based on acceleration
    """

    def __init__(self, name: str = "Engine v6.1 PRO"):
        super().__init__(name)

        self.engine_mode = "Scalp"
        self.active_activation = 18
        self.active_offset = 6

        # Indicator lengths (Pine defaults)
        self.ema_fast_len = 6
        self.ema_medm_len = 18
        self.ema_slow_len = 50
        self.atr_period = 14

        # ATR multiplier
        self.atr_mult_input = 1.8
        self.atr_mult_base = 1.8
        self.atr_mult_guard = 0.9

        # Hyper-growth protocol
        self.growth_target_x = 50.0
        self.use_momentum = True
        self.momentum_thresh = 18

        # Risk profiles (Pine defaults)
        self.risk_profile = "Manual"
        self.man_activation = 18
        self.man_offset = 6

        # Dynamic risk (v6.1 unique)
        self.aggressive_drawdown_threshold = 0.10
        self.aggressive_multiplier = 1.20
        self.peak_protect_multiplier = 0.30

        # Risk per trade
        self.risk_per_trade_pct = 97.0

        # Trade direction
        self.trade_direction = "Both"

        # Equity tracking
        self.equity_sma_len = 21
        self.warmup_trades = 3
        self.use_equity_guard = False
        self.eq_percent = 0.7
        self.initial_capital = 100.0

        # Constants
        self.FLOAT_EPSILON = 0.0001
        self.MIN_ATR_MULT = 1.0  # v6.1 clamps to [1.0, 2.0] not [0.5, 3.0]
        self.MAX_ATR_MULT = 2.0
        self.MIN_ADAPTIVE_LEN = 6
        self.MAX_ADAPTIVE_LEN = 30
        self.VOLATILITY_FLOOR = 1.0
        self.EQUITY_CURVE_MIN_SAMPLES = 3
        self.MAX_EQUITY_HISTORY = 100
        self.er_len = 14
        self.z_score = 2.2

    @staticmethod
    def _rolling_sma(arr, window):
        w = min(window, len(arr))
        if w <= 0:
            return float(arr[-1]) if arr else 0.0
        return float(np.mean(arr[-w:]))

    @staticmethod
    def _rolling_std(arr, window):
        w = min(window, len(arr))
        if w <= 1:
            return 0.0
        return float(np.std(arr[-w:], ddof=1))

    def _dmi_adx(self, df, period=14):
        high_s = df["high"]
        low_s = df["low"]
        close_s = df["close"]

        up = high_s.diff()
        down = -low_s.diff()

        plus_dm = pd.Series(
            np.where((up > down) & (up > 0), up, 0.0), index=df.index
        )
        minus_dm = pd.Series(
            np.where((down > up) & (down > 0), down, 0.0), index=df.index
        )

        prev_close = close_s.shift(1)
        tr1 = high_s - low_s
        tr2 = (high_s - prev_close).abs()
        tr3 = (low_s - prev_close).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        atr_w = tr.ewm(alpha=1.0 / period, adjust=False).mean()
        plus_dm_w = plus_dm.ewm(alpha=1.0 / period, adjust=False).mean()
        minus_dm_w = minus_dm.ewm(alpha=1.0 / period, adjust=False).mean()

        di_plus = 100.0 * plus_dm_w / atr_w
        di_minus = 100.0 * minus_dm_w / atr_w
        dx = 100.0 * (di_plus - di_minus).abs() / (di_plus + di_minus)
        adx = dx.ewm(alpha=1.0 / period, adjust=False).mean()

        adx_val = float(adx.iloc[-1]) if not pd.isna(adx.iloc[-1]) else 0.0
        di_p = float(di_plus.iloc[-1]) if not pd.isna(di_plus.iloc[-1]) else 0.0
        di_m = float(di_minus.iloc[-1]) if not pd.isna(di_minus.iloc[-1]) else 0.0
        return adx_val, di_p, di_m

    def generate_signals(self, df, symbol="", equity_history=None):
        required = {"open", "high", "low", "close", "volume"}
        if not required.issubset(df.columns):
            return {"token": symbol, "signal": 0.0, "direction": "NEUTRAL",
                    "metadata": {"error": f"Missing columns: {required - set(df.columns)}"}}

        min_rows = max(self.ema_slow_len, self.atr_period) + 5
        if len(df) < min_rows:
            return {"token": symbol, "signal": 0.0, "direction": "NEUTRAL",
                    "metadata": {"error": f"Insufficient rows ({len(df)} < {min_rows})"}}

        close = float(df["close"].iloc[-1])
        open_ = float(df["open"].iloc[-1])
        high = float(df["high"].iloc[-1])
        low = float(df["low"].iloc[-1])
        high_prev = float(df["high"].iloc[-2])
        low_prev = float(df["low"].iloc[-2])

        # Equity tracking
        if equity_history is None:
            equity_history = []
        equity_history = [float(e) for e in equity_history if e is not None and e > 0]
        if len(equity_history) > self.MAX_EQUITY_HISTORY:
            equity_history = equity_history[-self.MAX_EQUITY_HISTORY:]

        current_closed_equity = equity_history[-1] if equity_history else self.initial_capital
        in_warmup = len(equity_history) < self.warmup_trades
        has_min_samples = len(equity_history) >= self.EQUITY_CURVE_MIN_SAMPLES

        avg_equity = current_closed_equity
        if has_min_samples and len(equity_history) > 0:
            avg_equity = np.mean(equity_history)
        if avg_equity <= self.FLOAT_EPSILON:
            avg_equity = current_closed_equity

        is_strategy_cold = has_min_samples and not in_warmup and current_closed_equity < avg_equity

        # Hyper-phase
        target_equity_amt = self.initial_capital * self.growth_target_x
        is_hyper_phase = current_closed_equity < target_equity_amt

        if is_hyper_phase:
            is_strategy_cold = False

        # ATR multiplier
        atr_mult_use = (
            self.atr_mult_input if in_warmup
            else (self.atr_mult_guard if is_strategy_cold else self.atr_mult_base)
        )

        # Adaptive equity compounding (5-layer, same as v1.3 but clamped [1.0, 2.0])
        change = 0.0
        volatility = self.VOLATILITY_FLOOR

        if has_min_samples and len(equity_history) > self.er_len + 1:
            prev_equity = equity_history[-self.er_len - 1]
            if prev_equity is not None and prev_equity > 0:
                change = abs(current_closed_equity - prev_equity)
            vol_sum = 0.0
            for i in range(1, self.er_len + 1):
                if len(equity_history) > i + 1:
                    vol_sum += abs(equity_history[-i] - equity_history[-i - 1])
            volatility = vol_sum if vol_sum > self.FLOAT_EPSILON else self.VOLATILITY_FLOOR
        else:
            change = 0.0
            volatility = self.VOLATILITY_FLOOR

        eff_ratio = (change / volatility) if volatility > self.FLOAT_EPSILON else 0.0
        eff_ratio = max(0.0, min(1.0, eff_ratio))

        len_adaptive = 8.0 + (30.0 - 8.0) * (1.0 - eff_ratio)
        len_adaptive = max(self.MIN_ADAPTIVE_LEN, min(self.MAX_ADAPTIVE_LEN, len_adaptive))
        len_rounded = int(round(len_adaptive))

        eq_sma = self._rolling_sma(equity_history, len_rounded)
        eq_sma_prev = self._rolling_sma(equity_history[:-1], len_rounded) if len(equity_history) > 1 else eq_sma

        epsilon = 0.02
        dist_raw = ((current_closed_equity - eq_sma) / eq_sma) if eq_sma > self.FLOAT_EPSILON else 0.0
        dist = dist_raw if abs(dist_raw) > epsilon else 0.0
        confidence = 1.0 / (1.0 + np.exp(-4.0 * dist))
        base_mult = 1.0 + 0.8 * confidence
        base_mult = max(0.9, min(1.8, base_mult))

        vel = eq_sma - eq_sma_prev
        if len(equity_history) > 2:
            eq_sma_prev2 = self._rolling_sma(equity_history[:-2], len_rounded)
            vel_prev = eq_sma_prev - eq_sma_prev2
        else:
            vel_prev = vel
        acc = vel - vel_prev

        acc_smooth = acc
        if len(equity_history) > 3:
            acc_series = []
            max_off = min(10, len(equity_history) - 2)
            for off in range(max_off):
                sm = self._rolling_sma(equity_history[: -(off + 1)], len_rounded) if off + 1 < len(equity_history) else eq_sma
                sm_prev = self._rolling_sma(equity_history[: -(off + 2)], len_rounded) if off + 2 < len(equity_history) else sm
                sm_prev2 = self._rolling_sma(equity_history[: -(off + 3)], len_rounded) if off + 3 < len(equity_history) else sm_prev
                v = sm - sm_prev
                v_prev = sm_prev - sm_prev2
                acc_series.append(v - v_prev)
            if acc_series:
                acc_s = pd.Series(list(reversed(acc_series)))
                acc_smooth = float(acc_s.ewm(alpha=1.0 / 5.0, adjust=False).mean().iloc[-1])

        acc_impact = max(0.0, min(1.0, (-acc_smooth - 0.4) / 0.6))
        acc_adj = 1.0 - 0.1 * acc_impact

        eq_stdev = self._rolling_std(equity_history, len_rounded)
        eq_upper = eq_sma + self.z_score * eq_stdev
        eq_lower = eq_sma - self.z_score * eq_stdev

        chan_adj = 1.0
        if current_closed_equity < eq_lower:
            chan_adj = 0.95
        elif current_closed_equity > eq_upper:
            chan_adj = 1.03

        # Hyper-aware overrides
        len_factor = 0.8 if is_hyper_phase else 1.0
        len_adaptive = max(self.MIN_ADAPTIVE_LEN, min(self.MAX_ADAPTIVE_LEN, len_adaptive * len_factor))
        base_mult = max(1.0 if is_hyper_phase else 0.9, min(2.0 if is_hyper_phase else 1.8, base_mult))
        chan_adj = (0.97 if is_hyper_phase else 0.95) if current_closed_equity < eq_lower else ((1.05 if is_hyper_phase else 1.03) if current_closed_equity > eq_upper else 1.0)
        acc_adj = (1.0 - 0.07 * acc_impact) if is_hyper_phase else (1.0 - 0.1 * acc_impact)

        mult_adaptive = base_mult * acc_adj * chan_adj
        mult_adaptive = max(self.MIN_ATR_MULT, min(self.MAX_ATR_MULT, mult_adaptive))
        atr_mult_use = mult_adaptive

        # v6.1 unique: ATR sensitivity (switches length based on acceleration)
        atr_len = 10 if acc_smooth < -0.6 else 14

        # v6.1 unique: Dynamic risk multiplier with drawdown protection
        closed_equity_for_peak = current_closed_equity
        eq_peak = max(equity_history) if equity_history else closed_equity_for_peak
        dd_percent = (closed_equity_for_peak / eq_peak - 1) if eq_peak > 0 else 0.0

        if is_hyper_phase:
            risk_multiplier = self.aggressive_multiplier if dd_percent < -self.aggressive_drawdown_threshold else 1.0
        else:
            risk_multiplier = 1.0 if dd_percent < 0 else self.peak_protect_multiplier

        final_risk_pct = self.risk_per_trade_pct * risk_multiplier

        # Indicators
        fast_ema_s = df["close"].ewm(span=self.ema_fast_len, adjust=False).mean()
        medm_ema_s = df["close"].ewm(span=self.ema_medm_len, adjust=False).mean()
        slow_sma_s = df["close"].rolling(window=self.ema_slow_len).mean()

        fast_ema = float(fast_ema_s.iloc[-1])
        medm_ema = float(medm_ema_s.iloc[-1])
        slow_sma = float(slow_sma_s.iloc[-1])

        if pd.isna(fast_ema): fast_ema = close
        if pd.isna(medm_ema): medm_ema = close
        if pd.isna(slow_sma): slow_sma = close

        # ATR (Wilder RMA, v6.1 uses dynamic atr_len)
        high_s = df["high"]
        low_s = df["low"]
        close_s = df["close"]
        prev_close_s = close_s.shift(1)
        tr1 = high_s - low_s
        tr2 = (high_s - prev_close_s).abs()
        tr3 = (low_s - prev_close_s).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr_s = tr.ewm(alpha=1.0 / atr_len, adjust=False).mean()
        atr = float(atr_s.iloc[-1])
        if pd.isna(atr) or atr <= self.FLOAT_EPSILON:
            atr = close * 0.01

        atr_prev = float(atr_s.iloc[-2]) if len(atr_s) > 1 and not pd.isna(atr_s.iloc[-2]) else atr

        # Fan trend
        fan_up_trend = fast_ema > medm_ema and medm_ema > slow_sma
        fan_dn_trend = fast_ema < medm_ema and medm_ema < slow_sma

        # ADX
        adx_value, di_plus, di_minus = self._dmi_adx(df, period=self.atr_period)
        momentum_thresh_final = self.momentum_thresh if self.momentum_thresh > 0 else 18
        is_strong_trend = adx_value > momentum_thresh_final

        # v6.1 unique pin bar detection (close vs open comparison, not wick/body)
        bar_range = high - low
        bullish_pin_bar = (close > open_ and open_ - low > 0.66 * bar_range) or (close < open_ and close - low > 0.66 * bar_range)
        bearish_pin_bar = (close > open_ and high - close > 0.66 * bar_range) or (close < open_ and high - open_ > 0.66 * bar_range)

        # Momentum triggers
        if is_hyper_phase and self.use_momentum:
            valid_trigger_bull = bullish_pin_bar or (is_strong_trend and close > high_prev)
            valid_trigger_bear = bearish_pin_bar or (is_strong_trend and close < low_prev)
        else:
            valid_trigger_bull = bullish_pin_bar
            valid_trigger_bear = bearish_pin_bar

        # Price pierce (v6.1 uses open as reference, not just low/high)
        bull_pierce = (
            (low < fast_ema and open_ > fast_ema and close > fast_ema) or
            (low < medm_ema and open_ > medm_ema and close > medm_ema) or
            (low < slow_sma and open_ > slow_sma)
        )
        bear_pierce = (
            (high > fast_ema and open_ < fast_ema and close < fast_ema) or
            (high > medm_ema and open_ < medm_ema and close < medm_ema) or
            (high > slow_sma and open_ < slow_sma)
        )

        # Entry signals
        long_entry = fan_up_trend and bull_pierce and valid_trigger_bull
        short_entry = fan_dn_trend and bear_pierce and valid_trigger_bear

        # Trade direction filter
        allow_long = self.trade_direction in ("Both", "Long Only")
        allow_short = self.trade_direction in ("Both", "Short Only")

        # Position sizing (v6.1: bufferMult = 0.0 if hyper, 1.0 if normal)
        stop_dist = atr_prev * atr_mult_use
        stop_price_long = low_prev - stop_dist
        stop_price_short = high_prev + stop_dist
        risk_per_share_long = max(abs(close - stop_price_long), close * 0.001)
        risk_per_share_short = max(abs(close - stop_price_short), close * 0.001)

        available_equity = max(current_closed_equity, self.initial_capital)
        risk_amount = available_equity * (final_risk_pct / 100.0)
        qty_risk_long = risk_amount / risk_per_share_long if risk_per_share_long > 0 else 0
        qty_risk_short = risk_amount / risk_per_share_short if risk_per_share_short > 0 else 0

        buffer_mult = 0.0 if is_hyper_phase else 1.0
        efficiency = 0.97 if is_hyper_phase else 1.0
        denom_long = close + atr_prev * buffer_mult
        denom_short = close + atr_prev * buffer_mult
        qty_max_long = int(available_equity * efficiency / denom_long) if denom_long > 0 else 0
        qty_max_short = int(available_equity * efficiency / denom_short) if denom_short > 0 else 0

        final_qty_long = max(0, min(qty_risk_long, qty_max_long))
        final_qty_short = max(0, min(qty_risk_short, qty_max_short))

        # Signal resolution
        direction = "NEUTRAL"
        signal = 0.0
        if long_entry and allow_long:
            direction = "BUY"
            signal = 1.0
        elif short_entry and allow_short:
            direction = "SELL"
            signal = 1.0

        metadata = {
            "engine_mode": self.engine_mode,
            "risk_profile": self.risk_profile,
            "activation": self.active_activation,
            "offset": self.active_offset,
            "fast_ema": float(round(fast_ema, 8)),
            "medm_ema": float(round(medm_ema, 8)),
            "slow_sma": float(round(slow_sma, 8)),
            "atr": float(round(atr, 8)),
            "atr_len": atr_len,
            "atr_mult_use": float(round(atr_mult_use, 6)),
            "mult_adaptive": float(round(mult_adaptive, 6)),
            "adx": float(round(adx_value, 4)),
            "di_plus": float(round(di_plus, 4)),
            "di_minus": float(round(di_minus, 4)),
            "is_strong_trend": is_strong_trend,
            "fan_up_trend": fan_up_trend,
            "fan_dn_trend": fan_dn_trend,
            "bullish_pin_bar": bullish_pin_bar,
            "bearish_pin_bar": bearish_pin_bar,
            "bull_pierce": bull_pierce,
            "bear_pierce": bear_pierce,
            "is_hyper_phase": is_hyper_phase,
            "progress_pct": float(round((current_closed_equity / target_equity_amt * 100) if target_equity_amt > 0 else 0, 2)),
            "is_strategy_cold": is_strategy_cold,
            "in_warmup": in_warmup,
            "current_equity": float(round(current_closed_equity, 6)),
            "dd_percent": float(round(dd_percent, 6)),
            "risk_multiplier": float(round(risk_multiplier, 4)),
            "final_risk_pct": float(round(final_risk_pct, 2)),
            "stop_loss_long": float(round(stop_price_long, 8)),
            "stop_loss_short": float(round(stop_price_short, 8)),
            "qty_long": float(round(final_qty_long, 6)),
            "qty_short": float(round(final_qty_short, 6)),
            "buffer_mult": buffer_mult,
            "efficiency": efficiency,
            "len_adaptive": float(round(len_adaptive, 2)),
            "eff_ratio": float(round(eff_ratio, 6)),
            "base_mult": float(round(base_mult, 6)),
            "acc_adj": float(round(acc_adj, 6)),
            "chan_adj": float(round(chan_adj, 6)),
        }

        return {"token": symbol, "signal": signal, "direction": direction, "metadata": metadata}


if __name__ == "__main__":
    np.random.seed(42)
    n = 200
    idx = pd.date_range("2025-01-01", periods=n, freq="15min")
    close = 0.5 + np.cumsum(np.random.normal(0.001, 0.02, n)) * 0.01
    close = np.maximum(close, 0.01)
    open_ = close + np.random.normal(0, 0.005, n)
    high = np.maximum(open_, close) + np.abs(np.random.normal(0, 0.005, n))
    low = np.minimum(open_, close) - np.abs(np.random.normal(0, 0.005, n))
    volume = np.random.randint(1e6, 5e6, n).astype(float)
    df = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": volume}, index=idx)

    equity_hist = [100.0, 102.0, 101.0, 105.0, 108.0, 110.0, 115.0, 112.0, 118.0, 120.0,
                   125.0, 130.0, 128.0, 135.0, 140.0, 138.0, 145.0, 150.0, 148.0, 155.0]

    engine = EngineV6_1Strategy()
    result = engine.generate_signals(df, symbol="FARTCOIN", equity_history=equity_hist)
    print(result)