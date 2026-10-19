"""Regression test for issue #161.

``docker-compose.yml`` forwards host environment variables into the
container by name. If a forwarded name doesn't match a real
``validation_alias`` on ``Settings``, pydantic's ``extra="ignore"`` drops
the value silently — no warning, no error, and the field falls back to
its default. That happened for six variables at once (SSL verification,
port, site, rate limit, timeout, cloud host), and would have been caught
immediately by asserting the forwarded names against the model.
"""

import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
import yaml

from src.config.config import Settings

# Forwarded by docker-compose.yml but intentionally not a Settings field:
# read via os.getenv() elsewhere (UNIFI_PROFILE, in src/main.py), or
# documented for a not-yet-implemented feature (the rest). Not a target
# for this test, which only guards against *typos* in forwarded names
# that were meant to reach Settings.
KNOWN_NON_SETTINGS_PASSTHROUGHS = {
    "UNIFI_PROFILE",
    "UNIFI_METRICS_ENABLED",
    "UNIFI_WEBHOOK_REDIS_URL",
    "UNIFI_CONTROLLERS",
}


def _settings_aliases() -> set[str]:
    return {
        field.validation_alias
        for field in Settings.model_fields.values()
        if isinstance(field.validation_alias, str)
    }


ROOT = Path(__file__).parents[3]


def _compose() -> dict:
    return yaml.safe_load((ROOT / "docker-compose.yml").read_text())


def _compose_env_names() -> set[str]:
    return set(_compose()["services"]["unifi-mcp"]["environment"].keys())


def test_docker_compose_forwards_names_settings_actually_reads():
    aliases = _settings_aliases()
    forwarded = _compose_env_names()

    unifi_vars = {
        name for name in forwarded if name.startswith(("UNIFI_", "DRY_RUN", "REDIS_", "WEBHOOK_"))
    }
    unrecognized = unifi_vars - aliases - KNOWN_NON_SETTINGS_PASSTHROUGHS

    assert not unrecognized, (
        f"docker-compose.yml forwards {unrecognized} but no Settings field "
        "reads them under that name (validation_alias mismatch) or they "
        "aren't in KNOWN_NON_SETTINGS_PASSTHROUGHS - see issue #161"
    )


@pytest.mark.parametrize(
    ("name", "default"), [("UNIFI_READ_ONLY", "true"), ("UNIFI_DRY_RUN", "false")]
)
def test_docker_compose_forwards_safety_switches(name, default):
    """The stock compose file can run read-only or preview-only.

    With an explicit ``environment:`` block and no ``env_file``, a variable
    the block does not name never reaches the container, so setting it in
    ``.env`` did nothing.
    """
    env = _compose()["services"]["unifi-mcp"]["environment"]
    assert env.get(name) == f"${{{name}:-{default}}}"
    assert name in _settings_aliases()


def _healthcheck_script() -> str:
    test = _compose()["services"]["unifi-mcp"]["healthcheck"]["test"]
    assert test[:3] == ["CMD", "python", "-c"]
    return test[3]


def _run_healthcheck(monkeypatch: pytest.MonkeyPatch, **env: str) -> int:
    monkeypatch.setenv("UNIFI_API_KEY", "test-key")
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    result = subprocess.run(
        [sys.executable, "-c", _healthcheck_script()],
        cwd=ROOT,
        capture_output=True,
        timeout=60,
    )
    return result.returncode


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - http.server API
        self.send_response(200 if self.path == "/healthz" else 404)
        self.end_headers()

    def log_message(self, *args) -> None:
        pass


@pytest.fixture
def liveness_port():
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server.server_address[1]
    server.shutdown()
    server.server_close()


def test_healthcheck_passes_over_stdio_without_http(monkeypatch):
    """stdio serves no HTTP, so the check must not depend on a listener."""
    assert _run_healthcheck(monkeypatch, MCP_SERVER_TRANSPORT="stdio") == 0


@pytest.mark.parametrize("host", ["127.0.0.1", "0.0.0.0"])
def test_healthcheck_probes_healthz_over_network_transport(monkeypatch, liveness_port, host):
    code = _run_healthcheck(
        monkeypatch,
        MCP_SERVER_TRANSPORT="streamable_http",
        MCP_SERVER_HOST=host,
        MCP_SERVER_PORT=str(liveness_port),
    )
    assert code == 0


def test_healthcheck_fails_when_nothing_listens(monkeypatch, liveness_port):
    unused = liveness_port + 1 if liveness_port < 65535 else liveness_port - 1
    code = _run_healthcheck(
        monkeypatch,
        MCP_SERVER_TRANSPORT="http",
        MCP_SERVER_HOST="127.0.0.1",
        MCP_SERVER_PORT=str(unused),
    )
    assert code != 0


def test_healthcheck_targets_the_real_route():
    """The route is /healthz (src/main.py); /health is a 404."""
    script = _healthcheck_script()
    assert "/healthz" in script
    assert "/health'" not in script and '/health"' not in script


def test_toolbox_telemetry_is_opt_in():
    """No OTLP endpoint unless the operator names one.

    The server's own agnost tracking is off by default (``AGNOST_ENABLED``);
    the toolbox container used to export to api.agnost.ai unconditionally.
    """
    command = _compose()["services"]["mcp-toolbox"]["command"]
    otlp = [arg for arg in command if "telemetry-otlp" in arg]
    assert otlp == ["--telemetry-otlp=${TOOLBOX_TELEMETRY_OTLP:-}"]
    assert not any("agnost" in arg for arg in command)


def _env_file_values(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            name, _, value = line.partition("=")
            values[name.strip()] = value.strip()
    return values


def test_docker_compose_defaults_to_read_only_viewer():
    """The stock deployment is read-only with a viewer stdio caller.

    The server's own defaults are read-write with a fleet-admin stdio
    caller; compose lowers both unless the operator escalates in ``.env``.
    """
    env = _compose()["services"]["unifi-mcp"]["environment"]
    assert env["UNIFI_READ_ONLY"] == "${UNIFI_READ_ONLY:-true}"
    assert env["UNIFI_STDIO_ROLE"] == "${UNIFI_STDIO_ROLE:-viewer}"
    assert {"UNIFI_READ_ONLY", "UNIFI_STDIO_ROLE"} <= _settings_aliases()


def test_docker_env_example_ships_safe_defaults(monkeypatch):
    example = _env_file_values(ROOT / ".env.docker.example")
    assert example["UNIFI_READ_ONLY"] == "true"
    assert example["UNIFI_STDIO_ROLE"] == "viewer"

    monkeypatch.setenv("UNIFI_API_KEY", "test-key")
    monkeypatch.setenv("UNIFI_READ_ONLY", example["UNIFI_READ_ONLY"])
    monkeypatch.setenv("UNIFI_STDIO_ROLE", example["UNIFI_STDIO_ROLE"])
    settings = Settings(_env_file=None)
    assert settings.read_only is True
    assert settings.stdio_role == "viewer"
