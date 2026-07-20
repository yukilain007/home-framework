"""Render compiled contexts without performing selection or validation."""

from __future__ import annotations

from datetime import UTC, datetime

from home_framework.compiler import CompiledContext
from home_framework.export_metadata import metadata_for_context, serialize_export_metadata
from home_framework.models import CoreDocument, CurrentDocument


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


def render_markdown(
    compiled: CompiledContext,
    *,
    generated_at: datetime | None = None,
) -> str:
    """Render a compiled context as normalized UTF-8-ready Markdown text."""

    timestamp = generated_at or datetime.now(UTC)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    timestamp = timestamp.astimezone(UTC).replace(microsecond=0)

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

    lines.extend(
        [
            "---",
            "",
            "Generated from reviewed authority files.",
            "Generated output is disposable and must not be edited directly.",
        ]
    )
    return "\n".join(lines) + "\n"
