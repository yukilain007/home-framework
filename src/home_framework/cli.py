"""Typer command-line interface for validation and deterministic builds."""

from __future__ import annotations

import os
import tempfile
from datetime import date
from pathlib import Path
from typing import Annotated

import typer

from home_framework.compiler import CompilationError, compile_context
from home_framework.doctor import diagnose_workspace
from home_framework.initializer import InitializationError, initialize_workspace
from home_framework.renderer import render_markdown
from home_framework.repository import Diagnostic, RepositorySnapshot, load_repository

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Validate HOME authority files and build deterministic Markdown handoffs.",
)


def _format_diagnostic(diagnostic: Diagnostic) -> str:
    location = f":{diagnostic.location}" if diagnostic.location else ""
    return (
        f"{diagnostic.severity.upper()} {diagnostic.code} "
        f"{diagnostic.path}{location}: {diagnostic.message}"
    )


def _emit_diagnostic_items(diagnostics: tuple[Diagnostic, ...]) -> None:
    for diagnostic in diagnostics:
        typer.echo(_format_diagnostic(diagnostic), err=diagnostic.severity == "error")


def _emit_diagnostics(snapshot: RepositorySnapshot) -> None:
    _emit_diagnostic_items(snapshot.diagnostics)


def _parse_date(value: str | None) -> date:
    if value is None:
        return date.today()
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise CompilationError("--as-of must use YYYY-MM-DD") from error


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def _resolve_output_path(
    repository_root: Path,
    handoff_id: str,
    requested_output: Path | None,
    default_export_directory: str = "exports",
) -> Path:
    is_default = requested_output is None
    if is_default:
        candidate = repository_root / default_export_directory / f"{handoff_id}.md"
    elif requested_output is not None and requested_output.is_absolute():
        candidate = requested_output
    else:
        assert requested_output is not None
        candidate = repository_root / requested_output

    candidate = candidate.absolute()
    try:
        relative = candidate.relative_to(repository_root)
    except ValueError as error:
        raise CompilationError("output path must remain inside the repository") from error
    if ".." in relative.parts:
        raise CompilationError("output path must remain inside the repository")

    current = repository_root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            if is_default and current == repository_root / default_export_directory:
                raise CompilationError("default output directory must not be a symbolic link")
            raise CompilationError("output path must not contain a symbolic link")

    if not candidate.resolve(strict=False).is_relative_to(repository_root):
        raise CompilationError("output path must remain inside the repository")
    if candidate.parent.exists() and not candidate.parent.is_dir():
        raise CompilationError("output parent exists and is not a directory")
    return candidate


@app.command("init")
def init_command(
    path: Annotated[Path, typer.Argument(help="Workspace path to initialize.")],
    name: Annotated[
        str | None,
        typer.Option("--name", help="Safe workspace name stored in home.yaml."),
    ] = None,
) -> None:
    """Create a safe fictional workspace without initializing Git."""

    try:
        result = initialize_workspace(path, name)
    except InitializationError as error:
        typer.echo(f"ERROR init: {error}", err=True)
        raise typer.Exit(code=1) from error
    if result.already_initialized:
        typer.echo(f"Workspace already initialized: {result.root}")
    else:
        typer.echo(f"Initialized workspace: {result.root}")


@app.command("validate")
def validate_command(
    path: Annotated[Path, typer.Argument(help="Authority repository root.")] = Path("."),
) -> None:
    """Validate every recognized YAML file and cross-file reference."""

    snapshot = load_repository(path)
    _emit_diagnostics(snapshot)
    if snapshot.has_errors:
        raise typer.Exit(code=1)
    assert snapshot.manifest is not None
    warning_count = sum(item.severity == "warning" for item in snapshot.diagnostics)
    typer.echo(f"Validated {snapshot.document_count} documents with {warning_count} warnings.")


@app.command("doctor")
def doctor_command(
    path: Annotated[Path, typer.Argument(help="Workspace root to diagnose.")] = Path("."),
    as_of: Annotated[
        str | None,
        typer.Option("--as-of", help="Check date in YYYY-MM-DD; defaults to local date."),
    ] = None,
    strict: Annotated[
        bool,
        typer.Option("--strict", help="Return 1 when warnings are present."),
    ] = False,
) -> None:
    """Report workspace, lifecycle, export, security, and Git hygiene."""

    try:
        context_date = _parse_date(as_of)
    except CompilationError as error:
        typer.echo(f"ERROR doctor: {error}", err=True)
        raise typer.Exit(code=1) from error
    report = diagnose_workspace(path, context_date)
    typer.echo(f"Check date: {report.as_of.isoformat()}")
    _emit_diagnostic_items(report.diagnostics)
    error_count = sum(item.severity == "error" for item in report.diagnostics)
    typer.echo(f"Doctor found {error_count} errors and {report.warning_count} warnings.")
    if report.has_errors or (strict and report.warning_count):
        raise typer.Exit(code=1)


@app.command("build")
def build_command(
    handoff_id: Annotated[str, typer.Option("--handoff", help="Handoff document ID.")],
    path: Annotated[Path, typer.Argument(help="Authority repository root.")] = Path("."),
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Markdown output path."),
    ] = None,
    as_of: Annotated[
        str | None,
        typer.Option("--as-of", help="Context date in YYYY-MM-DD."),
    ] = None,
) -> None:
    """Validate, compile, render, and atomically write one handoff."""

    snapshot = load_repository(path)
    _emit_diagnostics(snapshot)
    if snapshot.has_errors:
        raise typer.Exit(code=1)
    assert snapshot.manifest is not None

    try:
        context_date = _parse_date(as_of)
        compiled = compile_context(snapshot, handoff_id, context_date)
        rendered = render_markdown(compiled)
        target = _resolve_output_path(
            snapshot.root,
            compiled.handoff.id,
            output,
            snapshot.manifest.defaults.export_directory,
        )
        _atomic_write(target, rendered)
    except (CompilationError, OSError) as error:
        typer.echo(f"ERROR build: {error}", err=True)
        raise typer.Exit(code=1) from error

    typer.echo(f"Selected {len(compiled.documents)} documents.")
    typer.echo(f"Output: {target}")
    typer.echo(f"Fingerprint: {compiled.fingerprint}")


if __name__ == "__main__":
    app()
