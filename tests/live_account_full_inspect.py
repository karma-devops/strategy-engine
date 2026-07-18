"""
Inspect full live HyperLiquid account state.
Uses live HyperLiquid credentials from env. DRY_RUN=true prevents any trade.
"""
import os

os.environ["INSTANCE_SECRET_KEY"] = __import__("cryptography.fernet").fernet.Fernet.generate_key().decode()
os.environ["DRY_RUN"] = "true"

from core.exchange import HyperLiquidClient


def main():
    hl = HyperLiquidClient()
    assert hl.account is not None, "HL account failed to load"

    addr = hl._query_address()
    print(f"Query address: {addr}")
    print(f"Account address env: {hl._address}")
    print(f"Derived from key: {hl.account.address if hl.account else None}")

    account_value = hl.get_account_value()
    withdrawable = hl.get_withdrawable()
    print(f"Account value: {account_value}")
    print(f"Withdrawable: {withdrawable}")

    # Try fetching all perps via info endpoint
    try:
        user_state = hl._info.user_state(addr)
        print(f"\nFull user_state keys: {user_state.keys() if isinstance(user_state, dict) else 'not dict'}")
        if isinstance(user_state, dict):
            for k, v in user_state.items():
                print(f"  {k}: {v}")
    except Exception as e:
        print(f"user_state fetch failed: {e}")

    try:
        all_positions = hl._info.frontend_open_orders(addr)
        print(f"\nfrontend_open_orders: {all_positions}")
    except Exception as e:
        print(f"frontend_open_orders fetch failed: {e}")


if __name__ == "__main__":
    main()
