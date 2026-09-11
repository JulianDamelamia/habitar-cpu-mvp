"""Jinja2 templates instance, filters, and a context helper used by all routers."""
from __future__ import annotations

from fastapi.templating import Jinja2Templates

from app.config import settings
from app.services.notifications import unread_count

templates = Jinja2Templates(directory="app/templates")


def _fmt_dt(value, fmt: str = "%d/%m/%Y %H:%M") -> str:
    if value is None:
        return ""
    return value.strftime(fmt)


templates.env.filters["fmt_dt"] = _fmt_dt
templates.env.filters["fmt_date"] = lambda v: _fmt_dt(v, "%d/%m/%Y")
templates.env.filters["fmt_time"] = lambda v: _fmt_dt(v, "%H:%M")
templates.env.filters["fmt_input"] = lambda v: _fmt_dt(v, "%Y-%m-%dT%H:%M")
templates.env.globals["app_name"] = settings.APP_NAME


def render(request, name, *, user=None, db=None, status_code: int = 200, **ctx):
    context = {"user": user, "unread": 0}
    if db is not None and user is not None:
        context["unread"] = unread_count(db, user.id)
    context.update(ctx)
    return templates.TemplateResponse(request, name, context, status_code=status_code)
