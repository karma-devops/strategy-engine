"""
FastAPI UI routes.
"""

import os
from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from api.ratelimit import limiter, READ_LIMIT, WRITE_LIMIT, AUTH_LIMIT
from config import config
from api.auth import verify_ui_credentials, require_ui_or_api
from instances.models import (
    engine,
    Instance,
    AccountSnapshot,
    Trade,
    Signal,
    Backtest,
    User,
    Strategy,
    Credential,
    get_or_seed_operator,
    get_user_or_seed_user,
    decrypt_api_key,
)
from instances.manager import manager
from strategies.registry import get_strategy

Session = sessionmaker(bind=engine)
router = APIRouter()  # Protected routes (auth required)
public_router = APIRouter()  # Public routes (no auth)
templates = Jinja2Templates(directory="app/templates")

# Inject theme from cookie (falls back to DB on settings save)
templates.env.globals["theme"] = "pulsr"

def _inject_theme(request: Request):
    """Read theme from cookie, falling back to DB-stored preference."""
    theme = request.cookies.get("pulsr-theme") or "pulsr"
    # Validate
    if theme not in ("pulsr", "hyperfluid", "portrait"):
        theme = "pulsr"
    return theme


# Per-user dashboard API keys are resolved per-request from the session cookie
# (see get_dashboard_api_key). No module-level cache: a shared cached key would
# bleed one tenant's key to another. SECURITY (T3-0).


def get_dashboard_api_key(request: Request = None) -> str:
    """Return the LOGGED-IN user's per-user `puls_` API key for dashboard client-side calls.

    SECURITY (T3-0 cross-user leak fix): NEVER a global/shared value. Previously a
    module-level cache held the operator key and bled it to other users. Now strictly
    per-request from the session cookie. Resolution order:
      - valid session cookie -> that user's own decrypted puls_ key
      - session cookie present but invalid/expired -> "" (403, empty dashboard; NEVER operator)
      - no session cookie (e.g. basic-auth operator) -> "" (operator UI uses its own session)
    No fallback to the operator key for any session user. This guarantees isolation.
    """
    if request is not None:
        session = request.cookies.get("pulsr_session")
        if session:
            try:
                import hmac as _hmac, hashlib as _hl, base64 as _b64, json as _js, time as _t, secrets as _sec
                token, sig = session.split(".")
                expected_sig = _hmac.new(config.INSTANCE_SECRET_KEY.encode(), token.encode(), _hl.sha256).hexdigest()
                if _sec.compare_digest(sig, expected_sig):
                    payload = _js.loads(_b64.b64decode(token).decode())
                    if payload.get("exp", 0) > int(_t.time()):
                        username = payload.get("username")
                        if username:
                            from instances.models import SessionLocal, User as _U
                            _db = SessionLocal()
                            try:
                                u = _db.query(_U).filter(_U.username == username).first()
                                if u and u.api_key:
                                    return decrypt_api_key(u.api_key)
                            finally:
                                _db.close()
                            return ""  # session user resolved but has no key - do NOT leak operator key
            except Exception:
                pass
    # No valid session cookie: resolve from Basic Auth (e.g. operator logged in
    # via URL-embedded credentials has no session cookie). Falls back to the
    # authenticated user's OWN puls_ key — never leaks another tenant's key.
    if request is not None:
        from fastapi.security import HTTPBasic
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Basic "):
            import base64
            try:
                decoded = base64.b64decode(auth[6:]).decode("utf-8")
                username, _password = decoded.split(":", 1)
                if username:
                    from instances.models import SessionLocal, User as _U2
                    _db = SessionLocal()
                    try:
                        u = _db.query(_U2).filter(_U2.username == username).first()
                        if u and u.api_key:
                            return decrypt_api_key(u.api_key)
                    finally:
                        _db.close()
            except Exception:
                pass
    # No valid auth → empty key (403 / empty dashboard). Never operator key.
    return ""


@public_router.post("/login")
@limiter.limit(AUTH_LIMIT)
async def login_post(request: Request, username: str = Form(...), password: str = Form(...)):
    """Validate username + password, issue session cookie on success."""
    from instances.models import SessionLocal, User, verify_password
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user or not user.password_hash or not verify_password(password, user.password_hash):
            return HTMLResponse(
                content='<script>localStorage.setItem("pulsr_login_error", "Invalid credentials"); history.back();</script>',
                status_code=401,
            )
        # Success — issue session cookie (signed token)
        import hmac, hashlib, base64, json, time
        payload = {"user_id": user.id, "username": user.username, "exp": int(time.time()) + 86400}
        token = base64.b64encode(json.dumps(payload).encode()).decode()
        sig = hmac.new(config.INSTANCE_SECRET_KEY.encode(), token.encode(), hashlib.sha256).hexdigest()
        cookie_val = f"{token}.{sig}"
        response = RedirectResponse(url="/app/dashboard", status_code=303)
        response.set_cookie("pulsr_session", cookie_val, max_age=86400, httponly=True, samesite="lax")
        return response
    finally:
        db.close()


@public_router.post("/signup")
@limiter.limit(AUTH_LIMIT)
async def signup_post(request: Request, username: str = Form(...), email: str = Form(...), password: str = Form(...)):
    """Create a new user account with auto-generated API key."""
    from instances.models import SessionLocal, User, hash_password, generate_api_key, encrypt_api_key, hash_api_key
    import uuid
    db = SessionLocal()
    try:
        # Validate inputs
        if len(username) < 3 or len(username) > 32:
            return HTMLResponse(
                content='<script>localStorage.setItem("pulsr_signup_error", "Username must be 3-32 characters"); history.back();</script>',
                status_code=400,
            )
        if len(password) < 6:
            return HTMLResponse(
                content='<script>localStorage.setItem("pulsr_signup_error", "Password must be at least 6 characters"); history.back();</script>',
                status_code=400,
            )
        # Check for existing user
        if db.query(User).filter(User.username == username).first():
            return HTMLResponse(
                content='<script>localStorage.setItem("pulsr_signup_error", "Username already taken"); history.back();</script>',
                status_code=409,
            )
        if email and db.query(User).filter(User.email == email).first():
            return HTMLResponse(
                content='<script>localStorage.setItem("pulsr_signup_error", "Email already registered"); history.back();</script>',
                status_code=409,
            )
        # Create user
        raw_key = generate_api_key()
        user = User(
            id=str(uuid.uuid4()),
            username=username,
            display_name=username.capitalize(),
            email=email or None,
            password_hash=hash_password(password),
            api_key=encrypt_api_key(raw_key),
            api_key_hash=hash_api_key(raw_key),
            start_balance=1000.0,
            default_dry_run=True,
            theme="pulsr",
        )
        db.add(user)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            return HTMLResponse(
                content='<script>localStorage.setItem("pulsr_signup_error", "Username or email already registered"); history.back();</script>',
                status_code=409,
            )
        # Seed this user's starter fleet: ONE engine — Engine HYPE v1 (HYPE/30m).
        from instances.models import seed_user_fleet
        seed_user_fleet(user)
        # Issue session cookie and redirect
        import hmac, hashlib, base64, json, time
        payload = {"user_id": user.id, "username": user.username, "exp": int(time.time()) + 86400}
        token = base64.b64encode(json.dumps(payload).encode()).decode()
        sig = hmac.new(config.INSTANCE_SECRET_KEY.encode(), token.encode(), hashlib.sha256).hexdigest()
        cookie_val = f"{token}.{sig}"
        response = RedirectResponse(url="/app/dashboard", status_code=303)
        response.set_cookie("pulsr_session", cookie_val, max_age=86400, httponly=True, samesite="lax")
        return response
    finally:
        db.close()


templates.env.filters["format_usd"] = lambda n: f"${float(n or 0):,.2f}"
templates.env.filters["format_pct"] = lambda n: f"{(float(n or 0)):+.2f}%"
templates.env.filters["format_num"] = lambda n, p=2: f"{(float(n or 0)):.{p}f}"
import json as _json
from jinja2 import Undefined

def _safe_tojson(o):
    """Jinja 'tojson' filter that tolerates missing context vars.

    Jinja passes jinja2.Undefined for variables absent from render context.
    The previous lambda did json.dumps(o) directly, which raised TypeError
    on Undefined and 500'd any template referencing an undefined var
    (e.g. engine_detail.html -> paper_trades). Here we coerce Undefined to
    None so the page still renders with an empty/fallback value.
    """
    if isinstance(o, Undefined):
        return _json.dumps(None)
    try:
        return _json.dumps(o)
    except TypeError:
        # Last-resort guard: never let a render-time JSON dump crash the page.
        return _json.dumps(None)

templates.env.filters["tojson"] = _safe_tojson


@public_router.get("/login", response_class=HTMLResponse)
@limiter.limit(READ_LIMIT)
def public_login_page(request: Request):
    """Serve the landing SPA with login page active."""
    return templates.TemplateResponse(request, "landing.html", context={"request": request, "page": "login"})


@public_router.get("/signup", response_class=HTMLResponse)
@limiter.limit(READ_LIMIT)
def public_signup_page(request: Request):
    """Serve the landing SPA with signup page active."""
    return templates.TemplateResponse(request, "landing.html", context={"request": request, "page": "signup"})


@router.get("/spec", response_class=HTMLResponse)
@limiter.limit(READ_LIMIT)
def design_spec(request: Request, username: str = Depends(verify_ui_credentials)):
    """Design system spec page."""
    return templates.TemplateResponse(request, "spec.html", context={"request": request})


@router.get("/", response_class=HTMLResponse)
@limiter.limit(READ_LIMIT)
def dashboard(request: Request, username: str = Depends(verify_ui_credentials)):
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        context={"request": request, "api_key": get_dashboard_api_key(request)},
    )


@router.get("/app/dashboard", response_class=HTMLResponse)
@limiter.limit(READ_LIMIT)
def dashboard_app(request: Request, username: str = Depends(verify_ui_credentials)):
    """Server-rendered dashboard (Option B): data from DB, no client router."""
    db = Session()
    try:
        # Look up user by username (from session cookie or basic auth)
        user = db.query(User).filter(User.username == username).first()
        user_id = user.id if user else None
        is_operator = username == "operator"

        # Operator sees all instances; other users see only their own
        query = db.query(Instance)
        if not is_operator and user_id:
            query = query.filter(Instance.user_id == user_id)
        instances = query.order_by(Instance.created_at.asc()).all() if hasattr(Instance, "created_at") else query.all()
        instances_data = [{
            "slug": i.slug,
            "name": i.name,
            "token": i.token,
            "strategy_id": i.strategy_id,
            "timeframe": i.timeframe,
            "status": i.status,
            "position_side": i.position_side,
            "leverage": i.leverage,
            "max_position_pct": i.max_position_pct,
            "dry_run": i.dry_run,
            "unrealized_pnl": i.unrealized_pnl or 0.0,
            "unrealized_pnl_pct": i.unrealized_pnl_pct or 0.0,
        } for i in instances]

        # Equity snapshots for the Pulse Graph — scoped to this user (T3-0)
        snap_filter = AccountSnapshot.dry_run == False
        if user_id:
            snap_filter = snap_filter & (AccountSnapshot.user_id == user_id)
        snapshots = db.query(AccountSnapshot).filter(snap_filter).order_by(AccountSnapshot.timestamp.asc()).limit(500).all()
        equity_series = [{"time": s.timestamp.isoformat(), "value": s.account_value} for s in snapshots]
        latest = snapshots[-1] if snapshots else None

        peak = 0.0
        max_dd = 0.0
        for s in snapshots:
            v = s.account_value
            if v > peak:
                peak = v
            if peak > 0:
                dd = (peak - v) / peak
                if dd > max_dd:
                    max_dd = dd

        active = sum(1 for i in instances if i.status == "running")
        open_pnl = sum((i.unrealized_pnl or 0.0) for i in instances)
        dry_global = all(i.dry_run for i in instances) if instances else True

        # Recent trades for the Active Trades table — scoped to this user's instances (T3-0)
        user_instance_ids = [i.slug for i in instances]
        trades = (
            db.query(Trade)
            .filter(Trade.instance_id.in_(user_instance_ids) if user_instance_ids else False)
            .order_by(Trade.timestamp.desc())
            .limit(15)
            .all()
        ) if user_instance_ids else []
        trades_data = [
            {
                "timestamp": t.timestamp.isoformat() if t.timestamp else None,
                "instance_id": t.instance_id,
                "side": t.side,
                "size": t.size or 0.0,
                "entry_price": t.entry_price or 0.0,
                "exit_price": t.exit_price,
                "pnl_usd": t.pnl_usd or 0.0,
                "dry_run": t.dry_run,
            } for t in trades
        ]

        # Realized PnL + best engine (scoped to user's live trades, T3-0)
        from collections import defaultdict
        live_trades = [t for t in trades if not t.dry_run] if trades else []
        realized_pnl = round(sum(t.pnl_usd for t in live_trades), 2) if live_trades else 0.0
        engine_pnl = defaultdict(float)
        for t in live_trades:
            engine_pnl[t.instance_id] += t.pnl_usd
        best_engine = None; best_engine_pnl = 0.0; best_engine_token = None; best_engine_strategy = None
        if engine_pnl:
            bs = max(engine_pnl, key=engine_pnl.get)
            best_engine = bs; best_engine_pnl = round(engine_pnl[bs], 2)
            bi = db.query(Instance).filter(Instance.slug == bs, Instance.user_id == user_id).first() if user_id else None
            if bi:
                best_engine_token = bi.token; best_engine_strategy = bi.strategy_id
        user_me = db.query(User).filter(User.username == username).first() if username else None
        start_balance = user_me.start_balance if user_me and user_me.start_balance > 0 else 0.0
        account_value = latest.account_value if latest else 0.0
        perp_account_value = latest.account_value if latest else 0.0
        has_hl_credentials = False
        # Live exchange value fallback: OPERATOR ONLY (T3-0). Non-operator users have no
        # HL creds of their own and must never see the operator's exchange balance.
        if is_operator:
            try:
                from core.exchange import get_hyperliquid_client
                hl = get_hyperliquid_client()
                has_hl_credentials = getattr(hl, 'has_credentials', False)
                if has_hl_credentials:
                    live_val = hl.get_account_value()
                    if live_val > 0:
                        account_value = round(live_val, 2)
                    live_perp = hl.get_perp_account_value()
                    if live_perp > 0:
                        perp_account_value = round(live_perp, 2)
            except Exception:
                pass

        return templates.TemplateResponse(
            request,
            "dashboard.html",
            context={
                "request": request,
                "api_key": get_dashboard_api_key(request),
                "account_value": account_value,
                "perp_account_value": perp_account_value,
                "realized_pnl": realized_pnl,
                "best_engine": best_engine,
                "best_engine_pnl": best_engine_pnl,
                "best_engine_token": best_engine_token,
                "best_engine_strategy": best_engine_strategy,
                "start_balance": start_balance,
                "drawdown_pct": round(max_dd * 100.0, 2),
                "active_engines": active,
                "total_engines": len(instances),
                "open_pnl": round(open_pnl, 2),
                "instances": instances_data,
                "equity_series": equity_series,
                "fleet": instances_data,
                "trades": trades_data,
                "dry_run_global": dry_global,
                "has_hl_credentials": has_hl_credentials,
                "active": "dashboard",
                "chat_context": "dashboard",
            },
        )
    finally:
        db.close()


@router.get("/app/assistant", response_class=HTMLResponse)
@limiter.limit(READ_LIMIT)
def assistant_app(request: Request, username: str = Depends(verify_ui_credentials)):
    """Full-page Assistant chat (uses the shared chat widget, expanded)."""
    return templates.TemplateResponse(
        request,
        "assistant.html",
        context={
            "request": request,
            "api_key": get_dashboard_api_key(request),
            "active": "assistant",
            "chat_context": "assistant",
        },
    )


@router.get("/instances/new", response_class=HTMLResponse)
@limiter.limit(READ_LIMIT)
def new_instance_form(request: Request, username: str = Depends(verify_ui_credentials)):
    return templates.TemplateResponse(request, "instance_form.html", context={"request": request})


@router.post("/instances")
@limiter.limit(WRITE_LIMIT)
def create_instance(
    request: Request,
    username: str = Depends(verify_ui_credentials),
    slug: str = Form(""),
    name: str = Form(...),
    token: str = Form(...),
    strategy_id: str = Form(...),
    mode: str = Form("Scalp"),
    profile: str = Form("aggressive_8_3"),
    timeframe: str = Form("15m"),
    leverage: int = Form(10),
    max_position_pct: float = Form(0.97),
    poll_interval_seconds: int = Form(30),
    activation: int = Form(8),
    offset: int = Form(3),
    hyperliquid_private_key: str = Form(""),
    account_address: str = Form(""),
    withdrawal_address: str = Form(""),
    # BUG #16: default to PAPER (dry_run=True) to match config.DEFAULT_INSTANCE.
    # Live trading should be an explicit opt-in, never the default.
    dry_run: bool = Form(True),
):
    db = Session()
    try:
        # PER-USER ISOLATION: resolve the logged-in owner's user_id so the
        # new engine is bound to them (not operator, not shared).
        owner = db.query(User).filter(User.username == username).first()
        owner_id = owner.id if owner else None
        # Auto-generate slug if empty
        if not slug:
            existing = db.query(Instance).count()
            slug = f"engine-{existing + 1}"
        slug = slug.lower().strip()
        # BUG #17: validate slug format (alphanumeric + dash, 1-32 chars)
        # to prevent arbitrary characters in a 32-char primary key.
        import re
        if not re.match(r"^[a-z0-9-]{1,32}$", slug):
            return {"ok": False, "message": "Slug must be 1-32 chars: lowercase letters, numbers, dashes only"}
        if db.query(Instance).filter(Instance.slug == slug).first():
            return {"ok": False, "message": f"Slug {slug} already exists"}
        inst = Instance(
            slug=slug,
            name=name,
            token=token.upper(),
            strategy_id=strategy_id,
            mode=mode,
            profile=profile,
            timeframe=timeframe,
            leverage=leverage,
            max_position_pct=max_position_pct,
            poll_interval_seconds=poll_interval_seconds,
            activation=activation,
            offset=offset,
            dry_run=dry_run,
            enabled=True,
            user_id=owner_id,  # PER-USER ISOLATION: bind engine to the logged-in owner
        )
        if account_address:
            inst.account_address = account_address.strip()
        if withdrawal_address:
            inst.withdrawal_address = withdrawal_address.strip()
        if hyperliquid_private_key:
            try:
                inst.set_private_key(hyperliquid_private_key.strip())
            except RuntimeError as e:
                return {"ok": False, "message": str(e)}
        db.add(inst)
        db.commit()
        manager.start_instance(inst)
        return RedirectResponse(url="/", status_code=303)
    finally:
        db.close()


@router.get("/app/backtests", response_class=HTMLResponse)
def backtests_redirect():
    return RedirectResponse(url="/app/testing/historical", status_code=301)


@router.get("/app/testing", response_class=HTMLResponse)
@limiter.limit(READ_LIMIT)
def testing_index(request: Request, username: str = Depends(verify_ui_credentials)):
    """Testing section landing — Historical + Paper Trading."""
    return templates.TemplateResponse(
        request, "testing_index.html",
        context={"request": request, "api_key": get_dashboard_api_key(request), "active": "testing"},
    )


@router.get("/app/testing/historical", response_class=HTMLResponse)
@limiter.limit(READ_LIMIT)
def testing_historical(request: Request, username: str = Depends(verify_ui_credentials)):
    """Historical backtests — form + results table + equity curve SVG."""
    db = Session()
    try:
        backtests = db.query(Backtest).filter(Backtest.kind == "backtest").order_by(Backtest.created_at.desc()).limit(50).all()
        bt_data = [{
            "id": b.id, "instance_slug": b.instance_slug, "token": b.token,
            "strategy_id": b.strategy_id, "timeframe": b.timeframe, "profile": b.profile,
            "activation": b.activation, "offset": b.offset, "leverage": b.leverage,
            "status": b.status, "total_return_pct": b.total_return_pct or 0.0,
            "win_rate": b.win_rate or 0.0, "profit_factor": b.profit_factor or 0.0,
            "max_drawdown_pct": b.max_drawdown_pct or 0.0, "total_trades": b.total_trades or 0,
            "sharpe_ratio": b.sharpe_ratio or 0.0,
            "equity_curve": b.equity_curve_json or [],
            "trades_json": b.trades_json or [],
            "created_at": b.created_at.isoformat() if b.created_at else "",
        } for b in backtests]
        # Equity curve for the most recent completed backtest (for the chart card)
        latest_equity = next((b["equity_curve"] for b in bt_data if b["equity_curve"]), [])
        return templates.TemplateResponse(
            request, "testing_historical.html",
            context={
                "request": request, "api_key": get_dashboard_api_key(request),
                "backtests": bt_data, "latest_equity": latest_equity, "active": "testing",
                "chat_context": "backtester",
            },
        )
    finally:
        db.close()


@router.get("/app/trades", response_class=HTMLResponse)
@limiter.limit(READ_LIMIT)
def trades_page(request: Request, username: str = Depends(verify_ui_credentials)):
    """All LIVE trades (dry_run=false) for the operator user (multi-tenant). P14d separation."""
    db = Session()
    try:
        user = get_user_or_seed_user(db, username)
        rows = db.query(Trade).filter(Trade.user_id == user.id, Trade.dry_run == False).order_by(Trade.timestamp.desc()).limit(200).all()
        trade_data = [{
            "id": t.id,
            "time": t.timestamp.strftime("%Y-%m-%d %H:%M") if t.timestamp else "",
            "instance": t.instance_id,
            "side": t.side,
            "size": round(t.size, 4),
            "entry_price": round(t.entry_price, 6) if t.entry_price else 0.0,
            "exit_price": round(t.exit_price, 6) if t.exit_price else None,
            "pnl_usd": round(t.pnl_usd, 2),
            "pnl_pct": round(t.pnl_pct, 2),
            "fees": round((t.entry_cost or 0.0) + (t.exit_cost or 0.0), 4),
            "open": t.exit_price is None,
        } for t in rows]
        open_count = sum(1 for t in trade_data if t["open"])
        closed = [t for t in trade_data if not t["open"]]
        total_pnl = round(sum(t["pnl_usd"] for t in closed), 2)
        wins = sum(1 for t in closed if t["pnl_usd"] > 0)
        win_rate = round(100.0 * wins / len(closed), 1) if closed else 0.0
        # P14e: paper trades for the collapsible section below live trades
        paper_rows = db.query(Trade).filter(Trade.user_id == user.id, Trade.dry_run == True).order_by(Trade.timestamp.desc()).limit(100).all()
        paper_data = [{
            "id": t.id,
            "time": t.timestamp.strftime("%Y-%m-%d %H:%M") if t.timestamp else "",
            "instance": t.instance_id,
            "side": t.side,
            "size": round(t.size, 4),
            "entry_price": round(t.entry_price, 6) if t.entry_price else 0.0,
            "exit_price": round(t.exit_price, 6) if t.exit_price else None,
            "pnl_usd": round(t.pnl_usd, 2),
            "pnl_pct": round(t.pnl_pct, 2),
            "fees": round((t.entry_cost or 0.0) + (t.exit_cost or 0.0), 4),
            "open": t.exit_price is None,
        } for t in paper_rows]
        # BUG-7: Active Positions section — instances currently holding a position
        active_positions = []
        inst_rows = db.query(Instance).filter(
            Instance.user_id == user.id,
            Instance.position_side.isnot(None),
            Instance.position_side != 'FLAT',
            Instance.position_size > 0,
        ).all()
        for inst in inst_rows:
            active_positions.append({
                "slug": inst.slug,
                "token": inst.token,
                "side": inst.position_side,
                "size": round(inst.position_size, 4),
                "entry": round(inst.entry_price, 6) if inst.entry_price else 0.0,
                "mark": round(inst.mark_price, 6) if inst.mark_price else 0.0,
                "pnl": round(inst.unrealized_pnl, 2) if inst.unrealized_pnl else 0.0,
                "pnl_pct": round(inst.unrealized_pnl_pct, 2) if inst.unrealized_pnl_pct else 0.0,
            })
        return templates.TemplateResponse(
            request,
            "trades.html",
            context={
                "request": request,
                "api_key": get_dashboard_api_key(request),
                "trades": trade_data,
                "paper_trades": paper_data,
                "open_count": open_count,
                "active_positions": active_positions,
                "total_trades": len(trade_data),
                "closed_count": len(closed),
                "total_pnl": total_pnl,
                "win_rate": win_rate,
                "active": "trades",
                "engines": sorted(set(t["instance"] for t in trade_data)),
            },
        )
    finally:
        db.close()


@router.get("/app/withdrawals", response_class=HTMLResponse)
@limiter.limit(READ_LIMIT)
def withdrawals_page(request: Request, username: str = Depends(verify_ui_credentials)):
    # T1-7 DEFERRED 2026-07-19: withdraw/deposit feature is broken/deferred
    # (BUG-11 broken SDK call, BUG-12 no deposit path). Per operator, keep the
    # page reachable but show a non-functional notice instead of the broken form.
    notice = (
        "<h2>Withdrawals &mdash; Not Functional Yet</h2>"
        "<p style='color:#e5534b;font-weight:600;'>⚠ This feature is in the works and "
        "not functional to withdraw yet.</p>"
        "<p>The withdrawal/deposit round-trip is currently deferred. Fund-moving "
        "actions are disabled on the backend. Check back when the feature ships.</p>"
    )
    return HTMLResponse(content=notice)


@router.get("/app/engines", response_class=HTMLResponse)
@limiter.limit(READ_LIMIT)
def engines_page(request: Request, username: str = Depends(verify_ui_credentials)):
    """All engines management page — grid of all engines with live controls."""
    db = Session()
    try:
        user = db.query(User).filter(User.username == username).first()
        user_id = user.id if user else None
        is_operator = username == "operator"
        query = db.query(Instance)
        if not is_operator and user_id:
            query = query.filter(Instance.user_id == user_id)
        instances = query.order_by(Instance.created_at.asc()).all() if hasattr(Instance, "created_at") else query.all()
        instances_data = [{
            "slug": i.slug,
            "name": i.name,
            "token": i.token,
            "strategy_id": i.strategy_id,
            "timeframe": i.timeframe,
            "status": i.status,
            "position_side": i.position_side,
            "leverage": i.leverage,
            "max_position_pct": i.max_position_pct,
            "dry_run": i.dry_run,
            "unrealized_pnl": i.unrealized_pnl or 0.0,
            "unrealized_pnl_pct": i.unrealized_pnl_pct or 0.0,
            "position_size": i.position_size or 0.0,
            "entry_price": i.entry_price or 0.0,
            "mark_price": i.mark_price or 0.0,
        } for i in instances]

        active = sum(1 for i in instances if i.status == "running")
        open_pnl = sum((i.unrealized_pnl or 0.0) for i in instances)
        dry_global = all(i.dry_run for i in instances) if instances else True

        # Win rate from trades
        trades = db.query(Trade).order_by(Trade.timestamp.desc()).limit(500).all()
        closed = [t for t in trades if t.exit_price is not None]
        wins = sum(1 for t in closed if (t.pnl_usd or 0) > 0)
        losses = sum(1 for t in closed if (t.pnl_usd or 0) < 0)
        breakevens = len(closed) - wins - losses
        win_rate = round(wins / len(closed) * 100, 1) if closed else 0.0

        # PnL distribution bins for histogram
        pnl_pcts = [float(t.pnl_pct or 0) for t in closed]
        dist_bins = []
        if pnl_pcts:
            min_p = min(pnl_pcts)
            max_p = max(pnl_pcts)
            span = max_p - min_p
            if span < 0.01:
                span = 1.0
            n_bins = min(15, max(8, len(pnl_pcts) // 3))
            bin_w = span / n_bins
            for i in range(n_bins):
                lo = min_p + i * bin_w
                hi = lo + bin_w
                count = sum(1 for p in pnl_pcts if lo <= p < hi or (i == n_bins - 1 and p == hi))
                is_win = (lo + hi) / 2 >= 0
                dist_bins.append({"lo": round(lo, 2), "hi": round(hi, 2), "count": count, "is_win": is_win})
        avg_profit = round(sum(p for p in pnl_pcts if p > 0) / max(wins, 1), 2) if wins else 0.0
        avg_loss = round(sum(p for p in pnl_pcts if p < 0) / max(losses, 1), 2) if losses else 0.0

        # Profit structure for waterfall
        total_profit = round(sum(float(t.pnl_usd or 0) for t in closed if (t.pnl_usd or 0) > 0), 2)
        total_loss = round(abs(sum(float(t.pnl_usd or 0) for t in closed if (t.pnl_usd or 0) < 0)), 2)
        commission = round(sum(float(getattr(t, "fee", 0) or 0) for t in closed), 4)
        net_pnl = round(total_profit - total_loss - commission, 2)

        # Per-instance equity for sparklines (from trades cumulative PnL)
        per_inst_equity = {}
        for inst in instances:
            inst_trades = db.query(Trade).filter(
                Trade.instance_id == inst.slug,
                Trade.exit_price is not None
            ).order_by(Trade.timestamp.asc()).limit(100).all()
            if inst_trades:
                cum = 0.0
                series = []
                for t in inst_trades:
                    cum += float(t.pnl_usd or 0)
                    series.append(cum)
                per_inst_equity[inst.slug] = series

        # Equity snapshots for the Pulse Graph
        snaps = db.query(AccountSnapshot).order_by(AccountSnapshot.timestamp.asc()).limit(500).all()
        equity_series = [{"time": s.timestamp.isoformat(), "value": s.account_value} for s in snaps]

        return templates.TemplateResponse(
            request,
            "engines.html",
            context={
                "request": request,
                "api_key": get_dashboard_api_key(request),
                "active_engines": active,
                "total_engines": len(instances),
                "open_pnl": round(open_pnl, 2),
                "win_rate": win_rate,
                "total_trades": len(closed),
                "instances": instances_data,
                "fleet": instances_data,
                "equity_series": equity_series,
                "dry_run_global": dry_global,
                "dist_bins": dist_bins,
                "avg_profit": avg_profit,
                "avg_loss": avg_loss,
                "wins": wins,
                "losses": losses,
                "breakevens": breakevens,
                "total_profit": total_profit,
                "total_loss": total_loss,
                "commission": commission,
                "net_pnl": net_pnl,
                "per_inst_equity": per_inst_equity,
                "active": "engines",
            },
        )
    finally:
        db.close()


@router.get("/app/engines/{slug}", response_class=HTMLResponse)
@limiter.limit(READ_LIMIT)
def engine_detail_page(request: Request, slug: str, username: str = Depends(verify_ui_credentials)):
    """Per-engine detail page — KPIs, Pulse Graph, position, trades, signals, console."""
    db = Session()
    try:
        user = db.query(User).filter(User.username == username).first()
        user_id = user.id if user else None
        is_operator = username == "operator"

        inst = db.query(Instance).filter(Instance.slug == slug).first()
        if not inst:
            return templates.TemplateResponse(request, "error.html", context={
                "request": request, "error": f"Engine '{slug}' not found", "active": "engines",
            }, status_code=404)

        # Check ownership: operator sees all, others see only their own
        if not is_operator and user_id and inst.user_id != user_id:
            return templates.TemplateResponse(request, "error.html", context={
                "request": request, "error": "Access denied — this engine does not belong to you", "active": "engines",
            }, status_code=403)

        inst_data = {
            "slug": inst.slug, "name": inst.name, "token": inst.token,
            "strategy_id": inst.strategy_id, "timeframe": inst.timeframe,
            "status": inst.status, "position_side": inst.position_side,
            "leverage": inst.leverage, "max_position_pct": inst.max_position_pct,
            "dry_run": inst.dry_run, "unrealized_pnl": inst.unrealized_pnl or 0.0,
            "unrealized_pnl_pct": inst.unrealized_pnl_pct or 0.0,
            "position_size": inst.position_size or 0.0,
            "entry_price": inst.entry_price or 0.0, "mark_price": inst.mark_price or 0.0,
            "poll_interval_seconds": inst.poll_interval_seconds or 30,
            "mode": getattr(inst, "mode", "Scalp"), "profile": getattr(inst, "profile", "aggressive_8_3"),
            "activation": getattr(inst, "activation", 8), "offset": getattr(inst, "offset", 3),
        }

        # This engine's trades (recent 50)
        trades = db.query(Trade).filter(Trade.instance_id == slug).order_by(Trade.timestamp.desc()).limit(50).all()
        trades_data = [{
            "timestamp": t.timestamp.isoformat() if t.timestamp else None,
            "side": t.side, "size": t.size or 0.0,
            "entry_price": t.entry_price or 0.0, "exit_price": t.exit_price,
            "pnl_usd": t.pnl_usd or 0.0, "pnl_pct": getattr(t, "pnl_pct", 0) or 0,
        } for t in trades]

        # Win rate
        closed = [t for t in trades if t.exit_price is not None]
        wins = sum(1 for t in closed if (t.pnl_usd or 0) > 0)
        losses = sum(1 for t in closed if (t.pnl_usd or 0) < 0)
        breakevens = len(closed) - wins - losses
        win_rate = round(wins / len(closed) * 100, 1) if closed else 0.0
        total_pnl = round(sum((t.pnl_usd or 0) for t in closed), 2)

        # PnL distribution bins for histogram
        pnl_pcts = [float(getattr(t, "pnl_pct", 0) or 0) for t in closed]
        dist_bins = []
        if pnl_pcts:
            min_p = min(pnl_pcts)
            max_p = max(pnl_pcts)
            span = max_p - min_p
            if span < 0.01:
                span = 1.0
            n_bins = min(15, max(8, len(pnl_pcts) // 3))
            bin_w = span / n_bins
            for i in range(n_bins):
                lo = min_p + i * bin_w
                hi = lo + bin_w
                count = sum(1 for p in pnl_pcts if lo <= p < hi or (i == n_bins - 1 and p == hi))
                is_win = (lo + hi) / 2 >= 0
                dist_bins.append({"lo": round(lo, 2), "hi": round(hi, 2), "count": count, "is_win": is_win})
        avg_profit = round(sum(p for p in pnl_pcts if p > 0) / max(wins, 1), 2) if wins else 0.0
        avg_loss = round(sum(p for p in pnl_pcts if p < 0) / max(losses, 1), 2) if losses else 0.0

        # Profit structure for waterfall
        total_profit = round(sum(float(t.pnl_usd or 0) for t in closed if (t.pnl_usd or 0) > 0), 2)
        total_loss = round(abs(sum(float(t.pnl_usd or 0) for t in closed if (t.pnl_usd or 0) < 0)), 2)
        commission = round(sum(float(getattr(t, "fee", 0) or 0) for t in closed), 4)
        net_pnl = round(total_profit - total_loss - commission, 2)

        # Streaks (consecutive winning/losing runs)
        streaks = []
        if pnl_pcts:
            cur_type = None
            cur_count = 0
            cur_pnl = 0.0
            for t in closed:
                t_pnl = float(t.pnl_usd or 0)
                t_type = "up" if t_pnl > 0 else "down" if t_pnl < 0 else "be"
                if t_type == cur_type:
                    cur_count += 1
                    cur_pnl += t_pnl
                else:
                    if cur_type and cur_count > 0:
                        streaks.append({"type": cur_type, "count": cur_count, "pnl": round(cur_pnl, 2)})
                    cur_type = t_type
                    cur_count = 1
                    cur_pnl = t_pnl
            if cur_type and cur_count > 0:
                streaks.append({"type": cur_type, "count": cur_count, "pnl": round(cur_pnl, 2)})

        # Sparkline data (cumulative PnL from trades)
        sparkline_data = []
        if closed:
            cum = 0.0
            sorted_closed = sorted(closed, key=lambda t: t.timestamp or "")
            for t in sorted_closed:
                cum += float(t.pnl_usd or 0)
                sparkline_data.append(round(cum, 2))

        # This engine's equity snapshots
        snaps = db.query(AccountSnapshot).filter(
            AccountSnapshot.instance_id == slug
        ).order_by(AccountSnapshot.timestamp.asc()).limit(500).all()
        equity_series = [{"time": s.timestamp.isoformat(), "value": s.account_value} for s in snaps]

        # This engine's recent signals
        signals = db.query(Signal).filter(Signal.instance_id == slug).order_by(
            Signal.timestamp.desc()
        ).limit(20).all() if hasattr(Signal, "instance_id") else []
        signals_data = [{
            "timestamp": s.timestamp.isoformat() if s.timestamp else None,
            "direction": getattr(s, "direction", ""), "strength": getattr(s, "strength", 0),
        } for s in signals]

        # Compute max drawdown from equity series
        if equity_series and len(equity_series) > 1:
            peak = equity_series[0]["value"]
            max_dd = 0.0
            for s in equity_series:
                if s["value"] > peak:
                    peak = s["value"]
                dd = (peak - s["value"]) / peak if peak > 0 else 0
                if dd > max_dd:
                    max_dd = dd
            max_drawdown_pct = round(max_dd * 100, 2)
        else:
            max_drawdown_pct = 0.0

        return templates.TemplateResponse(
            request,
            "engine_detail.html",
            context={
                "request": request,
                "api_key": get_dashboard_api_key(request),
                "inst": inst_data,
                "slug": slug,
                "trades": trades_data,
                # P14: paper-trade bar overlay on equity chart.
                # Was never passed -> template got Undefined -> tojson crashed (500).
                # Build {time_unix, pnl_usd} pairs from closed trades for the chart JS.
                "paper_trades": [
                    {
                        "time_unix": int(__import__("datetime").datetime.fromisoformat(t["timestamp"]).timestamp())
                        if t.get("timestamp") else 0,
                        "pnl_usd": float(t.get("pnl_usd") or 0.0),
                    }
                    for t in trades_data
                    if t.get("exit_price") is not None
                ],
                "signals": signals_data,
                "equity_series": equity_series,
                "win_rate": win_rate,
                "total_pnl": total_pnl,
                "total_trades": len(closed),
                "open_count": len([t for t in trades if t.exit_price is None]),
                "max_drawdown_pct": max_drawdown_pct,
                "dist_bins": dist_bins,
                "avg_profit": avg_profit,
                "avg_loss": avg_loss,
                "wins": wins,
                "losses": losses,
                "breakevens": breakevens,
                "total_profit": total_profit,
                "total_loss": total_loss,
                "commission": commission,
                "net_pnl": net_pnl,
                "streaks": streaks,
                "sparkline_data": sparkline_data,
                "active": "engines",
                # Phase 8A: per-engine HL credential selector
                "hl_credentials": [
                    {"id": c.id, "label": c.label, "priority": c.priority,
                     "preview": c.masked_preview or ""}
                    for c in db.query(Credential).filter(
                        Credential.user_id == inst.user_id,
                        Credential.type == "hl_api",
                        Credential.is_active == True,  # noqa: E712
                    ).order_by(Credential.priority).all()
                ],
                "hl_credential_id": inst.hl_credential_id or "",
                # Strategy config (Port 1: per-instance parameter overrides)
                "strategy_config": inst.strategy_config or {},
                "strategy_parameters": (
                    get_strategy(inst.strategy_id).get_parameters()
                    if get_strategy(inst.strategy_id) else []
                ),
            },
        )
    finally:
        db.close()


# ── Phase 8: Account Section ──────────────────────────────────────────────────

@router.get("/app/account", response_class=HTMLResponse)
@limiter.limit(READ_LIMIT)
def account_overview(request: Request, username: str = Depends(verify_ui_credentials)):
    """Account overview: portfolio value, start balance, PnL, engine allocation."""
    db = Session()
    try:
        user = get_user_or_seed_user(db, username)
        instances = db.query(Instance).filter(Instance.user_id == user.id).all()
        # Live account value from HL — ONLY if this user has their OWN HL credential.
        # Non-operator users seed with no HL key, so we must NOT call the operator's
        # global client (that would leak operator's live $ value). Show 0 / "connect".
        portfolio_value = 0.0
        perp_value = 0.0
        withdrawable = 0.0
        has_exchange = False
        if user.username == "operator":
            from core.exchange import get_hyperliquid_client
            hl = get_hyperliquid_client()
            portfolio_value = hl.get_account_value()
            perp_value = hl.get_perp_account_value()
            withdrawable = hl.get_withdrawable()
            has_exchange = True
        else:
            # Check if this user stored their own HL credential
            from instances.models import Credential
            cred = db.query(Credential).filter(
                Credential.user_id == user.id, Credential.type == "hl_api", Credential.is_active == True
            ).first()
            has_exchange = cred is not None
        # Per-engine allocation
        engine_alloc = []
        total_pnl = 0.0
        for inst in instances:
            snaps = db.query(AccountSnapshot).filter(
                AccountSnapshot.instance_id == inst.slug,
                AccountSnapshot.user_id == user.id,
            ).order_by(AccountSnapshot.timestamp.desc()).limit(1).first()
            av = snaps.account_value if snaps else (inst.start_balance or 0.0)
            pnl = inst.unrealized_pnl or 0.0
            total_pnl += pnl
            engine_alloc.append({
                "slug": inst.slug,
                "name": inst.name,
                "token": inst.token,
                "status": inst.status,
                "dry_run": inst.dry_run,
                "account_value": round(av, 2),
                "unrealized_pnl": round(pnl, 2),
                "leverage": inst.leverage,
            })
        active_count = sum(1 for e in engine_alloc if e["status"] == "running")
        return templates.TemplateResponse(
            request,
            "account_overview.html",
            context={
                "request": request,
                "api_key": get_dashboard_api_key(request),
                "user": {
                    "username": user.username,
                    "display_name": user.display_name,
                    "start_balance": user.start_balance,
                    "default_dry_run": user.default_dry_run,
                },
                "portfolio_value": round(portfolio_value, 2),
                "perp_value": round(perp_value, 2),
                "withdrawable": round(withdrawable or 0, 2),
                "start_balance": user.start_balance,
                "total_pnl": round(total_pnl, 2),
                "active_engines": active_count,
                "total_engines": len(engine_alloc),
                "engines": engine_alloc,
                "active": "account",
            },
        )
    finally:
        db.close()


@router.get("/app/account/settings", response_class=HTMLResponse)
def account_settings_redirect():
    """Redirect to existing settings page."""
    return RedirectResponse(url="/app/settings", status_code=301)


@router.get("/app/account/secrets", response_class=HTMLResponse)
@limiter.limit(READ_LIMIT)
def account_secrets(request: Request, username: str = Depends(verify_ui_credentials)):
    """Account Secrets: Wallets, HyperLiquid DEX API, AI Inference - with instructions."""
    db = Session()
    try:
        user = get_user_or_seed_user(db, username)
        instances = db.query(Instance).filter(Instance.user_id == user.id).all()
        # Mask addresses for display
        engine_creds = []
        for inst in instances:
            addr = inst.account_address or config.ACCOUNT_ADDRESS or ""
            masked = addr[:6] + "..." + addr[-4:] if len(addr) > 10 else addr
            has_key = bool(inst.hyperliquid_private_key_encrypted)
            engine_creds.append({
                "slug": inst.slug,
                "name": inst.name,
                "token": inst.token,
                "masked_address": masked,
                "has_key": has_key,
                "using_global": not has_key,
            })
        # Global env state (masked)
        global_addr = config.ACCOUNT_ADDRESS or ""
        global_masked = global_addr[:6] + "..." + global_addr[-4:] if len(global_addr) > 10 else global_addr or "Not set"
        has_global_hl = bool(config.HYPER_LIQUID_ETH_PRIVATE_KEY)
        # AI provider state
        ai_provider = config.AI_PROVIDER or "ollama"
        ai_model = config.AI_MODEL or ""
        ai_url = config.AI_API_URL or ""
        has_ai_key = bool(config.AI_API_KEY)
        ai_key_masked = config.AI_API_KEY[:8] + "..." if config.AI_API_KEY else "Not set"
        return templates.TemplateResponse(
            request,
            "account_secrets.html",
            context={
                "request": request,
                "api_key": get_dashboard_api_key(request),
                "user": {"username": user.username, "withdrawal_eth_address": user.withdrawal_eth_address},
                "engine_creds": engine_creds,
                "global_masked": global_masked,
                "has_global_hl": has_global_hl,
                "ai_provider": ai_provider,
                "ai_model": ai_model,
                "ai_url": ai_url,
                "has_ai_key": has_ai_key,
                "ai_key_masked": ai_key_masked,
                "active": "account",
            },
        )
    finally:
        db.close()


@router.get("/app/settings", response_class=HTMLResponse)
@limiter.limit(READ_LIMIT)
def settings_app(request: Request, username: str = Depends(verify_ui_credentials)):
    """Account Settings: profile, security, trading, wallet, plan & billing."""
    db = Session()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            user = get_user_or_seed_user(db, username)
        instances = db.query(Instance).filter(Instance.user_id == user.id).all()
        total_engines = len(instances)
        from strategies.registry import list_strategies
        total_strategies = len(list_strategies())
        return templates.TemplateResponse(
            request,
            "settings.html",
            context={
                "request": request,
                "api_key": get_dashboard_api_key(request),
                "user": {
                    "username": user.username,
                    "display_name": user.display_name,
                    "start_balance": user.start_balance,
                    "default_dry_run": user.default_dry_run,
                    "email": user.email,
                    "withdrawal_eth_address": user.withdrawal_eth_address,
                    "avatar_emoji": user.avatar_emoji,
                    "plan": user.plan or "free",
                    "twofa_enabled": user.twofa_enabled,
                    "theme": user.theme or "pulsr",
                    "timezone": user.timezone or "GMT",
                },
                "total_engines": total_engines,
                "total_strategies": total_strategies,
                "active": "settings",
            },
        )
    finally:
        db.close()


@router.post("/app/settings", response_class=HTMLResponse)
@limiter.limit(WRITE_LIMIT)
async def settings_app_save(request: Request, username: str = Depends(verify_ui_credentials)):
    """Persist all account settings."""
    form = await request.form()
    db = Session()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            user = get_user_or_seed_user(db, username)
        # Trading
        try:
            user.start_balance = float(form.get("start_balance", user.start_balance))
        except (ValueError, TypeError):
            pass
        user.default_dry_run = form.get("default_dry_run") in ("on", "true", "1", True)
        # Profile
        user.display_name = (form.get("display_name") or "").strip() or user.display_name
        user.email = (form.get("email") or "").strip() or None
        avatar = form.get("avatar_emoji")
        if avatar:
            user.avatar_emoji = str(avatar).strip()
        # Theme
        theme = (form.get("theme") or "").strip()
        if theme in ("pulsr", "hyperfluid", "portrait"):
            user.theme = theme
        # Security
        new_pw = (form.get("new_password") or "").strip()
        if new_pw:
            from instances.models import hash_password
            user.password_hash = hash_password(new_pw)
        user.twofa_enabled = form.get("twofa_enabled") in ("on", "true", "1", True)
        # Wallet
        user.withdrawal_eth_address = (form.get("withdrawal_eth_address") or "").strip() or None
        # Timezone (per-user display timezone; IANA name, default GMT)
        tz = (form.get("timezone") or "").strip()
        if tz:
            user.timezone = tz
        db.commit()
        instances = db.query(Instance).filter(Instance.user_id == user.id).all()
        from strategies.registry import list_strategies
        return templates.TemplateResponse(
            request,
            "settings.html",
            context={
                "request": request,
                "api_key": get_dashboard_api_key(request),
                "user": {
                    "username": user.username,
                    "display_name": user.display_name,
                    "start_balance": user.start_balance,
                    "default_dry_run": user.default_dry_run,
                    "email": user.email,
                    "withdrawal_eth_address": user.withdrawal_eth_address,
                    "avatar_emoji": user.avatar_emoji,
                    "plan": user.plan or "free",
                    "twofa_enabled": user.twofa_enabled,
                    "theme": user.theme or "pulsr",
                    "timezone": user.timezone or "GMT",
                },
                "total_engines": len(instances),
                "total_strategies": len(list_strategies()),
                "active": "settings",
                "saved": True,
            },
        )
    finally:
        db.close()


# ── Strategies section ──
STRATEGY_FILES = {
    "strategy_v1_3": {
        "pine": "pinescript-tv/Eve_Engine_v1_3.pine",
        "python": "engine/v1_3.py",
        "name": "Scalp v1.3",
        "description": "Aggressive scalp strategy with adaptive ATR trailing stop, EMA fan alignment, and ADX trend filtering. Activation 8 / Offset 3.",
    },
    "strategy_v1": {
        "pine": "pinescript-tv/Eve_Engine_v1_Swing.pine",
        "python": "engine/v1.py",
        "name": "Swing v1",
        "description": "Swing strategy with sniper 36/12 profile. Longer timeframe, wider trailing stops for trend capture.",
    },
    "strategy_v6_1": {
        "pine": "pinescript-tv/Engine_v6_1.pine",
        "python": "engine/v6_1.py",
        "name": "PRO v6.1",
        "description": "Professional strategy with manual 18/6 activation/offset. Balanced between scalp and swing.",
    },
}


def _read_source(path):
    """Read source file content, return empty string if not found."""
    try:
        full = os.path.join(os.path.dirname(os.path.dirname(__file__)), path)
        with open(full, "r") as f:
            return f.read()
    except Exception:
        return ""


@router.get("/app/strategies", response_class=HTMLResponse)
@limiter.limit(READ_LIMIT)
def strategies_page(request: Request, username: str = Depends(verify_ui_credentials)):
    """Strategies overview — grid of all registered strategies."""
    db = Session()
    try:
        from strategies.registry import STRATEGIES, get_presets
        strategies_data = []
        for sid, cls in STRATEGIES.items():
            info = STRATEGY_FILES.get(sid, {})
            presets = get_presets(sid)
            preset = list(presets.values())[0] if presets else {}
            # Aggregate trades using this strategy
            trades = db.query(Trade).filter(Trade.instance_id.in_(
                [i.slug for i in db.query(Instance).filter(Instance.strategy_id == sid).all()]
            )).all()
            closed = [t for t in trades if t.exit_price is not None]
            wins = sum(1 for t in closed if (t.pnl_usd or 0) > 0)
            total_pnl = round(sum((t.pnl_usd or 0) for t in closed), 2)
            win_rate = round(wins / len(closed) * 100, 1) if closed else 0.0
            # Engines running this strategy
            engines = db.query(Instance).filter(Instance.strategy_id == sid).all()
            strategies_data.append({
                "strategy_id": sid,
                "name": info.get("name", sid),
                "description": info.get("description", ""),
                "status": "active",
                "activation": preset.get("activation", "?"),
                "offset": preset.get("offset", "?"),
                "timeframe": preset.get("timeframe", "?"),
                "mode": preset.get("mode", "?"),
                "win_rate": win_rate,
                "total_pnl": total_pnl,
                "total_trades": len(closed),
                "engine_count": len(engines),
                "running_count": sum(1 for e in engines if e.status == "running"),
            })
        return templates.TemplateResponse(
            request,
            "strategies.html",
            context={
                "request": request,
                "api_key": get_dashboard_api_key(request),
                "strategies": strategies_data,
                "total_strategies": len(strategies_data),
                "active_count": sum(1 for s in strategies_data if s["status"] == "active"),
                "active": "strategies",
            },
        )
    finally:
        db.close()


@router.get("/app/strategies/upload", response_class=HTMLResponse)
@limiter.limit(READ_LIMIT)
def strategy_upload_page(request: Request, username: str = Depends(verify_ui_credentials)):
    """Strategy upload form — paste PineScript, save to DB as pending."""
    return templates.TemplateResponse(
        request,
        "strategy_upload.html",
        context={
            "request": request,
            "api_key": get_dashboard_api_key(request),
            "active": "strategies",
        },
    )


@router.get("/app/strategies/studio", response_class=HTMLResponse)
@limiter.limit(READ_LIMIT)
def strategy_studio_page(request: Request, username: str = Depends(verify_ui_credentials)):
    """Strategy Studio — Pine -> Python AI converter."""
    return templates.TemplateResponse(
        request,
        "strategy_studio.html",
        context={
            "request": request,
            "api_key": get_dashboard_api_key(request),
            "ai_provider": config.AI_PROVIDER,
            "ai_model": config.AI_MODEL,
            "active": "strategies",
            "chat_context": "studio",
        },
    )


@router.get("/app/strategies/{strategy_id}", response_class=HTMLResponse)
@limiter.limit(READ_LIMIT)
def strategy_detail_page(request: Request, strategy_id: str, username: str = Depends(verify_ui_credentials)):
    """Strategy detail — Overview / PineScript / Python / Documentation tabs."""
    db = Session()
    try:
        from strategies.registry import STRATEGIES, get_presets
        if strategy_id not in STRATEGIES:
            return templates.TemplateResponse(request, "error.html", context={
                "request": request, "error": f"Strategy '{strategy_id}' not found", "active": "strategies",
            }, status_code=404)
        info = STRATEGY_FILES.get(strategy_id, {})
        presets = get_presets(strategy_id)
        preset = list(presets.values())[0] if presets else {}
        pine_source = _read_source(info.get("pine", ""))
        python_source = _read_source(info.get("python", ""))
        # Engines using this strategy
        engines = db.query(Instance).filter(Instance.strategy_id == strategy_id).all()
        engines_data = [{
            "slug": e.slug, "name": e.name, "token": e.token,
            "status": e.status, "dry_run": e.dry_run, "timeframe": e.timeframe,
        } for e in engines]
        # Trades using this strategy
        trades = db.query(Trade).filter(Trade.instance_id.in_(
            [e.slug for e in engines]
        )).order_by(Trade.timestamp.desc()).limit(50).all()
        closed = [t for t in trades if t.exit_price is not None]
        wins = sum(1 for t in closed if (t.pnl_usd or 0) > 0)
        losses = sum(1 for t in closed if (t.pnl_usd or 0) < 0)
        total_pnl = round(sum((t.pnl_usd or 0) for t in closed), 2)
        win_rate = round(wins / len(closed) * 100, 1) if closed else 0.0
        return templates.TemplateResponse(
            request,
            "strategy_detail.html",
            context={
                "request": request,
                "api_key": get_dashboard_api_key(request),
                "strategy_id": strategy_id,
                "name": info.get("name", strategy_id),
                "description": info.get("description", ""),
                "preset": preset,
                "pine_source": pine_source,
                "python_source": python_source,
                "engines": engines_data,
                "win_rate": win_rate,
                "total_pnl": total_pnl,
                "total_trades": len(closed),
                "wins": wins,
                "losses": losses,
                "active": "strategies",
            },
        )
    finally:
        db.close()


@router.post("/api/v2/strategies/upload")
@limiter.limit(WRITE_LIMIT)
async def strategy_upload_api(request: Request, username: str = Depends(verify_ui_credentials)):
    """API: upload a new strategy. Accepts PineScript or Python source.
    Body: {name, strategy_id, pine_source?, python_source?, source_type: "pine"|"python"}
    """
    import uuid as _uuid
    from instances.models import engine as db_engine, Strategy, SessionLocal as DBSession

    body = await request.json()
    name = (body.get("name") or "").strip()
    strategy_id = (body.get("strategy_id") or "").strip().lower().replace(" ", "_")
    source_type = (body.get("source_type") or "pine").strip().lower()
    pine_source = (body.get("pine_source") or "").strip()
    python_source = (body.get("python_source") or "").strip()

    if not name or not strategy_id:
        return {"ok": False, "message": "name and strategy_id are required"}

    if source_type == "python":
        if not python_source:
            return {"ok": False, "message": "python_source is required when source_type=python"}
        # Validate: must compile
        try:
            compile(python_source, f"<{strategy_id}>", "exec")
        except SyntaxError as e:
            return {"ok": False, "message": f"Python syntax error: {e}"}
        # Validate: must have BaseStrategy subclass
        from strategies.base import BaseStrategy
        namespace = {"__builtins__": __builtins__, "BaseStrategy": BaseStrategy}
        try:
            exec(python_source, namespace)
        except Exception as e:
            return {"ok": False, "message": f"Python import/exec error: {e}"}
        # Find the class
        strategy_cls = None
        for obj in namespace.values():
            if isinstance(obj, type) and issubclass(obj, BaseStrategy) and obj is not BaseStrategy:
                strategy_cls = obj
                break
        if not strategy_cls:
            return {"ok": False, "message": "No BaseStrategy subclass found in Python source"}
        if not hasattr(strategy_cls, 'generate_signals') or not callable(getattr(strategy_cls, 'generate_signals')):
            return {"ok": False, "message": "Missing generate_signals() method"}
        # Auto-register
        from strategies.registry import register_uploaded_strategy
        register_uploaded_strategy(strategy_id, strategy_cls)
        # Get default config
        parameters = strategy_cls.get_default_config() if hasattr(strategy_cls, 'get_default_config') else {}

        db = DBSession()
        try:
            existing = db.query(Strategy).filter(Strategy.strategy_id == strategy_id).first()
            if existing:
                return {"ok": False, "message": f"Strategy '{strategy_id}' already exists"}
            strat = Strategy(
                id=str(_uuid.uuid4()),
                name=name,
                strategy_id=strategy_id,
                pine_source=pine_source or f"# Auto-generated placeholder for {strategy_id}",
                python_source=python_source,
                status="active",
                parameters=parameters,
                version="1.0",
            )
            db.add(strat)
            db.commit()
            return {"ok": True, "strategy_id": strategy_id, "message": "Strategy uploaded and activated"}
        finally:
            db.close()

    else:  # pine
        if not pine_source:
            return {"ok": False, "message": "pine_source is required when source_type=pine"}
        db = DBSession()
        try:
            existing = db.query(Strategy).filter(Strategy.strategy_id == strategy_id).first()
            if existing:
                return {"ok": False, "message": f"Strategy '{strategy_id}' already exists"}
            strat = Strategy(
                id=str(_uuid.uuid4()),
                name=name,
                strategy_id=strategy_id,
                pine_source=pine_source,
                status="pending",
                version="1.0",
            )
            db.add(strat)
            db.commit()
            return {"ok": True, "strategy_id": strategy_id, "message": "Strategy uploaded as pending"}
        finally:
            db.close()


@router.post("/api/v2/strategies/{strategy_id}/convert")
@limiter.limit(WRITE_LIMIT)
async def strategy_convert_api(strategy_id: str, request: Request, username: str = Depends(verify_ui_credentials)):
    """API: convert PineScript to Python via LLM. Returns python_source (preview, not saved).

    Two modes:
    - Body has `pine_source`: convert that directly (standalone paste, no DB write).
    - Body empty / no pine_source: load pine_source from the existing strategy row.
    """
    body = await request.json()
    pine_source = (body.get("pine_source") or "").strip()
    name = (body.get("name") or "").strip()
    save_slug = (body.get("save_slug") or "").strip()
    save_path = None
    if save_slug:
        # sanitize: slug chars only, no path traversal
        if not all(c.isalnum() or c in "-_" for c in save_slug):
            return {"ok": False, "message": "save_slug must match [a-z0-9_-]+"}
        from pathlib import Path

        root = Path(__file__).resolve().parent.parent
        save_dir = root / "strategies" / save_slug
        save_dir.mkdir(parents=True, exist_ok=True)
        save_path = str(save_dir / "strategy.py")

    # Phase 9: resolve operator user so the converter uses the DB-stored AI provider
    # (credential manager), falling back to env for operator.
    user_id = None
    db0 = Session()
    try:
        user = get_user_or_seed_user(db0, username)
        user_id = user.id
    finally:
        db0.close()

    if not pine_source:
        # Fallback: load from DB row
        db = Session()
        try:
            strat = db.query(Strategy).filter(Strategy.strategy_id == strategy_id).first()
            if not strat:
                return {"ok": False, "message": f"Strategy '{strategy_id}' not found"}
            pine_source = strat.pine_source or ""
            name = name or strat.name
        finally:
            db.close()
        if not pine_source.strip():
            return {"ok": False, "message": "No PineScript source to convert"}

    try:
        from core.llm import convert_pine_to_python

        python_source = convert_pine_to_python(
            pine_source, name or strategy_id, user_id=user_id,
            save_path=save_path,
        )
    except Exception as e:
        return {"ok": False, "message": f"Conversion failed: {e}"}
    resp = {
        "ok": True,
        "strategy_id": save_slug or strategy_id,
        "python_source": python_source,
        "message": (
            f"Conversion complete — saved to strategies/{save_slug}/strategy.py"
            if save_path
            else "Conversion complete — review then Save to activate."
        ),
    }
    if save_path:
        resp["saved_path"] = save_path
    return resp


@router.post("/api/v2/strategies/{strategy_id}/generate")
@limiter.limit(WRITE_LIMIT)
async def strategy_generate_api(strategy_id: str, request: Request, username: str = Depends(verify_ui_credentials)):
    """API (Track 5.9): generate PineScript + doc + fidelity for a strategy.

    Returns {ok, strategy_id, pinescript, doc, fidelity}.
      - pinescript: the strategy's PineScript source (from the Strategy row).
      - doc:        a deterministic markdown doc derived from the structural
                    summary (no LLM call — offline + verifiable).
      - fidelity:   structural diff surface via core.translate.pine_to_struct
                    ({indicators, inputs, vars, functions}) used by the
                    fidelity-score mechanism.

    Body may override with `pine_source` (standalone, no DB write).
    """
    body = await request.json()
    pine_source = (body.get("pine_source") or "").strip()

    if not pine_source:
        db = Session()
        try:
            strat = db.query(Strategy).filter(Strategy.strategy_id == strategy_id).first()
            if strat:
                pine_source = strat.pine_source or ""
        finally:
            db.close()
        # Fallback: read the originating .pine from the strategy subdir
        # (disk-based strategies may not have a DB Strategy row).
        if not pine_source.strip():
            from pathlib import Path

            strat_dir = Path(__file__).resolve().parent.parent / "strategies" / strategy_id
            pines = sorted(strat_dir.glob("*.pine")) if strat_dir.is_dir() else []
            if pines:
                pine_source = pines[0].read_text(encoding="utf-8", errors="replace")
        if not pine_source.strip():
            return {"ok": False, "message": f"No PineScript source for strategy '{strategy_id}' (no DB row and no .pine file)"}

    try:
        from core.translate import pine_to_struct

        struct = pine_to_struct(pine_source)
    except Exception as e:
        return {"ok": False, "message": f"Fidelity analysis failed: {e}"}

    indicators = struct.get("indicators", [])
    inputs = struct.get("inputs", [])
    vars_ = struct.get("vars", [])
    functions = struct.get("functions", [])

    doc_lines = [
        f"# Strategy: `{strategy_id}`",
        "",
        "Auto-generated structural summary (Track 5.9 fidelity surface).",
        "",
        f"- **Indicators:** {', '.join(indicators) if indicators else 'none detected'}",
        f"- **Inputs (tuneable):** {len(inputs)}",
    ]
    for inp in inputs:
        doc_lines.append(f"  - `{inp.get('name')}` ({inp.get('kind')})")
    doc_lines += [
        f"- **Variables:** {len(vars_)}",
        f"- **Functions:** {len(functions)}",
        "",
        "## PineScript source",
        "",
        "```pinescript",
        pine_source.strip(),
        "```",
    ]
    doc = "\n".join(doc_lines)

    # Fidelity score: fraction of the structural surface that is non-empty.
    surface_total = len(indicators) + len(inputs) + len(vars_) + len(functions)
    fidelity_score = round(min(1.0, surface_total / 12.0), 3) if surface_total else 0.0

    return {
        "ok": True,
        "strategy_id": strategy_id,
        "pinescript": pine_source,
        "doc": doc,
        "fidelity": {
            "score": fidelity_score,
            "surface": struct,
        },
    }


@router.post("/api/v2/chat")
@limiter.limit(WRITE_LIMIT)
async def chat_api(request: Request, username: str = Depends(verify_ui_credentials)):
    """API: assistant chat. Persists per-user session (cap 10) + messages.
    Body: {context, session_id?, message, model?}
      context: assistant | studio | backtester | dashboard
      model:   optional override (else User.assistant_model)
    Returns: {session_id, reply, model}
    """
    from core.llm import chat as llm_chat
    from instances.models import (
        ChatSession, ChatMessage, get_or_seed_operator, _now_utc,
    )
    MAX_SESSIONS = 10
    body = await request.json()
    context = (body.get("context") or "assistant").strip() or "assistant"
    session_id = (body.get("session_id") or "").strip()
    message = (body.get("message") or "").strip()
    model_override = (body.get("model") or "").strip() or None
    if not message:
        return {"ok": False, "message": "Empty message"}

    db = Session()
    try:
        user = get_user_or_seed_user(db, username)
        user_id = user.id

        # Resolve or create session
        sess = None
        if session_id:
            sess = db.query(ChatSession).filter(
                ChatSession.id == session_id,
                ChatSession.user_id == user_id,
            ).first()
        if not sess:
            # Cap sessions at 10: prune oldest beyond reserve
            count = db.query(ChatSession).filter(
                ChatSession.user_id == user_id).count()
            if count >= MAX_SESSIONS:
                oldest = db.query(ChatSession).filter(
                    ChatSession.user_id == user_id
                ).order_by(ChatSession.updated_at.asc()).first()
                if oldest:
                    db.query(ChatMessage).filter(
                        ChatMessage.session_id == oldest.id).delete()
                    db.delete(oldest)
                    db.commit()
            sess = ChatSession(user_id=user_id, context=context,
                               title=message[:48])
            db.add(sess)
            db.commit()
            db.refresh(sess)

        # Load history (last 20 messages for context window)
        history = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == sess.id)
            .order_by(ChatMessage.created_at.asc())
            .all()
        )
        sys_lines = [f"[context: {sess.context}] You are PULS-R, a trading strategy "
                    f"assistant for a HyperLiquid strategy engine. Be concise, technical, "
                    f"and correct. Help with strategy logic, PineScript, Python, and backtest interpretation."]
        # ── Inject live account context when on dashboard ──
        if context == "dashboard":
            try:
                from instances.models import Instance, AccountSnapshot, Trade
                live_instances = db.query(Instance).order_by(Instance.created_at.asc()).all()
                latest_snap = db.query(AccountSnapshot).order_by(AccountSnapshot.timestamp.desc()).first()
                live_val = 0.0
                try:
                    from core.exchange import get_hyperliquid_client
                    hl = get_hyperliquid_client()
                    if getattr(hl, 'has_credentials', False):
                        live_val = hl.get_account_value()
                except Exception:
                    pass
                acct_val = live_val if live_val > 0 else (latest_snap.account_value if latest_snap else 0.0)
                open_pnl = sum((i.unrealized_pnl or 0.0) for i in live_instances)
                active = sum(1 for i in live_instances if i.status == "running")
                realized = sum(t.pnl_usd for t in db.query(Trade).filter(Trade.dry_run == False).all()) if db.query(Trade).filter(Trade.dry_run == False).first() else 0.0
                engine_summary = "; ".join(
                    f"{i.name}({i.token}, {i.status}, pos={i.position_side or 'FLAT'} {i.position_size or 0:.1f}, pnl=${i.unrealized_pnl or 0:.2f})"
                    for i in live_instances
                )
                sys_lines.append(
                    f"LIVE ACCOUNT CONTEXT: account_value=${acct_val:.2f}, unrealized_pnl=${open_pnl:.2f}, "
                    f"realized_pnl=${realized:.2f}, active_engines={active}/{len(live_instances)}. "
                    f"ENGINES: {engine_summary}. "
                    f"Use this data to answer questions about the user's account, engines, and performance. "
                    f"Do not say you lack access — you have live data."
                )
            except Exception:
                pass
        msgs = list(sys_lines)
        for m in history:
            msgs.append(f"{m.role}: {m.content}")
        msgs.append(f"user: {message}")
        prompt = "\n".join(msgs)

        # Persist user message
        db.add(ChatMessage(session_id=sess.id, user_id=user_id,
                          role="user", content=message))
        db.commit()

        try:
            reply = llm_chat(
                sys_lines[0], prompt,
                user_id=user_id, model_role="assistant",
                model_override=model_override,
            )
            model_used = model_override or user.assistant_model or "glm-5.1"
        except Exception as e:
            return {"ok": False, "session_id": sess.id,
                    "message": f"LLM error: {e}"}

        db.add(ChatMessage(session_id=sess.id, user_id=user_id,
                          role="assistant", content=reply, model=model_used))
        sess.updated_at = _now_utc()
        db.commit()
        return {"ok": True, "session_id": sess.id, "reply": reply,
                "model": model_used}
    finally:
        db.close()


@router.delete("/api/v2/chat/session/{session_id}")
@limiter.limit(WRITE_LIMIT)
async def chat_session_delete_api(session_id: str, request: Request, username: str = Depends(verify_ui_credentials)):
    """API: delete a chat session and its messages."""
    from instances.models import ChatSession, ChatMessage, get_or_seed_operator
    db = Session()
    try:
        user = get_user_or_seed_user(db, username)
        sess = db.query(ChatSession).filter(
            ChatSession.id == session_id,
            ChatSession.user_id == user.id,
        ).first()
        if not sess:
            return {"ok": False, "message": "Session not found"}
        db.query(ChatMessage).filter(ChatMessage.session_id == sess.id).delete()
        db.delete(sess)
        db.commit()
        return {"ok": True, "message": "Session deleted"}
    finally:
        db.close()


@router.get("/api/v2/chat/sessions")
@limiter.limit(READ_LIMIT)
async def chat_sessions_api(request: Request, username: str = Depends(verify_ui_credentials)):
    """API: list last 10 chat sessions for the operator."""
    from instances.models import ChatSession, get_or_seed_operator
    db = Session()
    try:
        user = get_user_or_seed_user(db, username)
        sessions = (
            db.query(ChatSession)
            .filter(ChatSession.user_id == user.id)
            .order_by(ChatSession.updated_at.desc())
            .limit(10).all()
        )
        return {
            "ok": True,
            "sessions": [
                {"id": s.id, "title": s.title, "context": s.context,
                 "updated_at": s.updated_at.isoformat() if s.updated_at else None}
                for s in sessions
            ],
        }
    finally:
        db.close()


@router.get("/api/v2/chat/session/{session_id}")
@limiter.limit(READ_LIMIT)
async def chat_session_detail_api(session_id: str, request: Request, username: str = Depends(verify_ui_credentials)):
    """API: get messages for a specific chat session."""
    from instances.models import ChatSession, ChatMessage, get_or_seed_operator
    db = Session()
    try:
        user = get_user_or_seed_user(db, username)
        sess = db.query(ChatSession).filter(
            ChatSession.id == session_id,
            ChatSession.user_id == user.id,
        ).first()
        if not sess:
            return {"ok": False, "message": "Session not found"}
        msgs = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == sess.id)
            .order_by(ChatMessage.created_at.asc()).all()
        )
        return {
            "ok": True,
            "session": {"id": sess.id, "title": sess.title, "context": sess.context},
            "messages": [
                {"role": m.role, "content": m.content, "model": m.model}
                for m in msgs
            ],
        }
    finally:
        db.close()


@router.post("/api/v2/strategies/{strategy_id}/save")
@limiter.limit(WRITE_LIMIT)
async def strategy_save_api(strategy_id: str, request: Request, username: str = Depends(verify_ui_credentials)):
    """API: save converted Python + mark strategy active (usable in engines)."""
    body = await request.json()
    python_source = body.get("python_source") or ""
    documentation = body.get("documentation") or None
    if not python_source.strip():
        return {"ok": False, "message": "python_source is required"}
    db = Session()
    try:
        strat = db.query(Strategy).filter(Strategy.strategy_id == strategy_id).first()
        if not strat:
            return {"ok": False, "message": f"Strategy '{strategy_id}' not found"}
        strat.python_source = python_source
        if documentation is not None:
            strat.documentation = documentation
        strat.status = "active"
        db.commit()
        return {"ok": True, "strategy_id": strategy_id, "message": "Strategy saved and activated."}
    finally:
        db.close()


@router.get("/app/live", response_class=HTMLResponse)
@limiter.limit(READ_LIMIT)
def live_page(request: Request, username: str = Depends(verify_ui_credentials)):
    """Live Trading engines (dry_run=False). Mirrors dashboard but Live-only context."""
    return _instances_by_mode(request, live=True, username=username)


# Candles endpoint moved to api/instances.py (uses verify_api_key, not verify_ui_credentials)


@router.get("/app/paper", response_class=HTMLResponse)
def paper_redirect():
    return RedirectResponse(url="/app/testing/paper", status_code=301)


@router.get("/app/testing/paper", response_class=HTMLResponse)
@limiter.limit(READ_LIMIT)
def testing_paper(request: Request, username: str = Depends(verify_ui_credentials)):
    """Paper Trading — dry_run=True engines. Renders testing_paper.html."""
    return _instances_by_mode(request, live=False, template="testing_paper.html", username=username)


def _instances_by_mode(request: Request, live: bool, template: str = None, username: str = None):
    db = Session()
    try:
        user = get_user_or_seed_user(db, username)
        instances = db.query(Instance).filter(
            Instance.user_id == user.id,
            Instance.dry_run == (not live),
        ).all()
        inst_data = []
        equity_series = []
        for i in instances:
            snaps = db.query(AccountSnapshot).filter(
                AccountSnapshot.instance_id == i.slug,
                AccountSnapshot.user_id == user.id,
            ).order_by(AccountSnapshot.timestamp.asc()).all()
            series = [{"time": int(s.timestamp.timestamp()), "value": round(s.account_value, 2)} for s in snaps]
            equity_series.extend(series)
            inst_data.append({
                "slug": i.slug, "name": i.name, "token": i.token, "status": i.status,
                "dry_run": i.dry_run, "start_balance": i.start_balance or 0.0,
                "unrealized_pnl": i.unrealized_pnl or 0.0,
                "account_value": i.unrealized_pnl or 0.0,
            })
        equity_series.sort(key=lambda x: x["time"])
        total_pnl = sum((i["unrealized_pnl"] for i in inst_data), 0.0)
        active = sum(1 for i in inst_data if i["status"] == "running")
        # Paper trades for the testing/paper view (dry_run == (not live)).
        paper_rows = db.query(Trade).filter(
            Trade.user_id == user.id, Trade.dry_run == (not live)
        ).order_by(Trade.timestamp.desc()).limit(100).all()
        paper_data = [{
            "id": t.id,
            "time": t.timestamp.strftime("%Y-%m-%d %H:%M") if t.timestamp else "",
            "instance": t.instance_id,
            "side": t.side,
            "size": round(t.size, 4),
            "entry_price": round(t.entry_price, 6) if t.entry_price else 0.0,
            "exit_price": round(t.exit_price, 6) if t.exit_price else None,
            "pnl_usd": round(t.pnl_usd, 2),
            "pnl_pct": round(t.pnl_pct, 2),
            "fees": round((t.entry_cost or 0.0) + (t.exit_cost or 0.0), 4),
            "open": t.exit_price is None,
        } for t in paper_rows]
        return templates.TemplateResponse(
            request,
            template or "live_paper.html",
            context={
                "request": request,
                "api_key": get_dashboard_api_key(request),
                "mode": "live" if live else "paper",
                "mode_label": "Live Trading" if live else "Paper Trading",
                "instances": inst_data,
                "equity_series": equity_series,
                "paper_trades": paper_data,
                "active_engines": active,
                "total_engines": len(inst_data),
                "total_pnl": round(total_pnl, 2),
                "active": "live" if live else "paper",
            },
        )
    finally:
        db.close()

