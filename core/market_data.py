"""
Minimal HyperLiquid OHLCV fetcher.
"""

import json
from datetime import datetime, timedelta
from typing import Optional

import requests
import pandas as pd

from instances.models import SessionLocal, OHLCData


class HyperLiquidMarketData:
    BASE_URL = "https://api.hyperliquid.xyz/info"
    MAX_ROWS = 5000
    MAX_RETRIES = 3

    def __init__(self):
        self._session = requests.Session()

    @staticmethod
    def save_ohlc_batch(token: str, timeframe: str, df: pd.DataFrame):
        """Idempotently upsert fetched candles into ohlc_data for long-term history."""
        if df is None or df.empty:
            return
        db = SessionLocal()
        try:
            seen = set()
            for _, row in df.iterrows():
                ts = row["timestamp"]
                if (token, timeframe, ts) in seen:
                    continue
                seen.add((token, timeframe, ts))
                existing = db.query(OHLCData).filter(
                    OHLCData.token == token, OHLCData.timeframe == timeframe, OHLCData.timestamp == ts
                ).first()
                if existing:
                    existing.open, existing.high, existing.low, existing.close, existing.volume = (
                        float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"]), float(row["volume"])
                    )
                else:
                    db.add(OHLCData(
                        token=token, timeframe=timeframe, timestamp=ts,
                        open=float(row["open"]), high=float(row["high"]),
                        low=float(row["low"]), close=float(row["close"]), volume=float(row["volume"]),
                    ))
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"[WARN] OHLC persist failed: {e}")
        finally:
            db.close()

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

        # BUG #18: HL candleSnapshot does NOT support a "limit" key — it
        # returns everything from startTime→endTime. The old code fetched a
        # fixed 60-day window every tick (wasteful). Compute startTime from
        # bars * timeframe so we only pull the window we actually need.
        tf_minutes = {
            "1m": 1, "5m": 5, "15m": 15, "30m": 30,
            "1h": 60, "2h": 120, "4h": 240, "1d": 1440,
        }.get(timeframe, 15)
        window = timedelta(minutes=tf_minutes * bars)
        # Add 5% slack so we don't under-fetch near boundaries
        start_time = end_time - window * 1.05

        payload = {
            "type": "candleSnapshot",
            "req": {
                "coin": symbol,
                "interval": timeframe,
                "startTime": int(start_time.timestamp() * 1000),
                "endTime": int(end_time.timestamp() * 1000),
                # NOTE: "limit" is intentionally omitted — HL ignores it.
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

        # Persist to DB for long-term accumulation (idempotent upsert)
        try:
            HyperLiquidMarketData.save_ohlc_batch(symbol, timeframe, df)
        except Exception:
            pass

        # Return most recent `bars` sorted ascending
        df = df.sort_values("timestamp").tail(bars).reset_index(drop=True)
        return df

    @staticmethod
    def load_ohlc_from_db(token: str, timeframe: str, limit: int = 5000) -> pd.DataFrame:
        """Load accumulated candles from DB (oldest→newest), up to `limit` rows."""
        db = SessionLocal()
        try:
            rows = db.query(OHLCData).filter(
                OHLCData.token == token, OHLCData.timeframe == timeframe
            ).order_by(OHLCData.timestamp.asc()).limit(limit).all()
            if not rows:
                return pd.DataFrame()
            data = [{
                "timestamp": r.timestamp, "open": r.open, "high": r.high,
                "low": r.low, "close": r.close, "volume": r.volume,
            } for r in rows]
            return pd.DataFrame(data)
        finally:
            db.close()

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
