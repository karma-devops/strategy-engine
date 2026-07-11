"""
Inspect live AAVE position and calculate estimated entry/exit costs.
Uses live HyperLiquid credentials from env. DRY_RUN=true prevents any trade.
"""
import os

os.environ["INSTANCE_SECRET_KEY"] = __import__("cryptography.fernet").fernet.Fernet.generate_key().decode()
os.environ["DRY_RUN"] = "true"

from core.exchange import HyperLiquidClient


def main():
    hl = HyperLiquidClient()
    assert hl.account is not None, "HL account failed to load"

    account_value = hl.get_account_value()
    print(f"Account value: {account_value:.6f}")

    position = hl.get_position("AAVE")
    print(f"AAVE position: {position}")

    if not position:
        print("No open AAVE position.")
        return

    szi = float(position.get("szi", 0))
    side = "LONG" if szi > 0 else "SHORT"
    entry_px = float(position.get("entryPx", 0))
    mark_px = float(position.get("markPx", 0))
    size = abs(szi)
    pnl = float(position.get("unrealizedPnl", 0))
    pnl_pct = float(position.get("returnOnEquity", 0)) * 100

    price_diff = mark_px - entry_px
    price_diff_pct = (price_diff / entry_px * 100) if entry_px else 0

    fee_rate = 0.00035
    notional = size * mark_px
    entry_cost_est = notional * fee_rate
    exit_cost_est = notional * fee_rate
    total_cost_est = entry_cost_est + exit_cost_est

    print(f"\nPosition: {side} {size:.6f} AAVE")
    print(f"Entry price: {entry_px:.6f}")
    print(f"Mark price:  {mark_px:.6f}")
    print(f"Price diff:  {price_diff:.6f} ({price_diff_pct:.2f}%)")
    print(f"Unrealized PnL: {pnl:.6f} USDC ({pnl_pct:.2f}% ROE)")
    print(f"Notional (mark): {notional:.2f} USDC")
    print(f"Est entry cost (taker): {entry_cost_est:.4f} USDC")
    print(f"Est exit cost  (taker): {exit_cost_est:.4f} USDC")
    print(f"Est total cost: {total_cost_est:.4f} USDC")
    print(f"PnL after costs (taker estimate): {pnl - total_cost_est:.4f} USDC")

    if (pnl - total_cost_est) > 0:
        print("\nDECISION: Position is profitable after estimated costs.")
    else:
        print("\nDECISION: Position is NOT profitable after estimated costs.")


if __name__ == "__main__":
    main()
