"""Regression checks for the portable fleet Compose deployment."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = shutil.which("docker")
BASE = ROOT / "docker-compose.fleet.yml"
SCALE = ROOT / "docker-compose.fleet-scale.yml"


def _config(*, scale: bool = False, **overrides: str) -> subprocess.CompletedProcess[str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if key
        not in {
            "POSTGRES_PASSWORD",
            "DATABASE_URL",
            "MIGRATION_DATABASE_URL",
            "REDIS_PASSWORD",
            "UNIFI_API_KEY",
            "MCP_AUTH_TOKEN",
            "UNIFI_FLEET_CREDENTIAL_KEY",
        }
    }
    env.update(
        {
            "POSTGRES_PASSWORD": "dbpassword",  # pragma: allowlist secret
            "UNIFI_API_KEY": "test-key",  # pragma: allowlist secret
            "MCP_AUTH_TOKEN": "test-token",  # pragma: allowlist secret
            "UNIFI_FLEET_CREDENTIAL_KEY": "test-encryption-key",  # pragma: allowlist secret
        }
    )
    env.update(overrides)
    command = ["docker", "compose", "-f", str(BASE)]
    if scale:
        command += ["-f", str(SCALE)]
    return subprocess.run(
        command + ["config", "--format", "json"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.skipif(COMPOSE is None, reason="Docker Compose is not installed")
class TestFleetCompose:
    def test_database_credentials_reach_every_consumer(self):
        import json

        result = _config()
        assert result.returncode == 0, result.stderr
        services = json.loads(result.stdout)["services"]
        url = (
            "postgresql://unifi_mcp:dbpassword@postgres:5432/unifi_mcp"  # pragma: allowlist secret
        )
        assert (
            services["postgres"]["environment"]["POSTGRES_PASSWORD"]
            == "dbpassword"  # pragma: allowlist secret
        )
        for name in ("migrate", "unifi-mcp", "worker"):
            assert services[name]["environment"]["DATABASE_URL"] == url
        assert services["migrate"]["environment"]["MIGRATION_DATABASE_URL"] == url
        assert "MIGRATION_DATABASE_URL" not in services["unifi-mcp"]["environment"]

    def test_migration_can_use_a_separate_owner(self):
        import json

        runtime = (
            "postgresql://runtime:runtime-pass@postgres:5432/unifi_mcp"  # pragma: allowlist secret
        )
        owner = "postgresql://owner:owner-pass@postgres:5432/unifi_mcp"  # pragma: allowlist secret
        result = _config(DATABASE_URL=runtime, MIGRATION_DATABASE_URL=owner)
        assert result.returncode == 0, result.stderr
        services = json.loads(result.stdout)["services"]
        assert services["migrate"]["environment"]["MIGRATION_DATABASE_URL"] == owner
        assert services["unifi-mcp"]["environment"]["DATABASE_URL"] == runtime
        assert services["worker"]["environment"]["DATABASE_URL"] == runtime

    def test_scale_requires_redis_password(self):
        result = _config(scale=True)
        assert result.returncode != 0
        assert "REDIS_PASSWORD" in result.stderr

    def test_scale_auth_and_persistence(self):
        import json

        result = _config(scale=True, REDIS_PASSWORD="redispassword")
        assert result.returncode == 0, result.stderr
        services = json.loads(result.stdout)["services"]
        redis = services["redis"]
        assert "--requirepass" in " ".join(redis["command"])
        assert "redispassword" in " ".join(redis["command"])
        assert "yes" in redis["command"]
        assert any(mount["target"] == "/data" for mount in redis["volumes"])
        assert redis["environment"]["REDISCLI_AUTH"] == "redispassword"
        assert redis["healthcheck"]["test"] == ["CMD-SHELL", "redis-cli ping | grep -qx PONG"]
        for name in ("unifi-mcp", "worker"):
            assert (
                services[name]["environment"]["REDIS_URL"] == "redis://:redispassword@redis:6379/0"
            )

    def test_encoded_redis_url_can_override_default(self):
        import json

        result = _config(
            scale=True,
            REDIS_PASSWORD="has@symbol",  # pragma: allowlist secret
            REDIS_URL="redis://:has%40symbol@redis:6379/0",
        )
        assert result.returncode == 0, result.stderr
        services = json.loads(result.stdout)["services"]
        assert services["redis"]["environment"]["REDISCLI_AUTH"] == "has@symbol"
        for name in ("unifi-mcp", "worker"):
            assert (
                services[name]["environment"]["REDIS_URL"] == "redis://:has%40symbol@redis:6379/0"
            )

    def test_missing_postgres_password_fails_closed(self):
        result = _config(POSTGRES_PASSWORD="")
        assert result.returncode != 0
        assert "POSTGRES_PASSWORD" in result.stderr
