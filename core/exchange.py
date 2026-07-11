"""
HyperLiquid SDK wrapper for strategy-engine.
All trading methods are guarded by DRY_RUN.
"""

import os
import random
import time
import traceback
from typing import Optional, Tuple

from hyperliquid.info import Info
from hyperliquid.exchange import Exchange
from hyperliquid.utils import constants
from eth_account.signers.local import LocalAccount
import eth_account

from config import config


# ------------------------------------------------------------------
# Safe retry / backoff helper
# ------------------------------------------------------------------
NETWORK_ERRORS = (
    ConnectionError,
    TimeoutError,
    OSError,
)


def _is_non_retryable(exc: Exception) -> bool:
    """Auth, config, and client-side validation errors should not be retried."""
    msg = str(exc).lower()
    non_retryable_keywords = [
        "unauthorized",
        "forbidden",
        "invalid signature",
        "invalid address",
        "no account_address",
        "no private key",
        "cannot open",
        "invalid price",
        "invalid qty",
    ]
    return any(k in msg for k in non_retryable_keywords)


def retry_with_backoff(max_attempts: int = 3, base_delay: float = 1.0, max_delay: float = 10.0):
    """Decorator: exponential backoff with jitter for transient HL API errors."""
    def decorator(fn):
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except Exception as e:
                    last_exc = e
                    if attempt == max_attempts or _is_non_retryable(e):
                        raise
                    delay = min(base_delay * (2 ** (attempt - 1)) + random.uniform(0, 1), max_delay)
                    print(f"[RETRY] {fn.__name__} attempt {attempt}/{max_attempts} failed: {e}; sleeping {delay:.1f}s")
                    time.sleep(delay)
            raise last_exc
        return wrapper
    return decorator


class HyperLiquidClient:
    """
    Thin, safe wrapper around hyperliquid-python-sdk.
    Private key is loaded from env or per-instance override and never logged.
    """

    def __init__(self, private_key: Optional[str] = None, account_address: Optional[str] = None):
        self._private_key = private_key or config.HYPER_LIQUID_ETH_PRIVATE_KEY
        self._address = account_address or config.ACCOUNT_ADDRESS
        self.dry_run = config.DRY_RUN

        self.account: Optional[LocalAccount] = None
        if self._private_key:
            try:
                self.account = eth_account.Account.from_key(self._private_key)
            except Exception as e:
                print(f"[ERROR] Failed to load HL account: {e}")
                traceback.print_exc()

        self._info = Info(constants.MAINNET_API_URL, skip_ws=True)
        self._exchange: Optional[Exchange] = None
        if self.account:
            self._exchange = Exchange(self.account, constants.MAINNET_API_URL)

    @property
    def has_credentials(self) -> bool:
        return bool(self._address) or bool(self.account)

    # ------------------------------------------------------------------
    # Account helpers
    # ------------------------------------------------------------------
    def _query_address(self) -> str:
        if self._address:
            return self._address
        if self.account:
            return self.account.address
        raise RuntimeError("No ACCOUNT_ADDRESS or private key configured")

    @retry_with_backoff(max_attempts=3, base_delay=0.5, max_delay=5.0)
    def get_account_value(self) -> float:
        """Return total account value in USDC (perps + spot fallback)."""
        if not self.has_credentials:
            return 0.0
        try:
            state = self._info.user_state(self._query_address())
            value = float(state.get("marginSummary", {}).get("accountValue", 0))
            if value == 0.0:
                value = self._spot_usdc_balance(self._query_address())
            return value
        except Exception as e:
            print(f"[ERROR] get_account_value failed: {e}")
            return 0.0

    @retry_with_backoff(max_attempts=3, base_delay=0.5, max_delay=5.0)
    def get_withdrawable(self) -> float:
        """Return withdrawable balance (perps withdrawable + spot fallback)."""
        if not self.has_credentials:
            return 0.0
        try:
            state = self._info.user_state(self._query_address())
            account_value = float(state.get("marginSummary", {}).get("accountValue", 0))
            open_position_value = float(state.get("openPositionValue", 0))
            withdrawable = account_value - open_position_value
            if withdrawable == 0.0:
                withdrawable = self._spot_usdc_balance(self._query_address())
            return withdrawable
        except Exception as e:
            print(f"[ERROR] get_withdrawable failed: {e}")
            return 0.0

    def _spot_usdc_balance(self, address: str) -> float:
        """Check spot clearinghouse USDC balance (Manual mode fallback)."""
        try:
            import requests

            resp = requests.post(
                "https://api.hyperliquid.xyz/info",
                headers={"Content-Type": "application/json"},
                json={"type": "spotClearinghouseState", "user": address.lower()},
                timeout=10,
            )
            if resp.status_code == 200:
                spot_state = resp.json()
                for balance in spot_state.get("balances", []):
                    if balance.get("coin") == "USDC":
                        return float(balance.get("total", "0"))
        except Exception as e:
            print(f"[WARN] spot USDC check failed: {e}")
        return 0.0

    @retry_with_backoff(max_attempts=3, base_delay=0.5, max_delay=5.0)
    def get_position(self, symbol: str):
        """
        Return first non-zero position for symbol as dict, or None.
        Keys: coin, szi, entryPx, returnOnEquity, leverage.
        """
        if not self.has_credentials:
            return None
        try:
            state = self._info.user_state(self._query_address())
            for pos in state.get("assetPositions", []):
                raw = pos.get("position", {})
                if raw.get("coin") == symbol and float(raw.get("szi", 0)) != 0:
                    return raw
        except Exception as e:
            print(f"[ERROR] get_position failed: {e}")
        return None

    @retry_with_backoff(max_attempts=3, base_delay=0.5, max_delay=5.0)
    def set_leverage(self, symbol: str, leverage: int) -> Optional[dict]:
        if self.dry_run:
            print(f"[DRY RUN] Would set {symbol} leverage to {leverage}x")
            return {"status": "dry_run"}
        if not self._exchange:
            print("[ERROR] No exchange client available")
            return None
        try:
            return self._exchange.update_leverage(leverage, symbol, is_cross=True)
        except Exception as e:
            print(f"[ERROR] set_leverage failed: {e}")
            traceback.print_exc()
            return None

    # ------------------------------------------------------------------
    # Order execution
    # ------------------------------------------------------------------
    @retry_with_backoff(max_attempts=3, base_delay=1.0, max_delay=8.0)
    def market_open(
        self,
        symbol: str,
        side: str,  # "long" or "short"
        size_usd: float,
        leverage: int = 10,
    ) -> Optional[dict]:
        """
        Open a market-direction position.
        size_usd is NOTIONAL position size. Leverage is set first.
        """
        if self.dry_run:
            print(
                f"[DRY RUN] Would OPEN {side.upper()} {symbol} for ${size_usd:.2f} at {leverage}x"
            )
            return {"status": "dry_run", "symbol": symbol, "side": side, "size_usd": size_usd}

        if not self._exchange:
            print("[ERROR] No exchange client available")
            return None

        # Set leverage
        self.set_leverage(symbol, leverage)

        # Get current mid price
        from core.market_data import HyperLiquidMarketData
        md = HyperLiquidMarketData()
        mid = md.get_mid_price(symbol)
        if mid is None or mid <= 0:
            print(f"[ERROR] Cannot open {symbol}: invalid price {mid}")
            return None

        # Compute coin quantity and round to szDecimals
        from core.position_sizer import PositionSizer
        qty = PositionSizer.size_from_notional(symbol, size_usd, mid)
        if qty is None or qty <= 0:
            print(f"[ERROR] Cannot open {symbol}: invalid qty {qty}")
            return None

        is_buy = side.lower() == "long"
        # Use IOC limit order with 0.5% slippage to simulate market fill
        limit_px = mid * (1.005 if is_buy else 0.995)
        limit_px = round(limit_px, 6)

        try:
            result = self._exchange.order(
                symbol,
                is_buy,
                qty,
                limit_px,
                {"limit": {"tif": "Ioc"}},
                reduce_only=False,
            )
            print(f"[TRADE] OPEN {side.upper()} {symbol} {qty} @ ~${mid:.6f}")
            return result
        except Exception as e:
            print(f"[ERROR] market_open failed: {e}")
            traceback.print_exc()
            return None

    @retry_with_backoff(max_attempts=3, base_delay=1.0, max_delay=8.0)
    def market_close(self, symbol: str) -> Optional[dict]:
        """Close entire open position for symbol at market."""
        pos = self.get_position(symbol)
        if not pos:
            print(f"[INFO] No open position in {symbol} to close")
            return {"status": "no_position"}

        szi = float(pos.get("szi", 0))
        is_long = szi > 0
        qty = abs(szi)

        if self.dry_run:
            print(f"[DRY RUN] Would CLOSE {symbol} position ({'LONG' if is_long else 'SHORT'} {qty})")
            return {"status": "dry_run", "symbol": symbol, "qty": qty}

        if not self._exchange:
            print("[ERROR] No exchange client available")
            return None

        # Get current mid price
        from core.market_data import HyperLiquidMarketData
        md = HyperLiquidMarketData()
        mid = md.get_mid_price(symbol)
        if mid is None or mid <= 0:
            print(f"[ERROR] Cannot close {symbol}: invalid price {mid}")
            return None

        # Opposite side to close
        is_buy = not is_long
        limit_px = mid * (1.005 if is_buy else 0.995)
        limit_px = round(limit_px, 6)

        try:
            result = self._exchange.order(
                symbol,
                is_buy,
                qty,
                limit_px,
                {"limit": {"tif": "Ioc"}},
                reduce_only=True,
            )
            print(f"[TRADE] CLOSE {symbol} qty={qty}")
            return result
        except Exception as e:
            print(f"[ERROR] market_close failed: {e}")
            traceback.print_exc()
            return None

    @retry_with_backoff(max_attempts=3, base_delay=1.0, max_delay=8.0)
    def withdraw_to_wallet(self, amount: float, destination: Optional[str] = None) -> Optional[dict]:
        """
        Withdraw USDC to the configured/destination address.
        Always guarded by DRY_RUN for now.
        """
        if self.dry_run:
            print(f"[DRY RUN] Would withdraw ${amount:.2f} USDC")
            return {"status": "dry_run", "amount": amount}

        if not self._exchange:
            print("[ERROR] No exchange client available")
            return None

        target = destination or self._query_address()
        try:
            # Withdraw all USDC to target address; amount is advisory check
            result = self._exchange.withdraw(target, amount)
            print(f"[WITHDRAWAL] Sent ${amount:.2f} USDC to {target}")
            return result
        except Exception as e:
            print(f"[ERROR] withdraw_to_wallet failed: {e}")
            traceback.print_exc()
            return None


# Convenience singleton
hl_client = HyperLiquidClient()


def get_hyperliquid_client(instance: Optional[object] = None) -> HyperLiquidClient:
    """
    Return a HyperLiquidClient.
    If instance is provided and has per-instance credentials, use those;
    otherwise fall back to the global env-based singleton.
    """
    if instance is None:
        return hl_client
    private_key = None
    account_address = None
    try:
        private_key = instance.get_private_key()
        account_address = instance.get_account_address()
    except Exception as e:
        print(f"[ERROR] Failed to load per-instance credentials for {instance.slug}: {e}")
    if private_key or account_address:
        return HyperLiquidClient(private_key=private_key, account_address=account_address)
    return hl_client
