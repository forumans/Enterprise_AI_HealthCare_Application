import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from backend.app.api.routes.auth import ForgotPasswordRequest, LoginRequest, forgot_password, login
from backend.app.core import rate_limit
from backend.app.core.cross_tenant import AccountRef


class _FakeExecuteResult:
    def __init__(self, user):
        self._user = user

    def scalar_one_or_none(self):
        return self._user


class _FakeDbSession:
    def __init__(self, user):
        self._user = user

    async def execute(self, _stmt, *_args, **_kwargs):
        return _FakeExecuteResult(self._user)


def _lookup(account):
    """Patch the cross-tenant login lookup (a SECURITY DEFINER function in the real database)."""
    return patch("backend.app.api.routes.auth.cross_tenant.login_lookup", new=AsyncMock(return_value=account))


def _http(ip: str = "203.0.113.7"):
    """Minimal stand-in for the Starlette request (only headers and client are read)."""
    return SimpleNamespace(headers={}, client=SimpleNamespace(host=ip))


class AuthLoginTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        rate_limit.reset_all()

    async def test_login_raises_401_when_user_missing(self):
        request = LoginRequest(email="missing@example.com", password="secret", remember_me=False)
        db = _FakeDbSession(user=None)

        with _lookup(None), self.assertRaises(HTTPException) as ctx:
            await login(request=request, http_request=_http(), db=db)

        self.assertEqual(ctx.exception.status_code, 401)

    async def test_login_returns_token_payload_for_valid_credentials(self):
        request = LoginRequest(email="admin@example.com", password="Admin123!", remember_me=False)
        user = AccountRef(id="user-1", tenant_id="tenant-1", role="ADMIN", password_hash="hashed-password")
        db = _FakeDbSession(user=None)

        with _lookup(user), patch("backend.app.api.routes.auth.verify_password", return_value=True), patch(
            "backend.app.api.routes.auth.create_access_token", return_value="token-123"
        ):
            payload = await login(request=request, http_request=_http(), db=db)

        self.assertEqual(payload["access_token"], "token-123")
        self.assertEqual(payload["role"], "ADMIN")
        self.assertEqual(payload["tenant_id"], "tenant-1")
        self.assertIsNone(payload["user_name"])

    async def test_login_returns_the_profile_name_for_every_role(self):
        # GAP-14: not only patients; the admin dashboard shows the signed-in admin's name
        request = LoginRequest(email="admin@example.com", password="Admin123!", remember_me=False)
        user = AccountRef(id="user-1", tenant_id="tenant-1", role="ADMIN", password_hash="hashed-password")
        db = _FakeDbSession(user="Ada Admin")  # every query in this fake returns this value

        with _lookup(user), patch("backend.app.api.routes.auth.verify_password", return_value=True), patch(
            "backend.app.api.routes.auth.create_access_token", return_value="token-123"
        ):
            payload = await login(request=request, http_request=_http(), db=db)

        self.assertEqual(payload["user_name"], "Ada Admin")
        self.assertIsNone(payload["insurance_provider"])


class LoginRateLimitTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        rate_limit.reset_all()

    async def _fail(self, email: str, ip: str = "203.0.113.7") -> int:
        with _lookup(None), self.assertRaises(HTTPException) as ctx:
            await login(request=LoginRequest(email=email, password="wrong-password"), http_request=_http(ip), db=_FakeDbSession(user=None))
        return ctx.exception.status_code

    async def test_ten_failed_logins_lock_the_email_with_429(self):
        for _ in range(10):
            self.assertEqual(await self._fail("victim@example.com"), 401)
        self.assertEqual(await self._fail("victim@example.com"), 429)
        # From another address too: the limit is per email, not just per IP
        self.assertEqual(await self._fail("victim@example.com", ip="198.51.100.9"), 429)
        # Other accounts are unaffected
        self.assertEqual(await self._fail("someone-else@example.com", ip="198.51.100.9"), 401)

    async def test_a_successful_login_clears_the_failure_count(self):
        for _ in range(9):
            await self._fail("user@example.com")
        user = AccountRef(id="u1", tenant_id="t1", role="DOCTOR", password_hash="h")
        with _lookup(user), patch("backend.app.api.routes.auth.verify_password", return_value=True), patch(
            "backend.app.api.routes.auth.create_access_token", return_value="tok"
        ):
            await login(request=LoginRequest(email="user@example.com", password="Right-password"), http_request=_http(), db=_FakeDbSession(user=user))
        for _ in range(9):
            self.assertEqual(await self._fail("user@example.com"), 401)

    async def test_reset_emails_are_limited_per_address(self):
        with _lookup(None), patch("backend.app.api.routes.auth.send_email", new=AsyncMock(return_value=True)):
            for _ in range(5):
                await forgot_password(request=ForgotPasswordRequest(email="x@example.com"), http_request=_http(), db=_FakeDbSession(user=None))
            with self.assertRaises(HTTPException) as ctx:
                await forgot_password(request=ForgotPasswordRequest(email="X@example.com"), http_request=_http(), db=_FakeDbSession(user=None))
        self.assertEqual(ctx.exception.status_code, 429)
        self.assertIn("Retry-After", ctx.exception.headers)


if __name__ == "__main__":
    unittest.main()
