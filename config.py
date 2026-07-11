"""
Global configuration for strategy-engine.
Secrets are loaded from environment variables only.
"""

import os
import secrets as _secrets
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Web
    PORT = int(os.getenv("STRATEGY_ENGINE_PORT", "8888"))
    FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY") or _secrets.token_hex(32)

    # Dashboard auth
    DASHBOARD_USERNAME = os.getenv("DASHBOARD_USERNAME", "operator")
    DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "operator")

    # API key for agent endpoints
    AGENT_API_KEY = os.getenv("AGENT_API_KEY")

    # HyperLiquid secrets
    HYPER_LIQUID_ETH_PRIVATE_KEY = os.getenv("HYPER_LIQUID_ETH_PRIVATE_KEY")
    ACCOUNT_ADDRESS = os.getenv("ACCOUNT_ADDRESS")

    # Per-instance credential encryption
    INSTANCE_SECRET_KEY = os.getenv("INSTANCE_SECRET_KEY")

    # Trading safety
    DRY_RUN = os.getenv("DRY_RUN", "true").lower() in ("1", "true", "yes")

    # Database
    DATABASE_PATH = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "data", "strategy_engine.db"
    )
    DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATABASE_PATH}")

    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    # Default first instance
    DEFAULT_INSTANCE = {
        "name": "FARTCOIN Scalp v1.3",
        "token": "FARTCOIN",
        "strategy_id": "engine_v1_3",
        "mode": "Scalp",
        "profile": "aggressive_8_3",
        "timeframe": "15m",
        "leverage": 10,
        "max_position_pct": 0.97,
        "poll_interval_seconds": 30,
        "dry_run": True,
    }


config = Config()
