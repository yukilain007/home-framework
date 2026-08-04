# SPDX-FileCopyrightText: 2026 Yuki
# SPDX-License-Identifier: Apache-2.0

"""Pure construction of immutable HandoffPackage values."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator, model_validator

from home_framework.compiler import CompiledContext
from home_framework.export_metadata import (
    EXPORT_METADATA_PREFIX,
    ExportMetadataError,
    parse_export_metadata,
)
from home_framework.models import (
    DocumentId,
    HandoffContent,
    HandoffPackage,
    HandoffProvenance,
    Sha256Fingerprint,
    StrictModel,
)


class PackageFactoryError(ValueError):
    """Stable, fail-closed error raised while constructing a HandoffPackage."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


class ApprovalScope(StrictModel):
    """The exact compiled context covered by one explicit approval."""

    handoff_id: DocumentId
    context_date: date
    source_fingerprint: Sha256Fingerprint


class ApprovalInput(StrictModel):
    """Explicit user approval evidence required before Package creation."""

    status: Literal["user-approved"]
    source: Literal["explicit_user_confirmation", "approved_record"]
    confirmed_at: datetime
    scope: ApprovalScope

    @field_validator("confirmed_at")
    @classmethod
    def normalize_confirmed_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("confirmed_at must be timezone-aware")
        return value.astimezone(UTC)


class PackageFactoryRequest(BaseModel):
    """Explicit values accepted by the pure Package Factory seam."""

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="forbid",
        frozen=True,
    )

    compiled_context: CompiledContext
    rendered_content: str
    provenance: HandoffProvenance
    created_at: datetime
    rendered_generated_at: datetime

    @field_validator("rendered_content")
    @classmethod
    def validate_rendered_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("rendered_content must not be blank")
        return value

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        return value.astimezone(UTC)

    @field_validator("rendered_generated_at")
    @classmethod
    def validate_rendered_generated_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("rendered_generated_at must be timezone-aware")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_timestamp_alignment(self) -> PackageFactoryRequest:
        if self.created_at != self.rendered_generated_at:
            raise ValueError("created_at must equal rendered_generated_at")
        return self


_FINGERPRINT = re.compile(r"^[0-9a-f]{64}$")


def _validate_request(request: PackageFactoryRequest) -> None:
    compiled = request.compiled_context
    if not _FINGERPRINT.fullmatch(compiled.fingerprint):
        raise PackageFactoryError(
            "fingerprint_mismatch",
            "compiled context fingerprint must be a lowercase SHA-256 digest",
        )
    if compiled.handoff.schema_version != "1.0":
        raise PackageFactoryError(
            "unsupported_schema",
            f"handoff schema {compiled.handoff.schema_version!r} is not supported",
        )
    provenance = request.provenance
    if provenance.approval_status != "user-approved":
        raise PackageFactoryError(
            "missing_approval",
            "Package creation requires explicit user-approved provenance",
        )
    if provenance.authority_status != "reviewed":
        raise PackageFactoryError(
            "missing_approval",
            "Package creation requires reviewed authority provenance",
        )

    content = request.rendered_content
    if not content.startswith(EXPORT_METADATA_PREFIX):
        return
    try:
        metadata = parse_export_metadata(content)
    except ExportMetadataError as error:
        raise PackageFactoryError("invalid_content", str(error)) from error

    if metadata.handoff_id != compiled.handoff.id or metadata.context_date != compiled.as_of:
        raise PackageFactoryError(
            "handoff_mismatch",
            "rendered content metadata does not match the compiled handoff",
        )
    if metadata.fingerprint != compiled.fingerprint:
        raise PackageFactoryError(
            "fingerprint_mismatch",
            "rendered content metadata does not match the compiled fingerprint",
        )


def _content_digest(body: str) -> str:
    canonical_body = body.replace("\r\n", "\n").replace("\r", "\n")
    return "sha256:" + hashlib.sha256(canonical_body.encode("utf-8")).hexdigest()


def create_package(request: PackageFactoryRequest) -> HandoffPackage:
    """Create one immutable Package without reading or changing a workspace."""

    if not isinstance(request, PackageFactoryRequest):
        raise TypeError("request must be a PackageFactoryRequest")
    _validate_request(request)
    compiled = request.compiled_context
    content = HandoffContent(
        media_type="text/markdown",
        body=request.rendered_content,
        digest=_content_digest(request.rendered_content),
    )
    try:
        return HandoffPackage(
            package_schema="1.0",
            handoff_id=compiled.handoff.id,
            handoff_schema=compiled.handoff.schema_version,
            purpose=compiled.handoff.purpose,
            context_date=compiled.as_of,
            created_at=request.created_at,
            source_fingerprint=compiled.fingerprint,
            content=content,
            provenance=request.provenance,
        )
    except ValidationError as error:
        raise PackageFactoryError(
            "invalid_package",
            "compiled values could not form a valid HandoffPackage",
        ) from error
