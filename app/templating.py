"""Jinja2 templates instance, filters, and a context helper used by all routers."""
from __future__ import annotations

from decimal import Decimal
from urllib.parse import urlencode

from fastapi.templating import Jinja2Templates
from fastapi import Request
from fastapi.responses import RedirectResponse

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
templates.env.filters["fmt_creditos"] = lambda value: format(
    Decimal(str(value)).normalize(), "f"
)
templates.env.globals["app_name"] = settings.APP_NAME


def build_sort_links(
    request: Request,
    endpoint: str,
    fields: tuple[str, ...],
    current_sort: str,
    current_direction: str,
    default_directions: dict[str, str],
) -> dict[str, str]:
    query_items = [
        (key, value)
        for key, value in request.query_params.multi_items()
        if key not in {"sort", "direction"}
    ]
    links = {}
    for field in fields:
        direction = (
            ("desc" if current_direction == "asc" else "asc")
            if current_sort == field
            else default_directions[field]
        )
        url = request.url_for(endpoint).replace(
            query=urlencode(query_items + [("sort", field), ("direction", direction)])
        )
        links[field] = str(url)
    return links


def render(request, name, *, user=None, db=None, status_code: int = 200, **ctx):
    context = {"user": user, "unread": 0}
    if db is not None and user is not None:
        context["unread"] = unread_count(db, user.id)
    context.update(ctx)
    return templates.TemplateResponse(request, name, context, status_code=status_code)


def redirect_to(
    request: Request,
    endpoint: str,
    *,
    status_code: int = 303,
    query_params: dict[str, str] | None = None,
    **path_params,
) -> RedirectResponse:
    url = request.url_for(endpoint, **path_params)
    if query_params:
        url = url.include_query_params(**query_params)
    location = url.path
    if url.query:
        location = f"{location}?{url.query}"
    return RedirectResponse(url=location, status_code=status_code)
