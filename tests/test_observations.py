"""Acceptance criteria: Saisie d'observations (spec section 11)."""

from sqlmodel import select

from app.models import Observation
from tests.conftest import GROUP_NOM, get_groupe_id, get_objet_id


def test_add_observation_htmx_returns_fragment_not_redirect(group_client, db_session):
    objet_id = get_objet_id(db_session, "M42")

    resp = group_client.post(
        "/observations/add",
        data={
            "objet_id": objet_id,
            "date_observation": "2026-03-14",
            "type_capture": "visuel",
            "notes": "Belle nébuleuse, ciel bien noir.",
        },
        headers={"HX-Request": "true"},
    )

    assert resp.status_code == 200
    # A fragment, not a redirect: the object card + progress bar markup.
    assert f"object-card-{objet_id}" in resp.text
    assert "Capturé" in resp.text
    assert "1/110" in resp.text


def test_add_observation_without_htmx_redirects_to_dashboard(group_client, db_session):
    objet_id = get_objet_id(db_session, "M31")

    resp = group_client.post(
        "/observations/add",
        data={
            "objet_id": objet_id,
            "date_observation": "2026-01-01",
            "type_capture": "photo",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/dashboard"


def test_observation_persists_date_type_and_notes(group_client, db_session):
    objet_id = get_objet_id(db_session, "M13")
    groupe_id = get_groupe_id(db_session, GROUP_NOM)

    group_client.post(
        "/observations/add",
        data={
            "objet_id": objet_id,
            "date_observation": "2026-05-20",
            "type_capture": "photo",
            "notes": "Amas globulaire superbe au T250.",
        },
        headers={"HX-Request": "true"},
    )

    obs = db_session.exec(
        select(Observation).where(
            Observation.groupe_id == groupe_id, Observation.objet_id == objet_id
        )
    ).first()
    assert obs is not None
    assert str(obs.date_observation) == "2026-05-20"
    assert obs.type_capture == "photo"
    assert obs.notes == "Amas globulaire superbe au T250."
    assert obs.photo_path is None


def test_photo_upload_stores_file_and_sets_photo_path(group_client, db_session):
    objet_id = get_objet_id(db_session, "M57")
    groupe_id = get_groupe_id(db_session, GROUP_NOM)

    fake_photo = ("ring-nebula.jpg", b"\xff\xd8\xff not-a-real-jpeg-but-bytes", "image/jpeg")

    resp = group_client.post(
        "/observations/add",
        data={
            "objet_id": objet_id,
            "date_observation": "2026-06-01",
            "type_capture": "photo",
        },
        files={"photo": fake_photo},
        headers={"HX-Request": "true"},
    )
    assert resp.status_code == 200

    obs = db_session.exec(
        select(Observation).where(
            Observation.groupe_id == groupe_id, Observation.objet_id == objet_id
        )
    ).first()
    assert obs is not None
    assert obs.photo_path is not None
    assert obs.photo_path.endswith(".jpg")

    from app.config import settings
    from pathlib import Path

    stored_file = Path(settings.UPLOAD_DIR) / obs.photo_path
    assert stored_file.exists()
    assert stored_file.read_bytes() == b"\xff\xd8\xff not-a-real-jpeg-but-bytes"

    # The dashboard renders a link/img pointing at the public /uploads path.
    assert f"/uploads/{obs.photo_path}" in resp.text


def test_second_observation_same_object_upserts_instead_of_duplicating(
    group_client, db_session
):
    objet_id = get_objet_id(db_session, "M1")
    groupe_id = get_groupe_id(db_session, GROUP_NOM)

    group_client.post(
        "/observations/add",
        data={
            "objet_id": objet_id,
            "date_observation": "2026-02-01",
            "type_capture": "visuel",
            "notes": "Premier passage.",
        },
        headers={"HX-Request": "true"},
    )
    group_client.post(
        "/observations/add",
        data={
            "objet_id": objet_id,
            "date_observation": "2026-02-15",
            "type_capture": "photo",
            "notes": "Repris en photo.",
        },
        headers={"HX-Request": "true"},
    )

    rows = db_session.exec(
        select(Observation).where(
            Observation.groupe_id == groupe_id, Observation.objet_id == objet_id
        )
    ).all()
    assert len(rows) == 1, "UNIQUE_OBSERVATION_PER_OBJECT should upsert, not duplicate"
    assert rows[0].type_capture == "photo"
    assert rows[0].notes == "Repris en photo."
    assert str(rows[0].date_observation) == "2026-02-15"


def test_different_groupes_can_each_have_their_own_observation_for_same_object(
    group_client, group2_client, db_session
):
    objet_id = get_objet_id(db_session, "M45")

    group_client.post(
        "/observations/add",
        data={
            "objet_id": objet_id,
            "date_observation": "2026-03-01",
            "type_capture": "visuel",
        },
        headers={"HX-Request": "true"},
    )
    group2_client.post(
        "/observations/add",
        data={
            "objet_id": objet_id,
            "date_observation": "2026-03-02",
            "type_capture": "photo",
        },
        headers={"HX-Request": "true"},
    )

    rows = db_session.exec(
        select(Observation).where(Observation.objet_id == objet_id)
    ).all()
    assert len(rows) == 2


def test_delete_observation_removes_it_and_is_owner_only(
    group_client, group2_client, db_session
):
    objet_id = get_objet_id(db_session, "M8")

    add_resp = group_client.post(
        "/observations/add",
        data={
            "objet_id": objet_id,
            "date_observation": "2026-04-01",
            "type_capture": "visuel",
        },
        headers={"HX-Request": "true"},
    )
    assert add_resp.status_code == 200

    obs = db_session.exec(
        select(Observation).where(Observation.objet_id == objet_id)
    ).first()
    assert obs is not None

    # Another groupe may not delete it.
    forbidden = group2_client.post(f"/observations/{obs.id}/delete")
    assert forbidden.status_code == 403

    # The owning groupe can.
    ok = group_client.post(
        f"/observations/{obs.id}/delete", headers={"HX-Request": "true"}
    )
    assert ok.status_code == 200
    assert "0/110" in ok.text

    remaining = db_session.exec(
        select(Observation).where(Observation.objet_id == objet_id)
    ).all()
    assert remaining == []
