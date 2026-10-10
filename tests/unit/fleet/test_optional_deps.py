"""The base install must not load the optional fleet dependencies.

Phase 0 of docs/FLEET_SCALING_PLAN.md: with no REDIS_URL / DATABASE_URL
configured, the server must start exactly as before, without importing the
packages the ``[fleet]`` extra provides.

The probe *blocks* those packages rather than checking whether they were
imported: a developer venv can carry them transitively (an installed
``pydocket`` makes FastMCP import ``redis``), but what matters is that the
server imports cleanly when they are absent. It runs in a fresh interpreter
because tests/unit/test_cache.py stubs ``redis`` in this process's
``sys.modules``.
"""

import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[3]
FLEET_MODULES = ("redis", "sqlalchemy", "asyncpg", "alembic")


def test_server_imports_without_fleet_dependencies(tmp_path: Path):
    probe = (
        "import sys\n"
        "class Block:\n"
        "    def find_spec(self, name, path=None, target=None):\n"
        f"        if name.split('.')[0] in {FLEET_MODULES!r}:\n"
        "            raise ModuleNotFoundError(name)\n"
        "sys.meta_path.insert(0, Block())\n"
        "import src.main, src.fleet, src.cache\n"
        "assert not src.cache.REDIS_AVAILABLE\n"
    )
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("UNIFI_", "REDIS_", "DATABASE_"))
    }
    env.update({"UNIFI_API_KEY": "test-key", "PYTHONPATH": str(PROJECT_ROOT)})

    result = subprocess.run(  # noqa: S603 - fixed interpreter and argv
        [sys.executable, "-c", probe],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert result.returncode == 0, result.stderr
