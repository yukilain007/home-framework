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
    CoreDocument,
    CurrentDocument,
    Document,
    HandoffDocument,
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

    @property
    def has_errors(self) -> bool:
        return any(item.severity == "error" for item in self.diagnostics)

    @property
    def document_count(self) -> int:
        return len(self.core) + len(self.current) + len(self.candidates) + len(self.handoffs)

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
    )
