"""Shared pytest fixtures for the Messier Marathon test suite.

Strategy: the whole test session runs against one isolated temp SQLite
file (never the real ``data/messier.db``), created by monkeypatching the
module-level ``engine`` object in ``app.database`` *before* any test
imports/uses it. Because ``get_session()`` and ``create_db_and_tables()``
both look up the name ``engine`` in ``app.database``'s own module
namespace at call time (not at import time), simply reassigning
``app.database.engine`` is enough to redirect every dependency-injected
session and the lifespan's ``create_all`` to the temp DB -- no need to
touch app/*.py or use FastAPI dependency_overrides.

The Messier catalog (110 objects) is seeded once per session (it's static
data). Groupes and Observations are reset before every single test via an
autouse function-scoped fixture so tests stay isolated from one another.
"""

import json
import os
import shutil
import tempfile
from pathlib import Path

import pytest

# Must be set before `app.config` is first imported anywhere, since
# Settings() reads the environment at import time.
os.environ.setdefault(
    "SECRET_KEY", "test-secret-key-for-pytest-only-not-for-production-use"
)

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select

import app.database as db_module
from app.auth import hash_password
from app.config import settings
from app.main import app as fastapi_app
from app.models import Groupe, ObjetMessier, Observation

REPO_ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATH = REPO_ROOT / "messier_catalog.json"
TOTAL_OBJETS = 110

ADMIN_NOM = "TestAdmin"
ADMIN_PASSWORD = "admin-pass-123"
GROUP_NOM = "TestGroup"
GROUP_PASSWORD = "group-pass-123"
GROUP2_NOM = "TestGroup2"
GROUP2_PASSWORD = "group2-pass-123"


@pytest.fixture(scope="session", autouse=True)
def _isolated_test_environment():
    """Point the app at a throwaway SQLite DB + uploads dir, once, and
    load the real Messier catalog into it (static reference data, safe to
    share across the whole session).
    """
    tmp_dir = Path(tempfile.mkdtemp(prefix="messier-test-"))
    db_path = tmp_dir / "test.db"
    uploads_dir = tmp_dir / "uploads"
    uploads_dir.mkdir()

    test_engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )

    db_module.engine = test_engine
    settings.UPLOAD_DIR = str(uploads_dir)

    SQLModel.metadata.create_all(test_engine)

    with open(CATALOG_PATH, encoding="utf-8") as f:
        catalog = json.load(f)
    assert len(catalog) == TOTAL_OBJETS, "sanity check on fixture data itself"

    with Session(test_engine) as session:
        for obj_data in catalog:
            session.add(ObjetMessier(**obj_data))
        session.commit()

    yield

    shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.fixture(autouse=True)
def _reset_groupes_and_observations():
    """Before every test: wipe Groupe/Observation rows and recreate three
    known groupes (one admin, two regular). ObjetMessier catalog rows are
    left untouched (seeded once above).
    """
    with Session(db_module.engine) as session:
        for obs in session.exec(select(Observation)).all():
            session.delete(obs)
        for g in session.exec(select(Groupe)).all():
            session.delete(g)
        session.commit()

        session.add(
            Groupe(
                nom=ADMIN_NOM, password_hash=hash_password(ADMIN_PASSWORD), is_admin=True
            )
        )
        session.add(
            Groupe(
                nom=GROUP_NOM, password_hash=hash_password(GROUP_PASSWORD), is_admin=False
            )
        )
        session.add(
            Groupe(
                nom=GROUP2_NOM,
                password_hash=hash_password(GROUP2_PASSWORD),
                is_admin=False,
            )
        )
        session.commit()

    yield


@pytest.fixture
def db_session():
    """A raw Session against the test engine, for assertions on DB state
    that bypass the HTTP layer entirely.
    """
    with Session(db_module.engine) as session:
        yield session


@pytest.fixture
def client():
    """Plain (unauthenticated) TestClient. Using the `with` form runs the
    app's lifespan (create_db_and_tables -- idempotent no-op here since
    tables already exist).
    """
    with TestClient(fastapi_app) as c:
        yield c


@pytest.fixture
def group_client():
    """TestClient already logged in as the regular test groupe.

    Deliberately does NOT reuse the `client` fixture: each authenticated
    fixture needs its own cookie jar / TestClient instance, otherwise
    tests that combine e.g. group_client + group2_client would share one
    session cookie and the second login would silently clobber the
    first (SessionMiddleware sessions are per-cookie, not per-fixture).
    """
    with TestClient(fastapi_app) as c:
        resp = c.post("/login", data={"nom": GROUP_NOM, "password": GROUP_PASSWORD})
        assert resp.status_code in (200, 303)
        yield c


@pytest.fixture
def group2_client():
    """TestClient already logged in as a *different* regular groupe."""
    with TestClient(fastapi_app) as c:
        resp = c.post("/login", data={"nom": GROUP2_NOM, "password": GROUP2_PASSWORD})
        assert resp.status_code in (200, 303)
        yield c


@pytest.fixture
def admin_client():
    """TestClient already logged in as the admin groupe."""
    with TestClient(fastapi_app) as c:
        resp = c.post("/login", data={"nom": ADMIN_NOM, "password": ADMIN_PASSWORD})
        assert resp.status_code in (200, 303)
        yield c


def get_groupe_id(db_session: Session, nom: str) -> int:
    groupe = db_session.exec(select(Groupe).where(Groupe.nom == nom)).first()
    assert groupe is not None, f"expected seeded groupe {nom!r} to exist"
    return groupe.id


def get_objet_id(db_session: Session, designation: str) -> int:
    objet = db_session.exec(
        select(ObjetMessier).where(ObjetMessier.designation == designation)
    ).first()
    assert objet is not None, f"expected catalog object {designation!r} to exist"
    return objet.id
