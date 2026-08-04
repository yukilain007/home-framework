from pathlib import Path

from test_repository import create_layout, handoff_data, write_yaml

from home_framework.repository import load_repository


def continuity_contracts() -> list[tuple[str, dict[str, object]]]:
    return [
        (
            "persona.yaml",
            {
                "kind": "persona_autonomy",
                "schema_version": "1.0",
                "id": "persona.autonomy",
                "independentJudgment": True,
                "mayDisagree": True,
                "mayDeclineInteraction": True,
                "roleplayDoesNotOverrideBoundaries": True,
                "currentRealityOverridesStoredPersona": True,
                "notes": "An anchor, not a script.",
            },
        ),
        (
            "window.yaml",
            {
                "kind": "window_state_card",
                "schema_version": "1.0",
                "id": "window.current",
                "topic": "Fictional project handoff",
                "confirmedFacts": ["The migration is under review."],
                "toneAndMood": "Focused",
                "openThreads": ["Review the migration notes."],
                "anchors": ["Use the approved project scope."],
                "avoidAssumptions": ["Do not infer unstated motivations."],
                "generatedAt": "2026-08-03T10:00:00Z",
                "sourceWindow": "project-window-2026-08-03",
            },
        ),
        (
            "lifeline.yaml",
            {
                "kind": "lifeline",
                "schema_version": "1.0",
                "id": "timeline.recent",
                "coverageStart": "2026-08-01",
                "coverageEnd": "2026-08-03",
                "generatedAt": "2026-08-03T10:00:00Z",
                "recentEvents": ["A review meeting occurred on 2026-08-02."],
                "activeProjects": ["Fictional migration"],
                "currentConcerns": ["Keep the handoff scoped."],
            },
        ),
        (
            "memory.yaml",
            {
                "kind": "memory_candidate",
                "schema_version": "1.0",
                "id": "candidate.preference",
                "content": "A proposal that needs human review.",
                "category": "preference",
                "source": "conversation note",
                "rationale": "It may help future project handoffs.",
                "confidence": 0.6,
                "status": "proposed",
            },
        ),
        (
            "recall.yaml",
            {
                "kind": "recall_decision",
                "schema_version": "1.0",
                "id": "recall.project",
                "action": "reuse",
                "reason": "Reuse the reviewed candidate for audit inspection only.",
                "requestedScopes": ["project"],
                "selectedMemoryIds": ["candidate.preference"],
                "generatedAt": "2026-08-03T10:00:00Z",
            },
        ),
        (
            "maintenance.yaml",
            {
                "kind": "maintenance_channel",
                "schema_version": "1.0",
                "id": "maintenance.review",
                "purpose": "Separate maintenance review from live replies.",
                "allowedOutputs": ["proposals", "validation reports"],
                "requiresHumanReview": True,
                "modelHint": "model-agnostic",
            },
        ),
    ]


def test_optional_continuity_contracts_load_and_cross_reference(tmp_path: Path) -> None:
    create_layout(tmp_path)
    (tmp_path / "continuity").mkdir()
    for filename, data in continuity_contracts():
        write_yaml(tmp_path, f"continuity/{filename}", data)

    handoff = handoff_data()
    handoff["include"]["continuity_ids"] = [
        "persona.autonomy",
        "window.current",
        "timeline.recent",
        "candidate.preference",
        "recall.project",
        "maintenance.review",
    ]
    write_yaml(tmp_path, "handoffs/project.yaml", handoff)

    snapshot = load_repository(tmp_path)

    assert not snapshot.has_errors
    assert snapshot.continuity_count == 6
    assert {item.kind for item in snapshot.continuity_contracts} == {
        "persona_autonomy",
        "window_state_card",
        "lifeline",
        "memory_candidate",
        "recall_decision",
        "maintenance_channel",
    }
    assert snapshot.recall_decisions[0].selected_memory_ids == ("candidate.preference",)


def test_continuity_contracts_are_optional_for_existing_workspaces(tmp_path: Path) -> None:
    create_layout(tmp_path)

    snapshot = load_repository(tmp_path)

    assert not snapshot.has_errors
    assert snapshot.continuity_contracts == ()


def test_unknown_continuity_kind_is_reported(tmp_path: Path) -> None:
    create_layout(tmp_path)
    write_yaml(
        tmp_path,
        "continuity/unknown.yaml",
        {"kind": "unknown", "schema_version": "1.0", "id": "unknown.contract"},
    )

    snapshot = load_repository(tmp_path)

    assert any(item.code == "continuity_kind_unknown" for item in snapshot.diagnostics)


def test_missing_continuity_reference_is_reported(tmp_path: Path) -> None:
    create_layout(tmp_path)
    handoff = handoff_data()
    handoff["include"]["continuity_ids"] = ["missing.contract"]
    write_yaml(tmp_path, "handoffs/project.yaml", handoff)

    snapshot = load_repository(tmp_path)

    assert any(item.code == "missing_continuity_reference" for item in snapshot.diagnostics)


def test_recall_decision_requires_existing_memory_candidate(tmp_path: Path) -> None:
    create_layout(tmp_path)
    write_yaml(
        tmp_path,
        "continuity/recall.yaml",
        {
            "kind": "recall_decision",
            "schema_version": "1.0",
            "id": "recall.missing",
            "action": "reuse",
            "reason": "Audit test.",
            "requestedScopes": ["project"],
            "selectedMemoryIds": ["missing.candidate"],
            "generatedAt": "2026-08-03T10:00:00Z",
        },
    )

    snapshot = load_repository(tmp_path)

    assert any(item.code == "missing_memory_candidate_reference" for item in snapshot.diagnostics)
