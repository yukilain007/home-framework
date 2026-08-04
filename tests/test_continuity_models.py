from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from home_framework.models import (
    LifeLine,
    MaintenanceChannel,
    MemoryCandidate,
    PersonaAutonomy,
    RecallDecision,
    WindowStateCard,
)


def test_persona_autonomy_uses_explicit_independence_flags() -> None:
    model = PersonaAutonomy.model_validate(
        {
            "kind": "persona_autonomy",
            "schema_version": "1.0",
            "id": "persona.default",
            "independentJudgment": True,
            "mayDisagree": True,
            "mayDeclineInteraction": True,
            "roleplayDoesNotOverrideBoundaries": True,
            "currentRealityOverridesStoredPersona": True,
            "notes": "An anchor, not a script.",
        }
    )

    assert model.independent_judgment is True
    assert model.model_dump(by_alias=True)["currentRealityOverridesStoredPersona"] is True


def test_window_state_card_is_a_note_with_explicit_source_window() -> None:
    model = WindowStateCard.model_validate(
        {
            "kind": "window_state_card",
            "schema_version": "1.0",
            "id": "window.current",
            "topic": "Fictional release handoff",
            "confirmedFacts": ["The build is deterministic."],
            "toneAndMood": "focused",
            "openThreads": ["Review the generated Markdown."],
            "anchors": ["User approval is required."],
            "avoidAssumptions": ["Do not infer unstated deadlines."],
            "generatedAt": "2026-08-03T10:00:00Z",
            "sourceWindow": "2026-08-03 morning review",
        }
    )

    assert model.topic == "Fictional release handoff"
    assert model.confirmed_facts == ("The build is deterministic.",)
    assert model.source_window == "2026-08-03 morning review"


def test_lifeline_requires_an_ordered_explicit_coverage_range() -> None:
    model = LifeLine.model_validate(
        {
            "kind": "lifeline",
            "schema_version": "1.0",
            "id": "lifeline.current",
            "coverageStart": "2026-08-01",
            "coverageEnd": "2026-08-03",
            "generatedAt": "2026-08-03T10:00:00Z",
            "recentEvents": ["2026-08-02: fictional review completed"],
            "activeProjects": ["HOME continuity contracts"],
            "currentConcerns": ["Keep candidates out of handoffs"],
        }
    )

    assert model.coverage_start == date(2026, 8, 1)
    assert model.coverage_end == date(2026, 8, 3)

    invalid = model.model_dump(by_alias=True)
    invalid["coverageEnd"] = "2026-07-31"
    with pytest.raises(ValidationError, match="coverageEnd"):
        LifeLine.model_validate(invalid)


def test_memory_candidate_never_treats_accepted_as_automatic_promotion() -> None:
    candidate = MemoryCandidate.model_validate(
        {
            "kind": "memory_candidate",
            "schema_version": "1.0",
            "id": "memory.candidate.one",
            "content": "A possible fictional preference.",
            "category": "preference",
            "source": "user-provided draft",
            "rationale": "May help a future handoff.",
            "confidence": 0.8,
            "status": "accepted",
            "reviewedAt": "2026-08-03T10:00:00Z",
        }
    )

    assert candidate.status == "accepted"
    assert candidate.reviewed_at == datetime(2026, 8, 3, 10, tzinfo=UTC)


def test_memory_candidate_review_timestamp_matches_status() -> None:
    with pytest.raises(ValidationError, match="reviewedAt"):
        MemoryCandidate.model_validate(
            {
                "kind": "memory_candidate",
                "schema_version": "1.0",
                "id": "memory.proposed",
                "content": "A proposal.",
                "category": "fact",
                "source": "draft",
                "rationale": "Needs review.",
                "confidence": 0.4,
                "status": "proposed",
                "reviewedAt": "2026-08-03T10:00:00Z",
            }
        )


def test_recall_decision_none_cannot_select_memories() -> None:
    with pytest.raises(ValidationError, match="selectedMemoryIds"):
        RecallDecision.model_validate(
            {
                "kind": "recall_decision",
                "schema_version": "1.0",
                "id": "recall.none",
                "action": "none",
                "reason": "No reviewed memory is needed.",
                "requestedScopes": ["project"],
                "selectedMemoryIds": ["memory.one"],
                "generatedAt": "2026-08-03T10:00:00Z",
            }
        )


def test_maintenance_channel_requires_outputs_and_preserves_review_boundary() -> None:
    channel = MaintenanceChannel.model_validate(
        {
            "kind": "maintenance_channel",
            "schema_version": "1.0",
            "id": "channel.review",
            "purpose": "Prepare a reviewable draft separately from live replies.",
            "allowedOutputs": ["draft", "diagnostic"],
            "requiresHumanReview": True,
            "modelHint": None,
        }
    )

    assert channel.allowed_outputs == ("draft", "diagnostic")
    assert channel.requires_human_review is True


def test_continuity_models_reject_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        PersonaAutonomy.model_validate(
            {
                "kind": "persona_autonomy",
                "schema_version": "1.0",
                "id": "persona.default",
                "independentJudgment": True,
                "mayDisagree": True,
                "mayDeclineInteraction": True,
                "roleplayDoesNotOverrideBoundaries": True,
                "currentRealityOverridesStoredPersona": True,
                "unexpected": "no",
            }
        )


def test_persona_flags_are_strict_booleans() -> None:
    with pytest.raises(ValidationError):
        PersonaAutonomy.model_validate(
            {
                "kind": "persona_autonomy",
                "schema_version": "1.0",
                "id": "persona.strict",
                "independentJudgment": "true",
                "mayDisagree": True,
                "mayDeclineInteraction": True,
                "roleplayDoesNotOverrideBoundaries": True,
                "currentRealityOverridesStoredPersona": True,
            }
        )
