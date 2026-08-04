# SPDX-FileCopyrightText: 2026 Yuki
# SPDX-License-Identifier: Apache-2.0

"""Strict, versioned data contracts for HOME authority repositories."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from typing import Annotated, Literal, TypeAlias

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    TypeAdapter,
    field_validator,
    model_validator,
)

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
PackageSchemaVersion: TypeAlias = Literal["1.0"]
ContentMediaType: TypeAlias = Literal["text/markdown"]
Sha256Fingerprint: TypeAlias = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
ContentDigest: TypeAlias = Annotated[
    str,
    StringConstraints(pattern=r"^sha256:[0-9a-f]{64}$"),
]
Sensitivity: TypeAlias = Literal["public", "private", "secret"]
ExportSensitivity: TypeAlias = Literal["public", "private"]
AuthorityStatus: TypeAlias = Literal["active", "inactive", "archived"]
CandidateAction: TypeAlias = Literal["approve", "reject"]
ContinuityKind: TypeAlias = Literal[
    "persona_autonomy",
    "window_state_card",
    "lifeline",
    "memory_candidate",
    "recall_decision",
    "maintenance_channel",
]
MemoryCandidateStatus: TypeAlias = Literal["proposed", "accepted", "rejected"]
RecallAction: TypeAlias = Literal["none", "reuse", "supplement", "refresh"]
NonEmptyText: TypeAlias = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


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


class ContinuityModel(StrictModel):
    """Base for optional, human-reviewed continuity contracts."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    kind: ContinuityKind
    schema_version: SchemaVersion
    id: DocumentId


class PersonaAutonomy(ContinuityModel):
    """A judgment anchor, never a fixed roleplay script."""

    kind: Literal["persona_autonomy"]
    independent_judgment: bool = Field(alias="independentJudgment", strict=True)
    may_disagree: bool = Field(alias="mayDisagree", strict=True)
    may_decline_interaction: bool = Field(alias="mayDeclineInteraction", strict=True)
    roleplay_does_not_override_boundaries: bool = Field(
        alias="roleplayDoesNotOverrideBoundaries", strict=True
    )
    current_reality_overrides_stored_persona: bool = Field(
        alias="currentRealityOverridesStoredPersona", strict=True
    )
    notes: str | None = None


class WindowStateCard(ContinuityModel):
    """A dated context note, not a command list or task queue."""

    kind: Literal["window_state_card"]
    topic: NonEmptyText
    confirmed_facts: tuple[NonEmptyText, ...] = Field(alias="confirmedFacts")
    tone_and_mood: NonEmptyText | None = Field(default=None, alias="toneAndMood")
    open_threads: tuple[NonEmptyText, ...] = Field(alias="openThreads")
    anchors: tuple[NonEmptyText, ...]
    avoid_assumptions: tuple[NonEmptyText, ...] = Field(alias="avoidAssumptions")
    generated_at: datetime = Field(alias="generatedAt")
    source_window: NonEmptyText = Field(alias="sourceWindow")


class LifeLine(ContinuityModel):
    """A bounded timeline whose coverage always has explicit dates."""

    kind: Literal["lifeline"]
    coverage_start: date = Field(alias="coverageStart")
    coverage_end: date = Field(alias="coverageEnd")
    generated_at: datetime = Field(alias="generatedAt")
    recent_events: tuple[NonEmptyText, ...] = Field(alias="recentEvents")
    active_projects: tuple[NonEmptyText, ...] = Field(alias="activeProjects")
    current_concerns: tuple[NonEmptyText, ...] = Field(alias="currentConcerns")

    @model_validator(mode="after")
    def validate_coverage_range(self) -> LifeLine:
        if self.coverage_end < self.coverage_start:
            raise ValueError("coverageEnd must not be earlier than coverageStart")
        return self


class MemoryCandidate(ContinuityModel):
    """A reviewable proposal that never enters a handoff by itself."""

    kind: Literal["memory_candidate"]
    content: NonEmptyText
    category: NonEmptyText
    source: NonEmptyText
    rationale: NonEmptyText
    confidence: float = Field(ge=0, le=1)
    status: MemoryCandidateStatus
    reviewed_at: datetime | None = Field(default=None, alias="reviewedAt")

    @model_validator(mode="after")
    def validate_review_state(self) -> MemoryCandidate:
        if self.status == "proposed" and self.reviewed_at is not None:
            raise ValueError("proposed memory candidate must not set reviewedAt")
        if self.status in {"accepted", "rejected"} and self.reviewed_at is None:
            raise ValueError("accepted or rejected memory candidate requires reviewedAt")
        return self


class RecallDecision(ContinuityModel):
    """A model-agnostic record of a recall choice, not a permission grant."""

    kind: Literal["recall_decision"]
    action: RecallAction
    reason: NonEmptyText
    requested_scopes: tuple[ScopeName, ...] = Field(alias="requestedScopes")
    selected_memory_ids: tuple[DocumentId, ...] = Field(alias="selectedMemoryIds")
    generated_at: datetime = Field(alias="generatedAt")

    @model_validator(mode="after")
    def validate_selection(self) -> RecallDecision:
        if self.action == "none" and self.selected_memory_ids:
            raise ValueError("none recall action must not set selectedMemoryIds")
        if self.action != "none" and not self.selected_memory_ids:
            raise ValueError("recall action requires selectedMemoryIds")
        if len(set(self.selected_memory_ids)) != len(self.selected_memory_ids):
            raise ValueError("selectedMemoryIds must not contain duplicates")
        return self


class MaintenanceChannel(ContinuityModel):
    """A vendor-neutral boundary between live replies and maintenance work."""

    kind: Literal["maintenance_channel"]
    purpose: NonEmptyText
    allowed_outputs: tuple[NonEmptyText, ...] = Field(alias="allowedOutputs", min_length=1)
    requires_human_review: bool = Field(alias="requiresHumanReview", strict=True)
    model_hint: NonEmptyText | None = Field(default=None, alias="modelHint")


ContinuityContract = Annotated[
    PersonaAutonomy
    | WindowStateCard
    | LifeLine
    | MemoryCandidate
    | RecallDecision
    | MaintenanceChannel,
    Field(discriminator="kind"),
]
CONTINUITY_ADAPTER: TypeAdapter[ContinuityContract] = TypeAdapter(ContinuityContract)
ContinuityRenderable: TypeAlias = PersonaAutonomy | WindowStateCard | LifeLine | MaintenanceChannel


class HandoffInclude(StrictModel):
    """Explicit selectors and sensitivity allowlist for a handoff."""

    scopes: tuple[ScopeName, ...] = ()
    core_ids: tuple[DocumentId, ...] = ()
    current_ids: tuple[DocumentId, ...] = ()
    continuity_ids: tuple[DocumentId, ...] = ()
    sensitivities: tuple[ExportSensitivity, ...] = ("public",)


class HandoffOutput(StrictModel):
    """Requested output format for a handoff."""

    format: Literal["markdown"]


def _canonical_text(value: str) -> str:
    """Normalize line endings for content digest input."""

    return value.replace("\r\n", "\n").replace("\r", "\n")


def _content_digest(value: str) -> str:
    """Return the canonical SHA-256 digest for HandoffPackage content."""

    return "sha256:" + hashlib.sha256(_canonical_text(value).encode("utf-8")).hexdigest()


class HandoffContent(StrictModel):
    """Canonical, purpose-scoped content carried by a HandoffPackage."""

    media_type: ContentMediaType
    body: Annotated[str, StringConstraints(min_length=1)]
    digest: ContentDigest

    @field_validator("body", mode="before")
    @classmethod
    def normalize_line_endings(cls, value: object) -> object:
        if isinstance(value, str):
            return _canonical_text(value)
        return value

    @model_validator(mode="after")
    def validate_digest(self) -> HandoffContent:
        if not self.body.strip():
            raise ValueError("content body must not be blank")
        if self.digest != _content_digest(self.body):
            raise ValueError("content digest does not match body")
        return self


class HandoffProvenance(StrictModel):
    """Approval and producer status required at the external artifact boundary."""

    producer: Literal["home-framework"]
    authority_status: Literal["reviewed"]
    approval_status: Literal["user-approved"]


class HandoffPackage(StrictModel):
    """Immutable, provider-agnostic artifact consumed by future Handoff Adapters."""

    package_schema: PackageSchemaVersion
    handoff_id: DocumentId
    handoff_schema: SchemaVersion
    purpose: NonEmptyText
    context_date: date
    created_at: datetime
    source_fingerprint: Sha256Fingerprint
    content: HandoffContent
    provenance: HandoffProvenance

    @field_validator("created_at", mode="after")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        return value.astimezone(UTC)

    def canonical_json(self) -> str:
        """Serialize this package deterministically as canonical JSON."""

        return json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    def canonical_digest(self) -> str:
        """Return the SHA-256 digest of the canonical package serialization."""

        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


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
