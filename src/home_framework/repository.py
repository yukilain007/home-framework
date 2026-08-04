# SPDX-FileCopyrightText: 2026 Yuki
# SPDX-License-Identifier: Apache-2.0

"""Discover, parse, and cross-validate HOME authority repositories."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

import yaml
from packaging.version import Version
from pydantic import BaseModel, ValidationError

from home_framework import __version__
from home_framework.models import (
    CandidateDocument,
    ContinuityContract,
    CoreDocument,
    CurrentDocument,
    Document,
    HandoffDocument,
    LifeLine,
    MaintenanceChannel,
    MemoryCandidate,
    PersonaAutonomy,
    RecallDecision,
    WindowStateCard,
    WorkspaceManifest,
)
from home_framework.path_safety import PathSafetyError, first_symlink_component

Severity = Literal["info", "warning", "error"]


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """A stable, user-facing repository diagnostic."""

    severity: Severity
    code: str
    path: str
    location: str | None
    message: str


@dataclass(frozen=True, slots=True)
class RepositorySnapshot:
    """Immutable result of loading every recognized repository document."""

    root: Path
    core: tuple[CoreDocument, ...]
    current: tuple[CurrentDocument, ...]
    candidates: tuple[CandidateDocument, ...]
    handoffs: tuple[HandoffDocument, ...]
    diagnostics: tuple[Diagnostic, ...]
    manifest: WorkspaceManifest | None = None
    document_paths: tuple[tuple[str, str], ...] = ()
    persona_autonomy: tuple[PersonaAutonomy, ...] = ()
    window_state_cards: tuple[WindowStateCard, ...] = ()
    lifelines: tuple[LifeLine, ...] = ()
    continuity_memory_candidates: tuple[MemoryCandidate, ...] = ()
    recall_decisions: tuple[RecallDecision, ...] = ()
    maintenance_channels: tuple[MaintenanceChannel, ...] = ()

    @property
    def has_errors(self) -> bool:
        return any(item.severity == "error" for item in self.diagnostics)

    @property
    def document_count(self) -> int:
        return len(self.core) + len(self.current) + len(self.candidates) + len(self.handoffs)

    @property
    def continuity_contracts(self) -> tuple[ContinuityContract, ...]:
        """Return all continuity contracts in stable kind and ID order."""

        return tuple(
            sorted(
                (
                    *self.persona_autonomy,
                    *self.window_state_cards,
                    *self.lifelines,
                    *self.continuity_memory_candidates,
                    *self.recall_decisions,
                    *self.maintenance_channels,
                ),
                key=lambda item: (item.kind, item.id),
            )
        )

    @property
    def continuity_count(self) -> int:
        return len(self.continuity_contracts)

    def path_for(self, document_id: str, fallback: str) -> str:
        """Return the loaded workspace-relative source path for a document ID."""

        return next(
            (path for loaded_id, path in self.document_paths if loaded_id == document_id),
            fallback,
        )


@dataclass(frozen=True, slots=True)
class _DirectorySpec:
    relative: str
    kind: str
    model: type[BaseModel]


_DIRECTORIES = (
    _DirectorySpec("sources/core", "core", CoreDocument),
    _DirectorySpec("sources/current", "current", CurrentDocument),
    _DirectorySpec("candidates", "candidate", CandidateDocument),
    _DirectorySpec("handoffs", "handoff", HandoffDocument),
)

_CONTINUITY_MODELS: dict[str, type[BaseModel]] = {
    "persona_autonomy": PersonaAutonomy,
    "window_state_card": WindowStateCard,
    "lifeline": LifeLine,
    "memory_candidate": MemoryCandidate,
    "recall_decision": RecallDecision,
    "maintenance_channel": MaintenanceChannel,
}


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _first_symlink_component(path: Path, root: Path) -> Path | None:
    """Return the first symbolic-link component between root and path."""

    current = root
    for part in path.relative_to(root).parts:
        current /= part
        if current.is_symlink():
            return current
    return None


def _yaml_location(error: yaml.YAMLError) -> str | None:
    mark = getattr(error, "problem_mark", None)
    if mark is None:
        return None
    return f"line {mark.line + 1}, column {mark.column + 1}"


def _validation_location(parts: tuple[str | int, ...]) -> str | None:
    if not parts:
        return None
    return ".".join(str(part) for part in parts)


def _load_manifest(
    root: Path,
    diagnostics: list[Diagnostic],
) -> WorkspaceManifest | None:
    path = root / "home.yaml"
    if path.is_symlink():
        diagnostics.append(
            Diagnostic(
                "error",
                "manifest_symlink",
                "home.yaml",
                None,
                "workspace manifest must not be a symbolic link",
            )
        )
        return None
    if not path.exists():
        diagnostics.append(
            Diagnostic(
                "error",
                "missing_manifest",
                "home.yaml",
                None,
                "workspace manifest is missing",
            )
        )
        return None
    if not path.is_file():
        diagnostics.append(
            Diagnostic(
                "error",
                "manifest_path_invalid",
                "home.yaml",
                None,
                "workspace manifest path is not a regular file",
            )
        )
        return None

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError) as error:
        diagnostics.append(Diagnostic("error", "manifest_read", "home.yaml", None, str(error)))
        return None
    except yaml.YAMLError as error:
        diagnostics.append(
            Diagnostic(
                "error",
                "manifest_yaml_syntax",
                "home.yaml",
                _yaml_location(error),
                str(error).splitlines()[0],
            )
        )
        return None

    if not isinstance(raw, dict):
        diagnostics.append(
            Diagnostic(
                "error",
                "manifest_root_not_mapping",
                "home.yaml",
                None,
                "workspace manifest root must be a mapping",
            )
        )
        return None

    try:
        return WorkspaceManifest.model_validate(raw)
    except ValidationError as error:
        for issue in error.errors(include_url=False):
            diagnostics.append(
                Diagnostic(
                    "error",
                    "manifest_schema_validation",
                    "home.yaml",
                    _validation_location(issue["loc"]),
                    str(issue["msg"]),
                )
            )
        return None


def _load_file(
    path: Path,
    root: Path,
    spec: _DirectorySpec,
    diagnostics: list[Diagnostic],
) -> Document | None:
    relative_path = _relative(path, root)
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError) as error:
        diagnostics.append(Diagnostic("error", "file_read", relative_path, None, str(error)))
        return None
    except yaml.YAMLError as error:
        diagnostics.append(
            Diagnostic(
                "error",
                "yaml_syntax",
                relative_path,
                _yaml_location(error),
                str(error).splitlines()[0],
            )
        )
        return None

    if not isinstance(raw, dict):
        diagnostics.append(
            Diagnostic(
                "error",
                "root_not_mapping",
                relative_path,
                None,
                "YAML document root must be a mapping",
            )
        )
        return None

    actual_kind = raw.get("kind")
    if actual_kind is not None and actual_kind != spec.kind:
        diagnostics.append(
            Diagnostic(
                "error",
                "kind_mismatch",
                relative_path,
                "kind",
                f"directory requires kind {spec.kind!r}, found {actual_kind!r}",
            )
        )
        return None

    try:
        document = spec.model.model_validate(raw)
    except ValidationError as error:
        for issue in error.errors(include_url=False):
            location = _validation_location(issue["loc"])
            diagnostics.append(
                Diagnostic(
                    "error",
                    "schema_validation",
                    relative_path,
                    location,
                    str(issue["msg"]),
                )
            )
        return None
    return cast(Document, document)


def _load_continuity_file(
    path: Path,
    root: Path,
    diagnostics: list[Diagnostic],
) -> ContinuityContract | None:
    """Load one optional continuity contract selected by its explicit kind."""

    relative_path = _relative(path, root)
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError) as error:
        diagnostics.append(Diagnostic("error", "file_read", relative_path, None, str(error)))
        return None
    except yaml.YAMLError as error:
        diagnostics.append(
            Diagnostic(
                "error",
                "yaml_syntax",
                relative_path,
                _yaml_location(error),
                str(error).splitlines()[0],
            )
        )
        return None

    if not isinstance(raw, dict):
        diagnostics.append(
            Diagnostic(
                "error",
                "continuity_root_not_mapping",
                relative_path,
                None,
                "continuity contract root must be a mapping",
            )
        )
        return None

    kind = raw.get("kind")
    model = _CONTINUITY_MODELS.get(kind) if isinstance(kind, str) else None
    if model is None:
        diagnostics.append(
            Diagnostic(
                "error",
                "continuity_kind_unknown",
                relative_path,
                "kind",
                f"unsupported continuity contract kind {kind!r}",
            )
        )
        return None

    try:
        return cast(ContinuityContract, model.model_validate(raw))
    except ValidationError as error:
        for issue in error.errors(include_url=False):
            diagnostics.append(
                Diagnostic(
                    "error",
                    "continuity_schema_validation",
                    relative_path,
                    _validation_location(issue["loc"]),
                    str(issue["msg"]),
                )
            )
        return None


def _discover_yaml_files(
    directory: Path,
    root: Path,
    diagnostics: list[Diagnostic],
) -> list[Path]:
    paths: list[Path] = []
    for current_root, directory_names, filenames in os.walk(directory, followlinks=False):
        current = Path(current_root)
        safe_directories: list[str] = []
        for name in sorted(directory_names):
            child = current / name
            if child.is_symlink():
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "symlink_directory",
                        _relative(child, root),
                        None,
                        "symbolic-link directories are not allowed in authority repositories",
                    )
                )
            else:
                safe_directories.append(name)
        directory_names[:] = safe_directories

        for name in sorted(filenames):
            path = current / name
            if path.suffix.lower() not in {".yaml", ".yml"}:
                continue
            if path.is_symlink():
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "symlink_file",
                        _relative(path, root),
                        None,
                        "symbolic-link authority files are not allowed",
                    )
                )
                continue
            try:
                resolved = path.resolve(strict=True)
            except OSError as error:
                diagnostics.append(
                    Diagnostic("error", "file_read", _relative(path, root), None, str(error))
                )
                continue
            if not resolved.is_relative_to(root):
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "path_outside_repository",
                        _relative(path, root),
                        None,
                        "authority file resolves outside the repository root",
                    )
                )
                continue
            if path.is_file():
                paths.append(path)
    return sorted(paths)


def load_repository(root: Path | str) -> RepositorySnapshot:
    """Load all known YAML files and collect independent diagnostics."""

    requested_root = Path(root).absolute()
    try:
        symlink_component = first_symlink_component(requested_root)
    except PathSafetyError as error:
        return RepositorySnapshot(
            root=requested_root,
            core=(),
            current=(),
            candidates=(),
            handoffs=(),
            diagnostics=(
                Diagnostic(
                    "error",
                    "repository_root_inspection",
                    ".",
                    None,
                    str(error),
                ),
            ),
        )
    if symlink_component is not None:
        return RepositorySnapshot(
            root=requested_root,
            core=(),
            current=(),
            candidates=(),
            handoffs=(),
            diagnostics=(
                Diagnostic(
                    "error",
                    "repository_root_symlink",
                    ".",
                    None,
                    "repository root path must not contain a symbolic link",
                ),
            ),
        )
    if not requested_root.exists() or not requested_root.is_dir():
        return RepositorySnapshot(
            root=requested_root,
            core=(),
            current=(),
            candidates=(),
            handoffs=(),
            diagnostics=(
                Diagnostic(
                    "error",
                    "repository_root_invalid",
                    ".",
                    None,
                    "repository root does not exist or is not a directory",
                ),
            ),
        )
    repository_root = requested_root.resolve()
    diagnostics: list[Diagnostic] = []
    core: list[CoreDocument] = []
    current: list[CurrentDocument] = []
    candidates: list[CandidateDocument] = []
    handoffs: list[HandoffDocument] = []
    persona_autonomy: list[PersonaAutonomy] = []
    window_state_cards: list[WindowStateCard] = []
    lifelines: list[LifeLine] = []
    continuity_memory_candidates: list[MemoryCandidate] = []
    recall_decisions: list[RecallDecision] = []
    maintenance_channels: list[MaintenanceChannel] = []
    paths_by_id: dict[str, str] = {}
    reported_symlink_directories: set[str] = set()
    manifest = _load_manifest(repository_root, diagnostics)

    if manifest is not None and Version(__version__) < Version(manifest.framework.minimum_version):
        diagnostics.append(
            Diagnostic(
                "error",
                "framework_version_too_old",
                "home.yaml",
                "framework.minimum_version",
                f"workspace requires HOME Framework {manifest.framework.minimum_version} or newer",
            )
        )

    if manifest is not None:
        export_directory = repository_root / manifest.defaults.export_directory
        symlink_component = _first_symlink_component(export_directory, repository_root)
        if symlink_component is not None:
            diagnostics.append(
                Diagnostic(
                    "error",
                    "symlink_export_directory",
                    _relative(symlink_component, repository_root),
                    None,
                    "workspace export directory and its ancestors must not be symbolic links",
                )
            )
        elif export_directory.exists() and not export_directory.is_dir():
            diagnostics.append(
                Diagnostic(
                    "error",
                    "export_directory_invalid",
                    manifest.defaults.export_directory,
                    None,
                    "workspace export path exists and is not a directory",
                )
            )

    for spec in _DIRECTORIES:
        directory = repository_root / spec.relative
        symlink_component = _first_symlink_component(directory, repository_root)
        if symlink_component is not None:
            relative_symlink = _relative(symlink_component, repository_root)
            if relative_symlink not in reported_symlink_directories:
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "symlink_directory",
                        relative_symlink,
                        None,
                        "recognized repository directories and their ancestors must not be "
                        "symbolic links",
                    )
                )
                reported_symlink_directories.add(relative_symlink)
            continue
        if not directory.is_dir():
            diagnostics.append(
                Diagnostic(
                    "warning",
                    "missing_directory",
                    spec.relative,
                    None,
                    "expected directory is missing",
                )
            )
            continue
        try:
            resolved_directory = directory.resolve(strict=True)
        except OSError as error:
            diagnostics.append(
                Diagnostic("error", "directory_read", spec.relative, None, str(error))
            )
            continue
        if not resolved_directory.is_relative_to(repository_root):
            diagnostics.append(
                Diagnostic(
                    "error",
                    "path_outside_repository",
                    spec.relative,
                    None,
                    "recognized repository directory resolves outside the repository root",
                )
            )
            continue

        for path in _discover_yaml_files(directory, repository_root, diagnostics):
            document = _load_file(path, repository_root, spec, diagnostics)
            if document is None:
                continue

            relative_path = _relative(path, repository_root)
            first_path = paths_by_id.get(document.id)
            if first_path is not None:
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "duplicate_id",
                        relative_path,
                        "id",
                        f"document id {document.id!r} is already defined in {first_path}",
                    )
                )
            else:
                paths_by_id[document.id] = relative_path

            if isinstance(document, CoreDocument):
                core.append(document)
            elif isinstance(document, CurrentDocument):
                current.append(document)
            elif isinstance(document, CandidateDocument):
                candidates.append(document)
            else:
                handoffs.append(document)

    continuity_directory = repository_root / "continuity"
    continuity_symlink = _first_symlink_component(continuity_directory, repository_root)
    if continuity_symlink is not None:
        relative_symlink = _relative(continuity_symlink, repository_root)
        if relative_symlink not in reported_symlink_directories:
            diagnostics.append(
                Diagnostic(
                    "error",
                    "symlink_directory",
                    relative_symlink,
                    None,
                    "continuity directory and its ancestors must not be symbolic links",
                )
            )
            reported_symlink_directories.add(relative_symlink)
    elif continuity_directory.exists() and not continuity_directory.is_dir():
        diagnostics.append(
            Diagnostic(
                "error",
                "continuity_directory_invalid",
                "continuity",
                None,
                "continuity path exists and is not a directory",
            )
        )
    elif continuity_directory.is_dir():
        try:
            resolved_continuity = continuity_directory.resolve(strict=True)
        except OSError as error:
            diagnostics.append(
                Diagnostic("error", "directory_read", "continuity", None, str(error))
            )
        else:
            if not resolved_continuity.is_relative_to(repository_root):
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "path_outside_repository",
                        "continuity",
                        None,
                        "continuity directory resolves outside the repository root",
                    )
                )
            else:
                for path in _discover_yaml_files(
                    continuity_directory, repository_root, diagnostics
                ):
                    contract = _load_continuity_file(path, repository_root, diagnostics)
                    if contract is None:
                        continue
                    relative_path = _relative(path, repository_root)
                    first_path = paths_by_id.get(contract.id)
                    if first_path is not None:
                        diagnostics.append(
                            Diagnostic(
                                "error",
                                "duplicate_id",
                                relative_path,
                                "id",
                                f"document id {contract.id!r} is already defined in {first_path}",
                            )
                        )
                    else:
                        paths_by_id[contract.id] = relative_path
                    if isinstance(contract, PersonaAutonomy):
                        persona_autonomy.append(contract)
                    elif isinstance(contract, WindowStateCard):
                        window_state_cards.append(contract)
                    elif isinstance(contract, LifeLine):
                        lifelines.append(contract)
                    elif isinstance(contract, MemoryCandidate):
                        continuity_memory_candidates.append(contract)
                    elif isinstance(contract, RecallDecision):
                        recall_decisions.append(contract)
                    else:
                        maintenance_channels.append(contract)

    core_ids = {document.id for document in core}
    current_ids = {document.id for document in current}
    for handoff in handoffs:
        handoff_path = paths_by_id.get(handoff.id, "handoffs")
        for document_id in handoff.include.core_ids:
            if document_id not in core_ids:
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "missing_core_reference",
                        handoff_path,
                        "include.core_ids",
                        f"handoff references missing core id {document_id!r}",
                    )
                )
        for document_id in handoff.include.current_ids:
            if document_id not in current_ids:
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "missing_current_reference",
                        handoff_path,
                        "include.current_ids",
                        f"handoff references missing current id {document_id!r}",
                    )
                )
        continuity_ids = {
            item.id
            for item in (
                *persona_autonomy,
                *window_state_cards,
                *lifelines,
                *continuity_memory_candidates,
                *recall_decisions,
                *maintenance_channels,
            )
        }
        for document_id in handoff.include.continuity_ids:
            if document_id not in continuity_ids:
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "missing_continuity_reference",
                        handoff_path,
                        "include.continuity_ids",
                        f"handoff references missing continuity id {document_id!r}",
                    )
                )

    memory_candidate_ids = {item.id for item in continuity_memory_candidates}
    for decision in recall_decisions:
        decision_path = paths_by_id.get(decision.id, "continuity")
        for memory_id in decision.selected_memory_ids:
            if memory_id not in memory_candidate_ids:
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "missing_memory_candidate_reference",
                        decision_path,
                        "selectedMemoryIds",
                        f"recall decision references missing memory candidate {memory_id!r}",
                    )
                )

    ordered_diagnostics = tuple(
        sorted(
            diagnostics,
            key=lambda item: (
                item.path,
                item.severity,
                item.code,
                item.location or "",
                item.message,
            ),
        )
    )
    return RepositorySnapshot(
        root=repository_root,
        core=tuple(core),
        current=tuple(current),
        candidates=tuple(candidates),
        handoffs=tuple(handoffs),
        diagnostics=ordered_diagnostics,
        manifest=manifest,
        document_paths=tuple(sorted(paths_by_id.items())),
        persona_autonomy=tuple(persona_autonomy),
        window_state_cards=tuple(window_state_cards),
        lifelines=tuple(lifelines),
        continuity_memory_candidates=tuple(continuity_memory_candidates),
        recall_decisions=tuple(recall_decisions),
        maintenance_channels=tuple(maintenance_channels),
    )
