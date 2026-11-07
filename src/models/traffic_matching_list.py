"""Traffic Matching List data models.

The Integration API models each entry of a list as an object carrying a
``type`` discriminator and the value fields for that type — not as a bare
string (issue #282). The shapes come from the Integration API v11.0.97
spec:

===========================  ==========================================
List type                    Item types (``type`` discriminator)
===========================  ==========================================
``PORTS``                    ``PORT_NUMBER``, ``PORT_NUMBER_RANGE``
``IPV4_ADDRESSES``           ``IP_ADDRESS``, ``IP_ADDRESS_RANGE``,
                             ``SUBNET``
``IPV6_ADDRESSES``           ``IP_ADDRESS``, ``SUBNET``
===========================  ==========================================

``PORT_NUMBER`` and ``IP_ADDRESS``/``SUBNET`` carry a single ``value``
(an integer port or a string address/CIDR); the ``*_RANGE`` types carry
``start`` and ``stop`` instead. The API rejects an entry without its
``type`` ("Missing $.items[0].type value"), so create maps plain strings
onto the right object shape for the list's type.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TrafficMatchingListType(str, Enum):
    """Traffic matching list types."""

    PORTS = "PORTS"
    IPV4_ADDRESSES = "IPV4_ADDRESSES"
    IPV6_ADDRESSES = "IPV6_ADDRESSES"


class TrafficMatchingItemType(str, Enum):
    """Item types a traffic matching list entry can carry."""

    PORT_NUMBER = "PORT_NUMBER"
    PORT_NUMBER_RANGE = "PORT_NUMBER_RANGE"
    IP_ADDRESS = "IP_ADDRESS"
    IP_ADDRESS_RANGE = "IP_ADDRESS_RANGE"
    SUBNET = "SUBNET"


# Which item types are valid for which list type.
LIST_TYPE_ITEM_TYPES: dict[str, set[str]] = {
    TrafficMatchingListType.PORTS.value: {
        TrafficMatchingItemType.PORT_NUMBER.value,
        TrafficMatchingItemType.PORT_NUMBER_RANGE.value,
    },
    TrafficMatchingListType.IPV4_ADDRESSES.value: {
        TrafficMatchingItemType.IP_ADDRESS.value,
        TrafficMatchingItemType.IP_ADDRESS_RANGE.value,
        TrafficMatchingItemType.SUBNET.value,
    },
    TrafficMatchingListType.IPV6_ADDRESSES.value: {
        TrafficMatchingItemType.IP_ADDRESS.value,
        TrafficMatchingItemType.SUBNET.value,
    },
}


class TrafficMatchingListItem(BaseModel):
    """One entry of a traffic matching list.

    ``type`` selects which value fields are populated: the single-value
    types use ``value``, the range types use ``start`` and ``stop``.
    """

    # Extra fields are ignored, as in the sibling list model: an item the
    # controller adds a field to must still be readable.
    model_config = ConfigDict(populate_by_name=True)

    type: TrafficMatchingItemType = Field(..., description="Item type")
    value: str | int | None = Field(
        None, description="Single value: a port number, address, or CIDR"
    )
    start: str | int | None = Field(None, description="First value of a range")
    stop: str | int | None = Field(None, description="Last value of a range")

    @model_validator(mode="before")
    @classmethod
    def _coerce_numeric_port(cls, data: Any) -> Any:
        """Read a port sent as a number in a string as the number it is.

        The API types a port as an integer, but a controller that answers
        with ``"80"`` must not leave the server holding a value it then
        refuses to send back: the item would read as a string and the
        next write of it would be rejected as a non-integer.
        """
        if not isinstance(data, dict):
            return data
        item_type = data.get("type")
        item_type = getattr(item_type, "value", item_type)
        if item_type not in (
            TrafficMatchingItemType.PORT_NUMBER.value,
            TrafficMatchingItemType.PORT_NUMBER_RANGE.value,
        ):
            return data
        values = dict(data)
        for label in ("value", "start", "stop"):
            number = values.get(label)
            if isinstance(number, str) and number.strip().isdecimal():
                values[label] = int(number.strip())
        return values

    @model_validator(mode="after")
    def _check_value_fields(self) -> "TrafficMatchingListItem":
        """Reject an item whose fields do not match its type."""
        range_type = self.type in (
            TrafficMatchingItemType.PORT_NUMBER_RANGE,
            TrafficMatchingItemType.IP_ADDRESS_RANGE,
        )
        if range_type:
            if self.start is None or self.stop is None:
                raise ValueError(f"{self.type.value} requires both 'start' and 'stop'")
            if self.value is not None:
                raise ValueError(f"{self.type.value} does not take a 'value'")
        else:
            if self.value is None:
                raise ValueError(f"{self.type.value} requires a 'value'")
            if self.start is not None or self.stop is not None:
                raise ValueError(f"{self.type.value} does not take 'start' or 'stop'")
        return self


def _port_item(value: str | int) -> dict[str, Any]:
    """Build the item object for a PORTS list entry."""
    if isinstance(value, int):
        return {"type": TrafficMatchingItemType.PORT_NUMBER.value, "value": value}
    text = str(value).strip()
    if "-" in text:
        start, _, stop = text.partition("-")
        return {
            "type": TrafficMatchingItemType.PORT_NUMBER_RANGE.value,
            "start": int(start.strip()),
            "stop": int(stop.strip()),
        }
    return {"type": TrafficMatchingItemType.PORT_NUMBER.value, "value": int(text)}


def _address_item(value: str | int) -> dict[str, Any]:
    """Build the item object for an IPV4_ADDRESSES/IPV6_ADDRESSES entry."""
    text = str(value).strip()
    if "-" in text:
        start, _, stop = text.partition("-")
        return {
            "type": TrafficMatchingItemType.IP_ADDRESS_RANGE.value,
            "start": start.strip(),
            "stop": stop.strip(),
        }
    item_type = (
        TrafficMatchingItemType.SUBNET.value
        if "/" in text
        else TrafficMatchingItemType.IP_ADDRESS.value
    )
    return {"type": item_type, "value": text}


def normalize_list_items(
    list_type: str,
    items: list[Any],
) -> list[dict[str, Any]]:
    """Turn caller-supplied items into the API's item objects.

    Plain strings are mapped onto the object shape the list type calls
    for, so ``create_traffic_matching_list("PORTS", ..., ["80", "443"])``
    works as well as passing the objects the API itself returns. An item
    that is already an object is validated and passed through.

    Args:
        list_type: ``PORTS``, ``IPV4_ADDRESSES`` or ``IPV6_ADDRESSES``
        items: Item values, as strings or as API-shaped objects

    Returns:
        List of API-shaped item objects

    Raises:
        ValueError: If an item is malformed or not valid for the list type
    """
    allowed = LIST_TYPE_ITEM_TYPES.get(list_type, set())
    normalized: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, dict):
            _check_port_values(item)
            parsed = TrafficMatchingListItem.model_validate(item)
            _check_item_type_allowed(parsed.type.value, list_type, allowed)
            normalized.append(parsed.model_dump(exclude_none=True))
            continue
        if isinstance(item, bool) or not isinstance(item, str | int):
            raise ValueError(f"Invalid list item: {item!r}")
        if list_type == TrafficMatchingListType.PORTS.value:
            built = _port_item(item)
        else:
            built = _address_item(item)
        _check_port_values(built)
        parsed = TrafficMatchingListItem.model_validate(built)
        # A plain value can convert to a type the list does not take — an
        # IPv6 list has no range type, so "2001:db8::1-2001:db8::10" must
        # not become an IP_ADDRESS_RANGE. Both input forms enforce the
        # same restriction.
        _check_item_type_allowed(parsed.type.value, list_type, allowed)
        normalized.append(parsed.model_dump(exclude_none=True))
    return normalized


def _check_port_values(item: dict[str, Any]) -> None:
    """Enforce the port constraints the API documents.

    The Integration API spec types a port as an integer from 1 through
    65535. The check runs on the raw value, before the model coerces it:
    Pydantic would turn ``True`` into ``1`` and a numeric string into an
    int, hiding both from a later check.

    Args:
        item: An item object, as the caller or the mapping produced it

    Raises:
        ValueError: If a port is not an integer in range
    """
    item_type = item.get("type")
    item_type = getattr(item_type, "value", item_type)
    if item_type not in (
        TrafficMatchingItemType.PORT_NUMBER.value,
        TrafficMatchingItemType.PORT_NUMBER_RANGE.value,
    ):
        return
    for label in ("value", "start", "stop"):
        if label not in item or item[label] is None:
            continue
        number = item[label]
        if isinstance(number, bool):
            raise ValueError(f"{item_type} {label} must be an integer, got {number!r}")
        if isinstance(number, str):
            # A port the caller wrote as a number in a string is read as
            # the number it is; the item model coerces it.
            text = number.strip()
            if not text.isdecimal():
                raise ValueError(f"{item_type} {label} must be an integer, got {number!r}")
            number = int(text)
        elif not isinstance(number, int):
            raise ValueError(f"{item_type} {label} must be an integer, got {number!r}")
        if not 1 <= number <= 65535:
            raise ValueError(f"{item_type} {label} must be between 1 and 65535, got {number}")


def _check_item_type_allowed(item_type: str, list_type: str, allowed: set[str]) -> None:
    """Raise when an item type is not valid for the list type.

    Args:
        item_type: The item's type discriminator
        list_type: The list's type
        allowed: The item types the list type accepts

    Raises:
        ValueError: If the item type is not allowed for the list type
    """
    if item_type not in allowed:
        raise ValueError(
            f"Item type '{item_type}' is not valid for a '{list_type}' list "
            f"(allowed: {sorted(allowed)})"
        )


class TrafficMatchingList(BaseModel):
    """UniFi Traffic Matching List configuration."""

    id: str = Field(..., description="Traffic matching list ID", alias="_id")
    type: TrafficMatchingListType = Field(..., description="List type")
    name: str = Field(..., description="List name")
    items: list[TrafficMatchingListItem] = Field(
        default_factory=list, description="List items (ports, IPs, etc.)"
    )
    site_id: str | None = Field(None, description="Site ID")

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        json_schema_extra={
            "example": {
                "_id": "507f191e810c19729de860ea",
                "type": "PORTS",
                "name": "Common Web Ports",
                "items": [
                    {"type": "PORT_NUMBER", "value": 80},
                    {"type": "PORT_NUMBER", "value": 443},
                ],
            }
        },
    )

    @model_validator(mode="before")
    @classmethod
    def _accept_plain_items(cls, data: Any) -> Any:
        """Accept plain values for ``items`` as well as API-shaped objects.

        The Integration API reports each entry as an object (issue #282),
        but a controller that still answers with bare values must not fail
        the read. Plain values are mapped onto the object shape for the
        list's type, so callers always see one shape.
        """
        if not isinstance(data, dict):
            return data
        values = dict(data)
        list_type = values.get("type")
        items = values.get("items")
        if isinstance(list_type, str) and isinstance(items, list) and items:
            if any(not isinstance(item, dict) for item in items):
                try:
                    values["items"] = normalize_list_items(list_type, items)
                except ValueError:
                    # Leave the payload as the controller sent it; the
                    # validation below reports the problem.
                    return values
        return values


class TrafficMatchingListCreate(BaseModel):
    """Request model for creating traffic matching list."""

    type: TrafficMatchingListType = Field(..., description="List type")
    name: str = Field(..., description="List name", min_length=1, max_length=128)
    items: list[TrafficMatchingListItem] = Field(
        ..., description="List items (non-empty)", min_length=1
    )

    model_config = ConfigDict(use_enum_values=True)

    @model_validator(mode="before")
    @classmethod
    def _accept_plain_items(cls, data: Any) -> Any:
        """Accept plain values for ``items`` and a plain string for ``type``.

        Callers pass ports, addresses or CIDRs as strings; the API needs
        them as ``{type, value}`` objects, so map them here rather than
        making every caller know the object shape.
        """
        if not isinstance(data, dict):
            return data
        values = dict(data)
        list_type = values.get("type")
        items = values.get("items")
        if isinstance(list_type, str) and items is not None:
            try:
                values["items"] = normalize_list_items(list_type, items)
            except ValueError as e:
                raise ValueError(str(e)) from e
        return values


class TrafficMatchingListUpdate(BaseModel):
    """Request model for updating traffic matching list."""

    type: TrafficMatchingListType | None = Field(None, description="List type")
    name: str | None = Field(None, description="List name", min_length=1, max_length=128)
    items: list[TrafficMatchingListItem] | None = Field(None, description="List items")

    model_config = ConfigDict(use_enum_values=True)
