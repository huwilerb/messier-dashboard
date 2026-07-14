"""Admin-only routes: group management.

Context variables passed to templates:

- admin.html:
    groupe   -> Groupe (the logged-in admin, for nav display)
    is_admin -> bool (always True here, kept for template consistency
                with dashboard.html's nav)
    groupes  -> list[dict], one per non-admin+admin groupe, each with keys:
                "id" (int), "nom" (str), "is_admin" (bool),
                "created_at" (datetime), "observations_count" (int)
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.auth import hash_password, require_admin
from app.database import get_session
from app.models import Groupe, Observation

router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory="app/templates")


@router.get("")
def admin_home(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    groupe: Annotated[Groupe, Depends(require_admin)],
):
    all_groupes = session.exec(select(Groupe)).all()

    groupes: list[dict] = []
    for g in all_groupes:
        obs_count = len(
            session.exec(select(Observation).where(Observation.groupe_id == g.id)).all()
        )
        groupes.append(
            {
                "id": g.id,
                "nom": g.nom,
                "is_admin": g.is_admin,
                "created_at": g.created_at,
                "observations_count": obs_count,
            }
        )

    return templates.TemplateResponse(
        request,
        "admin.html",
        {"groupe": groupe, "is_admin": True, "groupes": groupes},
    )


@router.post("/groupes/create")
def create_groupe(
    session: Annotated[Session, Depends(get_session)],
    _admin: Annotated[Groupe, Depends(require_admin)],
    nom: Annotated[str, Form()],
    password: Annotated[str, Form()],
    is_admin: Annotated[bool, Form()] = False,
):
    existing = session.exec(select(Groupe).where(Groupe.nom == nom)).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ce nom de groupe existe déjà")

    new_groupe = Groupe(nom=nom, password_hash=hash_password(password), is_admin=is_admin)
    session.add(new_groupe)
    session.commit()

    return RedirectResponse(url="/admin", status_code=303)


@router.post("/groupes/{groupe_id}/reset-password")
def reset_password(
    groupe_id: int,
    session: Annotated[Session, Depends(get_session)],
    _admin: Annotated[Groupe, Depends(require_admin)],
    new_password: Annotated[str, Form()],
):
    target = session.get(Groupe, groupe_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Groupe inconnu")

    target.password_hash = hash_password(new_password)
    session.add(target)
    session.commit()

    return RedirectResponse(url="/admin", status_code=303)


@router.get("/groupes/{groupe_id}/delete")
def delete_groupe(
    groupe_id: int,
    session: Annotated[Session, Depends(get_session)],
    admin: Annotated[Groupe, Depends(require_admin)],
):
    if groupe_id == admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Impossible de supprimer votre propre groupe")

    target = session.get(Groupe, groupe_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Groupe inconnu")

    observations = session.exec(
        select(Observation).where(Observation.groupe_id == groupe_id)
    ).all()
    for obs in observations:
        session.delete(obs)

    session.delete(target)
    session.commit()

    return RedirectResponse(url="/admin", status_code=303)
