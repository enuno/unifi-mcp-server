"""Tests for gateway packet-capture tools."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import APIType
from src.tools.packet_capture import (
    download_gateway_packet_capture,
    get_gateway_packet_capture_status,
    start_gateway_packet_capture,
    stop_gateway_packet_capture,
)
from src.utils.exceptions import ValidationError


@pytest.fixture
def settings(tmp_path):
    value = MagicMock()
    value.api_type = APIType.LOCAL
    value.log_level = "INFO"
    value.packet_capture_download_dir = str(tmp_path)
    value.get_v2_api_path.side_effect = lambda site: f"/proxy/network/v2/api/site/{site}"
    return value


def _client(client_class, **responses):
    client = AsyncMock()
    client.authenticate = AsyncMock()
    for method, response in responses.items():
        setattr(client, method, AsyncMock(return_value=response))
    # download_bytes is awaited, so it needs an awaitable AsyncMock rather than
    # the plain return_value form used for the other methods.
    client.download_bytes = AsyncMock(return_value=responses.get("download_bytes", b""))
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client_class.return_value = client
    return client


async def test_start_gateway_packet_capture_uses_observed_payload(settings):
    with patch("src.tools.packet_capture.UniFiClient") as client_class:
        client = _client(client_class, post={"data": {"started": True}})
        result = await start_gateway_packet_capture(
            "default",
            "aa:bb:cc:dd:ee:ff",
            "network-1",
            settings,
            duration_seconds=60,
            confirm=True,
        )

    client.post.assert_awaited_once_with(
        "/proxy/network/v2/api/site/default/pcap-start",
        json_data={
            "mac": "aa:bb:cc:dd:ee:ff",
            "network_id": "network-1",
            "traffic_type": "WIRED",
            "duration": 60,
        },
    )
    assert result["site_id"] == "default"
    assert result["gateway_mac"] == "aa:bb:cc:dd:ee:ff"
    assert result["controller_response"] == {"data": {"started": True}}


async def test_start_gateway_packet_capture_requires_confirmation(settings):
    with patch("src.tools.packet_capture.UniFiClient") as client_class:
        with pytest.raises(ValidationError, match="requires confirmation"):
            await start_gateway_packet_capture(
                "default", "aa:bb:cc:dd:ee:ff", "network-1", settings
            )
    client_class.assert_not_called()


async def test_start_gateway_packet_capture_dry_run_makes_no_request(settings):
    with patch("src.tools.packet_capture.UniFiClient") as client_class:
        result = await start_gateway_packet_capture(
            "default",
            "aa:bb:cc:dd:ee:ff",
            "network-1",
            settings,
            duration_seconds=90,
            dry_run=True,
        )

    client_class.assert_not_called()
    assert result["dry_run"] is True
    assert result["payload"]["duration"] == 90


@pytest.mark.parametrize("duration", [29, 301])
async def test_start_gateway_packet_capture_bounds_duration(settings, duration):
    with pytest.raises(ValidationError, match="30 and 300"):
        await start_gateway_packet_capture(
            "default",
            "aa:bb:cc:dd:ee:ff",
            "network-1",
            settings,
            duration_seconds=duration,
            confirm=True,
        )


async def test_get_gateway_packet_capture_status_uses_observed_path(settings):
    with patch("src.tools.packet_capture.UniFiClient") as client_class:
        client = _client(client_class, get={"data": {"state": "RUNNING"}})
        result = await get_gateway_packet_capture_status("default", "aa:bb:cc:dd:ee:ff", settings)

    client.get.assert_awaited_once_with(
        "/proxy/network/v2/api/site/default/pcap-status/aa:bb:cc:dd:ee:ff"
    )
    assert result["controller_response"] == {"data": {"state": "RUNNING"}}


async def test_stop_gateway_packet_capture_uses_observed_path(settings):
    with patch("src.tools.packet_capture.UniFiClient") as client_class:
        client = _client(client_class, post={"data": {"stopped": True}})
        await stop_gateway_packet_capture("default", "aa:bb:cc:dd:ee:ff", settings, confirm=True)

    client.post.assert_awaited_once_with(
        "/proxy/network/v2/api/site/default/pcap-stop/aa:bb:cc:dd:ee:ff",
        json_data={},
    )


async def test_stop_gateway_packet_capture_dry_run(settings):
    with patch("src.tools.packet_capture.UniFiClient") as client_class:
        result = await stop_gateway_packet_capture(
            "default", "aa:bb:cc:dd:ee:ff", settings, dry_run=True
        )
    client_class.assert_not_called()
    assert result["dry_run"] is True


async def test_download_gateway_packet_capture_writes_private_file(settings, tmp_path):
    content = b"capture-bytes"
    with patch("src.tools.packet_capture.UniFiClient") as client_class:
        client = _client(client_class, download_bytes=content)
        result = await download_gateway_packet_capture(
            "default",
            "aa:bb:cc:dd:ee:ff",
            "../../capture.tar.gz",
            settings,
            confirm=True,
        )

    client.download_bytes.assert_awaited_once_with(
        "/proxy/network/v2/api/site/default/pcap-get/aa:bb:cc:dd:ee:ff", accept=None
    )
    destination = tmp_path / "capture.tar.gz"
    assert destination.read_bytes() == content
    assert destination.stat().st_mode & 0o777 == 0o600
    assert result["local_path"] == str(destination.resolve())
    assert result["size_bytes"] == len(content)
    assert len(result["sha256"]) == 64


async def test_download_gateway_packet_capture_supports_text_format(settings):
    with patch("src.tools.packet_capture.UniFiClient") as client_class:
        client = _client(client_class, download_bytes=b"summary")
        await download_gateway_packet_capture(
            "default",
            "aa:bb:cc:dd:ee:ff",
            "capture.txt",
            settings,
            text_format=True,
            confirm=True,
        )

    client.download_bytes.assert_awaited_once_with(
        "/proxy/network/v2/api/site/default/pcap-get/aa:bb:cc:dd:ee:ff/txt",
        accept="text/plain",
    )


async def test_download_gateway_packet_capture_dry_run_makes_no_request(settings):
    with patch("src.tools.packet_capture.UniFiClient") as client_class:
        result = await download_gateway_packet_capture(
            "default",
            "aa:bb:cc:dd:ee:ff",
            "capture.tar.gz",
            settings,
            dry_run=True,
        )
    client_class.assert_not_called()
    assert result["dry_run"] is True


@pytest.mark.parametrize("output_path", ["", ".", ".."])
async def test_download_gateway_packet_capture_rejects_empty_filename(settings, output_path):
    with pytest.raises(ValidationError, match="output_path"):
        await download_gateway_packet_capture(
            "default",
            "aa:bb:cc:dd:ee:ff",
            output_path,
            settings,
            confirm=True,
        )


def test_packet_capture_destination_stays_in_configured_directory(settings, tmp_path):
    from src.tools.packet_capture import _resolve_capture_destination

    assert (
        _resolve_capture_destination("/outside/name.tar.gz", settings)
        == Path(tmp_path / "name.tar.gz").resolve()
    )


async def test_packet_capture_rejects_cloud_mode(settings):
    """No Cloud Connector capture route is documented."""
    settings.api_type = APIType.CLOUD_V1
    with pytest.raises(ValidationError, match="direct local-console access"):
        await get_gateway_packet_capture_status("default", "aa:bb:cc:dd:ee:ff", settings)
    with pytest.raises(ValidationError, match="direct local-console access"):
        await start_gateway_packet_capture(
            "default", "aa:bb:cc:dd:ee:ff", "net-1", settings, confirm=True
        )


async def test_start_rejects_an_empty_network_id(settings):
    with pytest.raises(ValidationError, match="network_id"):
        await start_gateway_packet_capture(
            "default", "aa:bb:cc:dd:ee:ff", "   ", settings, confirm=True
        )


def test_capture_destination_refuses_a_symlink_planted_in_the_download_dir(settings, tmp_path):
    """A symlink AT the destination name must not redirect the write.

    Stripping the directory component is not enough on its own: an attacker
    who can create `<download_dir>/capture.tar.gz` as a symlink to somewhere
    else would otherwise have the capture written through it. Resolution moves
    the parent outside the confined dir, which the guard rejects.
    """
    from src.tools.packet_capture import _resolve_capture_destination

    base = tmp_path / "captures"
    base.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (base / "capture.tar.gz").symlink_to(outside / "capture.tar.gz")
    settings.packet_capture_download_dir = str(base)

    with pytest.raises(ValidationError, match="Refusing to write outside"):
        _resolve_capture_destination("capture.tar.gz", settings)


def test_capture_destination_allows_a_symlinked_download_dir(settings, tmp_path):
    """A download dir that is itself a symlink is fine once resolved."""
    from src.tools.packet_capture import _resolve_capture_destination

    real = tmp_path / "elsewhere"
    real.mkdir()
    (tmp_path / "link").symlink_to(real)
    settings.packet_capture_download_dir = str(tmp_path / "link")

    dest = _resolve_capture_destination("c.tar.gz", settings)
    assert dest.parent == real.resolve()


async def test_text_download_requests_text_plain(settings, tmp_path):
    """Regression: the /txt route is content-negotiated and needs Accept: text/plain.

    The console answers 406 Not Acceptable for the text rendering unless the
    request names the media type. Without this header the download fails.
    """
    with patch("src.tools.packet_capture.UniFiClient") as client_class:
        client = _client(client_class, download_bytes=b"===== BEGIN br3.pcap =====\n")
        await download_gateway_packet_capture(
            "default",
            "aa:bb:cc:dd:ee:ff",
            "capture.txt",
            settings,
            text_format=True,
            confirm=True,
        )

    client.download_bytes.assert_awaited_once_with(
        "/proxy/network/v2/api/site/default/pcap-get/aa:bb:cc:dd:ee:ff/txt",
        accept="text/plain",
    )


async def test_binary_download_sends_no_accept_header(settings, tmp_path):
    """The binary route is not content-negotiated and needs no Accept header."""
    with patch("src.tools.packet_capture.UniFiClient") as client_class:
        client = _client(client_class, download_bytes=b"\x1f\x8b\x08\x00binary")
        await download_gateway_packet_capture(
            "default",
            "aa:bb:cc:dd:ee:ff",
            "capture.pcap",
            settings,
            confirm=True,
        )

    client.download_bytes.assert_awaited_once_with(
        "/proxy/network/v2/api/site/default/pcap-get/aa:bb:cc:dd:ee:ff",
        accept=None,
    )
