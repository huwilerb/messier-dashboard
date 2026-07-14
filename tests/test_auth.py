"""Acceptance criteria: Authentification (spec section 11)."""

from tests.conftest import ADMIN_NOM, ADMIN_PASSWORD, GROUP_NOM, GROUP_PASSWORD


def test_login_with_correct_credentials_creates_session_and_redirects(client):
    resp = client.post(
        "/login",
        data={"nom": GROUP_NOM, "password": GROUP_PASSWORD},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/dashboard"

    # The session cookie now lets us reach a protected page.
    dash = client.get("/dashboard")
    assert dash.status_code == 200
    assert GROUP_NOM in dash.text


def test_login_with_wrong_password_is_rejected_with_error(client):
    resp = client.post(
        "/login", data={"nom": GROUP_NOM, "password": "not-the-password"}
    )
    assert resp.status_code == 401
    assert "incorrect" in resp.text.lower()

    # No session was established.
    dash = client.get("/dashboard", follow_redirects=False)
    assert dash.status_code == 303
    assert dash.headers["location"] == "/login"


def test_login_with_unknown_groupe_is_rejected(client):
    resp = client.post(
        "/login", data={"nom": "Does Not Exist", "password": "whatever"}
    )
    assert resp.status_code == 401
    assert "incorrect" in resp.text.lower()


def test_unauthenticated_dashboard_redirects_to_login(client):
    resp = client.get("/dashboard", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"


def test_unauthenticated_htmx_request_gets_hx_redirect_header(client):
    resp = client.get("/dashboard", headers={"HX-Request": "true"})
    assert resp.status_code == 200
    assert resp.headers.get("hx-redirect") == "/login"


def test_logout_clears_session(group_client):
    # Sanity: logged in.
    assert group_client.get("/dashboard").status_code == 200

    resp = group_client.post("/logout", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/leaderboard"

    # Session no longer grants access.
    dash = group_client.get("/dashboard", follow_redirects=False)
    assert dash.status_code == 303
    assert dash.headers["location"] == "/login"


def test_admin_page_forbidden_for_non_admin_groupe(group_client):
    resp = group_client.get("/admin")
    assert resp.status_code == 403


def test_admin_page_ok_for_admin_groupe(admin_client):
    resp = admin_client.get("/admin")
    assert resp.status_code == 200
    assert "Administration" in resp.text
    assert ADMIN_NOM in resp.text
