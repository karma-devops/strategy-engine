"""
Minimal HyperLiquid OHLCV fetcher.
"""

import json
from datetime import datetime, timedelta
from typing import Optional

import requests
import pandas as pd


class HyperLiquidMarketData:
    BASE_URL = "https://api.hyperliquid.xyz/info"
    MAX_ROWS = 5000
    MAX_RETRIES = 3

    def __init__(self):
        self._session = requests.Session()

    def _post(self, payload: dict) -> Optional[list]:
        for attempt in range(self.MAX_RETRIES):
            try:
                resp = self._session.post(
                    self.BASE_URL,
                    headers={"Content-Type": "application/json"},
                    data=json.dumps(payload),
                    timeout=10,
                )
                if resp.status_code == 200:
                    return resp.json()
                print(f"[WARN] HL API status {resp.status_code}: {resp.text[:200]}")
            except Exception as e:
                print(f"[WARN] HL API request failed (attempt {attempt + 1}): {e}")
        return None

    def get_candles(
        self,
        symbol: str,
        timeframe: str = "15m",
        bars: int = 100,
    ) -> pd.DataFrame:
        """
        Fetch OHLCV candles from HyperLiquid REST.
        Returns DataFrame with columns: timestamp, open, high, low, close, volume.
        """
        bars = min(int(bars), self.MAX_ROWS)
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=60)

        payload = {
            "type": "candleSnapshot",
            "req": {
                "coin": symbol,
                "interval": timeframe,
                "startTime": int(start_time.timestamp() * 1000),
                "endTime": int(end_time.timestamp() * 1000),
                "limit": bars,
            },
        }

        data = self._post(payload)
        if not data:
            return pd.DataFrame()

        rows = []
        for candle in data:
            ts = datetime.utcfromtimestamp(candle["t"] / 1000)
            rows.append(
                [
                    ts,
                    float(candle["o"]),
                    float(candle["h"]),
                    float(candle["l"]),
                    float(candle["c"]),
                    float(candle["v"]),
                ]
            )

        df = pd.DataFrame(
            rows, columns=["timestamp", "open", "high", "low", "close", "volume"]
        )
        numeric_cols = ["open", "high", "low", "close", "volume"]
        df[numeric_cols] = df[numeric_cols].astype("float64")

        # Return most recent `bars` sorted ascending
        df = df.sort_values("timestamp").tail(bars).reset_index(drop=True)
        return df

    def get_mid_price(self, symbol: str) -> Optional[float]:
        """Get mid price from L2 orderbook."""
        payload = {"type": "l2Book", "coin": symbol}
        data = self._post(payload)
        if not data or "levels" not in data:
            return None
        levels = data["levels"]
        if len(levels) < 2 or not levels[0] or not levels[1]:
            return None
        bid = float(levels[0][0]["px"])
        ask = float(levels[1][0]["px"])
        return (bid + ask) / 2.0

    def get_meta(self) -> dict:
        """Get universe metadata: szDecimals per symbol."""
        payload = {"type": "meta"}
        data = self._post(payload)
        if not data:
            return {}
        return {coin["name"]: coin for coin in data.get("universe", [])}


# Convenience singleton
market_data = HyperLiquidMarketData()
