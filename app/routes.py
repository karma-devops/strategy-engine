"""
FastAPI UI routes.
"""

from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import sessionmaker

from api.ratelimit import limiter, READ_LIMIT, WRITE_LIMIT
from config import config
from api.auth import verify_ui_credentials
from instances.models import engine, Instance
from instances.manager import manager

Session = sessionmaker(bind=engine)
router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
@limiter.limit(READ_LIMIT)
def dashboard(request: Request, username: str = Depends(verify_ui_credentials)):
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        context={"request": request, "api_key": config.AGENT_API_KEY or ""},
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
    dry_run: bool = Form(False),
):
    db = Session()
    try:
        # Auto-generate slug if empty
        if not slug:
            existing = db.query(Instance).count()
            slug = f"engine-{existing + 1}"
        slug = slug.lower().strip()
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


@router.get("/withdrawals", response_class=HTMLResponse)
@limiter.limit(READ_LIMIT)
def withdrawals_page(request: Request, username: str = Depends(verify_ui_credentials)):
    return templates.TemplateResponse(request, "withdrawals.html", context={"request": request})
