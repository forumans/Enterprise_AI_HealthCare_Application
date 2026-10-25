"""Compare the local database schema with a snapshot taken from AWS RDS.

    cd aws_env_spin_up\\scripts
    .\\run-migration.ps1 -SchemaSnapshot $env:TEMP\\schema_aws.json        # read-only, as the app user
    python compare_schema.py $env:TEMP\\schema_aws.json

Runs schema_snapshot.sql against the local database from healthcare_saas_app/backend/.env (as
the app user, read-only) and prints what differs: columns, enum values, indexes, constraints,
triggers, functions, extensions, schemas and the app user's table access. Exit code 1 if they differ.
"""

import asyncio
import json
import sys
from pathlib import Path

import asyncpg
from dotenv import dotenv_values

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
KEYS = ["columns", "enums", "indexes", "constraints", "triggers", "functions", "extensions", "schemas", "app_user_missing_access"]


async def local_snapshot() -> dict:
    url = dotenv_values(REPO / "healthcare_saas_app" / "backend" / ".env")["DATABASE_URL"]
    conn = await asyncpg.connect(url.replace("postgresql+asyncpg://", "postgresql://"), timeout=10)
    try:
        return json.loads(await conn.fetchval((HERE / "schema_snapshot.sql").read_text(encoding="utf-8")))
    finally:
        await conn.close()


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    aws = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    local = asyncio.run(local_snapshot())
    differs = False
    for key in KEYS:
        lo, aw = set(local.get(key) or []), set(aws.get(key) or [])
        print(f"{key:24} {'MATCH' if lo == aw else 'DIFFERS'} (local {len(lo)}, aws {len(aw)})")
        for item in sorted(lo - aw):
            print("    only local:", item)
        for item in sorted(aw - lo):
            print("    only aws:  ", item)
        differs |= lo != aw
    print("settings: local", local["settings"], "| aws", aws["settings"])
    return 1 if differs else 0


if __name__ == "__main__":
    sys.exit(main())
