"""Credential management API — multi-tenant, encrypted, user-scoped.

Routes:
  GET  /api/v2/credentials         → list (masked)
  POST /api/v2/credentials         → create
  PUT  /api/v2/credentials/{id}    → update (own only)
  DELETE /api/v2/credentials/{id}  → soft-delete (own only)
  POST /api/v2/credentials/{id}/test → test connectivity
"""

from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import sessionmaker

from config import config
from api.auth import verify_api_key
from api.ratelimit import limiter, WRITE_LIMIT, READ_LIMIT
from instances.models import engine, Credential, get_or_seed_operator

router = APIRouter(prefix="/api/v2/credentials", tags=["credentials"])

Session = sessionmaker(bind=engine)


class CredentialCreate(BaseModel):
    type: str  # eth_wallet | hl_api | ai_provider | app_api_key
    label: str
    priority: int = 0
    data: dict  # type-specific: {"address": "0x..."} / {"private_key": "...", "account_address": "0x..."} / {"provider": "...", "api_key": "...", "api_url": "...", "model": "..."} / {"key": "..."}


class CredentialUpdate(BaseModel):
    label: str | None = None
    priority: int | None = None
    is_active: bool | None = None
    data: dict | None = None


def _current_user_id(db):
    """Resolve current tenant user_id. Currently operator (single-tenant API key)."""
    return get_or_seed_operator(db).id


def _to_dict(c: Credential) -> dict:
    return {
        "id": c.id,
        "type": c.type,
        "label": c.label,
        "priority": c.priority,
        "masked_preview": c.masked_preview,
        "is_active": c.is_active,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


@router.get("")
@limiter.limit(READ_LIMIT)
def list_credentials(request: Request, api_key: str = Depends(verify_api_key)):
    db = Session()
    try:
        user_id = _current_user_id(db)
        creds = (
            db.query(Credential)
            .filter(Credential.user_id == user_id, Credential.is_active == True)  # noqa: E712
            .order_by(Credential.type, Credential.priority)
            .all()
        )
        return {"credentials": [_to_dict(c) for c in creds]}
    finally:
        db.close()


@router.post("")
@limiter.limit(WRITE_LIMIT)
def create_credential(request: Request, payload: CredentialCreate, api_key: str = Depends(verify_api_key)):
    if payload.type not in ("eth_wallet", "hl_api", "ai_provider", "app_api_key"):
        raise HTTPException(status_code=400, detail="Invalid credential type")
    db = Session()
    try:
        user_id = _current_user_id(db)
        cred = Credential(type=payload.type, label=payload.label, priority=payload.priority)
        cred.encrypt_and_store(payload.data, user_id)
        db.add(cred)
        db.commit()
        db.refresh(cred)
        return {"ok": True, "credential": _to_dict(cred)}
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.put("/{cred_id}")
@limiter.limit(WRITE_LIMIT)
def update_credential(request: Request, cred_id: str, payload: CredentialUpdate, api_key: str = Depends(verify_api_key)):
    db = Session()
    try:
        user_id = _current_user_id(db)
        cred = db.query(Credential).filter(Credential.id == cred_id, Credential.user_id == user_id).first()
        if not cred:
            raise HTTPException(status_code=404, detail="Credential not found")
        if payload.label is not None:
            cred.label = payload.label
        if payload.priority is not None:
            cred.priority = payload.priority
        if payload.is_active is not None:
            cred.is_active = payload.is_active
        if payload.data is not None:
            cred.encrypt_and_store(payload.data, user_id)
        db.commit()
        db.refresh(cred)
        return {"ok": True, "credential": _to_dict(cred)}
    finally:
        db.close()


@router.delete("/{cred_id}")
@limiter.limit(WRITE_LIMIT)
def delete_credential(request: Request, cred_id: str, api_key: str = Depends(verify_api_key)):
    db = Session()
    try:
        user_id = _current_user_id(db)
        cred = db.query(Credential).filter(Credential.id == cred_id, Credential.user_id == user_id).first()
        if not cred:
            raise HTTPException(status_code=404, detail="Credential not found")
        cred.is_active = False  # soft delete
        db.commit()
        return {"ok": True, "msg": "Credential deactivated"}
    finally:
        db.close()


@router.post("/{cred_id}/test")
@limiter.limit(WRITE_LIMIT)
def test_credential(request: Request, cred_id: str, api_key: str = Depends(verify_api_key)):
    """Test credential connectivity. Returns ok/error."""
    db = Session()
    try:
        user_id = _current_user_id(db)
        cred = db.query(Credential).filter(Credential.id == cred_id, Credential.user_id == user_id).first()
        if not cred:
            raise HTTPException(status_code=404, detail="Credential not found")
        data = cred.decrypt()
        if cred.type == "ai_provider":
            import requests
            url = data.get("api_url", "").rstrip("/")
            # Normalize to chat completions endpoint
            if not url.endswith("/chat/completions"):
                url = url + "/chat/completions"
            try:
                r = requests.post(
                    url,
                    headers={"Authorization": f"Bearer {data.get('api_key', '')}", "Content-Type": "application/json"},
                    json={"model": data.get("model", ""), "messages": [{"role": "user", "content": "ping"}], "max_tokens": 5},
                    timeout=15,
                )
                return {"ok": r.status_code in (200, 401), "status_code": r.status_code}
            except Exception as e:
                return {"ok": False, "error": str(e)}
        elif cred.type == "eth_wallet":
            # Basic address format validation
            addr = data.get("address", "")
            if addr.startswith("0x") and len(addr) == 42:
                return {"ok": True, "msg": "Valid Ethereum address format"}
            return {"ok": False, "error": "Invalid address format"}
        elif cred.type == "hl_api":
            # Could check balance via HL API — placeholder for now
            return {"ok": True, "msg": "Key stored (HL balance check not yet implemented)"}
        else:
            return {"ok": True, "msg": "Stored"}
    finally:
        db.close()
