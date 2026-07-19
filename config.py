"""
Global configuration for strategy-engine.
Secrets are loaded from environment variables only.
"""

import os
import secrets as _secrets
from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    """Fail-fast: mandatory env var must be present at boot.

    Prevents silent security regressions (e.g. shipping with a default
    dashboard password, or running credential encryption with no key).
    """
    val = os.getenv(name)
    if not val:
        raise RuntimeError(
            f"FATAL: required env var {name} is not set. "
            f"Set it in .env or the environment before booting."
        )
    return val


class Config:
    # Web
    PORT = int(os.getenv("STRATEGY_ENGINE_PORT", "8888"))
    FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY") or _secrets.token_hex(32)

    # Dashboard auth
    # Both username and password MUST be set via env — no defaults.
    # Fails fast at boot if either is missing (prevents silent misconfig).
    DASHBOARD_USERNAME = _require("DASHBOARD_USERNAME")
    DASHBOARD_PASSWORD = _require("DASHBOARD_PASSWORD")

    # API key for agent endpoints — mandatory, fails fast if unset
    AGENT_API_KEY = _require("AGENT_API_KEY")

    # HyperLiquid secrets
    HYPER_LIQUID_ETH_PRIVATE_KEY = os.getenv("HYPER_LIQUID_ETH_PRIVATE_KEY")
    ACCOUNT_ADDRESS = os.getenv("ACCOUNT_ADDRESS")

    # Per-instance credential encryption — mandatory, fails fast if unset
    INSTANCE_SECRET_KEY = _require("INSTANCE_SECRET_KEY")

    # Trading safety
    DRY_RUN = os.getenv("DRY_RUN", "true").lower() in ("1", "true", "yes")

    # AI provider (Strategy Studio Pine→Python conversion)
    AI_PROVIDER = os.getenv("AI_PROVIDER", "openrouter")  # ollama | openai | openrouter | anthropic
    AI_MODEL = os.getenv("AI_MODEL", "glm-5.1")
    AI_API_KEY = (
        os.getenv("AI_API_KEY")
        or os.getenv("OPENROUTER_API_KEY")
        or os.getenv("OPENROUTER_API_KEY_2")
        or os.getenv("OLLAMA_API_KEY")
        or os.getenv("OLLAMA_API_KEY_2")
    )
    AI_API_URL = os.getenv("AI_API_URL", "https://ollama.com/v1")

    # Database
    DATABASE_PATH = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "data", "strategy_engine.db"
    )
    # Ensure the data/ directory exists at boot so a fresh deploy doesn't
    # crash on first DB access (sqlite can't create the parent dir itself).
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
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


    # ── Multi-tenant credential resolver ──────────────────────────────────────
    # DB credentials take priority. Env-var fallback ONLY for operator user.
    # Other tenants must store credentials in the DB.
    OPERATOR_USERNAME = "operator"

    def get_credential(self, cred_type: str, user_id: str, priority: int = 0) -> dict | None:
        """Resolve a credential for a tenant.

        Order:
          1. DB: credentials WHERE user_id, type, priority, is_active
          2. If user is operator AND not found → env var fallback
          3. Otherwise → None

        Returns decrypted dict or None.
        """
        from instances.models import SessionLocal, Credential, User
        db = SessionLocal()
        try:
            cred = (
                db.query(Credential)
                .filter(
                    Credential.user_id == user_id,
                    Credential.type == cred_type,
                    Credential.priority == priority,
                    Credential.is_active == True,  # noqa: E712
                )
                .first()
            )
            if cred:
                return cred.decrypt()
            # Env fallback for operator only
            user = db.query(User).filter(User.id == user_id).first()
            if user and user.username == self.OPERATOR_USERNAME:
                return self._env_fallback(cred_type)
            return None
        finally:
            db.close()

    def _env_fallback(self, cred_type: str) -> dict | None:
        """Operator-only env var fallback. Returns dict or None."""
        if cred_type == "hl_api":
            if self.HYPER_LIQUID_ETH_PRIVATE_KEY:
                return {
                    "private_key": self.HYPER_LIQUID_ETH_PRIVATE_KEY,
                    "account_address": self.ACCOUNT_ADDRESS or "",
                }
            return None
        elif cred_type == "eth_wallet":
            if self.ACCOUNT_ADDRESS:
                return {"address": self.ACCOUNT_ADDRESS, "is_withdrawal": True}
            return None
        elif cred_type == "ai_provider":
            if self.AI_API_KEY:
                return {
                    "provider": self.AI_PROVIDER,
                    "api_key": self.AI_API_KEY,
                    "api_url": self.AI_API_URL,
                    "model": self.AI_MODEL,
                }
            return None
        elif cred_type == "app_api_key":
            if self.AGENT_API_KEY:
                return {"key": self.AGENT_API_KEY}
            return None
        return None


config = Config()
