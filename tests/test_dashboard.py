"""Acceptance criteria: Dashboard groupe (spec section 11)."""

import re

from tests.conftest import GROUP_NOM, get_objet_id


def _designations(objet_ids, db_session):
    from app.models import ObjetMessier

    return [db_session.get(ObjetMessier, oid).designation for oid in objet_ids]


def test_dashboard_lists_all_110_objects(group_client):
    resp = group_client.get("/dashboard")
    assert resp.status_code == 200
    card_ids = re.findall(r'id="object-card-(\d+)"', resp.text)
    assert len(card_ids) == 110
    assert len(set(card_ids)) == 110  # all distinct, no duplicates


def test_dashboard_progress_reflects_logged_observations(group_client, db_session):
    designations = ["M1", "M13", "M31", "M42", "M57"]
    for i, designation in enumerate(designations):
        objet_id = get_objet_id(db_session, designation)
        resp = group_client.post(
            "/observations/add",
            data={
                "objet_id": objet_id,
                "date_observation": f"2026-01-{10 + i:02d}",
                "type_capture": "visuel",
            },
            headers={"HX-Request": "true"},
        )
        assert resp.status_code == 200

    dash = group_client.get("/dashboard")
    assert dash.status_code == 200
    assert f"{len(designations)}/110" in dash.text

    expected_percent = round(len(designations) / 110 * 100, 1)
    assert f"{expected_percent}%" in dash.text

    # Every captured object shows the "captured" badge; count them.
    assert dash.text.count("is-captured") == len(designations)


def test_dashboard_shows_groupe_name(group_client):
    resp = group_client.get("/dashboard")
    assert GROUP_NOM in resp.text


def test_dashboard_zero_observations_shows_zero_progress(group_client):
    resp = group_client.get("/dashboard")
    assert "0/110" in resp.text
    assert "0.0%" in resp.text
    assert resp.text.count("is-captured") == 0
