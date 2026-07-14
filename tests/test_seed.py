"""Acceptance criteria: idempotence de seed.py (spec section 11 + section 9).

Runs against its own throwaway SQLite file (separate from the shared
conftest test DB), since we want to exercise seed()'s from-scratch
behaviour (empty DB -> 110 objets + 2 groupes) and then its idempotent
no-op behaviour on a second call, without interference from other tests'
fixtures resetting Groupe/Observation between tests.
"""

import tempfile
from pathlib import Path

from sqlmodel import create_engine, select

import app.database as db_module
import seed as seed_module
from app.models import Groupe, ObjetMessier
from sqlmodel import Session


def test_seed_is_idempotent_for_catalog_and_default_groupes(monkeypatch):
    tmp_dir = Path(tempfile.mkdtemp(prefix="messier-seed-test-"))
    db_path = tmp_dir / "seed_test.db"
    fresh_engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )

    # seed.py's own `seed()` function resolves the name `engine` from its
    # own module globals (bound once via `from app.database import
    # engine`), so it must be patched directly -- patching
    # app.database.engine alone would not be picked up by seed()'s already
    # -imported reference. monkeypatch restores both afterwards.
    monkeypatch.setattr(seed_module, "engine", fresh_engine)
    monkeypatch.setattr(db_module, "engine", fresh_engine)

    seed_module.seed()

    with Session(fresh_engine) as session:
        objets = session.exec(select(ObjetMessier)).all()
        groupes = session.exec(select(Groupe)).all()
    assert len(objets) == 110
    assert len(groupes) == 2
    assert {g.nom for g in groupes} == {"Admin", "Les Astronomes du Soir"}

    # Second run against the same DB must not duplicate anything.
    seed_module.seed()

    with Session(fresh_engine) as session:
        objets_again = session.exec(select(ObjetMessier)).all()
        groupes_again = session.exec(select(Groupe)).all()
    assert len(objets_again) == 110
    assert len(groupes_again) == 2

    fresh_engine.dispose()
