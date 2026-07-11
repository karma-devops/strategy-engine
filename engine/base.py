"""
Minimal base strategy for strategy-engine.
"""

from abc import ABC, abstractmethod


class BaseStrategy(ABC):
    def __init__(self, name: str):
        self.name = name

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
                "metadata": dict,
            }
        """
        raise NotImplementedError("Strategy must implement generate_signals()")
