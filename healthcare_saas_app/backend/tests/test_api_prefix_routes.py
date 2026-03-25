import unittest

from backend.app.main import app
from backend.app.middleware import TenantContextMiddleware


class ApiPrefixRouteRegistrationTests(unittest.TestCase):
    def test_api_prefixed_business_routes_are_registered(self):
        paths = {route.path for route in app.routes}

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
