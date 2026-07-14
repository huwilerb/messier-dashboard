# Messier Marathon

A small web app for an astronomy club's annual challenge: groups race to observe
(photograph or view) all **110 objects of the Messier catalog** in a year. Each
group logs its observations through a simple web form, and a public leaderboard
tracks everyone's progress.

## Stack

| Component     | Technology                                  |
| -------------- | -------------------------------------------- |
| Backend        | FastAPI (Python 3.13+)                       |
| Templates      | Jinja2 + HTMX (no heavy JS)                   |
| Database       | SQLite + SQLModel                             |
| Auth           | Signed session cookie + passlib/bcrypt        |
| Dependencies   | [uv](https://docs.astral.sh/uv/)              |
| Deployment     | Podman (rootless) + `podman-compose`          |

## Local development

Requires Python 3.13+ and [uv](https://docs.astral.sh/uv/).

```bash
# Install dependencies (creates .venv automatically)
uv sync

# Configure environment
cp .env.example .env
# then edit .env and set a real SECRET_KEY

# Create the database and seed the 110 Messier objects + default groups
uv run python seed.py

# Run the dev server
uv run uvicorn app.main:app --reload
```

The app is then available at http://localhost:8000.

Seed data creates two groups for local testing:

| Group                    | Password     | Role        |
| ------------------------ | ------------ | ----------- |
| `Admin`                  | `admin123`   | admin       |
| `Les Astronomes du Soir` | `motdepasse` | regular     |

Change or remove these before deploying anywhere real.

## Running tests

```bash
uv run --dev pytest
```

## Project structure

```
app/
├── main.py              # FastAPI instance, middleware, startup
├── config.py            # Settings loaded from environment / .env
├── database.py           # SQLite engine + session dependency
├── models.py             # Groupe, ObjetMessier, Observation
├── auth.py                # Password hashing + session-based auth dependencies
├── routers/
│   ├── auth.py            # /login, /logout
│   ├── observations.py    # dashboard, add/delete observation (HTMX)
│   ├── leaderboard.py      # public leaderboard, object detail
│   └── admin.py            # group management (admin only)
├── templates/              # Jinja2 templates + HTMX partials
└── static/                 # CSS and uploaded photos

messier_catalog.json      # The 110 Messier objects
seed.py                    # DB initialization script
tests/                     # pytest suite
Containerfile               # Container image definition
podman-compose.yml           # Container orchestration
```

## Deployment (Podman)

```bash
export SECRET_KEY="$(openssl rand -hex 32)"
podman-compose up -d --build
```

The app listens on port 8000. The SQLite database and uploaded photos are
stored in named Podman volumes (`messier-data`, `messier-uploads`) so they
persist across `podman-compose down` / `up` cycles; `podman-compose down -v`
removes them.

See `.env.example` for all configurable environment variables (upload size
limit, whether a group can log more than one capture per object, etc).
