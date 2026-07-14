"""SQLModel table definitions: Groupe, ObjetMessier, Observation.

Table and column names are kept exactly as specified in the project brief
(French names) since routers and templates reference them directly.
"""

from datetime import date, datetime

from sqlmodel import Field, SQLModel


class Groupe(SQLModel, table=True):
    """A club group/team that logs observations and can log in."""

    __tablename__ = "groupes"

    id: int | None = Field(default=None, primary_key=True)
    nom: str = Field(max_length=100, unique=True, index=True)  # e.g. "Galaxie Hunters"
    password_hash: str = Field(max_length=255)  # bcrypt hash, never expose
    is_admin: bool = Field(default=False)  # grants access to /admin
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ObjetMessier(SQLModel, table=True):
    """One of the 110 Messier catalog objects."""

    __tablename__ = "objets_messier"

    id: int | None = Field(default=None, primary_key=True)
    designation: str = Field(max_length=10, unique=True, index=True)  # "M1", "M42", ...
    nom_commun: str | None = Field(default=None, max_length=200)  # "Nebuleuse du Crabe"
    type_objet: str = Field(max_length=50)
    # One of: Galaxie, Nebuleuse, Amas ouvert, Amas globulaire,
    # Nebuleuse planetaire, Restes de supernova
    constellation: str = Field(max_length=50)
    description: str | None = Field(default=None)  # optional short description


class Observation(SQLModel, table=True):
    """A logged capture (photo or visual) of a Messier object by a group."""

    __tablename__ = "observations"

    id: int | None = Field(default=None, primary_key=True)
    groupe_id: int = Field(foreign_key="groupes.id", index=True)
    objet_id: int = Field(foreign_key="objets_messier.id", index=True)
    date_observation: date = Field(index=True)
    type_capture: str = Field(max_length=20)  # "photo" or "visuel"
    notes: str | None = Field(default=None, max_length=2000)
    photo_path: str | None = Field(default=None, max_length=500)  # relative path under UPLOAD_DIR
    date_saisie: datetime = Field(default_factory=datetime.utcnow)

    # Business rule (see app.config.Settings.UNIQUE_OBSERVATION_PER_OBJECT):
    # when enabled, a group may only have one Observation row per objet_id.
    # This is enforced at the application layer (upsert) in
    # app/routers/observations.py rather than as a DB-level unique
    # constraint, so the setting can be toggled without a migration.
