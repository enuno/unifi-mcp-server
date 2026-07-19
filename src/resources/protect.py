"""Protect MCP resource implementation."""

from ..api import ProtectClient
from ..config import Settings
from ..models.protect_camera import ProtectCamera
from ..models.protect_nvr import ProtectNVR
from ..utils import get_logger


class ProtectResource:
    """MCP resource for UniFi Protect."""

    def __init__(self, settings: Settings) -> None:
        """Initialize the Protect resource."""
        self.settings = settings
        self.logger = get_logger(__name__, settings.log_level)

    async def list_nvrs(self) -> list[ProtectNVR]:
        """List all UniFi Protect NVRs."""
        async with ProtectClient(self.settings) as client:
            await client.authenticate()
            response = await client.get(self.settings.get_protect_integration_path("nvrs"))

        data = response.get("data", []) if isinstance(response, dict) else []
        return [ProtectNVR.model_validate(item) for item in data]

    async def get_nvr(self, nvr_id: str) -> ProtectNVR | None:
        """Get a single UniFi Protect NVR by ID."""
        async with ProtectClient(self.settings) as client:
            await client.authenticate()
            response = await client.get(self.settings.get_protect_integration_path(f"nvrs/{nvr_id}"))

        data = response.get("data", response) if isinstance(response, dict) else response
        return ProtectNVR.model_validate(data) if data else None

    async def list_cameras(self) -> list[ProtectCamera]:
        """List all UniFi Protect cameras."""
        async with ProtectClient(self.settings) as client:
            await client.authenticate()
            response = await client.get(self.settings.get_protect_integration_path("cameras"))

        data = response.get("data", []) if isinstance(response, dict) else []
        return [ProtectCamera.model_validate(item) for item in data]

    async def get_camera(self, camera_id: str) -> ProtectCamera | None:
        """Get a single UniFi Protect camera by ID."""
        async with ProtectClient(self.settings) as client:
            await client.authenticate()
            response = await client.get(self.settings.get_protect_integration_path(f"cameras/{camera_id}"))

        data = response.get("data", response) if isinstance(response, dict) else response
        return ProtectCamera.model_validate(data) if data else None
