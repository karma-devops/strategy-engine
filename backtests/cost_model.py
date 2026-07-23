"""
Execution Cost Model — realistic crypto-perp trading costs.

Used by backtester, paper trading, and live engines to account for:
- maker / taker fees
- slippage (bps)
- spread (bps)

HyperLiquid typical values (subject to change — see https://hyperliquid.xyz/docs):
- maker fee: 0.02% (negative for rebate tiers, but default positive)
- taker fee: 0.05%
- slippage: ~5 bps on liquid meme pairs
- spread: ~3 bps typical
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


@dataclass
class ExecutionCostModel:
    """Realistic cost calculation for crypto perps.

    IMPORTANT NOTE ON BPS FIELD NAMING:
    The fields `slippage_bps` and `spread_bps` actually store DECIMAL FRACTIONS of notional,
    not raw basis points. For example, Decimal("0.0005") is 5 bps (0.05% of notional).
    Multiply directly by notional to get absolute cost. Do not pass raw values like '5.0' or '5'.
    """

    maker_fee: Decimal = Decimal("0.0002")      # 0.02% (typical maker)
    taker_fee: Decimal = Decimal("0.0005")       # 0.05% (typical taker)
    slippage_bps: Decimal = Decimal("0.0005")    # 5 bps (liquid meme) represented as decimal fraction
    spread_bps: Decimal = Decimal("0.0003")      # 3 bps typical represented as decimal fraction

    def calculate_entry_cost(
        self,
        position_value: Decimal,
        is_maker: bool = False,
    ) -> Decimal:
        """Total cost to open a position (as absolute value)."""
        fee = self.maker_fee if is_maker else self.taker_fee
        fee_cost = position_value * fee
        slippage_cost = position_value * self.slippage_bps
        spread_cost = position_value * self.spread_bps
        return fee_cost + slippage_cost + spread_cost

    def calculate_exit_cost(
        self,
        position_value: Decimal,
        is_maker: bool = False,
    ) -> Decimal:
        """Total cost to close a position (as absolute value)."""
        fee = self.maker_fee if is_maker else self.taker_fee
        fee_cost = position_value * fee
        slippage_cost = position_value * self.slippage_bps
        return fee_cost + slippage_cost

    def round_trip_cost_pct(self) -> Decimal:
        """Total cost as a percentage of notional for a full round-trip."""
        return (
            self.maker_fee
            + self.taker_fee
            + self.slippage_bps * 2
            + self.spread_bps
        ) * Decimal("100")

    def net_pnl(
        self,
        gross_pnl: Decimal,
        position_value: Decimal,
        is_maker_entry: bool = False,
        is_maker_exit: bool = False,
    ) -> Decimal:
        """Gross PnL minus entry + exit execution costs."""
        entry_cost = self.calculate_entry_cost(position_value, is_maker_entry)
        exit_cost = self.calculate_exit_cost(position_value, is_maker_exit)
        return gross_pnl - entry_cost - exit_cost


# Default singleton — tunable via environment or config if needed
DEFAULT_COST_MODEL = ExecutionCostModel()


def get_cost_model(
    maker_fee: Optional[float] = None,
    taker_fee: Optional[float] = None,
    slippage_bps: Optional[float] = None,
    spread_bps: Optional[float] = None,
) -> ExecutionCostModel:
    """Return a cost model, overriding defaults if provided."""
    return ExecutionCostModel(
        maker_fee=Decimal(str(maker_fee)) if maker_fee is not None else DEFAULT_COST_MODEL.maker_fee,
        taker_fee=Decimal(str(taker_fee)) if taker_fee is not None else DEFAULT_COST_MODEL.taker_fee,
        slippage_bps=Decimal(str(slippage_bps)) if slippage_bps is not None else DEFAULT_COST_MODEL.slippage_bps,
        spread_bps=Decimal(str(spread_bps)) if spread_bps is not None else DEFAULT_COST_MODEL.spread_bps,
    )
