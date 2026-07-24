"""
Minimal LLM client for Strategy Studio (Pine -> Python conversion).

Uses the OpenAI-compatible /chat/completions endpoint so it works with
Ollama Cloud, OpenRouter, OpenAI, or any compatible gateway. No SDK dependency
(httpx only) to keep the surface small and verifiable.

Assumptions:
- config.AI_PROVIDER / AI_MODEL / AI_API_KEY / AI_API_URL are set from env.
- Endpoint is OpenAI-compatible (Ollama Cloud exposes /v1/chat/completions).
- Network egress to AI_API_URL is available from the server process.
"""
from __future__ import annotations

import httpx

from config import config


def chat(system: str, user: str, *, user_id: str | None = None,
         model_role: str = "assistant", model_override: str | None = None,
         temperature: float = 0.2, timeout: float = 120.0) -> str:
    """Send a chat completion. Returns assistant text. Raises on transport/HTTP error.

    Credential resolution order:
      1. If user_id given -> config.get_credential("ai_provider", user_id) (DB, then env fallback).
      2. Else -> env vars (config.AI_API_KEY / AI_API_URL / AI_MODEL).
    Model resolution:
      model_override wins; else the user's stored pref (coder_model for model_role="coder",
      assistant_model otherwise); else config.AI_MODEL; else "glm-5.1".
    """
    if user_id:
        creds = config.get_credential("ai_provider", user_id)
    else:
        creds = None
    api_key = (creds or {}).get("api_key") or config.AI_API_KEY
    api_url = (creds or {}).get("api_url") or config.AI_API_URL

    # Resolve model: override -> user pref -> env -> glm-5.1 default
    model = model_override
    if not model and user_id:
        from instances.models import SessionLocal, User
        db = SessionLocal()
        try:
            u = db.query(User).filter(User.id == user_id).first()
            if u:
                model = u.coder_model if model_role == "coder" else u.assistant_model
        finally:
            db.close()
    model = model or config.AI_MODEL or "glm-5.1"

    if not api_key:
        raise RuntimeError(
            "No AI_API_KEY configured. Set AI_API_KEY (or OLLAMA_API_KEY) in env, "
            "or store an AI Provider credential in Account > Secrets."
        )
    url = (api_url or config.AI_API_URL).rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    return data["choices"][0]["message"]["content"]


def _strip_fences(raw: str) -> str:
    """Strip markdown code fences if the model ignored the 'no fences' instruction."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()


def convert_pine_to_python(
    pine_source: str,
    strategy_name: str = "",
    user_id: str | None = None,
    *,
    save_path: str | None = None,
    retries: int = 0,
) -> str:
    """Convert PineScript source to a Python strategy module via the LLM.

    Returns Python source code only (code fences stripped). Raises on failure.
    Uses the user's CODER model (User.coder_model) when user_id is given.

    Args:
        pine_source: PineScript v5 source text.
        strategy_name: Human label for the strategy (used in the prompt only).
        user_id: operator/account id for credential + coder-model resolution.
        save_path: if given, the cleaned Python source is written to this path
            (atomic: temp file + rename) so the strategy becomes a loadable module
            under strategies/<slug>/. None = preview only (no disk write).
        retries: number of additional attempts if the LLM transport/HTTP call
            fails (credential/timeouts). Each retry re-invokes chat(); the
            successful result is stripped + (optionally) saved. Set 0 for no retry.
    """
    system = (
        "You are an expert quant developer. Convert TradingView PineScript strategies "
        "into Python modules compatible with the PULS-R strategy-engine. "
        "The engine expects a class named '<Name>Strategy(BaseStrategy)' with a "
        "generate_signals(self, df, symbol=None, equity_history=None) -> dict method "
        "that returns a dict with TWO top-level keys: 'direction' and 'metadata'. "
        "The 'direction' key must be one of: 'BUY' | 'SELL' | 'NEUTRAL'. "
        "The 'metadata' dict must include indicator values: adx, fast_ema, medm_ema, slow_sma, "
        "fan_up_trend, fan_dn_trend, engine_mode, is_strategy_cold, in_warmup. "
        "CRITICAL — the returned dict MUST ALSO include a top-level 'exit_config' key (sibling of "
        "'metadata', NOT inside it) containing risk exits as decimal price levels: "
        "stop_loss_long, stop_loss_short, take_profit_long, take_profit_short. "
        "These are the actual SL/TP price levels the engine uses to manage the position. "
        "Example return shape: "
        "{'direction': 'BUY', 'metadata': {...indicators...}, "
        "'exit_config': {'stop_loss_long': 0.118, 'stop_loss_short': 0.132, "
        "'take_profit_long': 0.145, 'take_profit_short': 0.105}}. "
        "Use pandas DataFrame with columns: open, high, low, close, volume. "
        "Emit ONLY valid Python source code. No prose. No markdown fences."
    )
    user = f"Strategy name: {strategy_name or 'Unnamed'}\n\nPineScript source:\n```pinescript\n{pine_source}\n```"

    last_err: Exception | None = None
    cleaned = ""
    for attempt in range(1 + max(0, retries)):
        try:
            raw = chat(system, user, user_id=user_id, model_role="coder")
            cleaned = _strip_fences(raw)
            break  # success — exit retry loop
        except Exception as e:  # transport / HTTP / creds
            last_err = e
            continue  # try again if retries remain

    if not cleaned:
        raise RuntimeError(
            f"Conversion failed after {1 + max(0, retries)} attempt(s): {last_err}"
        )

    if save_path:
        import os
        import tempfile

        os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
        fd, tmp = tempfile.mkstemp(suffix=".tmp", dir=os.path.dirname(os.path.abspath(save_path)))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(cleaned)
            os.replace(tmp, save_path)  # atomic on POSIX
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    return cleaned
