"""Acceptance criteria: Administration (spec section 11)."""

from sqlmodel import select

from app.models import Groupe
from tests.conftest import get_groupe_id


def test_create_groupe_as_admin(admin_client, db_session):
    resp = admin_client.post(
        "/admin/groupes/create",
        data={"nom": "Nouveau Groupe", "password": "secret123"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/admin"

    created = db_session.exec(
        select(Groupe).where(Groupe.nom == "Nouveau Groupe")
    ).first()
    assert created is not None
    assert created.is_admin is False


def test_new_groupe_can_log_in(admin_client, client):
    admin_client.post(
        "/admin/groupes/create",
        data={"nom": "Login Testers", "password": "hunter22"},
    )

    resp = client.post(
        "/login", data={"nom": "Login Testers", "password": "hunter22"}
    )
    assert resp.status_code in (200, 303)
    dash = client.get("/dashboard")
    assert dash.status_code == 200


def test_create_groupe_forbidden_for_non_admin(group_client):
    resp = group_client.post(
        "/admin/groupes/create",
        data={"nom": "Sneaky Groupe", "password": "whatever"},
    )
    assert resp.status_code == 403


def test_create_groupe_duplicate_name_rejected(admin_client):
    resp = admin_client.post(
        "/admin/groupes/create",
        data={"nom": "TestGroup", "password": "whatever"},
    )
    assert resp.status_code == 400


def test_reset_password_admin_only(group_client, db_session):
    target_id = get_groupe_id(db_session, "TestGroup2")
    resp = group_client.post(
        f"/admin/groupes/{target_id}/reset-password",
        data={"new_password": "hacked"},
    )
    assert resp.status_code == 403


def test_reset_password_new_works_old_fails(admin_client, client, db_session):
    target_id = get_groupe_id(db_session, "TestGroup2")

    resp = admin_client.post(
        f"/admin/groupes/{target_id}/reset-password",
        data={"new_password": "brand-new-pass"},
        follow_redirects=False,
    )
    assert resp.status_code == 303

    old_login = client.post(
        "/login", data={"nom": "TestGroup2", "password": "group2-pass-123"}
    )
    assert old_login.status_code == 401

    new_login = client.post(
        "/login", data={"nom": "TestGroup2", "password": "brand-new-pass"}
    )
    assert new_login.status_code in (200, 303)
    assert client.get("/dashboard").status_code == 200


def test_delete_groupe_admin_only(group_client, db_session):
    target_id = get_groupe_id(db_session, "TestGroup2")
    resp = group_client.post(f"/admin/groupes/{target_id}/delete")
    assert resp.status_code == 403


def test_delete_groupe_removes_it_and_its_observations(
    admin_client, group2_client, db_session
):
    from tests.conftest import get_objet_id

    objet_id = get_objet_id(db_session, "M1")
    group2_client.post(
        "/observations/add",
        data={
            "objet_id": objet_id,
            "date_observation": "2026-01-01",
            "type_capture": "visuel",
        },
        headers={"HX-Request": "true"},
    )

    target_id = get_groupe_id(db_session, "TestGroup2")
    resp = admin_client.post(
        f"/admin/groupes/{target_id}/delete", follow_redirects=False
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/admin"

    remaining = db_session.get(Groupe, target_id)
    assert remaining is None

    from app.models import Observation

    obs_rows = db_session.exec(
        select(Observation).where(Observation.groupe_id == target_id)
    ).all()
    assert obs_rows == []


def test_admin_cannot_delete_own_groupe(admin_client, db_session):
    admin_id = get_groupe_id(db_session, "TestAdmin")
    resp = admin_client.post(f"/admin/groupes/{admin_id}/delete")
    assert resp.status_code == 400
