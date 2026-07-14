"""Public leaderboard and per-object detail pages (no auth required).

Context variables passed to templates:

- leaderboard.html:
    leaderboard -> list[dict] sorted by count desc, each dict has keys:
                   "nom" (str, groupe name), "count" (int, distinct
                   objects captured), "percent" (float, count/110*100,
                   1 decimal place)
    total_objets -> int, total number of Messier objects (110)

- objet_detail.html:
    objet         -> ObjetMessier
    observations  -> list[dict], one per Observation on this object across
                     all groups, each dict has keys: "groupe_nom" (str),
                     "date_observation" (date), "type_capture" (str),
                     "notes" (str | None), "photo_path" (str | None).
                     Deliberately a list of dicts (not raw Observation +
                     Groupe rows) so no group id/internal fields leak.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.database import get_session
from app.models import Groupe, ObjetMessier, Observation

router = APIRouter(tags=["leaderboard"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/leaderboard")
def leaderboard_view(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
):
    groupes = session.exec(select(Groupe).where(Groupe.is_admin == False)).all()  # noqa: E712
    total_objets = len(session.exec(select(ObjetMessier)).all())

    rows: list[dict] = []
    for groupe in groupes:
        observations = session.exec(
            select(Observation).where(Observation.groupe_id == groupe.id)
        ).all()
        distinct_objets = {obs.objet_id for obs in observations}
        count = len(distinct_objets)
        percent = round((count / total_objets) * 100, 1) if total_objets else 0.0
        rows.append({"nom": groupe.nom, "count": count, "percent": percent})

    rows.sort(key=lambda r: r["count"], reverse=True)

    return templates.TemplateResponse(
        request,
        "leaderboard.html",
        {"leaderboard": rows, "total_objets": total_objets},
    )


@router.get("/objet/{designation}")
def objet_detail(
    request: Request,
    designation: str,
    session: Annotated[Session, Depends(get_session)],
):
    objet = session.exec(
        select(ObjetMessier).where(ObjetMessier.designation == designation)
    ).first()
    if objet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Objet inconnu")

    observations = session.exec(
        select(Observation).where(Observation.objet_id == objet.id)
    ).all()

    rows: list[dict] = []
    for obs in observations:
        groupe = session.get(Groupe, obs.groupe_id)
        rows.append(
            {
                "groupe_nom": groupe.nom if groupe else "?",
                "date_observation": obs.date_observation,
                "type_capture": obs.type_capture,
                "notes": obs.notes,
                "photo_path": obs.photo_path,
            }
        )
    rows.sort(key=lambda r: r["date_observation"], reverse=True)

    return templates.TemplateResponse(
        request,
        "objet_detail.html",
        {"objet": objet, "observations": rows},
    )
