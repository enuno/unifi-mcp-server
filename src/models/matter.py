"""Matter and Thread inventory models (Network 11 private v2 API).

These models shape the responses of two Network 11 read routes:

* ``GET /proxy/network/v2/api/site/{site}/thread-networks``
* ``GET /proxy/network/v2/api/site/{site}/matter/nodes``

Both are **allowlists**: only the fields named here are surfaced, and the
controller's raw record is never passed through. Two exclusions are
deliberate and must not be relaxed:

* ``setupCode`` — a Matter node's pairing code. It is a live credential:
  anyone holding it can commission the device into another Matter fabric.
  The field is confirmed present in the Network 11.0.97 schema (the
  application carries a ``widenMatterNodeSetupCode`` migration), so its
  absence here is a decision, not an accident.
* ``fingerprint`` and the other Thread border-router internals
  (``host``, ``domainName``, ``stateBitmap``, ``sequenceNumber``,
  ``backboneRouterPort``) — border-router identification material with no
  operator-facing diagnostic value.

Field names are derived from the UniFi Network Application 11.0.97
distribution (see ``docs/research/matter-thread-network-11-discovery.md``);
they are not live-verified against a Network 11 controller. Every field is
optional so a controller that omits or renames one degrades to ``None``
instead of failing the whole read.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

#: Commissioning states a Matter node reports, from the Network 11.0.97
#: application bundle. Surfaced as a plain string so an unknown state from a
#: newer controller passes through instead of failing validation.
MATTER_NODE_STATES: tuple[str, ...] = (
    "QUEUED",
    "COMMISSIONING",
    "PROVISIONING",
    "COMMISSIONED",
    "FAILED",
    "UNVERIFIED",
    "REMOVED",
)

#: The ``type`` a Matter/Thread device carries in the active-client inventory.
MATTER_THREAD_CLIENT_TYPE = "MATTER_THREAD"


class ThreadBorderRouter(BaseModel):
    """One Thread border router advertising a network.

    Deliberately excludes ``fingerprint``, ``host``, ``domainName``,
    ``stateBitmap``, ``sequenceNumber`` and ``backboneRouterPort``.
    """

    model_config = ConfigDict(extra="ignore")

    name: str | None = Field(
        None, description="Border router name, when the controller reports one"
    )
    mac: str | None = Field(None, description="Border router MAC address")
    model: str | None = Field(None, description="Border router hardware model")
    vendor_name: str | None = Field(
        None, alias="vendorName", description="Border router vendor name"
    )
    thread_version: str | None = Field(
        None, alias="threadVersion", description="Thread protocol version this router runs"
    )
    routing_role: str | None = Field(
        None, alias="routingRole", description="Thread routing role (for example router or leader)"
    )
    online: bool | None = Field(
        None, description="Whether the controller currently sees the router"
    )


class ThreadNetwork(BaseModel):
    """A Thread network the site detects.

    A site sees its own Thread networks and may also detect a neighbouring
    one it does not control, so ``border_routers`` can be empty.
    """

    model_config = ConfigDict(extra="ignore")

    network_name: str | None = Field(None, alias="networkName", description="Thread network name")
    extended_pan_id: str | None = Field(
        None, alias="extendedPanId", description="Thread extended PAN ID"
    )
    channel: int | None = Field(None, description="Thread radio channel")
    controller: str | None = Field(
        None, description="Ecosystem controller for the network, when known"
    )
    thread_version: str | None = Field(
        None, alias="threadVersion", description="Highest Thread protocol version observed"
    )
    device_count: int | None = Field(
        None, alias="deviceCount", description="Devices the controller attributes to this network"
    )
    border_routers: list[ThreadBorderRouter] = Field(
        default_factory=list,
        alias="borderRouters",
        description="Border routers advertising this network",
    )
    fabric_count: int | None = Field(
        None, description="Number of Matter fabrics bound to this network"
    )

    @classmethod
    def from_api(cls, record: dict[str, Any]) -> ThreadNetwork:
        """Build a network from a controller record, allowlisting its fields.

        ``fabrics`` arrives as a list whose entries carry fabric identifiers;
        only its length is surfaced, because the identifiers are credentials
        of the owning ecosystem rather than operator diagnostics.
        """
        routers = [
            ThreadBorderRouter.model_validate(router)
            for router in record.get("borderRouters") or []
            if isinstance(router, dict)
        ]
        fabrics = record.get("fabrics")
        return cls.model_validate(
            {
                **{
                    key: record.get(key)
                    for key in (
                        "networkName",
                        "extendedPanId",
                        "channel",
                        "controller",
                        "threadVersion",
                        "deviceCount",
                    )
                },
                "borderRouters": routers,
                "fabric_count": len(fabrics) if isinstance(fabrics, list) else None,
            }
        )


class MatterNode(BaseModel):
    """A Matter node commissioned into (or pending on) the site.

    ``thread_client_id`` is the node's ``clientId``, renamed so a caller can
    join it to the active-client inventory without guessing which identifier
    to use. ``setup_code`` is never surfaced.
    """

    model_config = ConfigDict(extra="ignore")

    node_id: int | str | None = Field(
        None, alias="nodeId", description="Controller-assigned Matter node ID"
    )
    name: str | None = Field(None, description="Node name as shown in the UniFi UI")
    status: str | None = Field(
        None,
        description=(
            "Commissioning state, one of QUEUED, COMMISSIONING, PROVISIONING, "
            "COMMISSIONED, FAILED, UNVERIFIED or REMOVED"
        ),
    )
    online: bool | None = Field(None, description="Whether the node is currently reachable")
    device_type_name: str | None = Field(
        None, alias="deviceTypeName", description="Matter device type, as a readable name"
    )
    vendor_name: str | None = Field(None, alias="vendorName", description="Matter vendor name")
    product_name: str | None = Field(None, alias="productName", description="Matter product name")
    model: str | None = Field(None, description="Hardware model")
    software_version_string: str | None = Field(
        None, alias="softwareVersionString", description="Firmware version, as a readable string"
    )
    thread_client_id: str | None = Field(
        None,
        alias="clientId",
        description=(
            "The node's client inventory ID. Join it to a MATTER_THREAD record "
            "from the active-client inventory for the node's network identity."
        ),
    )
    last_online_at: int | str | None = Field(
        None, alias="lastOnlineAt", description="When the controller last saw the node online"
    )
    error_code: str | None = Field(
        None, alias="errorCode", description="Commissioning error code, when the node failed"
    )

    @classmethod
    def from_api(cls, record: dict[str, Any]) -> MatterNode:
        """Build a node from a controller record, allowlisting its fields.

        Only the allowlisted keys are read, so a ``setupCode`` (or any other
        unlisted field) present in the record cannot reach the result even if
        a future controller adds one under a different name.
        """
        allowed = (
            "nodeId",
            "name",
            "status",
            "online",
            "deviceTypeName",
            "vendorName",
            "productName",
            "model",
            "softwareVersionString",
            "clientId",
            "lastOnlineAt",
            "errorCode",
        )
        return cls.model_validate({key: record.get(key) for key in allowed})
