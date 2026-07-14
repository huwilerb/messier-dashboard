"""Group dashboard + observation CRUD.

Context variables passed to templates:

- dashboard.html:
    groupe                      -> Groupe (current logged-in group)
    objets                      -> list[ObjetMessier], all 110, sorted by
                                    numeric designation (M1, M2, ... M110)
    observations_by_objet_id    -> dict[int, Observation] mapping
                                    ObjetMessier.id -> this group's
                                    Observation for that object (only
                                    present for captured objects)
    progress_count              -> int, number of distinct objects captured
    progress_percent            -> float, progress_count / 110 * 100 (1 dp)
    is_admin                    -> bool, groupe.is_admin (nav convenience)

- partials/object_progress.html (returned by POST /observations/add and
  GET /observations/{id}/delete on HX-Request):
    objet             -> ObjetMessier
    observation       -> Observation | None (None after a delete)
    groupe            -> Groupe
    progress_count    -> int (updated total for this group)
    progress_percent  -> float (updated total for this group)
    error             -> str | None, set when the upload was rejected
                         (e.g. file too large) while still identifying
                         which object card to re-render
"""

import uuid
from datetime import date
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.auth import get_current_groupe
from app.config import settings
from app.database import get_session
from app.models import Groupe, ObjetMessier, Observation

router = APIRouter(tags=["observations"])
templates = Jinja2Templates(directory="app/templates")


def _designation_sort_key(objet: ObjetMessier) -> int:
    """Sort 'M1'..'M110' numerically rather than lexicographically."""
    digits = "".join(ch for ch in objet.designation if ch.isdigit())
    return int(digits) if digits else 0


def _all_objets(session: Session) -> list[ObjetMessier]:
    objets = session.exec(select(ObjetMessier)).all()
    return sorted(objets, key=_designation_sort_key)


def _observations_for_groupe(session: Session, groupe_id: int) -> dict[int, Observation]:
    observations = session.exec(
        select(Observation).where(Observation.groupe_id == groupe_id)
    ).all()
    return {obs.objet_id: obs for obs in observations}


def _progress(observations_by_objet_id: dict[int, Observation], total_objets: int) -> tuple[int, float]:
    count = len(observations_by_objet_id)
    percent = round((count / total_objets) * 100, 1) if total_objets else 0.0
    return count, percent


@router.get("/dashboard")
def dashboard(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    groupe: Annotated[Groupe, Depends(get_current_groupe)],
):
    objets = _all_objets(session)
    observations_by_objet_id = _observations_for_groupe(session, groupe.id)
    progress_count, progress_percent = _progress(observations_by_objet_id, len(objets))

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "groupe": groupe,
            "objets": objets,
            "observations_by_objet_id": observations_by_objet_id,
            "progress_count": progress_count,
            "progress_percent": progress_percent,
            "is_admin": groupe.is_admin,
        },
    )


def _save_photo(photo: UploadFile, contents: bytes) -> str:
    """Persist an uploaded photo under UPLOAD_DIR with a sanitized name.

    Returns the relative path (filename only) stored in Observation.photo_path.
    """
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)

    original_suffix = Path(photo.filename or "").suffix.lower()
    # Keep only a small allowlist-ish suffix; fall back to .jpg if unusual/absent.
    safe_suffix = original_suffix if original_suffix and len(original_suffix) <= 10 else ".jpg"
    filename = f"{uuid.uuid4().hex}{safe_suffix}"

    (upload_dir / filename).write_bytes(contents)
    return filename


@router.post("/observations/add")
async def add_observation(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    groupe: Annotated[Groupe, Depends(get_current_groupe)],
    objet_id: Annotated[int, Form()],
    date_observation: Annotated[date, Form()],
    type_capture: Annotated[str, Form()],
    notes: Annotated[str | None, Form()] = None,
    photo: Annotated[UploadFile | None, File()] = None,
):
    is_htmx = request.headers.get("HX-Request") == "true"

    objet = session.get(ObjetMessier, objet_id)
    if objet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Objet inconnu")

    photo_path: str | None = None
    error: str | None = None
    if photo is not None and photo.filename:
        contents = await photo.read()
        if len(contents) > settings.max_upload_size_bytes:
            error = f"Photo trop volumineuse (max {settings.MAX_UPLOAD_SIZE_MB} Mo)."
        else:
            photo_path = _save_photo(photo, contents)

    if error is None:
        existing = session.exec(
            select(Observation).where(
                Observation.groupe_id == groupe.id,
                Observation.objet_id == objet_id,
            )
        ).first()

        # Business rule (UNIQUE_OBSERVATION_PER_OBJECT): when a group already
        # has an observation for this object, we upsert (update in place)
        # rather than reject -- this is the more useful default for a club
        # that wants to let a group replace an older photo/notes.
        if existing is not None and settings.UNIQUE_OBSERVATION_PER_OBJECT:
            existing.date_observation = date_observation
            existing.type_capture = type_capture
            existing.notes = notes
            if photo_path is not None:
                existing.photo_path = photo_path
            session.add(existing)
            session.commit()
            session.refresh(existing)
            observation = existing
        else:
            observation = Observation(
                groupe_id=groupe.id,
                objet_id=objet_id,
                date_observation=date_observation,
                type_capture=type_capture,
                notes=notes,
                photo_path=photo_path,
            )
            session.add(observation)
            session.commit()
            session.refresh(observation)
    else:
        observation = session.exec(
            select(Observation).where(
                Observation.groupe_id == groupe.id,
                Observation.objet_id == objet_id,
            )
        ).first()

    if not is_htmx:
        return RedirectResponse(url="/dashboard", status_code=303)

    observations_by_objet_id = _observations_for_groupe(session, groupe.id)
    total_objets = session.exec(select(ObjetMessier)).all()
    progress_count, progress_percent = _progress(observations_by_objet_id, len(total_objets))

    return templates.TemplateResponse(
        request,
        "partials/object_progress.html",
        {
            "objet": objet,
            "observation": observation,
            "groupe": groupe,
            "progress_count": progress_count,
            "progress_percent": progress_percent,
            "error": error,
        },
    )


@router.get("/observations/{observation_id}/delete")
def delete_observation(
    request: Request,
    observation_id: int,
    session: Annotated[Session, Depends(get_session)],
    groupe: Annotated[Groupe, Depends(get_current_groupe)],
):
    observation = session.get(Observation, observation_id)
    if observation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Observation inconnue")
    if observation.groupe_id != groupe.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Vous n'êtes pas propriétaire de cette observation")

    objet = session.get(ObjetMessier, observation.objet_id)

    # Best-effort removal of the uploaded file; missing file is not fatal.
    if observation.photo_path:
        file_path = Path(settings.UPLOAD_DIR) / observation.photo_path
        file_path.unlink(missing_ok=True)

    session.delete(observation)
    session.commit()

    is_htmx = request.headers.get("HX-Request") == "true"
    if not is_htmx:
        return RedirectResponse(url="/dashboard", status_code=303)

    observations_by_objet_id = _observations_for_groupe(session, groupe.id)
    total_objets = session.exec(select(ObjetMessier)).all()
    progress_count, progress_percent = _progress(observations_by_objet_id, len(total_objets))

    return templates.TemplateResponse(
        request,
        "partials/object_progress.html",
        {
            "objet": objet,
            "observation": None,
            "groupe": groupe,
            "progress_count": progress_count,
            "progress_percent": progress_percent,
            "error": None,
        },
    )
