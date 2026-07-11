"""
Unit-style test for enter/exit idempotency in InstanceRunner._tick.
Mocks HyperLiquidClient so no network creds are needed.
"""
import os

os.environ["INSTANCE_SECRET_KEY"] = __import__("cryptography.fernet").fernet.Fernet.generate_key().decode()
os.environ["DRY_RUN"] = "true"
os.environ["DATABASE_URL"] = "sqlite:///data/test_idempotency.db"

from unittest.mock import MagicMock, patch
import pandas as pd

from instances.models import engine, Instance
from sqlalchemy.orm import sessionmaker


def _make_instance(slug="engine-idem", token="MOCK"):
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        inst = db.query(Instance).filter(Instance.slug == slug).first()
        if inst:
            db.delete(inst)
            db.commit()
        inst = Instance(
            slug=slug,
            name="Idem Test",
            token=token,
            strategy_id="engine_v1_3",
            mode="Scalp",
            profile="aggressive_8_3",
            timeframe="15m",
            leverage=10,
            max_position_pct=0.97,
            poll_interval_seconds=30,
            dry_run=True,
            enabled=True,
            status="stopped",
        )
        db.add(inst)
        db.commit()
        db.refresh(inst)
        return inst
    finally:
        db.close()


def _make_strategy_mock(direction="BUY", metadata=None):
    strategy = MagicMock()
    signal = 1.0 if direction in ("BUY", "SELL") else 0.0
    strategy.generate_signals.return_value = {
        "direction": direction,
        "signal": signal,
        "metadata": metadata or {"adx": 35.0, "engine_mode": "Scalp", "use_time_exit": False},
    }
    return strategy


def _make_hl_mock(position_side=None):
    hl = MagicMock()
    hl.has_credentials = True
    hl.get_account_value.return_value = 10000.0
    hl.get_withdrawable.return_value = 9000.0
    if position_side == "LONG":
        hl.get_position.return_value = {"coin": "MOCK", "szi": 1.0, "entryPx": 1.0, "markPx": 1.0, "unrealizedPnl": 0, "returnOnEquity": 0}
    elif position_side == "SHORT":
        hl.get_position.return_value = {"coin": "MOCK", "szi": -1.0, "entryPx": 1.0, "markPx": 1.0, "unrealizedPnl": 0, "returnOnEquity": 0}
    else:
        hl.get_position.return_value = None
    hl.market_close.return_value = {"status": "dry_run"}
    hl.market_open.return_value = {"status": "dry_run"}
    return hl


def main():
    for f in ["data/test_idempotency.db", "data/test_idempotency.db-wal", "data/test_idempotency.db-shm"]:
        if os.path.exists(f):
            os.remove(f)

    inst = _make_instance()
    from instances.runner import InstanceRunner
    runner = InstanceRunner(inst)

    # 1. Flat + BUY signal -> should enter LONG
    hl = _make_hl_mock(None)
    runner._hl = hl
    with patch("instances.runner.market_data") as md_mock:
        md_mock.get_candles.return_value = pd.DataFrame({"close": [1.0] * 100})
        runner._tick(_make_strategy_mock("BUY"), hl)
    assert runner._active_trade is not None and runner._active_trade["side"] == "LONG"
    assert hl.market_open.call_count == 1
    assert hl.market_close.call_count == 0
    print("Flat + BUY -> entered LONG")

    # 2. Still LONG + repeated BUY signal -> should NOT enter again
    hl = _make_hl_mock("LONG")
    runner._hl = hl
    with patch("instances.runner.market_data") as md_mock:
        md_mock.get_candles.return_value = pd.DataFrame({"close": [1.0] * 100})
        runner._tick(_make_strategy_mock("BUY"), hl)
    assert runner._active_trade["side"] == "LONG"
    assert hl.market_open.call_count == 0
    assert hl.market_close.call_count == 0
    print("Repeated BUY while LONG -> no re-entry")

    # 3. LONG + SELL (reversal) signal -> should close
    with patch("instances.runner.market_data") as md_mock:
        md_mock.get_candles.return_value = pd.DataFrame({"close": [1.0] * 100})
        runner._tick(_make_strategy_mock("SELL"), hl)
    assert runner._active_trade is None
    assert hl.market_close.call_count == 1
    print("LONG + SELL -> closed position")

    # 4. Flat again + SELL signal -> should enter SHORT
    hl = _make_hl_mock(None)
    runner._hl = hl
    with patch("instances.runner.market_data") as md_mock:
        md_mock.get_candles.return_value = pd.DataFrame({"close": [1.0] * 100})
        runner._tick(_make_strategy_mock("SELL"), hl)
    assert runner._active_trade is not None and runner._active_trade["side"] == "SHORT"
    assert hl.market_open.call_count == 1
    assert hl.market_close.call_count == 0
    print("Flat + SELL -> entered SHORT")

    # 5. Still SHORT + repeated SELL -> should NOT enter again
    hl = _make_hl_mock("SHORT")
    runner._hl = hl
    with patch("instances.runner.market_data") as md_mock:
        md_mock.get_candles.return_value = pd.DataFrame({"close": [1.0] * 100})
        runner._tick(_make_strategy_mock("SELL"), hl)
    assert runner._active_trade["side"] == "SHORT"
    assert hl.market_open.call_count == 0
    assert hl.market_close.call_count == 0
    print("Repeated SELL while SHORT -> no re-entry")

    # Cleanup
    for f in ["data/test_idempotency.db", "data/test_idempotency.db-wal", "data/test_idempotency.db-shm"]:
        if os.path.exists(f):
            os.remove(f)
    print("Enter/exit idempotency test: PASSED")


if __name__ == "__main__":
    main()
