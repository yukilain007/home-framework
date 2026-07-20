"""Safely create a small, fictional HOME Framework workspace."""

from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import ValidationError

from home_framework import __version__
from home_framework.models import WorkspaceManifest
from home_framework.path_safety import PathSafetyError, first_symlink_component
from home_framework.repository import load_repository

_DIRECTORIES = (
    "sources",
    "sources/core",
    "sources/current",
    "candidates",
    "handoffs",
    "exports",
)


class InitializationError(Exception):
    """Raised when a workspace cannot be initialized without data loss."""


@dataclass(frozen=True, slots=True)
class InitResult:
    """Outcome of an initialization request."""

    root: Path
    already_initialized: bool


def _atomic_write(path: Path, content: str) -> None:
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.link(temporary_path, path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def _default_name(path: Path) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", path.name.lower()).strip("-")
    if not normalized or not normalized[0].isalpha():
        normalized = f"workspace-{normalized or 'local'}"
    return normalized[:128].rstrip("-")


def _manifest(name: str) -> WorkspaceManifest:
    try:
        return WorkspaceManifest.model_validate(
            {
                "kind": "workspace",
                "schema_version": "1.0",
                "name": name,
                "framework": {"minimum_version": __version__},
                "defaults": {"export_directory": "exports"},
            }
        )
    except ValidationError as error:
        raise InitializationError(f"invalid workspace name: {name!r}") from error


def _yaml(data: object) -> str:
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)


def _file_plan(manifest: WorkspaceManifest) -> dict[str, str]:
    return {
        "home.yaml": _yaml(manifest.model_dump(mode="json")),
        ".gitignore": "exports/*.md\n*.tmp\n",
        "sources/core/workflow.yaml": _yaml(
            {
                "kind": "core",
                "schema_version": "1.0",
                "id": "workflow.clear",
                "content": "Use clear language for the fictional Atlas Notebook project.",
                "status": "active",
                "sensitivity": "public",
                "scope": ["project"],
                "priority": 80,
                "source": {"type": "human_authored", "reference": None},
                "created_at": "2026-07-20",
                "updated_at": "2026-07-20",
            }
        ),
        "sources/current/status.yaml": _yaml(
            {
                "kind": "current",
                "schema_version": "1.0",
                "id": "project.status",
                "content": "The fictional Atlas Notebook project is ready for local validation.",
                "status": "active",
                "sensitivity": "public",
                "scope": ["project"],
                "priority": 70,
                "source": {"type": "human_authored", "reference": None},
                "created_at": "2026-07-20",
                "updated_at": "2026-07-20",
                "valid_from": "2026-07-20",
                "expires_at": None,
            }
        ),
        "handoffs/project.yaml": _yaml(
            {
                "kind": "handoff",
                "schema_version": "1.0",
                "id": "project.execution",
                "title": "Fictional project execution context",
                "purpose": "Continue a fictional local implementation.",
                "include": {
                    "scopes": ["project"],
                    "core_ids": [],
                    "current_ids": [],
                    "sensitivities": ["public"],
                },
                "output": {"format": "markdown"},
            }
        ),
    }


def _is_complete_workspace(path: Path) -> bool:
    snapshot = load_repository(path)
    if snapshot.has_errors or snapshot.manifest is None:
        return False
    return all(
        not (path / relative).is_symlink() and (path / relative).is_dir()
        for relative in _DIRECTORIES
    )


def _create_missing_path(path: Path, created: list[Path]) -> None:
    missing: list[Path] = []
    current = path
    while not current.exists():
        if current.is_symlink():
            raise InitializationError("workspace path must not contain a symbolic link")
        missing.append(current)
        current = current.parent
    if current.is_symlink():
        raise InitializationError("workspace path must not contain a symbolic link")
    for directory in reversed(missing):
        directory.mkdir()
        created.append(directory)


def initialize_workspace(path: Path | str, name: str | None = None) -> InitResult:
    """Initialize a missing or empty path without overwriting user files."""

    requested = Path(path).absolute()
    try:
        symlink_component = first_symlink_component(requested)
    except PathSafetyError as error:
        raise InitializationError(str(error)) from error
    if symlink_component is not None:
        raise InitializationError("workspace path must not contain a symbolic link")
    manifest = _manifest(name or _default_name(requested))

    if requested.exists():
        if not requested.is_dir():
            raise InitializationError("workspace target exists and is not a directory")
        if any(requested.iterdir()):
            if _is_complete_workspace(requested):
                return InitResult(requested.resolve(), already_initialized=True)
            raise InitializationError(
                "non-empty path is not a valid workspace; initialization refused"
            )

    created_ancestors: list[Path] = []
    created_directories: list[Path] = []
    created_files: list[Path] = []
    try:
        if not requested.exists():
            _create_missing_path(requested, created_ancestors)
        for relative in _DIRECTORIES:
            directory = requested / relative
            if not directory.exists():
                directory.mkdir()
                created_directories.append(directory)
        for relative, content in _file_plan(manifest).items():
            target = requested / relative
            if target.exists() or target.is_symlink():
                raise InitializationError(f"initialization would overwrite {relative}")
            _atomic_write(target, content)
            created_files.append(target)
    except (InitializationError, OSError) as error:
        for created_file in reversed(created_files):
            if created_file.exists() and not created_file.is_symlink():
                created_file.unlink()
        for directory in reversed(created_directories):
            if directory.exists():
                try:
                    directory.rmdir()
                except OSError:
                    pass
        for directory in reversed(created_ancestors):
            if directory.exists():
                try:
                    directory.rmdir()
                except OSError:
                    pass
        if isinstance(error, InitializationError):
            raise
        raise InitializationError(str(error)) from error

    return InitResult(requested.resolve(), already_initialized=False)
