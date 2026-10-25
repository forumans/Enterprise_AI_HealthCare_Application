"""Walk the app's API routes in a way that works across FastAPI versions.

FastAPI up to ~0.135 flattened included routers into `app.routes` as APIRoute objects with the
full path. Newer FastAPI (0.162, as deployed on AWS) keeps them nested in internal
`_IncludedRouter` wrappers that carry the include prefix, so code that scans `app.routes` for
APIRoute silently finds nothing - and checks like "no duplicate routes" then pass vacuously.
"""

from __future__ import annotations

from typing import Iterator

from fastapi.routing import APIRoute
from starlette.routing import compile_path

# Sanity floor: the app registers well over this many API routes (each under /api and unprefixed)
MIN_EXPECTED_ROUTES = 100


def iter_api_routes(app) -> Iterator[tuple[str, APIRoute]]:
    """Yield (full path, route) for every APIRoute, in registration (= matching) order."""

    def walk(routes, prefix: str):
        for route in routes:
            if isinstance(route, APIRoute):
                yield prefix + route.path, route
            elif hasattr(route, "original_router") and hasattr(route, "include_context"):  # newer FastAPI
                yield from walk(route.original_router.routes, prefix + (route.include_context.prefix or ""))

    found = list(walk(app.router.routes, ""))
    if len(found) < MIN_EXPECTED_ROUTES:
        raise AssertionError(f"Only found {len(found)} API routes - the route walker no longer understands this FastAPI version.")
    yield from found


def find_route(app, path: str, method: str) -> APIRoute:
    """The route registered for this exact path template and method."""

    for full_path, route in iter_api_routes(app):
        if full_path == path and method in route.methods:
            return route
    raise AssertionError(f"{method} {path} is not registered")


def handler_for(app, concrete_path: str, method: str = "GET") -> str | None:
    """Name of the endpoint that serves a concrete URL (first match wins, as in Starlette)."""

    for full_path, route in iter_api_routes(app):
        regex, _, _ = compile_path(full_path)
        if method in route.methods and regex.match(concrete_path):
            return route.endpoint.__name__
    return None
