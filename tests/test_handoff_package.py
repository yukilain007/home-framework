from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError

from home_framework.models import HandoffPackage


def _content_digest(body: str) -> str:
    canonical_body = body.replace("\r\n", "\n").replace("\r", "\n")
    return "sha256:" + hashlib.sha256(canonical_body.encode("utf-8")).hexdigest()


def _package_data() -> dict[str, object]:
    body = "<!-- generated -->\n# Project execution\n"
    return {
        "package_schema": "1.0",
        "handoff_id": "project.execution",
        "handoff_schema": "1.0",
        "purpose": "Continue one approved project task",
        "context_date": "2026-08-03",
        "created_at": "2026-08-03T12:00:00Z",
        "source_fingerprint": "a" * 64,
        "content": {
            "media_type": "text/markdown",
            "body": body,
            "digest": _content_digest(body),
        },
        "provenance": {
            "producer": "home-framework",
            "authority_status": "reviewed",
            "approval_status": "user-approved",
        },
    }


def test_valid_handoff_package_is_accepted() -> None:
    package = HandoffPackage.model_validate(_package_data())

    assert package.handoff_id == "project.execution"
    assert package.provenance.approval_status == "user-approved"
    assert package.content.media_type == "text/markdown"


def test_invalid_source_fingerprint_is_rejected() -> None:
    data = _package_data()
    data["source_fingerprint"] = "not-a-sha256"

    with pytest.raises(ValidationError, match="source_fingerprint"):
        HandoffPackage.model_validate(data)


def test_invalid_content_digest_is_rejected() -> None:
    data = _package_data()
    content = dict(data["content"])
    content["digest"] = "sha256:" + "0" * 64
    data["content"] = content

    with pytest.raises(ValidationError, match="content digest"):
        HandoffPackage.model_validate(data)


def test_missing_or_unapproved_approval_is_rejected() -> None:
    missing = _package_data()
    provenance = dict(missing["provenance"])
    provenance.pop("approval_status")
    missing["provenance"] = provenance

    with pytest.raises(ValidationError, match="approval_status"):
        HandoffPackage.model_validate(missing)

    unapproved = _package_data()
    unapproved_provenance = dict(unapproved["provenance"])
    unapproved_provenance["approval_status"] = "pending"
    unapproved["provenance"] = unapproved_provenance

    with pytest.raises(ValidationError, match="user-approved"):
        HandoffPackage.model_validate(unapproved)


@pytest.mark.parametrize(
    "field",
    [
        "conversation_dump",
        "workspace_path",
        "credentials",
        "provider_session",
        "auto_send",
        "auto_upload",
        "memory_candidate",
        "recall_decision",
    ],
)
def test_forbidden_fields_are_rejected(field: str) -> None:
    data = _package_data()
    data[field] = {}

    with pytest.raises(ValidationError):
        HandoffPackage.model_validate(data)


def test_deterministic_serialization_produces_the_same_digest() -> None:
    first = HandoffPackage.model_validate(_package_data())
    reversed_data = dict(reversed(list(_package_data().items())))
    second = HandoffPackage.model_validate(reversed_data)

    assert first.canonical_json() == second.canonical_json()
    assert first.canonical_digest() == second.canonical_digest()


def test_same_instant_with_different_timezones_has_the_same_digest() -> None:
    first = HandoffPackage.model_validate(_package_data())
    shifted_data = _package_data()
    shifted_data["created_at"] = "2026-08-03T13:00:00+01:00"
    second = HandoffPackage.model_validate(shifted_data)

    assert first.canonical_json() == second.canonical_json()
    assert first.canonical_digest() == second.canonical_digest()
    assert first.canonical_json().count("2026-08-03T12:00:00Z") == 1


def test_lf_and_crlf_content_have_the_same_digest() -> None:
    lf = HandoffPackage.model_validate(_package_data())
    crlf_data = _package_data()
    crlf_content = dict(crlf_data["content"])
    crlf_body = crlf_content["body"].replace("\n", "\r\n")
    crlf_content["body"] = crlf_body
    crlf_content["digest"] = _content_digest(crlf_body)
    crlf_data["content"] = crlf_content
    crlf = HandoffPackage.model_validate(crlf_data)

    assert lf.content.body == crlf.content.body
    assert lf.canonical_json() == crlf.canonical_json()
    assert lf.canonical_digest() == crlf.canonical_digest()


def test_changed_semantic_content_has_a_different_digest() -> None:
    first = HandoffPackage.model_validate(_package_data())
    changed_data = _package_data()
    changed_content = dict(changed_data["content"])
    changed_body = changed_content["body"] + "A different approved statement.\n"
    changed_content["body"] = changed_body
    changed_content["digest"] = _content_digest(changed_body)
    changed_data["content"] = changed_content
    changed = HandoffPackage.model_validate(changed_data)

    assert first.canonical_digest() != changed.canonical_digest()
