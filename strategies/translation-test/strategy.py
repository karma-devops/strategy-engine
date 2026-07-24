import pandas as pd
import numpy as np
from strategies.base import BaseStrategy

class EveEngineV13Strategy(BaseStrategy):
    def __init__(self):
        super().__init__("EveEngineV13Strategy")

    def _calculate_atr(self, df, period=14):
        high = df['high']
        low = df['low']
        close = df['close']
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.ewm(alpha=1/period, adjust=False).mean()
        return atr

    def _calculate_adx(self, df, period=14):
        high = df['high']
        low = df['low']
        close = df['close']
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        plus_dm = high - high.shift(1)
        minus_dm = low.shift(1) - low
        plus_dm = plus_dm.where(plus_dm > minus_dm, 0)
        minus_dm = minus_dm.where(minus_dm > plus_dm, 0)
        plus_di = 100 * (plus_dm.ewm(alpha=1/period, adjust=False).mean() / tr.ewm(alpha=1/period, adjust=False).mean())
        minus_di = 100 * (minus_dm.ewm(alpha=1/period, adjust=False).mean() / tr.ewm(alpha=1/period, adjust=False).mean())
        dx = (abs(plus_di - minus_di) / (plus_di + minus_di)).fillna(0) * 100
        adx = dx.ewm(alpha=1/period, adjust=False).mean()
        return adx

    def generate_signals(self, df, symbol=None, equity_history=None):
        df = df.copy()
        # Indicator calculations
        df['fast_ema'] = df['close'].ewm(span=6, adjust=False).mean()
        df['medm_ema'] = df['close'].ewm(span=18, adjust=False).mean()
        df['slow_sma'] = df['close'].rolling(window=50, min_periods=1).mean()
        df['atr'] = self._calculate_atr(df, period=14)
        df['adx'] = self._calculate_adx(df, period=14)

        df['fan_up_trend'] = (df['fast_ema'] > df['medm_ema']) & (df['medm_ema'] > df['slow_sma'])
        df['fan_dn_trend'] = (df['fast_ema'] < df['medm_ema']) & (df['medm_ema'] < df['slow_sma'])

        # Pin bar detection
        df['bar_range'] = df['high'] - df['low']
        df['body'] = (df['close'] - df['open']).abs()
        df['upper_wick'] = df['high'] - df[['close', 'open']].max(axis=1)
        df['lower_wick'] = df[['close', 'open']].min(axis=1) - df['low']
        pin_bar_wick_ratio = 0.66
        pin_bar_body_ratio = 0.34
        df['bullish_pin_bar'] = (df['bar_range'] > 0) & (df['lower_wick'] >= pin_bar_wick_ratio * df['bar_range']) & (df['body'] <= pin_bar_body_ratio * df['bar_range'])
        df['bearish_pin_bar'] = (df['bar_range'] > 0) & (df['upper_wick'] >= pin_bar_wick_ratio * df['bar_range']) & (df['body'] <= pin_bar_body_ratio * df['bar_range'])

        # Pierce detection
        df['bull_pierce'] = ((df['low'] < df['fast_ema']) & (df['close'] > df['fast_ema'])) | \
                            ((df['low'] < df['medm_ema']) & (df['close'] > df['medm_ema'])) | \
                            ((df['low'] < df['slow_sma']) & (df['close'] > df['slow_sma']))
        df['bear_pierce'] = ((df['high'] > df['fast_ema']) & (df['close'] < df['fast_ema'])) | \
                            ((df['high'] > df['medm_ema']) & (df['close'] < df['medm_ema'])) | \
                            ((df['high'] > df['slow_sma']) & (df['close'] < df['slow_sma']))

        # Trend strength
        momentum_thresh_final = 18
        df['is_strong_trend'] = df['adx'] > momentum_thresh_final

        # Valid triggers
        is_hyper_phase = False
        use_momentum = True
        df['valid_trigger_bull'] = (is_hyper_phase & use_momentum) & (df['bullish_pin_bar'] | (df['is_strong_trend'] & (df['close'] > df['high'].shift(1)))) | df['bullish_pin_bar']
        df['valid_trigger_bear'] = (is_hyper_phase & use_momentum) & (df['bearish_pin_bar'] | (df['is_strong_trend'] & (df['close'] < df['low'].shift(1)))) | df['bearish_pin_bar']

        # Entry signals
        df['long_entry'] = df['fan_up_trend'] & df['bull_pierce'] & df['valid_trigger_bull']
        df['short_entry'] = df['fan_dn_trend'] & df['bear_pierce'] & df['valid_trigger_bear']

        # Direction
        last = df.iloc[-1]
        if last['long_entry']:
            direction = 'BUY'
        elif last['short_entry']:
            direction = 'SELL'
        else:
            direction = 'NEUTRAL'

        # Metadata
        metadata = {
            'adx': last['adx'],
            'fast_ema': last['fast_ema'],
            'medm_ema': last['medm_ema'],
            'slow_sma': last['slow_sma'],
            'fan_up_trend': last['fan_up_trend'],
            'fan_dn_trend': last['fan_dn_trend'],
            'engine_mode': 'Swing',
            'is_strategy_cold': False,
            'in_warmup': False
        }

        # Exit configuration
        atr_mult_use = 1.8
        stop_loss_long = last['low'] - last['atr'] * atr_mult_use
        stop_loss_short = last['high'] + last['atr'] * atr_mult_use
        take_profit_long = None
        take_profit_short = None

        exit_config = {
            'stop_loss_long': stop_loss_long,
            'stop_loss_short': stop_loss_short,
            'take_profit_long': take_profit_long,
            'take_profit_short': take_profit_short
        }

        return {
            'direction': direction,
            'metadata': metadata,
            'exit_config': exit_config
        }