# SPDX-FileCopyrightText: 2026 Yuki
# SPDX-License-Identifier: Apache-2.0

"""Render compiled contexts without performing selection or validation."""

from __future__ import annotations

from datetime import UTC, datetime

from home_framework.compiler import CompiledContext
from home_framework.export_metadata import metadata_for_context, serialize_export_metadata
from home_framework.models import (
    CoreDocument,
    CurrentDocument,
    LifeLine,
    MaintenanceChannel,
    PersonaAutonomy,
    WindowStateCard,
)


def _render_document(document: CoreDocument | CurrentDocument) -> list[str]:
    scopes = ", ".join(f"`{scope}`" for scope in document.scope) or "none"
    return [
        f"### `{document.id}`",
        "",
        f"- Priority: `{document.priority}`",
        f"- Sensitivity: `{document.sensitivity}`",
        f"- Scope: {scopes}",
        "",
        *document.content.splitlines(),
        "",
    ]


def _render_bullets(label: str, values: tuple[str, ...]) -> list[str]:
    lines = [f"- {label}:"]
    if values:
        lines.extend(f"  - {value}" for value in values)
    else:
        lines.append("  - _None recorded._")
    return lines


def _render_continuity(contract: object) -> list[str]:
    if isinstance(contract, PersonaAutonomy):
        return [
            "### Persona autonomy anchor",
            "",
            f"- Independent judgment: `{contract.independent_judgment}`",
            f"- May disagree: `{contract.may_disagree}`",
            f"- May decline interaction: `{contract.may_decline_interaction}`",
            "- Roleplay does not override boundaries: "
            f"`{contract.roleplay_does_not_override_boundaries}`",
            "- Current reality overrides stored persona: "
            f"`{contract.current_reality_overrides_stored_persona}`",
            "- This is a judgment anchor, not a fixed roleplay script.",
            *([f"- Notes: {contract.notes}"] if contract.notes else []),
            "",
        ]
    if isinstance(contract, WindowStateCard):
        return [
            "### Window state note",
            "",
            f"- Topic: {contract.topic}",
            *_render_bullets("Confirmed facts", contract.confirmed_facts),
            *_render_bullets("Open threads", contract.open_threads),
            *_render_bullets("Anchors", contract.anchors),
            *_render_bullets("Avoid assumptions", contract.avoid_assumptions),
            f"- Tone and mood: {contract.tone_and_mood or 'Not recorded'}",
            f"- Generated at: `{contract.generated_at.isoformat()}`",
            f"- Source window: `{contract.source_window}`",
            "- This is a context note, not a command or task list.",
            "",
        ]
    if isinstance(contract, LifeLine):
        return [
            "### LifeLine",
            "",
            f"- Coverage: `{contract.coverage_start.isoformat()}` to "
            f"`{contract.coverage_end.isoformat()}`",
            f"- Generated at: `{contract.generated_at.isoformat()}`",
            *_render_bullets("Recent events", contract.recent_events),
            *_render_bullets("Active projects", contract.active_projects),
            *_render_bullets("Current concerns", contract.current_concerns),
            "",
        ]
    if isinstance(contract, MaintenanceChannel):
        return [
            "### Maintenance channel",
            "",
            f"- Purpose: {contract.purpose}",
            *_render_bullets("Allowed outputs", contract.allowed_outputs),
            f"- Requires human review: `{contract.requires_human_review}`",
            f"- Model hint: {contract.model_hint or 'None'}",
            "",
        ]
    raise TypeError(f"unsupported continuity contract {type(contract)!r}")


def render_markdown(
    compiled: CompiledContext,
    *,
    generated_at: datetime,
) -> str:
    """Render a compiled context as normalized UTF-8-ready Markdown text."""

    if generated_at.tzinfo is None or generated_at.utcoffset() is None:
        raise ValueError("generated_at must be timezone-aware")
    timestamp = generated_at.astimezone(UTC)

    core = [item for item in compiled.documents if isinstance(item, CoreDocument)]
    current = [item for item in compiled.documents if isinstance(item, CurrentDocument)]
    lines = [
        serialize_export_metadata(metadata_for_context(compiled)),
        "<!-- generated file: do not edit -->",
        "",
        f"# {compiled.handoff.title}",
        "",
        f"> {compiled.handoff.purpose}",
        "",
        "## Build metadata",
        "",
        f"- Handoff: `{compiled.handoff.id}`",
        f"- Schema version: `{compiled.handoff.schema_version}`",
        f"- Context date: `{compiled.as_of.isoformat()}`",
        f"- Generated at: `{timestamp.isoformat().replace('+00:00', 'Z')}`",
        f"- Fingerprint: `{compiled.fingerprint}`",
        "",
        "## Stable core",
        "",
    ]
    if core:
        for core_document in core:
            lines.extend(_render_document(core_document))
    else:
        lines.extend(["_No stable core selected._", ""])

    lines.extend(["## Current context", ""])
    if current:
        for current_document in current:
            lines.extend(_render_document(current_document))
    else:
        lines.extend(["_No current context selected._", ""])

    if compiled.continuity:
        lines.extend(["## Continuity context", ""])
        for contract in compiled.continuity:
            lines.extend(_render_continuity(contract))

    lines.extend(
        [
            "---",
            "",
            "Generated from reviewed authority files.",
            "Generated output is disposable and must not be edited directly.",
        ]
    )
    return "\n".join(lines) + "\n"
