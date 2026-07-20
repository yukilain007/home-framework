"""Aggregate workspace, lifecycle, export, security, and Git diagnostics."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from home_framework.compiler import CompilationError, compile_context
from home_framework.export_metadata import classify_export
from home_framework.path_safety import PathSafetyError, first_symlink_component
from home_framework.repository import Diagnostic, load_repository
from home_framework.security import scan_workspace

EXPIRING_WINDOW_DAYS = 7


@dataclass(frozen=True, slots=True)
class DoctorReport:
    """Immutable result of a local workspace diagnosis."""

    root: Path
    as_of: date
    diagnostics: tuple[Diagnostic, ...]

    @property
    def has_errors(self) -> bool:
        return any(item.severity == "error" for item in self.diagnostics)

    @property
    def warning_count(self) -> int:
        return sum(item.severity == "warning" for item in self.diagnostics)


def _lifecycle_diagnostics(snapshot_root: Path, snapshot: object, as_of: date) -> list[Diagnostic]:
    from home_framework.repository import RepositorySnapshot

    assert isinstance(snapshot, RepositorySnapshot)
    diagnostics: list[Diagnostic] = []
    for candidate in snapshot.candidates:
        if not candidate.decision.reviewed:
            diagnostics.append(
                Diagnostic(
                    "warning",
                    "pending_candidate",
                    snapshot.path_for(candidate.id, f"candidates/{candidate.id}"),
                    None,
                    "candidate is awaiting human review",
                )
            )
        elif candidate.decision.action == "approve":
            diagnostics.append(
                Diagnostic(
                    "warning",
                    "approved_candidate",
                    snapshot.path_for(candidate.id, f"candidates/{candidate.id}"),
                    None,
                    "approved candidate remains outside reviewed authority files",
                )
            )

    inactive_count = sum(
        document.status == "inactive" for document in (*snapshot.core, *snapshot.current)
    )
    archived_count = sum(
        document.status == "archived" for document in (*snapshot.core, *snapshot.current)
    )
    if inactive_count:
        diagnostics.append(
            Diagnostic(
                "info",
                "inactive_authority",
                ".",
                None,
                f"{inactive_count} inactive authority document(s)",
            )
        )
    if archived_count:
        diagnostics.append(
            Diagnostic(
                "info",
                "archived_authority",
                ".",
                None,
                f"{archived_count} archived authority document(s)",
            )
        )

    expiring_limit = as_of + timedelta(days=EXPIRING_WINDOW_DAYS)
    for current in snapshot.current:
        if current.status != "active":
            continue
        diagnostic_path = snapshot.path_for(current.id, f"sources/current/{current.id}")
        if current.valid_from > as_of:
            diagnostics.append(
                Diagnostic(
                    "warning",
                    "future_current",
                    diagnostic_path,
                    None,
                    f"current authority begins on {current.valid_from.isoformat()}",
                )
            )
        elif current.expires_at is not None and current.expires_at < as_of:
            diagnostics.append(
                Diagnostic(
                    "warning",
                    "expired_current",
                    diagnostic_path,
                    None,
                    f"current authority expired on {current.expires_at.isoformat()}",
                )
            )
        elif current.expires_at is not None and current.expires_at <= expiring_limit:
            diagnostics.append(
                Diagnostic(
                    "warning",
                    "expiring_current",
                    diagnostic_path,
                    None,
                    f"current authority expires on {current.expires_at.isoformat()} "
                    f"within {EXPIRING_WINDOW_DAYS} days",
                )
            )
    return diagnostics


def _export_diagnostics(snapshot: object, as_of: date) -> list[Diagnostic]:
    from home_framework.repository import RepositorySnapshot

    assert isinstance(snapshot, RepositorySnapshot)
    if snapshot.manifest is None:
        return []
    export_relative = snapshot.manifest.defaults.export_directory
    export_directory = snapshot.root / export_relative
    if export_directory.is_symlink() or not export_directory.resolve(strict=False).is_relative_to(
        snapshot.root
    ):
        return []

    diagnostics: list[Diagnostic] = []
    if not export_directory.exists():
        diagnostics.append(
            Diagnostic(
                "warning",
                "missing_export_directory",
                export_relative,
                None,
                "workspace export directory is missing",
            )
        )
    if not snapshot.has_errors:
        for handoff in snapshot.handoffs:
            try:
                compiled = compile_context(snapshot, handoff.id, as_of)
            except CompilationError as error:
                diagnostics.append(
                    Diagnostic("error", "handoff_compile", "handoffs", handoff.id, str(error))
                )
                continue
            filename = f"{handoff.id}.md"
            diagnostics.append(
                classify_export(
                    export_directory / filename,
                    f"{export_relative}/{filename}",
                    compiled,
                )
            )

    if export_directory.is_dir():
        known_filenames = {f"{handoff.id}.md" for handoff in snapshot.handoffs}
        for path in sorted(export_directory.glob("*.md")):
            if path.name not in known_filenames:
                diagnostics.append(
                    Diagnostic(
                        "warning",
                        "unknown_handoff_export",
                        f"{export_relative}/{path.name}",
                        None,
                        "Markdown export does not correspond to a known handoff",
                    )
                )
    return diagnostics


def _run_git(root: Path, arguments: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "git",
            "--no-optional-locks",
            "-c",
            "core.fsmonitor=false",
            "-c",
            "core.hooksPath=/dev/null",
            "-C",
            str(root),
            *arguments,
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def _git_diagnostics(root: Path, export_directory: str | None) -> list[Diagnostic]:
    git_directory = root / ".git"
    if git_directory.is_symlink() or not git_directory.is_dir():
        return []
    probe = _run_git(root, ["rev-parse", "--show-toplevel"])
    if probe.returncode != 0:
        return []
    try:
        top_level = Path(probe.stdout.strip()).resolve(strict=True)
    except (OSError, ValueError):
        return []
    if top_level != root:
        return []

    diagnostics: list[Diagnostic] = []
    remotes = _run_git(root, ["remote"])
    remote_names = sorted(line for line in remotes.stdout.splitlines() if line)
    if remote_names:
        diagnostics.append(
            Diagnostic(
                "info",
                "git_remote_present",
                ".",
                None,
                f"configured Git remote name(s): {', '.join(remote_names)}",
            )
        )

    if export_directory is not None:
        tracked = _run_git(root, ["ls-files", "--", export_directory])
        for relative_path in sorted(
            line for line in tracked.stdout.splitlines() if line.endswith(".md")
        ):
            diagnostics.append(
                Diagnostic(
                    "warning",
                    "tracked_export",
                    relative_path,
                    None,
                    "generated Markdown export is tracked by Git; no change was made",
                )
            )

    status = _run_git(
        root,
        [
            "status",
            "--short",
            "--untracked-files=no",
            "--",
            "home.yaml",
            "sources/core",
            "sources/current",
            "candidates",
            "handoffs",
        ],
    )
    if status.stdout.strip():
        diagnostics.append(
            Diagnostic(
                "info",
                "modified_authority",
                ".",
                None,
                "Git reports modified or staged authority files; no change was made",
            )
        )
    return diagnostics


def diagnose_workspace(root: Path | str, as_of: date) -> DoctorReport:
    """Run every local, read-only diagnostic for one explicit workspace."""

    snapshot = load_repository(root)
    diagnostics = list(snapshot.diagnostics)
    try:
        safe_root = first_symlink_component(snapshot.root) is None
    except PathSafetyError as error:
        diagnostics.append(Diagnostic("error", "doctor_root_inspection", ".", None, str(error)))
        safe_root = False
    if safe_root and snapshot.root.is_dir():
        diagnostics.extend(_lifecycle_diagnostics(snapshot.root, snapshot, as_of))
        diagnostics.extend(_export_diagnostics(snapshot, as_of))
        diagnostics.extend(scan_workspace(snapshot.root))
        export_directory = (
            snapshot.manifest.defaults.export_directory if snapshot.manifest is not None else None
        )
        diagnostics.extend(_git_diagnostics(snapshot.root, export_directory))

    severity_order = {"error": 0, "warning": 1, "info": 2}
    ordered = tuple(
        sorted(
            diagnostics,
            key=lambda item: (
                severity_order[item.severity],
                item.path,
                item.code,
                item.location or "",
                item.message,
            ),
        )
    )
    return DoctorReport(root=snapshot.root, as_of=as_of, diagnostics=ordered)
