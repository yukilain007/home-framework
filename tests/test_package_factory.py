from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from home_framework.compiler import CompiledContext
from home_framework.export_metadata import ExportMetadata, serialize_export_metadata
from home_framework.models import HandoffDocument, HandoffProvenance
from home_framework.package_factory import (
    PackageFactoryError,
    PackageFactoryRequest,
    create_package,
)
from home_framework.renderer import render_markdown

FINGERPRINT = "a" * 64


def _handoff(*, handoff_id: str = "project.execution") -> HandoffDocument:
    return HandoffDocument.model_validate(
        {
            "kind": "handoff",
            "schema_version": "1.0",
            "id": handoff_id,
            "title": "Fictional project execution",
            "purpose": "Continue a fictional implementation from reviewed context.",
            "include": {
                "scopes": [],
                "core_ids": [],
                "current_ids": [],
                "continuity_ids": [],
                "sensitivities": ["public"],
            },
            "output": {"format": "markdown"},
        }
    )


def _compiled(
    *,
    handoff: HandoffDocument | None = None,
    fingerprint: str = FINGERPRINT,
) -> CompiledContext:
    return CompiledContext(
        handoff=handoff or _handoff(),
        documents=(),
        as_of=date(2026, 8, 3),
        fingerprint=fingerprint,
    )


def _provenance() -> HandoffProvenance:
    return HandoffProvenance(
        producer="home-framework",
        authority_status="reviewed",
        approval_status="user-approved",
    )


def _request(
    *,
    compiled: CompiledContext | None = None,
    rendered_content: str = "# Approved context\n",
    provenance: HandoffProvenance | None = None,
    created_at: datetime = datetime(2026, 8, 3, 12, tzinfo=UTC),
    rendered_generated_at: datetime | None = None,
) -> PackageFactoryRequest:
    rendered_generated_at = rendered_generated_at or created_at
    return PackageFactoryRequest(
        compiled_context=compiled or _compiled(),
        rendered_content=rendered_content,
        provenance=provenance or _provenance(),
        created_at=created_at,
        rendered_generated_at=rendered_generated_at,
    )


def test_valid_package_creation_derives_compiled_fields() -> None:
    package = create_package(_request())

    assert package.handoff_id == "project.execution"
    assert package.purpose == "Continue a fictional implementation from reviewed context."
    assert package.context_date == date(2026, 8, 3)
    assert package.source_fingerprint == FINGERPRINT
    assert package.provenance.approval_status == "user-approved"
    assert package.content.digest == (
        "sha256:" + hashlib.sha256(b"# Approved context\n").hexdigest()
    )


def test_missing_approval_fails_closed() -> None:
    provenance = HandoffProvenance.model_construct(
        producer="home-framework",
        authority_status="reviewed",
        approval_status="pending",
    )

    with pytest.raises(PackageFactoryError, match="missing_approval"):
        create_package(_request(provenance=provenance))


def test_fingerprint_mismatch_fails_closed() -> None:
    with pytest.raises(PackageFactoryError, match="fingerprint_mismatch"):
        create_package(_request(compiled=_compiled(fingerprint="not-a-fingerprint")))


def test_handoff_metadata_mismatch_fails_closed() -> None:
    metadata = serialize_export_metadata(
        ExportMetadata(
            schema_version="1.0",
            handoff_id="other.handoff",
            context_date=date(2026, 8, 3),
            fingerprint=FINGERPRINT,
        )
    )

    with pytest.raises(PackageFactoryError, match="handoff_mismatch"):
        create_package(_request(rendered_content=metadata + "\n# Wrong handoff\n"))


def test_invalid_timestamp_is_rejected() -> None:
    with pytest.raises(ValidationError, match="created_at"):
        _request(created_at=datetime(2026, 8, 3, 12))


def test_render_and_package_timestamps_must_align() -> None:
    with pytest.raises(ValidationError, match="rendered_generated_at"):
        _request(
            created_at=datetime(2026, 8, 3, 12, tzinfo=UTC),
            rendered_generated_at=datetime(2026, 8, 3, 12, 0, 1, tzinfo=UTC),
        )


def test_forbidden_request_fields_are_rejected() -> None:
    data = _request().model_dump()
    data["workspace"] = "/tmp/private-workspace"

    with pytest.raises(ValidationError, match="workspace"):
        PackageFactoryRequest.model_validate(data)


def test_package_generation_is_deterministic() -> None:
    first = create_package(_request())
    second = create_package(_request())

    assert first == second
    assert first.canonical_json() == second.canonical_json()
    assert first.canonical_digest() == second.canonical_digest()


def test_render_metadata_must_be_explicit() -> None:
    with pytest.raises(TypeError):
        render_markdown(_compiled())


def test_different_explicit_generated_at_changes_package_digest() -> None:
    compiled = _compiled()
    first_at = datetime(2026, 8, 3, 12, tzinfo=UTC)
    second_at = datetime(2026, 8, 3, 12, 0, 1, tzinfo=UTC)

    first = create_package(
        _request(
            rendered_content=render_markdown(compiled, generated_at=first_at),
            created_at=first_at,
        )
    )
    second = create_package(
        _request(
            rendered_content=render_markdown(compiled, generated_at=second_at),
            created_at=second_at,
        )
    )

    assert first.canonical_digest() != second.canonical_digest()
