"""
Live HyperLiquid credential test.
Uses env-provided HYPER_LIQUID_ETH_PRIVATE_KEY + ACCOUNT_ADDRESS.
DRY_RUN=true is enforced; no trades are sent.
"""
import os

os.environ["INSTANCE_SECRET_KEY"] = __import__("cryptography.fernet").fernet.Fernet.generate_key().decode()
os.environ["DRY_RUN"] = "true"
os.environ["DATABASE_URL"] = "sqlite:///data/test_live_account.db"

from core.exchange import HyperLiquidClient


def main():
    assert os.environ.get("DRY_RUN") == "true", "DRY_RUN must be true for this test"
    hl = HyperLiquidClient()
    assert hl.account is not None, "HL account failed to load from private key"
    assert hl.has_credentials, "HL has_credentials should be true"

    addr = hl._query_address()
    print(f"Loaded account address: {addr}")

    account_value = hl.get_account_value()
    print(f"Account value: {account_value}")
    assert isinstance(account_value, (int, float)), "account_value should be numeric"

    withdrawable = hl.get_withdrawable()
    print(f"Withdrawable: {withdrawable}")
    assert isinstance(withdrawable, (int, float)), "withdrawable should be numeric"

    position = hl.get_position("FARTCOIN")
    print(f"FARTCOIN position: {position}")

    # Cleanup
    for f in ["data/test_live_account.db", "data/test_live_account.db-wal", "data/test_live_account.db-shm"]:
        if os.path.exists(f):
            os.remove(f)
    print("Live account test: PASSED")


if __name__ == "__main__":
    main()
