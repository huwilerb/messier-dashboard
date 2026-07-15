"""Password hashing helpers and session-cookie auth dependencies."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from passlib.context import CryptContext
from sqlmodel import Session

from app.config import settings
from app.database import get_session
from app.models import Groupe

# deprecated="auto" means hashes made at a previous BCRYPT_ROUNDS value keep
# verifying and get transparently rehashed at the current cost on next login.
_pwd_context = CryptContext(
    schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=settings.BCRYPT_ROUNDS
)


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt."""
    return _pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Check a plaintext password against a bcrypt hash."""
    return _pwd_context.verify(plain_password, password_hash)


class NotAuthenticated(HTTPException):
    """Raised when a route requires a logged-in groupe and none is set.

    Handled in app/main.py: redirects to /login (full redirect, or
    HX-Redirect for HTMX requests) instead of surfacing a raw 401 body.
    """

    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )


def get_current_groupe(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> Groupe:
    """Resolve the Groupe logged in via the session cookie.

    The session dict is populated at login with
    ``{"groupe_id": int, "groupe_nom": str}`` (see app/routers/auth.py).
    Raises NotAuthenticated (-> redirect to /login) if not logged in.
    """
    groupe_id = request.session.get("groupe_id")
    if groupe_id is None:
        raise NotAuthenticated()

    groupe = session.get(Groupe, groupe_id)
    if groupe is None:
        # Stale session (e.g. group was deleted) -> force re-login.
        request.session.clear()
        raise NotAuthenticated()

    return groupe


def get_current_groupe_optional(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> Groupe | None:
    """Same as get_current_groupe but returns None instead of raising."""
    groupe_id = request.session.get("groupe_id")
    if groupe_id is None:
        return None
    return session.get(Groupe, groupe_id)


def require_admin(
    groupe: Annotated[Groupe, Depends(get_current_groupe)],
) -> Groupe:
    """Dependency ensuring the current groupe is an admin."""
    if not groupe.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required"
        )
    return groupe
