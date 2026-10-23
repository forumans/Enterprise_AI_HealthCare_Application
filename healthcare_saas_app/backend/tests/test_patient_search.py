import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend.app.api.routes.doctor import search_patients


class _FakeScalars:
    def all(self):
        return []


class _FakeResult:
    def scalars(self):
        return _FakeScalars()


class _FakeDbSession:
    async def execute(self, _stmt):
        return _FakeResult()


class PatientSearchTests(unittest.IsolatedAsyncioTestCase):
    async def test_search_never_writes_files(self):
        # Patient search used to append names/DOB/gender to a local debug file: a privacy leak,
        # and a crash on Lambda's read-only filesystem.
        identity = SimpleNamespace(user_id="doctor-user", tenant_id="tenant-1")
        with patch("builtins.open", side_effect=AssertionError("search_patients must not open files")):
            self.assertEqual(await search_patients(q="Jo", identity=identity, db=_FakeDbSession()), [])
            self.assertEqual(await search_patients(q="J", identity=identity, db=_FakeDbSession()), [])


if __name__ == "__main__":
    unittest.main()
