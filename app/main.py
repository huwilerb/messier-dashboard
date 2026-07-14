"""FastAPI application entrypoint: app.main:app"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.auth import NotAuthenticated
from app.config import settings
from app.database import create_db_and_tables
from app.routers import admin, auth, leaderboard, observations


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(title="Messier Marathon", debug=settings.DEBUG, lifespan=lifespan)

app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)


@app.exception_handler(NotAuthenticated)
async def not_authenticated_handler(request: Request, exc: NotAuthenticated):
    """Redirect anonymous visitors to /login instead of raising a bare 401.

    HTMX requests get an HX-Redirect header (client-side navigation)
    instead of a normal Location redirect, since HTMX does not follow
    redirects for non-GET requests the same way a browser navigation does.
    """
    if request.headers.get("HX-Request") == "true":
        return Response(status_code=200, headers={"HX-Redirect": "/login"})
    return RedirectResponse(url="/login", status_code=303)


app.include_router(auth.router)
app.include_router(observations.router)
app.include_router(leaderboard.router)
app.include_router(admin.router)

# Ensure static/upload directories exist before StaticFiles mounts them
Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
Path("app/static").mkdir(parents=True, exist_ok=True)

# Serve uploaded photos publicly at /uploads/<filename>
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")
# Serve CSS / other static assets at /static
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/")
def root():
    return RedirectResponse(url="/leaderboard", status_code=303)
