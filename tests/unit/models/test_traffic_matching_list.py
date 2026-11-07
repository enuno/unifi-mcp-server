"""Tests for the traffic matching list item models (issue #282).

The Integration API represents each entry as an object carrying a ``type``
discriminator, not as a bare string. Reading a list with the old
``list[str]`` model failed validation for every non-empty list, and
creating one sent bare strings, which the API rejects with "Missing
$.items[0].type value".
"""

import pytest
from pydantic import ValidationError

from src.models.traffic_matching_list import (
    TrafficMatchingList,
    TrafficMatchingListCreate,
    TrafficMatchingListItem,
    normalize_list_items,
)


class TestTrafficMatchingListItem:
    def test_port_number(self):
        item = TrafficMatchingListItem.model_validate({"type": "PORT_NUMBER", "value": 53})
        assert item.type.value == "PORT_NUMBER"
        assert item.value == 53

    def test_port_number_range(self):
        item = TrafficMatchingListItem.model_validate(
            {"type": "PORT_NUMBER_RANGE", "start": 8000, "stop": 8080}
        )
        assert item.start == 8000
        assert item.stop == 8080

    def test_single_value_type_rejects_start_and_stop(self):
        """A single-value type carries no range fields."""
        with pytest.raises(ValidationError, match="does not take 'start' or 'stop'"):
            TrafficMatchingListItem.model_validate(
                {"type": "PORT_NUMBER", "value": 80, "start": 80}
            )

    def test_subnet(self):
        item = TrafficMatchingListItem.model_validate({"type": "SUBNET", "value": "192.168.3.0/24"})
        assert item.value == "192.168.3.0/24"

    def test_value_type_must_match_its_type(self):
        with pytest.raises(ValidationError, match="requires a 'value'"):
            TrafficMatchingListItem.model_validate({"type": "PORT_NUMBER"})

    def test_range_requires_start_and_stop(self):
        with pytest.raises(ValidationError, match="requires both 'start' and 'stop'"):
            TrafficMatchingListItem.model_validate({"type": "PORT_NUMBER_RANGE", "start": 80})

    def test_range_rejects_a_value(self):
        with pytest.raises(ValidationError, match="does not take a 'value'"):
            TrafficMatchingListItem.model_validate(
                {"type": "PORT_NUMBER_RANGE", "start": 80, "stop": 90, "value": 80}
            )

    def test_unknown_type_is_rejected(self):
        with pytest.raises(ValidationError):
            TrafficMatchingListItem.model_validate({"type": "NONSENSE", "value": "x"})


class TestNormalizeListItems:
    def test_port_string_becomes_a_port_number(self):
        assert normalize_list_items("PORTS", ["80", "443"]) == [
            {"type": "PORT_NUMBER", "value": 80},
            {"type": "PORT_NUMBER", "value": 443},
        ]

    def test_integer_port_becomes_a_port_number(self):
        """A port may arrive as an integer rather than a string."""
        assert normalize_list_items("PORTS", [80, 443]) == [
            {"type": "PORT_NUMBER", "value": 80},
            {"type": "PORT_NUMBER", "value": 443},
        ]

    def test_port_range_string_becomes_a_range(self):
        assert normalize_list_items("PORTS", ["8000-8080"]) == [
            {"type": "PORT_NUMBER_RANGE", "start": 8000, "stop": 8080}
        ]

    def test_cidr_string_becomes_a_subnet(self):
        assert normalize_list_items("IPV4_ADDRESSES", ["192.168.3.0/24"]) == [
            {"type": "SUBNET", "value": "192.168.3.0/24"}
        ]

    def test_bare_address_string_becomes_an_address(self):
        assert normalize_list_items("IPV4_ADDRESSES", ["192.168.3.5"]) == [
            {"type": "IP_ADDRESS", "value": "192.168.3.5"}
        ]

    def test_address_range_string_becomes_a_range(self):
        assert normalize_list_items("IPV4_ADDRESSES", ["10.0.0.1-10.0.0.10"]) == [
            {"type": "IP_ADDRESS_RANGE", "start": "10.0.0.1", "stop": "10.0.0.10"}
        ]

    def test_objects_pass_through(self):
        items = [{"type": "PORT_NUMBER", "value": 53}]
        assert normalize_list_items("PORTS", items) == items

    def test_item_type_not_valid_for_the_list_is_rejected(self):
        with pytest.raises(ValueError, match="not valid for a 'PORTS' list"):
            normalize_list_items("PORTS", [{"type": "SUBNET", "value": "10.0.0.0/8"}])

    def test_ipv6_range_type_is_rejected(self):
        """IPv6 lists take IP_ADDRESS and SUBNET, not a range."""
        with pytest.raises(ValueError, match="not valid"):
            normalize_list_items(
                "IPV6_ADDRESSES",
                [{"type": "IP_ADDRESS_RANGE", "start": "2001:db8::1", "stop": "2001:db8::10"}],
            )

    def test_ipv6_range_scalar_is_rejected(self):
        """A plain value must not convert into a type the list rejects.

        An IPv6 list has no range type, so "2001:db8::1-2001:db8::10" must
        not become an IP_ADDRESS_RANGE. The object form is rejected above;
        the scalar form has to be rejected the same way.
        """
        with pytest.raises(ValueError, match="not valid"):
            normalize_list_items("IPV6_ADDRESSES", ["2001:db8::1-2001:db8::10"])

    def test_ipv6_address_scalar_is_accepted(self):
        assert normalize_list_items("IPV6_ADDRESSES", ["2001:db8::1"]) == [
            {"type": "IP_ADDRESS", "value": "2001:db8::1"}
        ]

    def test_port_out_of_range_is_rejected(self):
        """The API types a port as 1..65535."""
        with pytest.raises(ValueError, match="between 1 and 65535"):
            normalize_list_items("PORTS", [{"type": "PORT_NUMBER", "value": 70000}])

    def test_port_zero_is_rejected(self):
        with pytest.raises(ValueError, match="between 1 and 65535"):
            normalize_list_items("PORTS", [{"type": "PORT_NUMBER", "value": 0}])

    def test_non_numeric_port_object_is_rejected(self):
        with pytest.raises(ValueError, match="must be an integer"):
            normalize_list_items("PORTS", [{"type": "PORT_NUMBER", "value": "http"}])

    def test_port_range_out_of_range_is_rejected(self):
        with pytest.raises(ValueError, match="between 1 and 65535"):
            normalize_list_items(
                "PORTS", [{"type": "PORT_NUMBER_RANGE", "start": 80, "stop": 70000}]
            )

    def test_boolean_port_is_rejected(self):
        with pytest.raises(ValueError, match="must be an integer"):
            normalize_list_items("PORTS", [{"type": "PORT_NUMBER", "value": True}])

    def test_valid_port_boundaries_are_accepted(self):
        assert normalize_list_items("PORTS", [{"type": "PORT_NUMBER", "value": 65535}]) == [
            {"type": "PORT_NUMBER", "value": 65535}
        ]

    def test_a_numeric_port_string_is_read_as_a_number(self):
        """A port written as a number in a string is the number it is."""
        assert normalize_list_items("PORTS", [{"type": "PORT_NUMBER", "value": "80"}]) == [
            {"type": "PORT_NUMBER", "value": 80}
        ]

    def test_a_numeric_port_string_out_of_range_is_rejected(self):
        with pytest.raises(ValueError, match="between 1 and 65535"):
            normalize_list_items("PORTS", [{"type": "PORT_NUMBER", "value": "70000"}])

    def test_non_scalar_item_is_rejected(self):
        with pytest.raises(ValueError, match="Invalid list item"):
            normalize_list_items("PORTS", [None])

    def test_non_numeric_port_is_rejected(self):
        with pytest.raises(ValueError):
            normalize_list_items("PORTS", ["http"])


class TestTrafficMatchingListModel:
    def test_reads_api_shaped_items(self):
        """The API's own payload must validate (issue #282)."""
        tml = TrafficMatchingList.model_validate(
            {
                "_id": "tml-1",
                "type": "PORTS",
                "name": "Web Ports",
                "items": [
                    {"type": "PORT_NUMBER", "value": 53},
                    {"type": "PORT_NUMBER", "value": 80},
                ],
            }
        )
        assert tml.items[0].type.value == "PORT_NUMBER"
        assert tml.items[0].value == 53

    def test_reads_subnet_items(self):
        tml = TrafficMatchingList.model_validate(
            {
                "_id": "tml-2",
                "type": "IPV4_ADDRESSES",
                "name": "Blocked",
                "items": [{"type": "SUBNET", "value": "192.168.3.0/24"}],
            }
        )
        assert tml.items[0].value == "192.168.3.0/24"

    def test_reads_plain_values(self):
        """A controller that still answers with bare values is readable."""
        tml = TrafficMatchingList.model_validate(
            {"_id": "tml-3", "type": "PORTS", "name": "Web", "items": ["80", "443"]}
        )
        assert [i.value for i in tml.items] == [80, 443]

    def test_unreadable_plain_values_are_reported(self):
        """A bare value that is not a port cannot be read.

        The read path leaves the controller's payload alone when it cannot
        map it, so the item validation below is what reports the problem.
        """
        with pytest.raises(ValidationError) as excinfo:
            TrafficMatchingList.model_validate(
                {"_id": "tml-4", "type": "PORTS", "name": "Web", "items": ["http"]}
            )
        assert "items" in str(excinfo.value)

    def test_a_port_sent_as_a_string_reads_as_a_number(self):
        """A controller that answers with "80" must not break the next write.

        Reading a list and feeding its items back to update is a normal
        sequence; if the port stayed a string, that write would be
        rejected as a non-integer.
        """
        tml = TrafficMatchingList.model_validate(
            {
                "_id": "tml-5",
                "type": "PORTS",
                "name": "Web",
                "items": [{"type": "PORT_NUMBER", "value": "80"}],
            }
        )
        assert tml.items[0].value == 80


class TestTrafficMatchingListCreate:
    def test_accepts_plain_strings(self):
        create = TrafficMatchingListCreate.model_validate(
            {"type": "IPV4_ADDRESSES", "name": "Blocked", "items": ["192.168.3.0/24"]}
        )
        assert create.items[0].type.value == "SUBNET"
        assert create.items[0].value == "192.168.3.0/24"

    def test_accepts_port_strings(self):
        create = TrafficMatchingListCreate.model_validate(
            {"type": "PORTS", "name": "Web", "items": ["80", "443"]}
        )
        assert [i.value for i in create.items] == [80, 443]

    def test_accepts_objects(self):
        create = TrafficMatchingListCreate.model_validate(
            {"type": "PORTS", "name": "Web", "items": [{"type": "PORT_NUMBER", "value": 80}]}
        )
        assert create.items[0].value == 80

    def test_rejects_an_item_type_that_does_not_fit(self):
        with pytest.raises(ValidationError):
            TrafficMatchingListCreate.model_validate(
                {"type": "PORTS", "name": "Web", "items": [{"type": "SUBNET", "value": "10/8"}]}
            )

    def test_dump_omits_the_unused_value_fields(self):
        """The API rejects an unused field as an unknown property.

        Verified live: a PORTS item dumped with its null ``start``/``stop``
        made the controller answer "Unknown request body property
        '$.items[0].start'", so the create payload must exclude them.
        """
        create = TrafficMatchingListCreate.model_validate(
            {"type": "PORTS", "name": "Web", "items": ["80"]}
        )
        dumped = create.model_dump(exclude_none=True)
        assert dumped["items"] == [{"type": "PORT_NUMBER", "value": 80}]
        assert "start" not in dumped["items"][0]
        assert "stop" not in dumped["items"][0]

    def test_dump_emits_the_item_type_as_a_plain_string(self):
        create = TrafficMatchingListCreate.model_validate(
            {"type": "PORTS", "name": "Web", "items": ["80"]}
        )
        dumped = create.model_dump(exclude_none=True)
        assert dumped["items"][0]["type"] == "PORT_NUMBER"
