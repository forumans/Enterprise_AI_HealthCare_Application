import unittest

from backend.app.main import app
from backend.app.middleware import TenantContextMiddleware


class ApiPrefixRouteRegistrationTests(unittest.TestCase):
    def test_api_prefixed_business_routes_are_registered(self):
        # Newer FastAPI wraps included routers in objects without a `.path`, so read the
        # resolved paths from the OpenAPI schema instead of walking app.routes.
        paths = set(app.openapi()["paths"])

        self.assertIn("/api/auth/login", paths)
        self.assertIn("/api/tenants/current", paths)
        self.assertIn("/api/doctors", paths)
        self.assertIn("/api/appointments/all", paths)

    def test_api_public_auth_routes_are_excluded_from_tenant_middleware(self):
        tenant_middleware = next(m for m in app.user_middleware if m.cls is TenantContextMiddleware)
        excluded_paths = tenant_middleware.kwargs["excluded_paths"]

        self.assertIn("/api/auth/login", excluded_paths)
        self.assertIn("/api/auth/register", excluded_paths)


if __name__ == "__main__":
    unittest.main()
