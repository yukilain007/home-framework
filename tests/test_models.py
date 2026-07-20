from datetime import date

import pytest
from pydantic import ValidationError

from home_framework.models import (
    CandidateDocument,
    CoreDocument,
    CurrentDocument,
    HandoffDocument,
)


def core_data() -> dict[str, object]:
    return {
        "kind": "core",
        "schema_version": "1.0",
        "id": "communication.natural",
        "content": "Prefer clear and respectful communication.",
        "status": "active",
        "sensitivity": "public",
        "scope": ["conversation"],
        "priority": 80,
        "source": {"type": "human_authored", "reference": None},
        "created_at": "2026-07-20",
        "updated_at": "2026-07-20",
    }


def current_data() -> dict[str, object]:
    return {
        **core_data(),
        "kind": "current",
        "id": "project.release",
        "scope": ["project"],
        "valid_from": "2026-07-20",
        "expires_at": None,
    }


def candidate_data() -> dict[str, object]:
    return {
        "kind": "candidate",
        "schema_version": "1.0",
        "id": "candidate.example",
        "proposed_kind": "core",
        "content": "A possible preference awaiting human review.",
        "sensitivity": "private",
        "scope": ["conversation"],
        "source": {"type": "human_authored", "reference": None},
        "created_at": "2026-07-20",
        "decision": {"reviewed": False, "action": None, "reviewed_at": None},
    }


def handoff_data() -> dict[str, object]:
    return {
        "kind": "handoff",
        "schema_version": "1.0",
        "id": "project.execution",
        "title": "Project execution context",
        "purpose": "Continue implementation using reviewed fictional material.",
        "include": {"scopes": ["project"], "core_ids": [], "current_ids": []},
        "output": {"format": "markdown"},
    }


def test_unknown_field_is_rejected() -> None:
    data = core_data()
    data["unexpected"] = True

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        CoreDocument.model_validate(data)


@pytest.mark.parametrize("document_id", ["UPPER.case", "has space", "../escape", ""])
def test_invalid_id_is_rejected(document_id: str) -> None:
    data = core_data()
    data["id"] = document_id

    with pytest.raises(ValidationError):
        CoreDocument.model_validate(data)


def test_updated_at_before_created_at_is_rejected() -> None:
    data = core_data()
    data["created_at"] = "2026-07-20"
    data["updated_at"] = "2026-07-19"

    with pytest.raises(ValidationError, match="updated_at must not be earlier"):
        CoreDocument.model_validate(data)


@pytest.mark.parametrize("priority", ["50", True])
def test_priority_coercion_is_rejected(priority: object) -> None:
    data = core_data()
    data["priority"] = priority

    with pytest.raises(ValidationError):
        CoreDocument.model_validate(data)


def test_current_expiry_before_valid_from_is_rejected() -> None:
    data = current_data()
    data["valid_from"] = "2026-07-20"
    data["expires_at"] = "2026-07-19"

    with pytest.raises(ValidationError, match="expires_at must not be earlier"):
        CurrentDocument.model_validate(data)


def test_current_activity_is_date_bounded_and_inclusive() -> None:
    data = current_data()
    data["expires_at"] = "2026-07-21"
    current = CurrentDocument.model_validate(data)

    assert not current.is_active_on(date(2026, 7, 19))
    assert current.is_active_on(date(2026, 7, 20))
    assert current.is_active_on(date(2026, 7, 21))
    assert not current.is_active_on(date(2026, 7, 22))


@pytest.mark.parametrize(
    ("decision", "message"),
    [
        (
            {"reviewed": False, "action": "approve", "reviewed_at": None},
            "unreviewed decision cannot set action or reviewed_at",
        ),
        (
            {"reviewed": True, "action": None, "reviewed_at": "2026-07-20"},
            "reviewed decision requires action and reviewed_at",
        ),
        (
            {"reviewed": True, "action": "reject", "reviewed_at": None},
            "reviewed decision requires action and reviewed_at",
        ),
    ],
)
def test_candidate_decision_state_must_be_consistent(
    decision: dict[str, object], message: str
) -> None:
    data = candidate_data()
    data["decision"] = decision

    with pytest.raises(ValidationError, match=message):
        CandidateDocument.model_validate(data)


def test_candidate_reviewed_boolean_coercion_is_rejected() -> None:
    data = candidate_data()
    data["decision"] = {"reviewed": "false", "action": None, "reviewed_at": None}

    with pytest.raises(ValidationError):
        CandidateDocument.model_validate(data)


def test_handoff_defaults_to_public_sensitivity() -> None:
    handoff = HandoffDocument.model_validate(handoff_data())

    assert handoff.include.sensitivities == ("public",)


def test_handoff_can_declare_private_sensitivity() -> None:
    data = handoff_data()
    include = data["include"]
    assert isinstance(include, dict)
    include["sensitivities"] = ["public", "private"]

    handoff = HandoffDocument.model_validate(data)

    assert handoff.include.sensitivities == ("public", "private")


def test_handoff_rejects_secret_sensitivity() -> None:
    data = handoff_data()
    include = data["include"]
    assert isinstance(include, dict)
    include["sensitivities"] = ["public", "secret"]

    with pytest.raises(ValidationError, match="sensitivities"):
        HandoffDocument.model_validate(data)
