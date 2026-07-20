"""Strict, versioned data contracts for HOME authority repositories."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, TypeAdapter, model_validator

DocumentId: TypeAlias = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=128,
        pattern=r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$",
    ),
]
ScopeName: TypeAlias = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=64,
        pattern=r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$",
    ),
]
SafeRelativePath: TypeAlias = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=256,
        pattern=r"^[a-z0-9][a-z0-9._-]*(?:/[a-z0-9][a-z0-9._-]*)*$",
    ),
]
FrameworkVersion: TypeAlias = Annotated[
    str,
    StringConstraints(pattern=r"^\d+\.\d+\.\d+(?:a\d+)?$"),
]
SchemaVersion: TypeAlias = Literal["1.0"]
Sensitivity: TypeAlias = Literal["public", "private", "secret"]
ExportSensitivity: TypeAlias = Literal["public", "private"]
AuthorityStatus: TypeAlias = Literal["active", "inactive", "archived"]
CandidateAction: TypeAlias = Literal["approve", "reject"]


class StrictModel(BaseModel):
    """Base model that rejects unknown fields and is immutable after validation."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class Source(StrictModel):
    """Provenance supplied by a human-controlled authority file."""

    type: Literal["human_authored", "human_reviewed", "verified_import"]
    reference: str | None = None


class AuthorityDocument(StrictModel):
    """Fields shared by reviewed core and current authority documents."""

    schema_version: SchemaVersion
    id: DocumentId
    content: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    status: AuthorityStatus
    sensitivity: Sensitivity
    scope: tuple[ScopeName, ...]
    priority: Annotated[int, Field(strict=True, ge=0, le=100)] = 50
    source: Source
    created_at: date
    updated_at: date

    @model_validator(mode="after")
    def validate_update_order(self) -> AuthorityDocument:
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must not be earlier than created_at")
        return self


class CoreDocument(AuthorityDocument):
    """Stable, reviewed authority content."""

    kind: Literal["core"]


class CurrentDocument(AuthorityDocument):
    """Time-bounded reviewed context."""

    kind: Literal["current"]
    valid_from: date
    expires_at: date | None = None

    @model_validator(mode="after")
    def validate_validity_window(self) -> CurrentDocument:
        if self.expires_at is not None and self.expires_at < self.valid_from:
            raise ValueError("expires_at must not be earlier than valid_from")
        return self

    def is_active_on(self, as_of: date) -> bool:
        """Return whether this current document is active on an inclusive date window."""

        if self.status != "active" or as_of < self.valid_from:
            return False
        return self.expires_at is None or as_of <= self.expires_at


class CandidateDecision(StrictModel):
    """Human review state for a candidate that never enters compilation."""

    reviewed: Annotated[bool, Field(strict=True)]
    action: CandidateAction | None = None
    reviewed_at: date | None = None

    @model_validator(mode="after")
    def validate_review_state(self) -> CandidateDecision:
        if not self.reviewed and (self.action is not None or self.reviewed_at is not None):
            raise ValueError("unreviewed decision cannot set action or reviewed_at")
        if self.reviewed and (self.action is None or self.reviewed_at is None):
            raise ValueError("reviewed decision requires action and reviewed_at")
        return self


class CandidateDocument(StrictModel):
    """Untrusted proposal awaiting or recording human review."""

    kind: Literal["candidate"]
    schema_version: SchemaVersion
    id: DocumentId
    proposed_kind: Literal["core", "current"]
    content: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    sensitivity: Sensitivity
    scope: tuple[ScopeName, ...]
    source: Source
    created_at: date
    decision: CandidateDecision


class HandoffInclude(StrictModel):
    """Explicit selectors and sensitivity allowlist for a handoff."""

    scopes: tuple[ScopeName, ...] = ()
    core_ids: tuple[DocumentId, ...] = ()
    current_ids: tuple[DocumentId, ...] = ()
    sensitivities: tuple[ExportSensitivity, ...] = ("public",)


class HandoffOutput(StrictModel):
    """Requested output format for a handoff."""

    format: Literal["markdown"]


class HandoffDocument(StrictModel):
    """Reviewed instructions for selecting a context handoff."""

    kind: Literal["handoff"]
    schema_version: SchemaVersion
    id: DocumentId
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    purpose: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    include: HandoffInclude
    output: HandoffOutput


class WorkspaceFramework(StrictModel):
    """Framework compatibility declared by a workspace."""

    minimum_version: FrameworkVersion


class WorkspaceDefaults(StrictModel):
    """Small set of workspace-wide path defaults."""

    export_directory: SafeRelativePath


class WorkspaceManifest(StrictModel):
    """Versioned marker identifying a HOME Framework workspace."""

    kind: Literal["workspace"]
    schema_version: SchemaVersion
    name: DocumentId
    framework: WorkspaceFramework
    defaults: WorkspaceDefaults


Document = Annotated[
    CoreDocument | CurrentDocument | CandidateDocument | HandoffDocument,
    Field(discriminator="kind"),
]
DOCUMENT_ADAPTER: TypeAdapter[Document] = TypeAdapter(Document)
