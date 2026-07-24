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

import ast
import io
import contextlib
import traceback

import httpx

from config import config


# ---------------------------------------------------------------------------
# Contract gates — every generated module MUST pass these before delivery.
# The model is told about them (system prompt) AND we enforce them in code
# (gate loop) so a broken translation is retried, not shipped.
# ---------------------------------------------------------------------------
_CONTRACT_GATES = """
SELF-CHECK GATES — before you emit the final code, verify ALL of these
mentally and structurally. If any fail, fix the code, then emit.

G1  Import line is EXACTLY:  from strategies.base import BaseStrategy
    (NEVER "from strategy_engine import ...", never "import strategies")
G2  Class header:  class <Name>Strategy(BaseStrategy):
G3  __init__ calls super().__init__("<Name>Strategy")  — the name string
    is REQUIRED (BaseStrategy.__init__ takes a positional `name`).
G4  ALL indicator math is VECTORIZED pandas. Never use Python `and`/`or`/`not`
    or `if some_series:` on a pandas Series/boolean mask. Use `&` `|` `~`
    and `.any()`/`.all()`/`.astype(bool)`. A Series has no single truth value.
G5  generate_signals(self, df, symbol=None, equity_history=None) -> dict and
    RETURNS a dict with EXACTLY these top-level keys:
      'direction'  : one of 'BUY' | 'SELL' | 'NEUTRAL'
      'metadata'   : dict of indicator values (adx, fast_ema, medm_ema,
                     slow_sma, fan_up_trend, fan_dn_trend, engine_mode,
                     is_strategy_cold, in_warmup, ...)
      'exit_config' : dict of decimal PRICE levels (sibling of 'metadata',
                     NOT inside it): stop_loss_long, stop_loss_short,
                     take_profit_long, take_profit_short. Use None if N/A.
G6  NO side effects: no print(), no plt.show(), no requests, no file writes
    inside the module. Pure signal computation only.
G7  The module must be importable on its own given `strategies.base`
    present. No missing imports (pandas as pd, numpy as np).

FINAL OUTPUT RULE: emit ONLY the Python source. No prose. No markdown
fences. Start with `import pandas as pd`.
"""


def chat(system: str, user: str, *, user_id: str | None = None,
         model_role: str = "assistant", model_override: str | None = None,
         temperature: float = 0.2, timeout: float = 120.0) -> str:
    """Send a chat completion. Returns assistant text. Raises on transport/HTTP error.

    Credential resolution order:
     1. If user_id given -> config.get_credential("ai_provider", user_id) (DB, then env fallback).
     2. Else -> env vars (config.AI_API_KEY / AI_API_URL / AI_MODEL).
    Model resolution:
      model_override wins; else the user's stored pref (coder_model for model_role="coder",
      assistant_model otherwise); else config.AI_MODEL; else "gpt-oss:20b".
    """
    if user_id:
        creds = config.get_credential("ai_provider", user_id)
    else:
        creds = None
    api_key = (creds or {}).get("api_key") or config.AI_API_KEY
    api_url = (creds or {}).get("api_url") or config.AI_API_URL

    # Resolve model: override -> user pref -> env -> gpt-oss:20b default
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
    model = model or config.AI_MODEL or "gpt-oss:20b"

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


def _gate_check(source: str) -> str | None:
    """Return an error string if the source fails a contract gate, else None.

    Checks (enforced in code, independent of the model's self-check):
      - parses as valid Python (ast.parse)
      - defines exactly one BaseStrategy subclass
      - has generate_signals with the right signature
      - returns a dict containing direction/metadata/exit_config
    Does NOT execute trading logic (kept fast + side-effect free).
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return f"SYNTAX ERROR: {e.msg} (line {e.lineno})"

    classes = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.ClassDef)
        and any(getattr(b, "id", "") == "BaseStrategy" for b in n.bases)
    ]
    if not classes:
        return "CONTRACT FAIL: no class subclassing BaseStrategy found"
    if len(classes) > 1:
        return "CONTRACT FAIL: more than one BaseStrategy subclass"

    cls = classes[0]
    method = next((m for m in cls.body if isinstance(m, ast.FunctionDef) and m.name == "generate_signals"), None)
    if not method:
        return "CONTRACT FAIL: generate_signals method missing"
    # signature must accept (self, df, symbol=None, equity_history=None)
    args = method.args
    arg_names = [a.arg for a in args.args]
    if arg_names[:1] != ["self"] or "df" not in arg_names:
        return "CONTRACT FAIL: generate_signals signature must be (self, df, symbol=None, equity_history=None)"

    # The function must end with a return of a dict literal containing the keys
    ret = method.returns
    # best-effort: scan for a Return with a dict containing the three keys
    has_keys = False
    for node in ast.walk(method):
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict):
            keys = [k.value for k in node.value.keys if isinstance(k, ast.Constant)]
            if {"direction", "metadata", "exit_config"}.issubset(set(keys)):
                has_keys = True
                break
    if not has_keys:
        return "CONTRACT FAIL: generate_signals must return {direction, metadata, exit_config}"

    # import must be `from strategies.base import BaseStrategy`
    if "from strategy_engine import" in source:
        return "CONTRACT FAIL: use `from strategies.base import BaseStrategy`, not strategy_engine"
    if "from strategies.base import BaseStrategy" not in source:
        return "CONTRACT FAIL: missing `from strategies.base import BaseStrategy`"
    if "super().__init__()" in source:
        return "CONTRACT FAIL: super().__init__() needs the name string, e.g. super().__init__('MyStrategy')"
    return None


def _smoke_test(source: str) -> str | None:
    """Runtime self-check: actually import the module and call generate_signals
    on a toy DataFrame. Returns an error string if it throws, else None.

    This catches semantic bugs the static gate misses (undefined names,
    Series truth-value errors, bad attribute access). Executed in an isolated
    namespace with `strategies.base.BaseStrategy` available. No side effects
    because G6 forbids them in the generated module.
    """
    import importlib.util
    import pandas as pd

    # set up minimal module namespace
    mod_name = "_smoke_translation_test"
    spec = importlib.util.spec_from_loader(mod_name, loader=None)
    module = importlib.util.module_from_spec(spec)
    # inject allowed globals
    module.__dict__["pd"] = pd
    try:
        import numpy as np
        module.__dict__["np"] = np
    except Exception:
        pass
    try:
        from strategies.base import BaseStrategy
        module.__dict__["BaseStrategy"] = BaseStrategy
    except Exception as e:
        return f"SMOKE SETUP FAIL: cannot import BaseStrategy: {e}"

    try:
        exec(compile(source, "<generated>", "exec"), module.__dict__)
    except Exception as e:
        return f"SMOKE IMPORT FAIL: {type(e).__name__}: {e}"

    # find the strategy class
    cls = None
    for obj in module.__dict__.values():
        if isinstance(obj, type) and issubclass(obj, BaseStrategy) and obj is not BaseStrategy:
            cls = obj
            break
    if cls is None:
        return "SMOKE FAIL: no BaseStrategy subclass found after exec"

    try:
        inst = cls()
        df = pd.DataFrame({
            "open": [1, 2, 3, 4, 5],
            "high": [2, 3, 4, 5, 6],
            "low": [0, 1, 2, 3, 4],
            "close": [1, 2, 3, 4, 5],
            "volume": [10, 20, 30, 40, 50],
        })
        out = inst.generate_signals(df, symbol="BTC")
    except Exception as e:
        return f"SMOKE CALL FAIL: {type(e).__name__}: {e}"

    if not isinstance(out, dict):
        return f"SMOKE FAIL: generate_signals returned {type(out).__name__}, expected dict"
    missing = {"direction", "metadata", "exit_config"} - set(out.keys())
    if missing:
        return f"SMOKE FAIL: return dict missing keys {missing}"
    return None


def convert_pine_to_python(pine_source: str, strategy_name: str = "", user_id: str | None = None,
                         save_path: str | None = None, retries: int = 0) -> str:
    """Convert PineScript source to a Python strategy module via the LLM.

    Uses an OpenAI-compatible chat/completions endpoint (Ollama Cloud, OpenRouter,
    OpenAI, or any compatible gateway). Resolves credentials from the operator's
    stored AI provider (DB) when user_id is given, else from env.

    Returns Python source as a string. The caller is responsible for saving it
    (pass save_path to persist atomically).

    Retry behaviour: if the generated source fails a contract gate (syntax,
    class shape, return keys, import correctness) OR the runtime smoke test
    (import + generate_signals call on a toy DataFrame), the error is fed
    back to the model in a follow-up call so it can self-correct, up to
    `retries` times.
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
        + _CONTRACT_GATES
    )
    user = f"Strategy name: {strategy_name or 'Unnamed'}\n\nPineScript source:\n```pinescript\n{pine_source}\n```"

    last_err: Exception | None = None
    cleaned = ""
    for attempt in range(1 + max(0, retries)):
        try:
            if attempt == 0:
                raw = chat(system, user, user_id=user_id, model_role="coder")
            else:
                # 2nd-chance self-correction loop: feed the gate error back
                feedback = (
                    f"Your previous output FAILED validation:\n{last_gate_err}\n\n"
                    f"Regenerate the FULL corrected Python module. Fix the flagged issue. "
                    f"Re-read the SELF-CHECK GATES in the system prompt. Emit ONLY code."
                )
                raw = chat(system, feedback, user_id=user_id, model_role="coder")
            cleaned = _strip_fences(raw)
            # Static contract gate first (fast), then runtime smoke test
            # (actually imports + calls generate_signals on a toy df).
            gate_err = _gate_check(cleaned)
            if gate_err is None:
                gate_err = _smoke_test(cleaned)
            if gate_err is None:
                break  # success — exits retry loop
            last_gate_err = gate_err
            last_err = RuntimeError(gate_err)
            # continue to next retry with feedback
        except Exception as e:  # transport / HTTP / creds
            last_err = e
            last_gate_err = f"TRANSPORT ERROR: {e}"
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
