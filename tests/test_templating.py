from urllib.parse import parse_qs, urlsplit

from starlette.requests import Request

from app.templating import build_query_links


def test_build_query_links_preserves_existing_filters():
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "scheme": "http",
            "server": ("testserver", 80),
            "client": ("testclient", 50000),
            "path": "/admin/carreras",
            "query_string": b"tipo=grado&nombre=arquitectura",
            "headers": [],
        }
    )

    links = build_query_links(
        request,
        {
            "fecha": {"orden": "fecha", "direccion": "desc"},
            "nombre": {"orden": "nombre", "direccion": "asc"},
        },
    )

    assert parse_qs(urlsplit(links["fecha"]).query) == {
        "tipo": ["grado"],
        "nombre": ["arquitectura"],
        "orden": ["fecha"],
        "direccion": ["desc"],
    }
