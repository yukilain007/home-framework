from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from pydantic import ValidationError

from home_framework.adapter import (
    AdapterError,
    ExternalRepresentationArtifact,
    LocalMarkdownAdapter,
)
from home_framework.models import HandoffPackage


def _content_digest(body: str) -> str:
    canonical_body = body.replace("\r\n", "\n").replace("\r", "\n")
    return "sha256:" + hashlib.sha256(canonical_body.encode("utf-8")).hexdigest()


def _package() -> HandoffPackage:
    body = "# Approved context\n"
    return HandoffPackage.model_validate(
        {
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
    )


def test_valid_local_markdown_adaptation_preserves_package_fields() -> None:
    package = _package()

    artifact = LocalMarkdownAdapter().adapt(package)

    assert artifact.media_type == "text/markdown"
    assert artifact.body == package.content.body
    assert artifact.package_schema == package.package_schema
    assert artifact.handoff_id == package.handoff_id
    assert artifact.handoff_schema == package.handoff_schema
    assert artifact.source_fingerprint == package.source_fingerprint
    assert artifact.package_digest == package.canonical_digest()
    assert artifact.source_provenance == package.provenance
    assert artifact.adapter_id == "local-markdown"
    assert artifact.target_type == "markdown"


def test_adapter_preserves_provenance_without_creating_approval() -> None:
    package = _package()

    artifact = LocalMarkdownAdapter().adapt(package)

    assert artifact.source_provenance.model_dump() == package.provenance.model_dump()
    assert artifact.source_provenance.approval_status == "user-approved"


def test_artifact_digest_is_deterministic_and_valid() -> None:
    package = _package()
    adapter = LocalMarkdownAdapter()

    first = adapter.adapt(package)
    second = adapter.adapt(package)

    assert first == second
    assert first.artifact_digest == second.artifact_digest
    assert first.canonical_json() == second.canonical_json()
    assert first.verify_digest() is True


@pytest.mark.parametrize("field", ["package_schema", "handoff_schema"])
def test_unsupported_schema_is_rejected(field: str) -> None:
    data = _package().model_dump(mode="json")
    data[field] = "2.0"
    forged = HandoffPackage.model_construct(**data)

    with pytest.raises(AdapterError, match="unsupported_schema"):
        LocalMarkdownAdapter().adapt(forged)


def test_adapter_does_not_access_workspace_or_accept_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_open(*args: object, **kwargs: object) -> object:
        raise AssertionError("adapter attempted filesystem access")

    monkeypatch.setattr("builtins.open", fail_open)

    artifact = LocalMarkdownAdapter().adapt(_package())

    assert artifact.body == "# Approved context\n"
    with pytest.raises(TypeError, match="HandoffPackage"):
        LocalMarkdownAdapter().adapt(Path("workspace"))  # type: ignore[arg-type]


def test_artifact_rejects_unknown_fields() -> None:
    data = LocalMarkdownAdapter().adapt(_package()).model_dump()
    data["workspace"] = "private"

    with pytest.raises(ValidationError, match="workspace"):
        ExternalRepresentationArtifact.model_validate(data)
