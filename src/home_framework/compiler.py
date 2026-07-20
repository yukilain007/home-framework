"""Deterministically select reviewed authority documents for a handoff."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date

from home_framework.models import CoreDocument, CurrentDocument, HandoffDocument
from home_framework.repository import RepositorySnapshot

CompiledDocument = CoreDocument | CurrentDocument


class CompilationError(Exception):
    """Raised when a repository cannot be safely compiled."""


@dataclass(frozen=True, slots=True)
class CompiledContext:
    """Immutable, deterministic result consumed by renderers."""

    handoff: HandoffDocument
    documents: tuple[CompiledDocument, ...]
    as_of: date
    fingerprint: str


def _is_selected(
    document: CompiledDocument,
    handoff: HandoffDocument,
) -> bool:
    if isinstance(document, CoreDocument):
        explicit_ids = handoff.include.core_ids
    else:
        explicit_ids = handoff.include.current_ids
    return document.id in explicit_ids or bool(set(document.scope) & set(handoff.include.scopes))


def _sort_key(document: CompiledDocument) -> tuple[int, int, str]:
    kind_order = 0 if isinstance(document, CoreDocument) else 1
    return kind_order, -document.priority, document.id


def _fingerprint(
    handoff: HandoffDocument,
    documents: tuple[CompiledDocument, ...],
    as_of: date,
) -> str:
    payload = {
        "as_of": as_of.isoformat(),
        "documents": [document.model_dump(mode="json") for document in documents],
        "handoff": handoff.model_dump(mode="json"),
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def compile_context(
    snapshot: RepositorySnapshot,
    handoff_id: str,
    as_of: date,
) -> CompiledContext:
    """Compile a handoff using fail-closed selection and stable ordering."""

    if snapshot.has_errors:
        raise CompilationError("repository contains errors; compilation refused")

    handoff = next((item for item in snapshot.handoffs if item.id == handoff_id), None)
    if handoff is None:
        raise CompilationError(f"handoff {handoff_id!r} was not found")
    if "secret" in handoff.include.sensitivities:
        raise CompilationError("secret sensitivity cannot be exported")

    selected: list[CompiledDocument] = []
    for core_document in snapshot.core:
        if core_document.status != "active":
            continue
        if core_document.sensitivity not in handoff.include.sensitivities:
            continue
        if _is_selected(core_document, handoff):
            selected.append(core_document)

    for current_document in snapshot.current:
        if not current_document.is_active_on(as_of):
            continue
        if current_document.sensitivity not in handoff.include.sensitivities:
            continue
        if _is_selected(current_document, handoff):
            selected.append(current_document)

    documents = tuple(sorted(selected, key=_sort_key))
    return CompiledContext(
        handoff=handoff,
        documents=documents,
        as_of=as_of,
        fingerprint=_fingerprint(handoff, documents, as_of),
    )
