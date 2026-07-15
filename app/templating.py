"""Single shared Jinja2Templates instance for the whole app.

Each router previously built its own Jinja2Templates(directory=...), so
every shared template/partial (base.html, the macros) was parsed and
cached once per environment instead of once total, and Starlette's
default auto_reload=True made every render stat the template file on
disk to check its mtime -- a wasted syscall per request on slow storage.
Import `templates` from here instead of constructing a new instance.
"""

import jinja2
from fastapi.templating import Jinja2Templates

from app.config import settings

_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader("app/templates"),
    autoescape=jinja2.select_autoescape(),
    auto_reload=settings.DEBUG,
)

templates = Jinja2Templates(env=_env)
