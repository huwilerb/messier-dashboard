"""Acceptance criteria: Leaderboard + Détail objet (spec section 11)."""

from tests.conftest import ADMIN_NOM, GROUP_NOM, GROUP2_NOM, get_objet_id


def _log_observation(client, db_session, designation, date_str="2026-01-01"):
    objet_id = get_objet_id(db_session, designation)
    resp = client.post(
        "/observations/add",
        data={
            "objet_id": objet_id,
            "date_observation": date_str,
            "type_capture": "visuel",
        },
        headers={"HX-Request": "true"},
    )
    assert resp.status_code == 200


def test_leaderboard_accessible_without_auth(client):
    resp = client.get("/leaderboard")
    assert resp.status_code == 200
    assert "Classement" in resp.text


def test_leaderboard_orders_by_observation_count_descending(
    group_client, group2_client, db_session
):
    # GROUP_NOM logs 3 objects, GROUP2_NOM logs 1.
    for designation in ["M1", "M13", "M31"]:
        _log_observation(group_client, db_session, designation)
    _log_observation(group2_client, db_session, "M42")

    resp = group_client.get("/leaderboard")
    assert resp.status_code == 200

    pos_group1 = resp.text.index(GROUP_NOM)
    pos_group2 = resp.text.index(GROUP2_NOM)
    assert pos_group1 < pos_group2, "group with more captures should rank first"


def test_leaderboard_shows_correct_percent_of_110(group_client, db_session):
    for designation in ["M1", "M13", "M31", "M42"]:
        _log_observation(group_client, db_session, designation)

    resp = group_client.get("/leaderboard")
    expected_percent = round(4 / 110 * 100, 1)
    assert f"{expected_percent}%" in resp.text
    assert "4" in resp.text


def test_leaderboard_excludes_admin_groupe(admin_client, db_session):
    _log_observation(admin_client, db_session, "M1")
    resp = admin_client.get("/leaderboard")
    assert ADMIN_NOM not in resp.text


def test_objet_detail_returns_200_with_type_and_constellation(client):
    resp = client.get("/objet/M42")
    assert resp.status_code == 200
    assert "M42" in resp.text
    assert "Nébuleuse" in resp.text
    assert "Orion" in resp.text


def test_objet_detail_unknown_designation_404(client):
    resp = client.get("/objet/M9999")
    assert resp.status_code == 404


def test_objet_detail_lists_observations_from_multiple_groupes(
    group_client, group2_client, db_session
):
    _log_observation(group_client, db_session, "M8", "2026-01-05")
    _log_observation(group2_client, db_session, "M8", "2026-01-06")

    resp = group_client.get("/objet/M8")
    assert resp.status_code == 200
    assert "Observations (2)" in resp.text
    assert GROUP_NOM in resp.text
    assert GROUP2_NOM in resp.text
    # The backend's own contract renders groupe_nom (not an id) per row;
    # verify no raw "groupe_id" field/key leaks into the rendered page.
    assert "groupe_id" not in resp.text
