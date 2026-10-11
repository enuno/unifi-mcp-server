"""The Ansible deployment (deploy/ansible) stays in step with the server.

The playbook writes the server's environment from a mapping of setting
names; these tests catch a name that is misspelt, a setting the compose
file passes that the playbook forgets, and a secret the playbook reads that
the vault template does not list.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from src.config import Settings

ROOT = Path(__file__).resolve().parents[2]
ANSIBLE = ROOT / "deploy" / "ansible"
INVENTORIES = ("single", "cluster")

#: Read with os.environ outside Settings (as in tests/unit/config/test_config.py).
OUTSIDE_SETTINGS = {
    "MIGRATION_DATABASE_URL",
    "UNIFI_AUDIT_CHAIN_KEY",
    "UNIFI_AUDIT_LOG_KEY",
    "UNIFI_FLEET_CREDENTIAL_KEY",
}


def _load(path: Path) -> object:
    return yaml.safe_load(path.read_text())


def _server_env_keys() -> set[str]:
    data = _load(ANSIBLE / "roles" / "unifi_mcp" / "vars" / "main.yml")
    assert isinstance(data, dict)
    return set(data["unifi_mcp_server_env_base"])


def _settings_aliases() -> set[str]:
    return {str(field.validation_alias) for field in Settings.model_fields.values()}


def _playbook_text() -> str:
    paths = [*ANSIBLE.glob("roles/**/*.yml"), *ANSIBLE.glob("roles/**/*.j2")]
    paths += [ANSIBLE / "site.yml", ANSIBLE / "vars" / "derived.yml"]
    return "\n".join(p.read_text() for p in paths)


class TestServerEnvironment:
    def test_every_name_is_a_server_setting(self):
        unknown = _server_env_keys() - _settings_aliases() - OUTSIDE_SETTINGS
        assert not unknown, f"not settings the server reads: {sorted(unknown)}"

    def test_covers_what_the_fleet_compose_file_passes(self):
        compose = _load(ROOT / "docker-compose.fleet.yml")
        assert isinstance(compose, dict)
        passed = set(compose["services"]["unifi-mcp"]["environment"])
        missing = passed - _server_env_keys()
        assert not missing, f"docker-compose.fleet.yml passes, the playbook does not: {missing}"

    def test_serves_streamable_http_with_a_token(self):
        data = _load(ANSIBLE / "roles" / "unifi_mcp" / "vars" / "main.yml")
        assert isinstance(data, dict)
        env = data["unifi_mcp_server_env_base"]
        assert env["MCP_SERVER_TRANSPORT"] == "streamable_http"
        assert "vault_mcp_auth_token" in env["MCP_AUTH_TOKEN"]


class TestVault:
    @pytest.mark.parametrize("inventory", INVENTORIES)
    def test_example_lists_every_secret_the_playbook_reads(self, inventory: str):
        example = _load(
            ANSIBLE / "inventories" / inventory / "group_vars" / "all" / "vault.yml.example"
        )
        assert isinstance(example, dict)
        read = set(re.findall(r"\bvault_[a-z_]+\b", _playbook_text()))
        # Optional SIEM secrets are documented in SECURITY.md, not required.
        optional = {"vault_siem_webhook_secret", "vault_siem_otlp_headers"}
        assert read - optional <= set(example)
        assert all(value == "" for value in example.values()), "the example holds no secrets"

    def test_real_vault_files_are_ignored(self):
        ignored = (ROOT / ".gitignore").read_text()
        assert "deploy/ansible/inventories/*/group_vars/all/vault.yml" in ignored


class TestInventories:
    @pytest.mark.parametrize("inventory", INVENTORIES)
    def test_has_mcp_hosts(self, inventory: str):
        data = _load(ANSIBLE / "inventories" / inventory / "hosts.yml")
        assert isinstance(data, dict)
        groups = data["all"]["children"]
        assert groups["mcp"]["hosts"]

    def test_cluster_hosts_have_private_addresses(self):
        data = _load(ANSIBLE / "inventories" / "cluster" / "hosts.yml")
        assert isinstance(data, dict)
        for group in data["all"]["children"].values():
            for name, host in group["hosts"].items():
                if host:  # a host defined in an earlier group
                    assert "private_address" in host, name


class TestRuntimeRole:
    def test_grants_match_security_md(self):
        template = (
            ANSIBLE / "roles" / "unifi_mcp" / "templates" / "runtime-role.sql.j2"
        ).read_text()
        security = (ROOT / "SECURITY.md").read_text()

        def grants(text: str) -> set[str]:
            joined = re.sub(r"\s*\n\s*", " ", text)
            return {
                g.replace("{{ postgres_db | default('unifi_mcp') }}", "unifi_mcp")
                for g in re.findall(r"GRANT [^;]+;", joined)
            }

        playbook = grants(template)
        documented = {g for g in grants(security) if "unifi_mcp_runtime" in g}
        assert documented <= playbook
        assert playbook - documented == {
            "GRANT CONNECT ON DATABASE unifi_mcp TO unifi_mcp_runtime;",
            "GRANT USAGE ON SCHEMA public TO unifi_mcp_runtime;",
        }

    def test_password_is_never_in_the_template(self):
        template = (
            ANSIBLE / "roles" / "unifi_mcp" / "templates" / "runtime-role.sql.j2"
        ).read_text()
        assert "vault_" not in template
        assert "\\getenv runtime_password RUNTIME_PASSWORD" in template


@pytest.mark.skipif(
    shutil.which("ansible-playbook") is None, reason="ansible-playbook not installed"
)
@pytest.mark.parametrize("inventory", INVENTORIES)
def test_playbook_syntax(inventory: str):
    result = subprocess.run(
        [
            "ansible-playbook",
            "-i",
            f"inventories/{inventory}/hosts.yml",
            "site.yml",
            "--syntax-check",
        ],
        cwd=ANSIBLE,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


HELM = ROOT / "deploy" / "helm" / "unifi-mcp"
HELM_BINARY = shutil.which("helm")


def _chart_env_keys() -> set[str]:
    helpers = (HELM / "templates" / "_helpers.tpl").read_text()
    block = helpers.split('define "unifi-mcp.env"', 1)[1].split("{{- end -}}", 1)[0]
    return set(re.findall(r'"([A-Z][A-Z0-9_]+)"', block))


class TestHelmChart:
    def test_every_name_is_a_server_setting(self):
        keys = _chart_env_keys()
        assert "MCP_SERVER_TRANSPORT" in keys
        unknown = keys - _settings_aliases() - OUTSIDE_SETTINGS
        assert not unknown, f"not settings the server reads: {sorted(unknown)}"

    def test_sets_what_the_playbook_sets(self):
        # Secrets come from the chart's Secret, not its env block.
        secret = {
            "UNIFI_API_KEY",
            "MCP_AUTH_TOKEN",
            "UNIFI_AUDIT_CHAIN_KEY",
            "UNIFI_AUDIT_LOG_KEY",
            "UNIFI_AUDIT_SIEM_WEBHOOK_SECRET",
            "UNIFI_AUDIT_SIEM_OTLP_HEADERS",
            "DATABASE_URL",
            "UNIFI_FLEET_CREDENTIAL_KEY",
            "REDIS_URL",
        }
        # Left at the server's defaults by the chart.
        defaults = {"UNIFI_AUDIT_SIEM_BUFFER_MAX_MB", "UNIFI_AUDIT_SIEM_ANCHOR_SECONDS"}
        missing = _server_env_keys() - secret - defaults - _chart_env_keys()
        assert not missing, f"the playbook sets, the chart does not: {sorted(missing)}"

    def test_refuses_every_secret_in_extra_env(self):
        helpers = (HELM / "templates" / "_helpers.tpl").read_text()
        refused = set(re.search(r"if has \$name \(list ([^)]*)\)", helpers).group(1).split())
        refused = {name.strip('"') for name in refused}
        expected = {"MIGRATION_DATABASE_URL"} | {
            "UNIFI_API_KEY",
            "MCP_AUTH_TOKEN",
            "UNIFI_AUDIT_CHAIN_KEY",
            "UNIFI_AUDIT_LOG_KEY",
            "UNIFI_FLEET_CREDENTIAL_KEY",
            "DATABASE_URL",
            "REDIS_URL",
            "UNIFI_AUDIT_SIEM_WEBHOOK_SECRET",
            "UNIFI_AUDIT_SIEM_OTLP_HEADERS",
        }
        assert refused == expected

    def test_chart_version_tracks_the_package(self):
        chart = _load(HELM / "Chart.yaml")
        assert isinstance(chart, dict)
        pyproject = (ROOT / "pyproject.toml").read_text()
        version = re.search(r'^version = "([^"]+)"', pyproject, re.M).group(1)
        assert chart["appVersion"] == version


@pytest.mark.skipif(HELM_BINARY is None, reason="helm not installed")
class TestHelmRender:
    def _template(self, *args: str) -> subprocess.CompletedProcess[str]:
        assert HELM_BINARY is not None
        return subprocess.run(
            [HELM_BINARY, "template", "t", str(HELM), *args],
            capture_output=True,
            text=True,
            check=False,
        )

    @pytest.mark.parametrize("values", sorted((HELM / "ci").glob("*.yaml")), ids=lambda p: p.name)
    def test_ci_values_render(self, values: Path):
        result = self._template("-f", str(values))
        assert result.returncode == 0, result.stderr
        docs = [d for d in yaml.safe_load_all(result.stdout) if d]
        for doc in docs:
            if doc["kind"] in ("Deployment", "Job", "CronJob"):
                spec = (
                    doc["spec"]["template"]["spec"]
                    if doc["kind"] != "CronJob"
                    else (doc["spec"]["jobTemplate"]["spec"]["template"]["spec"])
                )
                assert spec["automountServiceAccountToken"] is False
                for container in spec["containers"]:
                    assert container["securityContext"]["readOnlyRootFilesystem"] is True
                    names = {e["name"] for e in container.get("env", [])}
                    assert not names & {"UNIFI_API_KEY", "MCP_AUTH_TOKEN", "DATABASE_URL"}

    def test_needs_an_existing_secret(self):
        result = self._template("--set", "controller.localHost=192.0.2.1")
        assert result.returncode != 0
        assert "existingSecret is required" in result.stderr

    def test_refuses_a_secret_in_extra_env(self):
        result = self._template(
            "--set",
            "existingSecret=s",
            "--set",
            "controller.localHost=192.0.2.1",
            "--set",
            "server.extraEnv.MCP_AUTH_TOKEN=leak",
        )
        assert result.returncode != 0
        assert "leak" not in result.stdout
