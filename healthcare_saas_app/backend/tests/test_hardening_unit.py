"""Database-free checks for the security hardening pass: headers, log hygiene, docs, filenames."""

from __future__ import annotations

import asyncio
import dataclasses
import json
import logging
import unittest
from unittest.mock import patch

from backend.app import main as main_module
from backend.app.core.storage import safe_filename
from backend.app.main import _RedactAccessLog, app


async def _call(asgi_app, method: str, path: str, body: bytes = b"", headers: list[tuple[bytes, bytes]] | None = None):
    """Send one HTTP request straight to the ASGI app; return (status, headers dict, body bytes)."""

    sent = False
    messages: list[dict] = []

    async def receive():
        nonlocal sent
        if sent:
            return {"type": "http.disconnect"}
        sent = True
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        messages.append(message)

    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": method, "scheme": "http",
        "path": path, "raw_path": path.encode(), "query_string": b"", "root_path": "",
        "headers": [(b"host", b"testserver"), (b"content-type", b"application/json"), *(headers or [])],
        "client": ("203.0.113.7", 5000), "server": ("testserver", 80),
    }
    await asgi_app(scope, receive, send)
    start = next(m for m in messages if m["type"] == "http.response.start")
    response_headers = {k.decode().lower(): v.decode() for k, v in start["headers"]}
    return start["status"], response_headers, b"".join(m.get("body", b"") for m in messages if m["type"] == "http.response.body")


class SecurityHeaderTests(unittest.TestCase):
    def test_401_from_the_auth_middleware_carries_the_security_headers(self):
        status, headers, _ = asyncio.run(_call(app, "GET", "/api/appointments"))
        self.assertEqual(status, 401)
        self.assertEqual(headers.get("x-frame-options"), "DENY")
        self.assertEqual(headers.get("x-content-type-options"), "nosniff")
        self.assertEqual(headers.get("cache-control"), "no-store")
        self.assertIn("strict-transport-security", headers)


class ValidationLogTests(unittest.TestCase):
    def test_validation_errors_log_fields_but_never_submitted_values(self):
        body = json.dumps({"full_name": "Jane Secretname", "email": "jane.private@example.test", "password": "pw"}).encode()
        with self.assertLogs("healthcare.app", level="WARNING") as logs:
            status, _, response = asyncio.run(_call(app, "POST", "/api/auth/register", body))
        self.assertEqual(status, 422)
        output = "\n".join(logs.output)
        self.assertIn("password", output)  # the failing field is named...
        for secret in ("Jane Secretname", "jane.private@example.test", '"pw"'):
            self.assertNotIn(secret, output)  # ...but no submitted value appears
            self.assertNotIn(secret, response.decode())


class ApiDocsTests(unittest.TestCase):
    def test_interactive_docs_are_disabled_in_production(self):
        with patch.object(main_module, "settings", dataclasses.replace(main_module.settings, app_env="production")):
            production_app = main_module.create_app()
        self.assertIsNone(production_app.docs_url)
        self.assertIsNone(production_app.openapi_url)
        self.assertIsNone(production_app.redoc_url)


class AccessLogRedactionTests(unittest.TestCase):
    def test_query_strings_and_client_addresses_are_dropped(self):
        record = logging.LogRecord(
            "uvicorn.access", logging.INFO, __file__, 1, '%s - "%s %s HTTP/%s" %d',
            ("203.0.113.7:5000", "GET", "/api/support/patients?q=jane.private@example.test", "1.1", 200), None,
        )
        _RedactAccessLog().filter(record)
        message = record.getMessage()
        self.assertNotIn("jane.private", message)
        self.assertNotIn("203.0.113.7", message)
        self.assertIn("/api/support/patients", message)


class FilenameTests(unittest.TestCase):
    def test_safe_filename_strips_paths_and_unsafe_characters(self):
        self.assertEqual(safe_filename("../../etc/passwd"), "passwd")
        self.assertEqual(safe_filename("C:\\Users\\me\\scan 1.pdf"), "scan_1.pdf")
        self.assertEqual(safe_filename(".hidden"), "hidden")
        self.assertEqual(safe_filename(None), "document")
        self.assertEqual(safe_filename(""), "document")


if __name__ == "__main__":
    unittest.main()
