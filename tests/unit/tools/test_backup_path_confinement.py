"""Tests for download_backup path confinement and backup_filename validation.

Covers the two halves of the fix:

* ``validate_backup_filename`` rejects path separators and ``..`` so a crafted
  filename cannot retarget the authenticated controller GET (and the URL is
  percent-encoded before use), and
* ``download_backup`` writes only inside ``UNIFI_BACKUP_DOWNLOAD_DIR`` using the
  filename component of ``output_path``, refusing to follow a symlink.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

import src.tools.backups as backups_module
from src.api.client import UniFiClient
from src.config import Settings
from src.tools.backups import download_backup
from src.utils.exceptions import ValidationError
from src.utils.validators import validate_backup_filename

# --------------------------------------------------------------------------- #
# validate_backup_filename
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("name", ["backup_2025-01-29.unf", "a.unf", "AutoBackup_1.0.unifi"])
def test_validate_backup_filename_accepts_plain_names(name) -> None:
    assert validate_backup_filename(name) == name


@pytest.mark.parametrize(
    "name",
    [
        "../../etc/passwd",
        "../secret.unf",
        "sub/dir.unf",
        "back\\slash.unf",
        "..",
        ".",
        "",
        "with space.unf",
        "semi;colon.unf",
        "query?x=1.unf",
    ],
)
def test_validate_backup_filename_rejects_bad_names(name) -> None:
    with pytest.raises(ValidationError):
        validate_backup_filename(name)


# --------------------------------------------------------------------------- #
# Client: traversal rejected before any HTTP call; valid names are encoded
# --------------------------------------------------------------------------- #


def _local_settings(monkeypatch) -> Settings:
    for key in ("UNIFI_API_KEY", "UNIFI_API_TYPE", "UNIFI_LOCAL_HOST"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("UNIFI_API_KEY", "test-key")
    monkeypatch.setenv("UNIFI_API_TYPE", "local")
    monkeypatch.setenv("UNIFI_LOCAL_HOST", "10.0.0.1")
    return Settings()


@pytest.mark.asyncio
async def test_client_download_backup_rejects_traversal(monkeypatch) -> None:
    settings = _local_settings(monkeypatch)
    client = UniFiClient(settings)
    requested: list[str] = []

    async def _record(url):  # pragma: no cover - must not be reached
        requested.append(str(url))
        raise AssertionError("HTTP request must not be issued for a bad filename")

    client.client = MagicMock()
    client.client.get = _record
    with patch.object(client, "resolve_site_id", AsyncMock(return_value="default")):
        with pytest.raises(ValidationError):
            await client.download_backup(site_id="default", backup_filename="../../api/s/default")

    assert requested == []


@pytest.mark.asyncio
async def test_client_download_backup_encodes_filename(monkeypatch) -> None:
    settings = _local_settings(monkeypatch)
    client = UniFiClient(settings)
    seen: dict[str, str] = {}

    def _handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, content=b"backup-bytes")

    client.client = httpx.AsyncClient(transport=httpx.MockTransport(_handler))
    try:
        with patch.object(client, "resolve_site_id", AsyncMock(return_value="default")):
            content = await client.download_backup(
                site_id="default", backup_filename="backup_2025-01-29.unf"
            )
    finally:
        await client.client.aclose()

    assert content == b"backup-bytes"
    assert seen["url"].endswith("/proxy/network/data/backup/backup_2025-01-29.unf")


# --------------------------------------------------------------------------- #
# Tool: writes confined to UNIFI_BACKUP_DOWNLOAD_DIR
# --------------------------------------------------------------------------- #


def _tool_settings(base_dir) -> MagicMock:
    settings = MagicMock()
    settings.log_level = "INFO"
    settings.backup_download_dir = str(base_dir)
    return settings


def _mock_backup_client(content: bytes = b"backup-bytes") -> MagicMock:
    client = MagicMock()
    client.authenticate = AsyncMock()
    client.download_backup = AsyncMock(return_value=content)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    return client


@pytest.mark.asyncio
async def test_download_backup_strips_traversal_and_confines(tmp_path) -> None:
    settings = _tool_settings(tmp_path)
    client = _mock_backup_client()
    with patch.object(backups_module, "UniFiClient", return_value=client):
        with patch.object(backups_module, "log_audit"):
            result = await download_backup(
                site_id="default",
                backup_filename="b.unf",
                output_path="../../../../etc/evil.unf",
                settings=settings,
            )

    written = tmp_path / "evil.unf"
    assert written.exists()
    assert written.read_bytes() == b"backup-bytes"
    assert result["local_path"] == str(written)
    # Nothing escaped the confinement directory.
    assert not (tmp_path.parent / "evil.unf").exists()


@pytest.mark.asyncio
async def test_download_backup_absolute_path_confined(tmp_path) -> None:
    settings = _tool_settings(tmp_path)
    client = _mock_backup_client()
    with patch.object(backups_module, "UniFiClient", return_value=client):
        with patch.object(backups_module, "log_audit"):
            result = await download_backup(
                site_id="default",
                backup_filename="b.unf",
                output_path="/etc/cron.d/pwn",
                settings=settings,
            )

    assert result["local_path"] == str(tmp_path / "pwn")
    assert (tmp_path / "pwn").exists()


@pytest.mark.asyncio
async def test_download_backup_private_permissions(tmp_path) -> None:
    settings = _tool_settings(tmp_path)
    client = _mock_backup_client()
    with patch.object(backups_module, "UniFiClient", return_value=client):
        with patch.object(backups_module, "log_audit"):
            await download_backup(
                site_id="default",
                backup_filename="b.unf",
                output_path="backup.unf",
                settings=settings,
            )
    mode = (tmp_path / "backup.unf").stat().st_mode & 0o777
    assert mode == 0o600


@pytest.mark.asyncio
async def test_download_backup_does_not_follow_symlink(tmp_path) -> None:
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"original")
    base = tmp_path / "downloads"
    base.mkdir()
    (base / "link.unf").symlink_to(outside)

    settings = _tool_settings(base)
    client = _mock_backup_client(b"attacker-influenced")
    with patch.object(backups_module, "UniFiClient", return_value=client):
        with patch.object(backups_module, "log_audit"):
            # A symlink at the destination resolves outside the confinement
            # directory (caught as ValidationError) or, on a TOCTOU race, is
            # refused by O_NOFOLLOW (OSError). Either way the write is blocked.
            with pytest.raises((ValidationError, OSError)):
                await download_backup(
                    site_id="default",
                    backup_filename="b.unf",
                    output_path="link.unf",
                    settings=settings,
                )

    # The symlink target outside the confinement directory is untouched.
    assert outside.read_bytes() == b"original"


@pytest.mark.asyncio
async def test_download_backup_rejects_empty_filename(tmp_path) -> None:
    settings = _tool_settings(tmp_path)
    client = _mock_backup_client()
    with patch.object(backups_module, "UniFiClient", return_value=client):
        with patch.object(backups_module, "log_audit"):
            with pytest.raises(ValidationError):
                await download_backup(
                    site_id="default",
                    backup_filename="b.unf",
                    output_path="/",
                    settings=settings,
                )
