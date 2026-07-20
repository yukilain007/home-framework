from dataclasses import FrozenInstanceError, replace
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from home_framework.compiler import CompilationError, compile_context
from home_framework.models import CandidateDocument, CoreDocument, CurrentDocument, HandoffDocument
from home_framework.renderer import render_markdown
from home_framework.repository import Diagnostic, RepositorySnapshot


def core(
    document_id: str,
    *,
    status: str = "active",
    sensitivity: str = "public",
    scopes: tuple[str, ...] = ("project",),
    priority: int = 50,
    content: str | None = None,
) -> CoreDocument:
    return CoreDocument.model_validate(
        {
            "kind": "core",
            "schema_version": "1.0",
            "id": document_id,
            "content": content or f"Fictional authority content for {document_id}.",
            "status": status,
            "sensitivity": sensitivity,
            "scope": list(scopes),
            "priority": priority,
            "source": {"type": "human_authored", "reference": None},
            "created_at": "2026-07-20",
            "updated_at": "2026-07-20",
        }
    )


def current(
    document_id: str,
    *,
    status: str = "active",
    sensitivity: str = "public",
    scopes: tuple[str, ...] = ("project",),
    priority: int = 50,
    valid_from: str = "2026-07-20",
    expires_at: str | None = None,
) -> CurrentDocument:
    return CurrentDocument.model_validate(
        {
            **core(
                document_id,
                status=status,
                sensitivity=sensitivity,
                scopes=scopes,
                priority=priority,
            ).model_dump(mode="json"),
            "kind": "current",
            "valid_from": valid_from,
            "expires_at": expires_at,
        }
    )


def candidate() -> CandidateDocument:
    return CandidateDocument.model_validate(
        {
            "kind": "candidate",
            "schema_version": "1.0",
            "id": "candidate.fictional",
            "proposed_kind": "core",
            "content": "A fictional candidate that must never compile.",
            "sensitivity": "public",
            "scope": ["project"],
            "source": {"type": "human_authored", "reference": None},
            "created_at": "2026-07-20",
            "decision": {"reviewed": True, "action": "approve", "reviewed_at": "2026-07-20"},
        }
    )


def handoff(
    *,
    scopes: tuple[str, ...] = ("project",),
    core_ids: tuple[str, ...] = (),
    current_ids: tuple[str, ...] = (),
    sensitivities: tuple[str, ...] = ("public",),
) -> HandoffDocument:
    return HandoffDocument.model_validate(
        {
            "kind": "handoff",
            "schema_version": "1.0",
            "id": "project.execution",
            "title": "Fictional project execution",
            "purpose": "Continue a fictional implementation from reviewed context.",
            "include": {
                "scopes": list(scopes),
                "core_ids": list(core_ids),
                "current_ids": list(current_ids),
                "sensitivities": list(sensitivities),
            },
            "output": {"format": "markdown"},
        }
    )


def snapshot(
    *,
    core_documents: tuple[CoreDocument, ...] = (),
    current_documents: tuple[CurrentDocument, ...] = (),
    candidates: tuple[CandidateDocument, ...] = (),
    selected_handoff: HandoffDocument | None = None,
    diagnostics: tuple[Diagnostic, ...] = (),
) -> RepositorySnapshot:
    return RepositorySnapshot(
        root=Path("/fictional/repository"),
        core=core_documents,
        current=current_documents,
        candidates=candidates,
        handoffs=(selected_handoff or handoff(),),
        diagnostics=diagnostics,
    )


def compile_snapshot(repository: RepositorySnapshot):  # type: ignore[no-untyped-def]
    return compile_context(repository, "project.execution", date(2026, 7, 20))


def test_repository_errors_refuse_compilation() -> None:
    repository = snapshot(diagnostics=(Diagnostic("error", "broken", "file.yaml", None, "broken"),))

    with pytest.raises(CompilationError, match="repository contains errors"):
        compile_snapshot(repository)


def test_missing_handoff_refuses_compilation() -> None:
    repository = snapshot()

    with pytest.raises(CompilationError, match="handoff 'missing.handoff' was not found"):
        compile_context(repository, "missing.handoff", date(2026, 7, 20))


def test_empty_selectors_default_to_no_context() -> None:
    repository = snapshot(
        core_documents=(core("core.visible"),),
        current_documents=(current("current.visible"),),
        selected_handoff=handoff(scopes=()),
    )

    compiled = compile_snapshot(repository)

    assert compiled.documents == ()


def test_candidate_is_never_selected() -> None:
    compiled = compile_snapshot(snapshot(candidates=(candidate(),)))

    assert compiled.documents == ()


@pytest.mark.parametrize(
    "document",
    [
        current("current.expired", valid_from="2026-07-01", expires_at="2026-07-19"),
        current("current.future", valid_from="2026-07-21"),
        current("current.inactive", status="inactive"),
    ],
)
def test_invalid_current_is_excluded(document: CurrentDocument) -> None:
    compiled = compile_snapshot(snapshot(current_documents=(document,)))

    assert compiled.documents == ()


def test_inactive_core_is_excluded() -> None:
    compiled = compile_snapshot(
        snapshot(core_documents=(core("core.inactive", status="inactive"),))
    )

    assert compiled.documents == ()


def test_private_is_excluded_by_default() -> None:
    compiled = compile_snapshot(
        snapshot(core_documents=(core("core.private", sensitivity="private"),))
    )

    assert compiled.documents == ()


def test_private_is_selected_when_explicitly_allowed() -> None:
    repository = snapshot(
        core_documents=(core("core.private", sensitivity="private"),),
        selected_handoff=handoff(sensitivities=("public", "private")),
    )

    compiled = compile_snapshot(repository)

    assert [document.id for document in compiled.documents] == ["core.private"]


def test_secret_allowlist_refuses_compilation() -> None:
    safe_handoff = handoff()
    unsafe_include = safe_handoff.include.model_copy(update={"sensitivities": ("public", "secret")})
    repository = snapshot(
        core_documents=(core("core.secret", sensitivity="secret"),),
        selected_handoff=safe_handoff.model_copy(update={"include": unsafe_include}),
    )

    with pytest.raises(CompilationError, match="secret sensitivity cannot be exported"):
        compile_snapshot(repository)


def test_secret_scope_match_cannot_select_secret_content() -> None:
    compiled = compile_snapshot(
        snapshot(core_documents=(core("core.secret", sensitivity="secret"),))
    )

    assert compiled.documents == ()


def test_explicit_secret_id_cannot_select_secret_content() -> None:
    repository = snapshot(
        core_documents=(core("core.secret", sensitivity="secret", scopes=("other",)),),
        selected_handoff=handoff(scopes=(), core_ids=("core.secret",)),
    )

    compiled = compile_snapshot(repository)

    assert compiled.documents == ()


def test_mixed_sensitivities_select_only_explicitly_allowed_content() -> None:
    repository = snapshot(
        core_documents=(
            core("core.public", sensitivity="public"),
            core("core.private", sensitivity="private"),
            core("core.secret", sensitivity="secret"),
        ),
        selected_handoff=handoff(sensitivities=("public", "private")),
    )

    compiled = compile_snapshot(repository)

    assert [document.id for document in compiled.documents] == [
        "core.private",
        "core.public",
    ]


def test_explicit_id_or_scope_intersection_selects_documents() -> None:
    repository = snapshot(
        core_documents=(
            core("core.scope", scopes=("project",)),
            core("core.explicit", scopes=("conversation",)),
            core("core.other", scopes=("conversation",)),
        ),
        current_documents=(current("current.explicit", scopes=("conversation",)),),
        selected_handoff=handoff(
            scopes=("project",),
            core_ids=("core.explicit",),
            current_ids=("current.explicit",),
        ),
    )

    compiled = compile_snapshot(repository)

    assert [document.id for document in compiled.documents] == [
        "core.explicit",
        "core.scope",
        "current.explicit",
    ]


@pytest.mark.parametrize(
    "document",
    [
        core("core.inactive-explicit", status="inactive", scopes=("other",)),
        core("core.archived-explicit", status="archived", scopes=("other",)),
        current("current.inactive-explicit", status="inactive", scopes=("other",)),
        current("current.archived-explicit", status="archived", scopes=("other",)),
        current(
            "current.future-explicit",
            scopes=("other",),
            valid_from="2026-07-21",
        ),
        current(
            "current.expired-explicit",
            scopes=("other",),
            valid_from="2026-07-01",
            expires_at="2026-07-19",
        ),
    ],
)
def test_explicit_id_cannot_bypass_lifecycle_filters(
    document: CoreDocument | CurrentDocument,
) -> None:
    if isinstance(document, CoreDocument):
        repository = snapshot(
            core_documents=(document,),
            selected_handoff=handoff(scopes=(), core_ids=(document.id,)),
        )
    else:
        repository = snapshot(
            current_documents=(document,),
            selected_handoff=handoff(scopes=(), current_ids=(document.id,)),
        )

    assert compile_snapshot(repository).documents == ()


def test_documents_are_sorted_by_kind_priority_and_id() -> None:
    repository = snapshot(
        core_documents=(
            core("core.low", priority=10),
            core("core.zed", priority=90),
            core("core.alpha", priority=90),
        ),
        current_documents=(
            current("current.low", priority=10),
            current("current.high", priority=80),
        ),
    )

    compiled = compile_snapshot(repository)

    assert [document.id for document in compiled.documents] == [
        "core.alpha",
        "core.zed",
        "core.low",
        "current.high",
        "current.low",
    ]


def test_fingerprint_is_stable_and_excludes_generated_time() -> None:
    repository = snapshot(core_documents=(core("core.stable"),))

    first = compile_snapshot(repository)
    second = compile_snapshot(repository)

    assert first.fingerprint == second.fingerprint
    assert len(first.fingerprint) == 64
    assert first.documents == second.documents


def test_content_change_changes_fingerprint() -> None:
    first = compile_snapshot(snapshot(core_documents=(core("core.stable", content="First"),)))
    second = compile_snapshot(snapshot(core_documents=(core("core.stable", content="Second"),)))

    assert first.fingerprint != second.fingerprint


def test_fingerprint_does_not_depend_on_repository_traversal_order() -> None:
    alpha = core("core.alpha", priority=50)
    zed = core("core.zed", priority=50)

    first = compile_snapshot(snapshot(core_documents=(alpha, zed)))
    second = compile_snapshot(snapshot(core_documents=(zed, alpha)))

    assert first.fingerprint == second.fingerprint


def test_fingerprint_does_not_depend_on_yaml_key_order() -> None:
    original = core("core.keys")
    reversed_data = dict(reversed(list(original.model_dump(mode="json").items())))
    reconstructed = CoreDocument.model_validate(reversed_data)

    first = compile_snapshot(snapshot(core_documents=(original,)))
    second = compile_snapshot(snapshot(core_documents=(reconstructed,)))

    assert first.fingerprint == second.fingerprint


def test_fingerprint_does_not_depend_on_absolute_repository_path() -> None:
    repository = snapshot(core_documents=(core("core.path"),))

    first = compile_snapshot(replace(repository, root=Path("/fictional/one")))
    second = compile_snapshot(replace(repository, root=Path("/fictional/two")))

    assert first.fingerprint == second.fingerprint


def test_handoff_change_changes_fingerprint() -> None:
    repository = snapshot(core_documents=(core("core.handoff"),))
    changed_handoff = repository.handoffs[0].model_copy(update={"purpose": "A changed purpose."})

    first = compile_snapshot(repository)
    second = compile_snapshot(replace(repository, handoffs=(changed_handoff,)))

    assert first.fingerprint != second.fingerprint


def test_context_date_change_changes_fingerprint() -> None:
    repository = snapshot(core_documents=(core("core.date"),))

    first = compile_context(repository, "project.execution", date(2026, 7, 20))
    second = compile_context(repository, "project.execution", date(2026, 7, 21))

    assert first.fingerprint != second.fingerprint


def test_compiled_context_is_immutable() -> None:
    compiled = compile_snapshot(snapshot())

    with pytest.raises(FrozenInstanceError):
        compiled.as_of = date(2026, 7, 21)  # type: ignore[misc]


def test_markdown_renderer_contains_metadata_and_sections() -> None:
    compiled = compile_snapshot(
        snapshot(
            core_documents=(core("core.rendered", content="Stable fictional guidance."),),
            current_documents=(current("current.rendered"),),
        )
    )

    rendered = render_markdown(
        compiled,
        generated_at=datetime(2026, 7, 20, 12, 0, tzinfo=UTC),
    )

    first_line, second_line, *_ = rendered.splitlines()
    assert first_line.startswith("<!-- home-framework-export: ")
    assert second_line == "<!-- generated file: do not edit -->"
    assert "# Fictional project execution" in rendered
    assert "- Handoff: `project.execution`" in rendered
    assert "- Context date: `2026-07-20`" in rendered
    assert f"- Fingerprint: `{compiled.fingerprint}`" in rendered
    assert "## Stable core" in rendered
    assert "Stable fictional guidance." in rendered
    assert "## Current context" in rendered
    assert rendered.endswith("Generated output is disposable and must not be edited directly.\n")


def test_markdown_renderer_marks_empty_sections() -> None:
    rendered = render_markdown(
        compile_snapshot(snapshot()),
        generated_at=datetime(2026, 7, 20, 12, 0, tzinfo=UTC),
    )

    assert "_No stable core selected._" in rendered
    assert "_No current context selected._" in rendered
