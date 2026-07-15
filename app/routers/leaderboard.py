"""Public leaderboard, catalogue, and per-object detail pages (no auth required).

Context variables passed to templates:

- leaderboard.html:
    leaderboard -> list[dict] sorted by count desc, each dict has keys:
                   "nom" (str, groupe name), "count" (int, distinct
                   objects captured), "percent" (float, count/110*100,
                   1 decimal place)
    total_objets -> int, total number of Messier objects (110)

- catalogue.html:
    objets          -> list[ObjetMessier], sorted by numeric designation
                        (M1, M2, ... M110), filtered to `selected_type`
                        and/or `selected_saison` if set. No per-group
                        capture status: this page is public and not
                        scoped to any logged-in group.
    types            -> list[str], distinct type_objet values present in
                         the catalog, sorted alphabetically.
    type_counts      -> dict[str, int], number of objects per type (over
                         the full unfiltered catalog, for the filter UI).
    selected_type    -> str | None, the type_objet currently filtered to
                         (None means "all").
    seasons          -> list[str], season keys in calendar order:
                         "hiver", "printemps", "ete", "automne".
    season_labels    -> dict[str, str], season key -> display label.
    season_counts    -> dict[str, int], number of objects visible at some
                         point during each season (over the full
                         unfiltered catalog).
    selected_saison  -> str | None, the season currently filtered to.
    total_objets     -> int, total number of Messier objects (110),
                         unaffected by the filter.

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
from app.routers.observations import _all_objets

router = APIRouter(tags=["leaderboard"])
templates = Jinja2Templates(directory="app/templates")

# Calendar-order season -> months, using standard meteorological seasons.
SEASON_MONTHS: dict[str, set[int]] = {
    "hiver": {12, 1, 2},
    "printemps": {3, 4, 5},
    "ete": {6, 7, 8},
    "automne": {9, 10, 11},
}
SEASON_LABELS: dict[str, str] = {
    "hiver": "Hiver",
    "printemps": "Printemps",
    "ete": "Été",
    "automne": "Automne",
}


@router.get("/objets")
def catalogue_view(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    type_objet: str | None = None,
    saison: str | None = None,
):
    all_objets = _all_objets(session)

    type_counts: dict[str, int] = {}
    for objet in all_objets:
        type_counts[objet.type_objet] = type_counts.get(objet.type_objet, 0) + 1
    types = sorted(type_counts)

    season_counts: dict[str, int] = {}
    for season, months in SEASON_MONTHS.items():
        season_counts[season] = sum(
            1 for o in all_objets if months & set(o.mois_visibles_list)
        )

    selected_type = type_objet if type_objet in type_counts else None
    selected_saison = saison if saison in SEASON_MONTHS else None

    objets = all_objets
    if selected_type:
        objets = [o for o in objets if o.type_objet == selected_type]
    if selected_saison:
        season_months = SEASON_MONTHS[selected_saison]
        objets = [o for o in objets if season_months & set(o.mois_visibles_list)]

    return templates.TemplateResponse(
        request,
        "catalogue.html",
        {
            "objets": objets,
            "types": types,
            "type_counts": type_counts,
            "selected_type": selected_type,
            "seasons": list(SEASON_MONTHS),
            "season_labels": SEASON_LABELS,
            "season_counts": season_counts,
            "selected_saison": selected_saison,
            "total_objets": len(all_objets),
        },
    )


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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Objet inconnu"
        )

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
