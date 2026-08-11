"""Unit tests for src/a2a/route_policy.py."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any

import pytest

from src.a2a.route_policy import (
    ConfirmationToken,
    ConfirmationWorkflow,
    RoutePolicy,
    SafetyController,
    SafetyResult,
)
from src.config.config import Settings


def auth(permissions: set[str] | None = None, **credentials: Any) -> SimpleNamespace:
    """Build a stand-in auth context with the given permissions and credentials."""
    return SimpleNamespace(permissions=permissions or {"admin"}, credentials=credentials)


@pytest.fixture
def controller() -> SafetyController:
    """Return a controller using the built-in default policies."""
    return SafetyController()


class TestDataclasses:
    """Tests for the module's dataclass defaults."""

    def test_safety_result_defaults(self) -> None:
        result = SafetyResult(True, "read", "allowed")

        assert result.requires_confirmation is False
        assert result.rate_limited is False
        assert result.policy is None

    def test_confirmation_token_starts_unconfirmed(self) -> None:
        now = datetime.now(tz=timezone.utc)
        token = ConfirmationToken("t", "delete_site", "hash", "why", now, now)

        assert token.confirmed is False


class TestDefaultPolicies:
    """Tests for SafetyController._build_default_policies."""

    def test_without_settings_uses_baseline_rates(self, controller: SafetyController) -> None:
        by_path = {policy.path: policy for policy in controller._policies}

        assert by_path["/a2a/agent-card"].rateLimit == 120
        assert by_path["/a2a/delegate"].rateLimit == 30
        assert by_path["tool://destructive"].rateLimit == 5
        assert by_path["/a2a/audit"].requiredAuth == "admin"

    def test_rates_are_derived_from_settings(self, local_settings: Settings) -> None:
        local_settings.rate_limit_requests = 200

        by_path = {p.path: p for p in SafetyController(local_settings)._policies}

        assert by_path["/a2a/agent-card"].rateLimit == 200
        assert by_path["/a2a/delegate"].rateLimit == 50
        assert by_path["tool://destructive"].rateLimit == 10

    def test_derived_rates_never_drop_below_one(self, local_settings: Settings) -> None:
        local_settings.rate_limit_requests = 1

        by_path = {p.path: p for p in SafetyController(local_settings)._policies}

        assert by_path["/a2a/delegate"].rateLimit == 1
        assert by_path["tool://destructive"].rateLimit == 1

    def test_explicit_policies_replace_the_defaults(self) -> None:
        policy = RoutePolicy("tool://custom", ("POST",), "read", "none", 7)

        assert SafetyController(policies=[policy])._policies == [policy]


class TestNormalizeAndHash:
    """Tests for the small static helpers."""

    def test_tool_names_are_trimmed_and_lowercased(self) -> None:
        assert SafetyController._normalize_tool_name("  Delete_Site  ") == "delete_site"

    def test_params_hash_is_stable_regardless_of_key_order(self) -> None:
        first = SafetyController._params_hash({"a": 1, "b": 2})
        second = SafetyController._params_hash({"b": 2, "a": 1})

        assert first == second

    def test_params_hash_changes_with_values(self) -> None:
        assert SafetyController._params_hash({"a": 1}) != SafetyController._params_hash({"a": 2})


class TestClassifyTool:
    """Tests for SafetyController._classify_tool."""

    @pytest.mark.parametrize(
        "tool_name", ["delete_site", "revoke_key", "block_client", "factory_reset_device"]
    )
    def test_destructive_prefixes(self, controller: SafetyController, tool_name: str) -> None:
        level, policy = controller._classify_tool(tool_name, {})

        assert level == "destructive"
        assert policy.requiredAuth == "destructive"
        assert policy.confirmationLevel == "critical"

    def test_destructive_keywords_anywhere_in_the_name(self, controller: SafetyController) -> None:
        level, _ = controller._classify_tool("site_purge_all", {})

        assert level == "destructive"

    @pytest.mark.parametrize("tool_name", ["create_wlan", "update_site", "adopt_device"])
    def test_write_prefixes(self, controller: SafetyController, tool_name: str) -> None:
        level, policy = controller._classify_tool(tool_name, {})

        assert level == "write"
        assert policy.requiredAuth == "write"
        assert policy.confirmationLevel == "standard"

    def test_write_keywords_anywhere_in_name(self, controller: SafetyController) -> None:
        level, _ = controller._classify_tool("site_sync_now", {})

        assert level == "write"

    @pytest.mark.parametrize("tool_name", ["list_sites", "get_device", "search_events"])
    def test_read_tools(self, controller: SafetyController, tool_name: str) -> None:
        level, policy = controller._classify_tool(tool_name, {})

        assert level == "read"
        assert policy.requiredAuth == "read"
        assert policy.rateLimit == 120

    def test_rates_follow_settings(self, local_settings: Settings) -> None:
        local_settings.rate_limit_requests = 400
        controller = SafetyController(local_settings)

        assert controller._classify_tool("delete_site", {})[1].rateLimit == 20
        assert controller._classify_tool("create_wlan", {})[1].rateLimit == 100
        assert controller._classify_tool("list_sites", {})[1].rateLimit == 400


class TestFindPolicy:
    """Tests for SafetyController._find_policy."""

    def test_an_exact_policy_path_wins(self) -> None:
        policy = RoutePolicy("tool://list_sites", ("POST",), "read", "none", 9)
        controller = SafetyController(policies=[policy])

        assert controller._find_policy("List_Sites") is policy

    def test_the_wildcard_policy_matches_any_tool(self) -> None:
        policy = RoutePolicy("tool://*", ("POST",), "read", "standard", 11)
        controller = SafetyController(policies=[policy])

        assert controller._find_policy("anything") is policy

    @pytest.mark.parametrize(
        ("tool_name", "expected"),
        [("delete_site", "destructive"), ("create_wlan", "write"), ("list_sites", "read")],
    )
    def test_falls_back_to_classification(self, tool_name: str, expected: str) -> None:
        route_only = RoutePolicy("/a2a/audit", ("GET",), "admin", "none", 7)
        controller = SafetyController(policies=[route_only])

        assert controller._find_policy(tool_name).requiredAuth == expected

    def test_an_empty_policy_list_falls_back_to_the_defaults(self) -> None:
        controller = SafetyController(policies=[])

        assert controller._find_policy("delete_site").path == "tool://*"


class TestRequiresConfirmation:
    """Tests for SafetyController.requires_confirmation."""

    @pytest.mark.parametrize("key", ["confirm", "confirmed", "confirmation", "approve"])
    def test_an_explicit_confirmation_flag_short_circuits(
        self, controller: SafetyController, key: str
    ) -> None:
        assert controller.requires_confirmation("delete_site", {key: True}) is False

    def test_destructive_tools_require_confirmation(self, controller: SafetyController) -> None:
        assert controller.requires_confirmation("delete_site", {}) is True

    def test_write_tools_with_a_mutating_marker_require_confirmation(
        self, controller: SafetyController
    ) -> None:
        assert controller.requires_confirmation("update_site", {}) is True

    def test_plain_write_tools_do_not_require_confirmation(
        self, controller: SafetyController
    ) -> None:
        assert controller.requires_confirmation("adopt_device", {}) is False

    def test_write_tools_honour_an_explicit_request(self, controller: SafetyController) -> None:
        result = controller.requires_confirmation("adopt_device", {"requires_confirmation": True})

        assert result is True

    def test_read_tools_do_not_require_confirmation(self, controller: SafetyController) -> None:
        assert controller.requires_confirmation("list_sites", {}) is False

    def test_read_tools_honour_an_explicit_request(self, controller: SafetyController) -> None:
        result = controller.requires_confirmation("list_sites", {"requires_confirmation": True})

        assert result is True


class TestCheckRateLimit:
    """Tests for SafetyController.check_rate_limit."""

    def test_allows_calls_up_to_the_limit_then_blocks(self) -> None:
        policy = RoutePolicy("tool://*", ("POST",), "read", "none", 2)
        controller = SafetyController(policies=[policy])

        assert controller.check_rate_limit("agent-a", "list_sites") is True
        assert controller.check_rate_limit("agent-a", "list_sites") is True
        assert controller.check_rate_limit("agent-a", "list_sites") is False

    def test_limits_are_tracked_per_agent(self) -> None:
        policy = RoutePolicy("tool://*", ("POST",), "read", "none", 1)
        controller = SafetyController(policies=[policy])

        assert controller.check_rate_limit("agent-a", "list_sites") is True
        assert controller.check_rate_limit("agent-b", "list_sites") is True

    def test_limits_are_tracked_per_tool(self) -> None:
        controller = SafetyController(policies=[])

        assert controller.check_rate_limit("agent-a", "delete_site") is True
        assert controller.check_rate_limit("agent-a", "remove_site") is True

    def test_entries_older_than_the_window_are_evicted(self, local_settings: Settings) -> None:
        local_settings.rate_limit_period = 60
        policy = RoutePolicy("tool://*", ("POST",), "read", "none", 1)
        controller = SafetyController(local_settings, policies=[policy])
        stale = datetime.now(tz=timezone.utc).timestamp() - 3600
        controller._request_windows[("agent-a", "list_sites")].append(stale)

        assert controller.check_rate_limit("agent-a", "list_sites") is True


class TestPermissionsAllow:
    """Tests for SafetyController._permissions_allow."""

    def test_admin_allows_everything(self, controller: SafetyController) -> None:
        assert controller._permissions_allow({"admin"}, "destructive") is True

    @pytest.mark.parametrize("permission", ["read", "write", "destructive"])
    def test_read_accepts_any_permission(
        self, controller: SafetyController, permission: str
    ) -> None:
        assert controller._permissions_allow({permission}, "read") is True

    def test_write_rejects_read_only(self, controller: SafetyController) -> None:
        assert controller._permissions_allow({"read"}, "write") is False

    def test_destructive_requires_the_destructive_permission(
        self, controller: SafetyController
    ) -> None:
        assert controller._permissions_allow({"write"}, "destructive") is False
        assert controller._permissions_allow({"destructive"}, "destructive") is True

    def test_unknown_requirements_are_matched_literally(self, controller: SafetyController) -> None:
        assert controller._permissions_allow({"custom"}, "custom") is True
        assert controller._permissions_allow({"read"}, "custom") is False

    def test_comparison_is_case_insensitive(self, controller: SafetyController) -> None:
        assert controller._permissions_allow({"ADMIN"}, "destructive") is True


class TestValidateSafetyConstraints:
    """Tests for SafetyController.validate_safety_constraints."""

    def test_missing_auth_is_rejected(self, controller: SafetyController) -> None:
        result = controller.validate_safety_constraints("list_sites", {}, None)

        assert result.allowed is False
        assert result.reason == "authentication required"
        assert result.risk_level == "read"

    def test_insufficient_permissions_are_rejected(self, controller: SafetyController) -> None:
        result = controller.validate_safety_constraints(
            "delete_site", {"confirm": True}, auth({"read"})
        )

        assert result.allowed is False
        assert "missing required permission" in result.reason

    def test_a_confirmed_destructive_call_is_allowed(self, controller: SafetyController) -> None:
        result = controller.validate_safety_constraints(
            "delete_site", {"confirm": True}, auth({"destructive"})
        )

        assert result.allowed is True
        assert result.reason == "allowed"
        assert result.risk_level == "destructive"

    def test_an_unconfirmed_destructive_call_requests_confirmation(
        self, controller: SafetyController
    ) -> None:
        result = controller.validate_safety_constraints("delete_site", {}, auth({"destructive"}))

        assert result.allowed is False
        assert result.requires_confirmation is True
        assert result.reason == "confirmation required"

    def test_rate_limited_calls_are_reported(self) -> None:
        policy = RoutePolicy("tool://*", ("POST",), "read", "none", 1)
        controller = SafetyController(policies=[policy])
        controller.validate_safety_constraints("list_sites", {}, auth())

        result = controller.validate_safety_constraints("list_sites", {}, auth())

        assert result.allowed is False
        assert result.rate_limited is True
        assert result.reason == "rate limit exceeded"

    @pytest.mark.parametrize("key", ["agent_id", "client_id", "subject", "sub"])
    def test_the_agent_identity_is_read_from_any_known_claim(self, key: str) -> None:
        policy = RoutePolicy("tool://*", ("POST",), "read", "none", 1)
        controller = SafetyController(policies=[policy])

        controller.validate_safety_constraints("list_sites", {}, auth(**{key: "agent-a"}))

        assert ("agent-a", "list_sites") in controller._request_windows

    def test_an_unidentified_caller_is_tracked_as_anonymous(self) -> None:
        controller = SafetyController(policies=[])

        controller.validate_safety_constraints("list_sites", {}, auth())

        assert ("anonymous", "list_sites") in controller._request_windows

    def test_a_wildcard_policy_is_replaced_by_the_inferred_policy(self) -> None:
        policy = RoutePolicy("tool://*", ("POST",), "read", "standard", 100)
        controller = SafetyController(policies=[policy])

        result = controller.validate_safety_constraints(
            "delete_site", {"confirm": True}, auth({"read"})
        )

        assert result.allowed is False
        assert result.policy is not None
        assert result.policy.requiredAuth == "destructive"

    def test_a_context_without_permissions_is_rejected(self, controller: SafetyController) -> None:
        result = controller.validate_safety_constraints(
            "list_sites", {}, SimpleNamespace(permissions=None, credentials={})
        )

        assert result.allowed is False


class TestConfirmationWorkflow:
    """Tests for ConfirmationWorkflow."""

    @pytest.fixture
    def workflow(self) -> ConfirmationWorkflow:
        return ConfirmationWorkflow()

    def test_request_confirmation_issues_a_unique_token(
        self, workflow: ConfirmationWorkflow
    ) -> None:
        first = workflow.request_confirmation("delete_site", {"site_id": "s"}, "destructive")
        second = workflow.request_confirmation("delete_site", {"site_id": "s"}, "destructive")

        assert first.token != second.token
        assert first.tool_name == "delete_site"
        assert first.reason == "destructive"
        assert first.expires_at > first.created_at

    def test_the_ttl_controls_the_expiry(self) -> None:
        token = ConfirmationWorkflow(ttl_seconds=30).request_confirmation("delete_site", {}, "why")

        assert token.expires_at - token.created_at == timedelta(seconds=30)

    def test_a_boolean_response_approves_or_denies(self, workflow: ConfirmationWorkflow) -> None:
        token = workflow.request_confirmation("delete_site", {}, "why")

        assert workflow.verify_confirmation(token, True) is True
        assert workflow.verify_confirmation(token, False) is False

    @pytest.mark.parametrize("response", ["true", "YES", "approved", "confirm"])
    def test_an_affirmative_word_is_not_enough_on_its_own(
        self, workflow: ConfirmationWorkflow, response: str
    ) -> None:
        """A string response doubles as the token, so a bare 'yes' is rejected."""
        token = workflow.request_confirmation("delete_site", {}, "why")

        assert workflow.verify_confirmation(token, response) is False

    def test_a_string_response_that_looks_like_a_token_must_match(
        self, workflow: ConfirmationWorkflow
    ) -> None:
        token = workflow.request_confirmation("delete_site", {}, "why")

        assert workflow.verify_confirmation(token, "not-the-token") is False

    def test_the_issued_token_string_is_accepted_as_the_response(
        self, workflow: ConfirmationWorkflow
    ) -> None:
        token = workflow.request_confirmation("delete_site", {}, "why")

        assert workflow.verify_confirmation(token.token, token.token) is False

    @pytest.mark.parametrize("key", ["approved", "confirmed", "ok", "allow"])
    def test_mapping_responses_approve_on_any_known_key(
        self, workflow: ConfirmationWorkflow, key: str
    ) -> None:
        token = workflow.request_confirmation("delete_site", {}, "why")

        assert workflow.verify_confirmation(token, {key: True}) is True

    def test_a_mapping_response_may_echo_the_token(self, workflow: ConfirmationWorkflow) -> None:
        token = workflow.request_confirmation("delete_site", {}, "why")

        assert workflow.verify_confirmation(token, {"approved": True, "token": token.token}) is True

    def test_a_mapping_response_with_the_wrong_token_is_rejected(
        self, workflow: ConfirmationWorkflow
    ) -> None:
        token = workflow.request_confirmation("delete_site", {}, "why")

        result = workflow.verify_confirmation(token, {"approved": True, "token": "wrong"})

        assert result is False

    def test_a_confirmation_token_key_is_also_accepted(
        self, workflow: ConfirmationWorkflow
    ) -> None:
        token = workflow.request_confirmation("delete_site", {}, "why")
        response = {"approved": True, "confirmation_token": token.token}

        assert workflow.verify_confirmation(token, response) is True

    def test_a_mismatched_params_hash_is_rejected(self, workflow: ConfirmationWorkflow) -> None:
        token = workflow.request_confirmation("delete_site", {"site_id": "s"}, "why")

        result = workflow.verify_confirmation(token, {"approved": True, "params_hash": "wrong"})

        assert result is False

    def test_a_matching_params_hash_is_accepted(self, workflow: ConfirmationWorkflow) -> None:
        params = {"site_id": "s"}
        token = workflow.request_confirmation("delete_site", params, "why")
        response = {"approved": True, "params_hash": SafetyController._params_hash(params)}

        assert workflow.verify_confirmation(token, response) is True

    def test_other_response_types_are_coerced_to_a_boolean(
        self, workflow: ConfirmationWorkflow
    ) -> None:
        token = workflow.request_confirmation("delete_site", {}, "why")

        assert workflow.verify_confirmation(token, [1]) is True
        assert workflow.verify_confirmation(token, []) is False

    def test_approval_marks_the_stored_token_confirmed(
        self, workflow: ConfirmationWorkflow
    ) -> None:
        token = workflow.request_confirmation("delete_site", {}, "why")

        workflow.verify_confirmation(token, True)

        assert workflow._tokens[token.token].confirmed is True

    def test_an_unknown_token_is_rejected(self, workflow: ConfirmationWorkflow) -> None:
        assert workflow.verify_confirmation("never-issued", True) is False

    def test_an_expired_token_is_rejected_and_discarded(self) -> None:
        workflow = ConfirmationWorkflow(ttl_seconds=-1)
        token = workflow.request_confirmation("delete_site", {}, "why")

        assert workflow.verify_confirmation(token, True) is False
        assert token.token not in workflow._tokens

    def test_expire_confirmation_removes_the_token(self, workflow: ConfirmationWorkflow) -> None:
        token = workflow.request_confirmation("delete_site", {}, "why")

        workflow.expire_confirmation(token)

        assert workflow.verify_confirmation(token, True) is False

    def test_expire_confirmation_accepts_a_raw_token_string(
        self, workflow: ConfirmationWorkflow
    ) -> None:
        token = workflow.request_confirmation("delete_site", {}, "why")

        workflow.expire_confirmation(token.token)

        assert token.token not in workflow._tokens

    def test_expiring_an_unknown_token_is_a_no_op(self, workflow: ConfirmationWorkflow) -> None:
        workflow.expire_confirmation("never-issued")
