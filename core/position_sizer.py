"""
Position sizing utilities for HyperLiquid.
"""

from core.market_data import market_data


class PositionSizer:
    @staticmethod
    def size_from_notional(symbol: str, notional_usd: float, price: float) -> float:
        """
        Convert desired notional USD position size into coin quantity,
        rounded to HyperLiquid szDecimals.
        """
        if notional_usd <= 0 or price <= 0:
            return 0.0

        meta = market_data.get_meta()
        info = meta.get(symbol)
        if not info:
            # Fallback: 4 decimals
            sz_decimals = 4
        else:
            sz_decimals = int(info.get("szDecimals", 4))

        qty = notional_usd / price
        return round(qty, sz_decimals)

    @staticmethod
    def max_position_notional(account_value: float, max_position_pct: float) -> float:
        return account_value * max_position_pct

    @staticmethod
    def notional_from_free_balance(
        free_balance: float,
        leverage: int,
        max_position_pct: float,
    ) -> float:
        """
        Max notional position we can open given free balance, leverage, and cap.
        """
        if free_balance <= 0 or leverage <= 0:
            return 0.0
        return free_balance * leverage * max_position_pct
