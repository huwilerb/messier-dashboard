"""Login / logout routes.

Context variables passed to templates:
- login.html: `error` (str | None) -- set when credentials are invalid.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.auth import verify_password
from app.database import get_session
from app.models import Groupe
from app.templating import templates

router = APIRouter(tags=["auth"])


@router.get("/login")
def login_form(request: Request):
    return templates.TemplateResponse(request, "login.html", {"error": None})


@router.post("/login")
def login_submit(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    nom: Annotated[str, Form()],
    password: Annotated[str, Form()],
):
    groupe = session.exec(select(Groupe).where(Groupe.nom == nom)).first()

    if groupe is None or not verify_password(password, groupe.password_hash):
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Nom de groupe ou mot de passe incorrect."},
            status_code=401,
        )

    request.session.clear()
    request.session["groupe_id"] = groupe.id
    request.session["groupe_nom"] = groupe.nom

    return RedirectResponse(url="/dashboard", status_code=303)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/leaderboard", status_code=303)
