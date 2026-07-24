"""
Minimal base strategy for strategy-engine.
"""

from abc import ABC, abstractmethod


class BaseStrategy(ABC):
    def __init__(self, name: str, **kwargs):
        self.name = name
        # Apply any kwargs as attributes (for per-instance config overrides)
        for key, val in kwargs.items():
            if hasattr(self, key) or key in self._accepted_params():
                setattr(self, key, val)

    @classmethod
    def _accepted_params(cls) -> set:
        """Override in subclass to whitelist accepted kwargs."""
        return set()

    @classmethod
    def get_parameters(cls) -> list[dict]:
        """
        Declare configurable parameters for UI rendering.
        Each dict: {name, label, type, default, group, ...}
        type: "select" (with options), "int", "float", "bool"
        Override in subclass.
        """
        return []

    @classmethod
    def get_default_config(cls) -> dict:
        """Return default parameter values from get_parameters()."""
        return {p["name"]: p["default"] for p in cls.get_parameters()}

    @abstractmethod
    def generate_signals(
        self,
        df,
        symbol: str = "",
        equity_history: list = None,
    ) -> dict:
        """
        Generate a trading signal for the latest bar in ``df``.

        Returns:
            dict: {
                "token": str,
                "signal": float,        # 0..1
                "direction": str,       # "BUY", "SELL", or "NEUTRAL"
                "metadata": dict,       # indicator values, equity state, etc.
                "exit_config": dict,     # strategy-declared exit parameters
            }

        Exit Contract (exit_config):
            The strategy declares which exits exist and their parameters.
            The runner/worker are NEUTRAL CONSUMERS - they evaluate only
            what the strategy declares. No fabricated exits.

            Required keys (strategy must emit all, use None if N/A):
                stop_loss_long: float | None      # hard stop price for long
                stop_loss_short: float | None     # hard stop price for short
                take_profit_long: float | None    # TP price (None = no fixed TP)
                take_profit_short: float | None
                trail_activation: int             # ticks to activate trailing
                trail_offset: int                # ticks for trail offset
                use_time_exit: bool               # time-based exit enabled?
                time_exit_bars: int | None        # max bars in trade (if use_time_exit)
                engine_mode: str                 # "Swing" | "Scalp"
                fan_up_trend: bool               # EMA fan stacked bullish
                fan_dn_trend: bool               # EMA fan stacked bearish
                fast_ema: float                  # current fast EMA value
                medm_ema: float                   # current medium EMA value

        Exit Evaluation Order (consumer follows this):
            1. Stop Loss     - if stop_loss_long/short is not None
            2. Trailing Stop - if trail_activation > 0
            3. Take Profit   - if take_profit_long/short is not None
            4. Trend Change  - EMA cross (always, bar-to-bar)
            5. Time Exit     - if use_time_exit is True and engine_mode == "Scalp"

        NOT in the exit contract (removed - not in any PineScript):
            - Full fan alignment against position (fabricated)
            - Reversal signal / opposite entry signal (fabricated)
        """
        raise NotImplementedError("Strategy must implement generate_signals()")
