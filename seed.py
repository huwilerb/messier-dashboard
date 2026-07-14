#!/usr/bin/env python3
"""Database initialization script.

Usage: python seed.py

Creates all tables (if missing), loads the 110 Messier objects from
messier_catalog.json, and creates a default admin group plus one example
group. Idempotent: if the catalog is already loaded, it exits without
making changes (existing groups/observations are left untouched).
"""

import json
import sys
from pathlib import Path

# Allow running this script directly (python seed.py) by adding the repo
# root to sys.path so `import app` resolves.
sys.path.insert(0, str(Path(__file__).parent))

from sqlmodel import Session, func, select

from app.auth import hash_password
from app.database import create_db_and_tables, engine
from app.models import Groupe, ObjetMessier


def load_catalog(json_path: Path) -> list[dict]:
    with open(json_path, encoding="utf-8") as f:
        return json.load(f)


def seed() -> None:
    create_db_and_tables()

    with Session(engine) as session:
        # SQLModel's Session has no .query() (that's the legacy SQLAlchemy
        # ORM API) -- use select()/exec() instead.
        existing_count = session.exec(
            select(func.count()).select_from(ObjetMessier)
        ).one()
        if existing_count > 0:
            print(f"Base deja amorcee ({existing_count} objets). Abandon.")
            return

        catalog_path = Path(__file__).parent / "messier_catalog.json"
        objects = load_catalog(catalog_path)

        for obj_data in objects:
            session.add(ObjetMessier(**obj_data))

        # Default admin group.
        admin_group = session.exec(select(Groupe).where(Groupe.nom == "Admin")).first()
        if admin_group is None:
            session.add(
                Groupe(
                    nom="Admin",
                    password_hash=hash_password("admin123"),
                    is_admin=True,
                )
            )

        # Example group for manual testing.
        example_group = session.exec(
            select(Groupe).where(Groupe.nom == "Les Astronomes du Soir")
        ).first()
        if example_group is None:
            session.add(
                Groupe(
                    nom="Les Astronomes du Soir",
                    password_hash=hash_password("motdepasse"),
                    is_admin=False,
                )
            )

        session.commit()
        print(f"Base amorcee : {len(objects)} objets Messier + groupes par defaut")


if __name__ == "__main__":
    seed()
