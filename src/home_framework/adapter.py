# SPDX-FileCopyrightText: 2026 Yuki
# SPDX-License-Identifier: Apache-2.0

"""Provider-neutral, artifact-only Handoff Adapter contracts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, StringConstraints, ValidationError, model_validator

from home_framework.models import (
    DocumentId,
    HandoffPackage,
    HandoffProvenance,
    NonEmptyText,
    PackageSchemaVersion,
    SchemaVersion,
    Sha256Fingerprint,
    StrictModel,
)

AdapterVersion = Annotated[str, StringConstraints(pattern=r"^\d+\.\d+\.\d+$")]
ArtifactSchemaVersion = Literal["1.0"]


class AdapterError(ValueError):
    """Stable, fail-closed error raised by an Handoff Adapter."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


class AdapterContract(StrictModel):
    """Declared compatibility and behavior of one provider-neutral Adapter."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_schema: ArtifactSchemaVersion
    adapter_id: DocumentId
    adapter_version: AdapterVersion
    target_type: NonEmptyText
    accepted_package_schemas: tuple[PackageSchemaVersion, ...] = Field(min_length=1)
    accepted_handoff_schemas: tuple[SchemaVersion, ...] = Field(min_length=1)
    capabilities: tuple[NonEmptyText, ...] = ()
    limitations: tuple[NonEmptyText, ...] = ()
    requires_human_review: bool = Field(strict=True)

    @model_validator(mode="after")
    def validate_declarations(self) -> AdapterContract:
        if len(set(self.capabilities)) != len(self.capabilities):
            raise ValueError("capabilities must not contain duplicates")
        if len(set(self.limitations)) != len(self.limitations):
            raise ValueError("limitations must not contain duplicates")
        return self


class ExternalRepresentationArtifact(StrictModel):
    """Immutable representation derived from one validated HandoffPackage."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    artifact_schema: ArtifactSchemaVersion
    adapter_id: DocumentId
    adapter_version: AdapterVersion
    target_type: NonEmptyText
    package_schema: PackageSchemaVersion
    handoff_id: DocumentId
    handoff_schema: SchemaVersion
    source_fingerprint: Sha256Fingerprint
    package_digest: Sha256Fingerprint
    media_type: NonEmptyText
    body: Annotated[str, StringConstraints(min_length=1)]
    source_provenance: HandoffProvenance
    artifact_digest: Sha256Fingerprint

    def _canonical_payload(self) -> dict[str, object]:
        return self.model_dump(mode="json", exclude={"artifact_digest"})

    def canonical_json(self) -> str:
        """Serialize the complete artifact deterministically."""

        return json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    def verify_digest(self) -> bool:
        """Return whether the stored artifact digest matches canonical metadata and body."""

        canonical = json.dumps(
            self._canonical_payload(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest() == self.artifact_digest

    @model_validator(mode="after")
    def validate_artifact_digest(self) -> ExternalRepresentationArtifact:
        if not self.verify_digest():
            raise ValueError("artifact_digest does not match canonical artifact")
        return self


def _local_contract() -> AdapterContract:
    return AdapterContract(
        contract_schema="1.0",
        adapter_id="local-markdown",
        adapter_version="1.0.0",
        target_type="markdown",
        accepted_package_schemas=("1.0",),
        accepted_handoff_schemas=("1.0",),
        capabilities=("markdown-pass-through", "deterministic-output"),
        limitations=("no-file-write", "no-network", "no-provider-integration"),
        requires_human_review=True,
    )


def _artifact_digest(payload: dict[str, object]) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


@dataclass(frozen=True, slots=True)
class LocalMarkdownAdapter:
    """Pure in-memory pass-through Adapter for approved Markdown handoffs."""

    contract: AdapterContract = field(default_factory=_local_contract)

    def adapt(self, package: HandoffPackage) -> ExternalRepresentationArtifact:
        """Return a deterministic Markdown artifact without filesystem or network access."""

        if not isinstance(package, HandoffPackage):
            raise TypeError("package must be a HandoffPackage")
        if package.package_schema not in self.contract.accepted_package_schemas:
            raise AdapterError(
                "unsupported_schema",
                f"package schema {package.package_schema!r} is not supported",
            )
        if package.handoff_schema not in self.contract.accepted_handoff_schemas:
            raise AdapterError(
                "unsupported_schema",
                f"handoff schema {package.handoff_schema!r} is not supported",
            )

        try:
            validated = HandoffPackage.model_validate(package.model_dump(mode="python"))
        except ValidationError as error:
            raise AdapterError("invalid_package", "input Package failed validation") from error
        if validated.provenance.approval_status != "user-approved":
            raise AdapterError("invalid_provenance", "Package is not user-approved")

        payload: dict[str, object] = {
            "artifact_schema": "1.0",
            "adapter_id": self.contract.adapter_id,
            "adapter_version": self.contract.adapter_version,
            "target_type": self.contract.target_type,
            "package_schema": validated.package_schema,
            "handoff_id": validated.handoff_id,
            "handoff_schema": validated.handoff_schema,
            "source_fingerprint": validated.source_fingerprint,
            "package_digest": validated.canonical_digest(),
            "media_type": "text/markdown",
            "body": validated.content.body,
            "source_provenance": validated.provenance.model_dump(mode="json"),
        }
        artifact_digest = _artifact_digest(payload)
        return ExternalRepresentationArtifact(
            artifact_schema="1.0",
            adapter_id=self.contract.adapter_id,
            adapter_version=self.contract.adapter_version,
            target_type=self.contract.target_type,
            package_schema=validated.package_schema,
            handoff_id=validated.handoff_id,
            handoff_schema=validated.handoff_schema,
            source_fingerprint=validated.source_fingerprint,
            package_digest=validated.canonical_digest(),
            media_type="text/markdown",
            body=validated.content.body,
            source_provenance=validated.provenance,
            artifact_digest=artifact_digest,
        )
