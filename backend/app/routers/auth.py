from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import (
    DUMMY_HASH, check_auth_write, cookie_name, csrf_token, get_current_user,
    issue_session, limit_auth_attempts,
)
from app.auth_schemas import Credentials, SessionRead, UserRead, WorkspaceRead
from app.config import settings
from app.dependencies import get_db
from app.models import User, Workspace, WorkspaceMembership, AuditLog
from app.passwords import hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["Authentication"])
DbSession = Annotated[Session, Depends(get_db)]


@router.post("/register", response_model=SessionRead, status_code=201, dependencies=[Depends(check_auth_write)])
def register(payload: Credentials, request: Request, response: Response, db: DbSession):
    limit_auth_attempts(db, request)
    workspace = db.scalar(select(Workspace).where(Workspace.slug == "aurora-demo", Workspace.is_demo.is_(True)))
    if not settings.demo_registration_enabled or workspace is None:
        raise HTTPException(403, "Cadastro público disponível somente na demonstração Aurora.")
    user = User(email=payload.email, password_hash=hash_password(payload.password.get_secret_value()), active=True)
    db.add(user)
    try:
        db.flush()
        db.add(WorkspaceMembership(workspace_id=workspace.id, user_id=user.id, active=True))
        db.add(AuditLog(workspace_id=workspace.id, actor_id=user.id, actor_kind="user", action="create",
                        entity="workspace_memberships", entity_id=f"{workspace.id}:{user.id}",
                        changes={"user_id": {"after": user.id}, "active": {"after": True}}))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Não foi possível cadastrar uma conta com este email.") from None
    return SessionRead(user=UserRead.model_validate(user), workspace=WorkspaceRead.model_validate(workspace), csrf_token=issue_session(db, user, workspace, request, response))


@router.post("/login", response_model=SessionRead, dependencies=[Depends(check_auth_write)])
def login(payload: Credentials, request: Request, response: Response, db: DbSession):
    limit_auth_attempts(db, request)
    user = db.scalar(select(User).where(User.email == payload.email))
    valid = verify_password(payload.password.get_secret_value(), user.password_hash if user and user.password_hash else DUMMY_HASH)
    if not valid or user is None or not user.active:
        raise HTTPException(401, "Email ou senha inválidos.")
    workspace = db.scalar(select(Workspace).join(WorkspaceMembership).where(
        WorkspaceMembership.user_id == user.id, WorkspaceMembership.active.is_(True),
    ).order_by(Workspace.is_demo.desc(), Workspace.id).limit(1))
    if workspace is None: raise HTTPException(403, "Você não possui acesso ativo a um espaço de trabalho.")
    return SessionRead(user=UserRead.model_validate(user), workspace=WorkspaceRead.model_validate(workspace), csrf_token=issue_session(db, user, workspace, request, response))


@router.get("/me", response_model=SessionRead)
def me(request: Request, user: Annotated[User, Depends(get_current_user)]):
    return SessionRead(user=UserRead.model_validate(user), workspace=WorkspaceRead.model_validate(request.state.workspace), csrf_token=csrf_token(request.cookies[cookie_name()]))


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: DbSession, user: Annotated[User, Depends(get_current_user)]):
    db.delete(request.state.auth_session)
    db.commit()
    response.delete_cookie(cookie_name(), path="/", secure=settings.auth_cookie_secure, httponly=True, samesite="strict")
