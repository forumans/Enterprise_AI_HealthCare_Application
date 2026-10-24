"""Middleware wiring: public paths, and server errors that the browser can actually read."""

import asyncio
import json
import unittest
from types import SimpleNamespace

from fastapi.routing import APIRoute

from backend.app.core.dependencies import get_current_identity
from backend.app.main import SERVER_ERROR_DETAIL, app, catch_unhandled_errors


def _needs_identity(route: APIRoute) -> bool:
    stack = list(route.dependant.dependencies)
    while stack:
        dep = stack.pop()
        if dep.call is get_current_identity:
            return True
        stack.extend(dep.dependencies)
    return False


class PublicPathTests(unittest.TestCase):
    def test_no_public_path_serves_a_route_that_needs_a_login(self):
        # A public (excluded) path skips token decoding, so a handler that needs the identity
        # would answer 401 even to logged-in users - which the frontend treats as "session ended".
        excluded = next(m for m in app.user_middleware if m.cls.__name__ == "TenantContextMiddleware").kwargs["excluded_paths"]
        broken = [route.path for route in app.routes if isinstance(route, APIRoute) and route.path in excluded and _needs_identity(route)]
        self.assertEqual(broken, [])

    def test_doctor_list_is_not_public(self):
        excluded = next(m for m in app.user_middleware if m.cls.__name__ == "TenantContextMiddleware").kwargs["excluded_paths"]
        self.assertNotIn("/api/doctors", excluded)


class ServerErrorTests(unittest.TestCase):
    def test_unexpected_errors_become_a_json_500(self):
        async def boom(_request):
            raise RuntimeError("permission denied for table support_staff")

        request = SimpleNamespace(method="POST", url=SimpleNamespace(path="/api/admin/users"))
        response = asyncio.run(catch_unhandled_errors(request, boom))
        self.assertEqual(response.status_code, 500)
        self.assertEqual(json.loads(response.body), {"detail": SERVER_ERROR_DETAIL})  # internals stay in the log

    def test_error_handler_sits_inside_cors(self):
        # user_middleware is outermost-first: CORS must wrap the error handler so 500s get CORS headers
        names = [m.cls.__name__ if m.cls.__name__ != "BaseHTTPMiddleware" else m.kwargs["dispatch"].__name__ for m in app.user_middleware]
        self.assertEqual(names[:2], ["CORSMiddleware", "catch_unhandled_errors"])


if __name__ == "__main__":
    unittest.main()
