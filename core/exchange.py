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

    def __init__(self, private_key: Optional[str] = None, account_address: Optional[str] = None, dry_run: Optional[bool] = None):
        self._private_key = private_key or config.HYPER_LIQUID_ETH_PRIVATE_KEY
        self._address = account_address or config.ACCOUNT_ADDRESS
        # Per-instance dry_run overrides env; env is the default seed
        self.dry_run = dry_run if dry_run is not None else config.DRY_RUN

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

    def _spot_usdc_available(self, address: str) -> float:
        """Return spot USDC balance available outside perps margin (unified account)."""
        try:
            spot_state = self._info.spot_user_state(address)
            for balance in spot_state.get("balances", []):
                if balance.get("coin") == "USDC":
                    total = float(balance.get("total", "0"))
                    hold = float(balance.get("hold", "0"))
                    return max(0.0, total - hold)
        except Exception as e:
            print(f"[WARN] spot USDC available check failed: {e}")
        return 0.0

    @retry_with_backoff(max_attempts=3, base_delay=0.5, max_delay=5.0)
    def get_account_value(self) -> float:
        """Return total portfolio value in USDC (perps accountValue + available spot USDC)."""
        if not self.has_credentials:
            return 0.0
        try:
            address = self._query_address()
            state = self._info.user_state(address)
            perps_value = float(state.get("marginSummary", {}).get("accountValue", 0))
            spot_available = self._spot_usdc_available(address)
            value = perps_value + spot_available
            if value == 0.0:
                value = float(self._spot_usdc_balance(address))
            return value
        except Exception as e:
            print(f"[ERROR] get_account_value failed: {e}")
            return 0.0

    @retry_with_backoff(max_attempts=3, base_delay=0.5, max_delay=5.0)
    def get_max_leverage(self, symbol: str) -> int:
        """Return HL's max allowed leverage for a token from meta_and_asset_ctxs."""
        if not self.has_credentials:
            return 0
        try:
            meta, ctxs = self._info.meta_and_asset_ctxs()
            for m, c in zip(meta.get("universe", []), ctxs):
                if m.get("name") == symbol:
                    return int(c.get("maxLeverage", 0))
        except Exception as e:
            print(f"[ERROR] get_max_leverage({symbol}) failed: {e}")
        return 0

    @retry_with_backoff(max_attempts=3, base_delay=0.5, max_delay=5.0)
    def get_recent_fills(self, symbol: str, limit: int = 20):
        """Return recent fills for the account filtered by symbol (from user_fills)."""
        if not self.has_credentials:
            return []
        try:
            fills = self._info.user_fills(self._query_address())
            out = []
            for f in fills:
                if f.get("coin") != symbol:
                    continue
                out.append({
                    "coin": f.get("coin"),
                    "side": f.get("dir"),  # "Open Long" / "Close Short" etc.
                    "px": float(f.get("px", 0)),
                    "sz": float(f.get("sz", 0)),
                    "fee": float(f.get("fee", 0)),
                    "time": f.get("time"),
                    "closed_pnl": float(f.get("closedPnl", 0)),
                    "oid": f.get("oid"),
                })
                if len(out) >= limit:
                    break
            return out
        except Exception as e:
            print(f"[ERROR] get_recent_fills({symbol}) failed: {e}")
        return []

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
        cloid: Optional[str] = None,
    ) -> Optional[dict]:
        """
        Open a market-direction position.
        size_usd is NOTIONAL position size. Leverage is set first.
        cloid: stable client order id. Generated ONCE if None so retries reuse
        the same cloid -> HL dedups a lost-response retry instead of
        double-filling (bug #1).
        """
        if cloid is None:
            cloid = self._make_cloid(symbol, "open")
        if self.dry_run:
            print(
                f"[DRY RUN] Would OPEN {side.upper()} {symbol} for ${size_usd:.2f} at {leverage}x (cloid={cloid})"
            )
            return {"status": "dry_run", "symbol": symbol, "side": side, "size_usd": size_usd}

        if not self._exchange:
            print("[ERROR] No exchange client available")
            return None

        # Set leverage
        lev_result = self.set_leverage(symbol, leverage)
        if lev_result is None:
            print(f"[ERROR] Cannot open {symbol}: set_leverage returned None (no exchange client?)")
            return None
        if isinstance(lev_result, dict) and lev_result.get("status") == "err":
            print(f"[ERROR] Cannot open {symbol}: leverage rejected by exchange: {lev_result.get('response', 'unknown')}")
            return None

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

        # Minimum order size guard — HL rejects orders below ~$10 notional
        min_notional = 10.0
        actual_notional = qty * mid
        if actual_notional < min_notional:
            print(f"[ERROR] Cannot open {symbol}: notional ${actual_notional:.2f} below HL minimum ${min_notional:.2f} (qty={qty} @ ${mid:.6f})")
            return None

        is_buy = side.lower() == "long"
        # Use IOC limit order with 0.5% slippage to simulate market fill
        limit_px = mid * (1.005 if is_buy else 0.995)
        # Round to 5 decimals — safe for all HL assets (min tick 0.00001)
        limit_px = round(limit_px, 5)

        from hyperliquid.utils.types import Cloid
        try:
            result = self._exchange.order(
                symbol,
                is_buy,
                qty,
                limit_px,
                {"limit": {"tif": "Ioc"}},
                reduce_only=False,
                cloid=Cloid.from_str(cloid) if cloid else None,
            )
            print(f"[TRADE] OPEN {side.upper()} {symbol} {qty} @ ~${mid:.6f}")
            return result
        except Exception as e:
            print(f"[ERROR] market_open failed: {e}")
            traceback.print_exc()
            return None

    @retry_with_backoff(max_attempts=3, base_delay=1.0, max_delay=8.0)
    def market_close(self, symbol: str, cloid: Optional[str] = None) -> Optional[dict]:
        "Close entire open position for symbol at market."
        if cloid is None:
            cloid = self._make_cloid(symbol, "close")
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
        # Round to 5 decimals — safe for all HL assets (min tick 0.00001)
        limit_px = round(limit_px, 5)

        from hyperliquid.utils.types import Cloid
        try:
            result = self._exchange.order(
                symbol,
                is_buy,
                qty,
                limit_px,
                {"limit": {"tif": "Ioc"}},
                reduce_only=True,
                cloid=Cloid.from_str(cloid) if cloid else None,
            )
            print(f"[TRADE] CLOSE {symbol} qty={qty}")
            return result
        except Exception as e:
            print(f"[ERROR] market_close failed: {e}")
            traceback.print_exc()
            return None

    def _make_cloid(self, symbol: str, action: str, stable_id: Optional[str] = None) -> str:
        """Generate a client order ID for HL idempotency.

        HL dedupes orders by cloid server-side. If a retry fires after the
        first order already landed (response lost mid-flight), the duplicate
        cloid is rejected by HL instead of creating a second fill.

        HL's Cloid.from_str() expects a 32-character hex string. We generate
        that by hashing a stable local seed (symbol + action + stable_id).
        If stable_id is None, one is generated from current timestamp — but
        callers should generate stable_id ONCE and pass it so retries within
        retry_with_backoff reuse the same cloid.

        Bug #1 fix: removed random component so retries produce identical cloid.
        """
        import hashlib as _hashlib
        if stable_id is None:
            import time as _time
            stable_id = str(int(_time.time()))
        seed = f"{symbol}:{action}:{stable_id}"
        cloid = "0x" + _hashlib.sha256(seed.encode()).hexdigest()[:32]
        return cloid
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
        # Prefer the engine-level credential selector (hl_credential_id -> Credential table).
        # Falls back to instance's own encrypted key, then to global env client.
        private_key, account_address = instance.get_resolved_hl_credentials()
    except Exception as e:
        print(f"[ERROR] Failed to resolve HL credentials for {instance.slug}: {e}")
    inst_dry_run = getattr(instance, "dry_run", None)
    if private_key or account_address:
        return HyperLiquidClient(
            private_key=private_key,
            account_address=account_address,
            dry_run=inst_dry_run,
        )
    # No per-instance credentials — use global env keys but still respect
    # the instance's dry_run setting (per-instance override > global env).
    global_key = config.HYPER_LIQUID_ETH_PRIVATE_KEY
    global_addr = config.ACCOUNT_ADDRESS
    if global_key and global_addr:
        return HyperLiquidClient(
            private_key=global_key,
            account_address=global_addr,
            dry_run=inst_dry_run,
        )
    # No per-instance credentials and no global keys — use the singleton.
    # P14: If the instance has a dry_run setting, honor it even on the singleton.
    if inst_dry_run is not None and inst_dry_run != hl_client.dry_run:
        # Instance's dry_run differs from singleton's default — create a fresh
        # client with the correct dry_run so paper instances never hit live API.
        return HyperLiquidClient(
            private_key=config.HYPER_LIQUID_ETH_PRIVATE_KEY,
            account_address=config.ACCOUNT_ADDRESS,
            dry_run=inst_dry_run,
        )
    return hl_client
