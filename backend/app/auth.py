import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.dependencies import get_db
from app.models import AuthAttempt, AuthSession, User, AutomationJob, Workspace, WorkspaceMembership
from app.passwords import hash_password

COOKIE_NAME = "aurora_session"
DUMMY_HASH = hash_password(secrets.token_urlsafe(32))


def cookie_name() -> str:
    # Browsers enforce Secure, host-only and Path=/ for the production prefix.
    return f"__Host-{COOKIE_NAME}" if settings.auth_cookie_secure else COOKIE_NAME


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def csrf_token(token: str) -> str:
    return hmac.new(token.encode(), b"aurora-csrf-v1", hashlib.sha256).hexdigest()


def check_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin and origin not in settings.web_origins:
        raise HTTPException(403, "Origem não permitida.")


def check_auth_write(request: Request) -> None:
    check_origin(request)
    if request.headers.get("x-aurora-request") != "1":
        raise HTTPException(403, "Cabeçalho de proteção CSRF ausente.")


def get_current_user(request: Request, db: Annotated[Session, Depends(get_db)]) -> User:
    authorization = request.headers.get("authorization", "")
    bearer = authorization.startswith("Bearer ")
    token = authorization[7:] if bearer else request.cookies.get(cookie_name(), "")
    if not 32 <= len(token) <= 256:
        raise HTTPException(401, "Sessão ausente ou expirada. Entre novamente.")
    session = db.get(AuthSession, token_hash(token))
    if session is None or session.expires_at <= utcnow():
        raise HTTPException(401, "Sessão ausente ou expirada. Entre novamente.")
    user = db.get(User, session.user_id)
    if user is None or not user.active:
        raise HTTPException(401, "Sessão ausente ou expirada. Entre novamente.")
    membership = db.get(WorkspaceMembership, (session.workspace_id, user.id))
    workspace = db.get(Workspace, session.workspace_id)
    if membership is None or not membership.active or workspace is None:
        raise HTTPException(401, "Seu acesso ao espaço de trabalho não está ativo. Entre novamente.")
    # Identity and membership are verified. Apply their trusted workspace before
    # loading AutomationJob, which is itself protected by the financial read guard.
    db.info.update(workspace_id=workspace.id, actor_id=user.id)
    if bearer:
        job = db.get(AutomationJob, session.job_id) if session.job_id else None
        analysis_path = f"/automations/{session.job_id}/analysis"
        if (job is None or job.workspace_id != session.workspace_id or job.status != "running"
            or request.method != "GET" or request.url.path not in {"/dashboard/summary", "/alerts", analysis_path}
            or request.query_params.get("year") != str(job.year)
            or request.query_params.get("month") != str(job.month)):
            raise HTTPException(403, "Credencial restrita à leitura do período desta tarefa.")
        if request.url.path == analysis_path and (
            request.query_params.get("workspace_id") != str(job.workspace_id)
            or request.query_params.get("import_id") != job.import_id
            or request.query_params.get("attempt") != str(job.attempts)
        ):
            raise HTTPException(403, "Contexto de automação incompatível com a tarefa.")
    elif session.job_id is not None:
        raise HTTPException(401, "Sessão inválida.")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        check_origin(request)
        supplied = request.headers.get("x-csrf-token", "")
        if not hmac.compare_digest(supplied.encode("utf-8"), csrf_token(token).encode("ascii")):
            raise HTTPException(403, "Proteção CSRF inválida. Atualize a sessão.")
    if bearer:
        db.info.update(actor_kind="automation", automation_job_id=job.id,
                       automation_attempt=job.attempts)
    request.state.workspace = workspace
    request.state.auth_session = session
    return user


def issue_session(db: Session, user: User, workspace: Workspace, request: Request, response: Response) -> str:
    old = request.cookies.get(cookie_name())
    if old:
        previous = db.get(AuthSession, token_hash(old))
        if previous is not None:
            db.delete(previous)
    token = secrets.token_urlsafe(32)
    max_age = settings.auth_session_hours * 3600
    db.add(AuthSession(token_hash=token_hash(token), user_id=user.id, workspace_id=workspace.id, expires_at=utcnow() + timedelta(seconds=max_age)))
    db.commit()
    response.set_cookie(cookie_name(), token, max_age=max_age, httponly=True, secure=settings.auth_cookie_secure, samesite="strict", path="/")
    response.headers["Cache-Control"] = "no-store"
    return csrf_token(token)


def limit_auth_attempts(db: Session, request: Request) -> None:
    # Use the actual peer address, never a caller-controlled forwarded header.
    key = token_hash(f"auth:{request.client.host if request.client else 'unknown'}")
    for attempt in range(2):
        record = db.scalar(select(AuthAttempt).where(AuthAttempt.key == key).with_for_update())
        now = utcnow()
        if record and record.expires_at > now and record.count >= 20:
            raise HTTPException(429, "Muitas tentativas. Aguarde 15 minutos.", headers={"Retry-After": "900"})
        if record is None:
            db.add(AuthAttempt(key=key, count=1, expires_at=now + timedelta(minutes=15)))
        elif record.expires_at <= now:
            record.count, record.expires_at = 1, now + timedelta(minutes=15)
        else:
            record.count += 1
        try:
            db.commit()
            return
        except IntegrityError:
            db.rollback()
            if attempt:
                raise HTTPException(503, "Não foi possível iniciar a autenticação. Tente novamente.") from None
