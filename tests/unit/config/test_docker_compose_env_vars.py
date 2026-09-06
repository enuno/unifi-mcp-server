"""Regression test for issue #161.

``docker-compose.yml`` forwards host environment variables into the
container by name. If a forwarded name doesn't match a real
``validation_alias`` on ``Settings``, pydantic's ``extra="ignore"`` drops
the value silently — no warning, no error, and the field falls back to
its default. That happened for six variables at once (SSL verification,
port, site, rate limit, timeout, cloud host), and would have been caught
immediately by asserting the forwarded names against the model.
"""

from pathlib import Path

import yaml

from src.config.config import Settings

# Forwarded by docker-compose.yml but intentionally not a Settings field:
# read via os.getenv() elsewhere (UNIFI_PROFILE, in src/main.py), or
# documented for a not-yet-implemented feature (the rest). Not a target
# for this test, which only guards against *typos* in forwarded names
# that were meant to reach Settings.
KNOWN_NON_SETTINGS_PASSTHROUGHS = {
    "UNIFI_PROFILE",
    "DRY_RUN",
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


def _compose_env_names() -> set[str]:
    compose_path = Path(__file__).parents[3] / "docker-compose.yml"
    compose = yaml.safe_load(compose_path.read_text())
    env = compose["services"]["unifi-mcp"]["environment"]
    return set(env.keys())


def test_docker_compose_forwards_names_settings_actually_reads():
    aliases = _settings_aliases()
    forwarded = _compose_env_names()

    unifi_vars = {name for name in forwarded if name.startswith(("UNIFI_", "DRY_RUN"))}
    unrecognized = unifi_vars - aliases - KNOWN_NON_SETTINGS_PASSTHROUGHS

    assert not unrecognized, (
        f"docker-compose.yml forwards {unrecognized} but no Settings field "
        "reads them under that name (validation_alias mismatch) or they "
        "aren't in KNOWN_NON_SETTINGS_PASSTHROUGHS - see issue #161"
    )
