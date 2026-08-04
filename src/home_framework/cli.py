# SPDX-FileCopyrightText: 2026 Yuki
# SPDX-License-Identifier: Apache-2.0

"""Typer command-line interface for validation and deterministic builds."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from home_framework.adapter import (
    AdapterError,
    ExternalRepresentationArtifact,
    LocalMarkdownAdapter,
)
from home_framework.compiler import CompilationError, CompiledDocument, compile_context
from home_framework.doctor import diagnose_workspace
from home_framework.initializer import InitializationError, initialize_workspace
from home_framework.models import HandoffPackage, HandoffProvenance
from home_framework.package_export import (
    ExportResult,
    PackageExportConflictError,
    PackageExportError,
    PackageExportReadError,
    PackageExportVerificationError,
    export_package,
)
from home_framework.package_factory import (
    ApprovalInput,
    PackageFactoryError,
    PackageFactoryRequest,
    create_package,
)
from home_framework.package_verification import PackageVerificationError, verify_package_artifact
from home_framework.renderer import render_markdown
from home_framework.repository import Diagnostic, RepositorySnapshot, load_repository

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Validate HOME authority files and build deterministic Markdown handoffs.",
)

package_app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help=(
        "Create, verify, export, and adapt local HandoffPackage artifacts; "
        "no operation delivers or uploads anything."
    ),
)
app.add_typer(package_app, name="package")


def _package_verification_report(
    artifact: Path,
    package: HandoffPackage,
) -> dict[str, object]:
    package_digest = package.canonical_digest()
    content_digest = package.content.digest
    return {
        "operation": "package.verify",
        "status": "valid",
        "artifact_path": str(artifact),
        "handoff_id": package.handoff_id,
        "package_schema": package.package_schema,
        "handoff_schema": package.handoff_schema,
        "source_fingerprint": package.source_fingerprint,
        "package_digest": {
            "expected": package_digest,
            "actual": package_digest,
            "match": True,
        },
        "content_digest": {
            "expected": content_digest,
            "actual": content_digest,
            "match": True,
        },
        "provenance": package.provenance.model_dump(mode="json"),
        "checks": {
            "schema": "pass",
            "canonical_serialization": "pass",
            "source_fingerprint": "pass",
            "content_digest": "pass",
            "package_digest": "pass",
            "provenance": "pass",
            "forbidden_fields": "pass",
        },
        "authority_created": False,
        "delivery_performed": False,
    }


def _invalid_package_verification_report(
    artifact: Path,
    category: str,
    message: str,
) -> dict[str, object]:
    return {
        "operation": "package.verify",
        "status": "invalid",
        "artifact_path": str(artifact),
        "error_code": category,
        "error": message,
        "checks": {category: "fail"},
        "authority_created": False,
        "delivery_performed": False,
    }


def _invalid_package_adaptation_report(
    artifact: Path,
    category: str,
    message: str,
) -> dict[str, object]:
    return {
        "operation": "package.adapt",
        "status": "invalid",
        "artifact_path": str(artifact),
        "error_code": category,
        "error": message,
        "authority_created": False,
        "delivery_performed": False,
    }


def _emit_package_verification_report(
    report: dict[str, object],
    output_format: str,
) -> None:
    if output_format == "json":
        typer.echo(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return

    status = str(report["status"]).upper()
    typer.echo(f"{status} package.verify")
    typer.echo(f"Artifact: {report['artifact_path']}")
    if status == "VALID":
        typer.echo(f"Handoff ID: {report['handoff_id']}")
        package_digest = report["package_digest"]
        assert isinstance(package_digest, dict)
        typer.echo(f"Package digest: {package_digest['actual']}")
        typer.echo(f"Source fingerprint: {report['source_fingerprint']}")
        typer.echo("Approval: user-approved")
    else:
        typer.echo(f"Category: {report['error_code']}")
        typer.echo(f"Error: {report['error']}")


def _package_adaptation_report(
    artifact: Path,
    representation: ExternalRepresentationArtifact,
) -> dict[str, object]:
    return {
        "operation": "package.adapt",
        "status": "valid",
        "artifact_path": str(artifact),
        "adapter_id": representation.adapter_id,
        "adapter_version": representation.adapter_version,
        "target_type": representation.target_type,
        "handoff_id": representation.handoff_id,
        "package_digest": representation.package_digest,
        "source_fingerprint": representation.source_fingerprint,
        "artifact_digest": representation.artifact_digest,
        "source_provenance": representation.source_provenance.model_dump(mode="json"),
        "media_type": representation.media_type,
        "delivery_performed": False,
    }


def _emit_package_adaptation_report(
    report: dict[str, object],
    output_format: str,
) -> None:
    if output_format == "json":
        typer.echo(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return

    status = str(report["status"]).upper()
    typer.echo(f"{status} package.adapt")
    typer.echo(f"Artifact: {report['artifact_path']}")
    if status == "VALID":
        typer.echo(f"Adapter: {report['adapter_id']} {report['adapter_version']}")
        typer.echo(f"Artifact digest: {report['artifact_digest']}")
        typer.echo(f"Package digest: {report['package_digest']}")
        typer.echo("Delivery: not performed")
    else:
        typer.echo(f"Category: {report['error_code']}")
        typer.echo(f"Error: {report['error']}")


def _package_export_report(
    source: Path,
    result: ExportResult,
) -> dict[str, object]:
    return {
        "operation": "package.export",
        "status": "valid",
        "source_artifact": str(source),
        "artifact_path": str(result.path),
        "package_digest": result.package_digest,
        "created": result.created,
        "verified": result.verified,
        "authority_created": False,
        "delivery_performed": False,
    }


def _invalid_package_export_report(
    source: Path,
    category: str,
    message: str,
) -> dict[str, object]:
    return {
        "operation": "package.export",
        "status": "invalid",
        "source_artifact": str(source),
        "error_code": category,
        "error": message,
        "authority_created": False,
        "delivery_performed": False,
    }


def _emit_package_export_report(
    report: dict[str, object],
    output_format: str,
) -> None:
    if output_format == "json":
        typer.echo(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return

    status = str(report["status"]).upper()
    typer.echo("EXPORTED package.export" if status == "VALID" else "INVALID package.export")
    if status == "VALID":
        typer.echo(f"Artifact: {report['artifact_path']}")
        typer.echo(f"Package digest: {report['package_digest']}")
        typer.echo(f"Created: {str(report['created']).lower()}")
        typer.echo(f"Verified: {str(report['verified']).lower()}")
    else:
        typer.echo(f"Category: {report['error_code']}")
        typer.echo(f"Error: {report['error']}")


def _package_create_report(
    package: HandoffPackage,
    approval: ApprovalInput,
    compiled_documents: tuple[CompiledDocument, ...],
    export_result: ExportResult | None = None,
) -> dict[str, object]:
    if export_result is None:
        status = "preview"
        dry_run = True
        output_path: str | None = None
        exported: dict[str, object] = {}
    else:
        status = "created" if export_result.created else "reused"
        dry_run = False
        output_path = str(export_result.path)
        exported = {
            "created": export_result.created,
            "verified": export_result.verified,
        }
    return {
        "operation": "package.create",
        "status": status,
        "dry_run": dry_run,
        "handoff_id": package.handoff_id,
        "context_date": package.context_date.isoformat(),
        "source_fingerprint": package.source_fingerprint,
        "package_digest": package.canonical_digest(),
        "selected_authority": [document.id for document in compiled_documents],
        "approval": {
            "status": approval.status,
            "source": approval.source,
            "confirmed_at": approval.confirmed_at.isoformat().replace("+00:00", "Z"),
            "scope_match": True,
        },
        "output_path": output_path,
        **exported,
        "authority_created": False,
        "delivery_performed": False,
    }


def _invalid_package_create_report(
    category: str,
    message: str,
    *,
    output_requested: bool = False,
    status: str | None = None,
) -> dict[str, object]:
    return {
        "operation": "package.create",
        "status": status or ("failed" if output_requested else "invalid"),
        "dry_run": not output_requested,
        "error_code": category,
        "error": message,
        "output_path": None,
        "authority_created": False,
        "delivery_performed": False,
    }


def _emit_package_create_report(
    report: dict[str, object],
    output_format: str,
) -> None:
    if output_format == "json":
        typer.echo(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return

    status = str(report["status"]).upper()
    if status == "PREVIEW":
        typer.echo("PREVIEW package.create")
    elif status in {"CREATED", "REUSED", "CONFLICT", "FAILED"}:
        typer.echo(f"{status} package.create")
    else:
        typer.echo("INVALID package.create")
    if status == "PREVIEW":
        typer.echo(f"Handoff ID: {report['handoff_id']}")
        typer.echo(f"Context date: {report['context_date']}")
        typer.echo(f"Source fingerprint: {report['source_fingerprint']}")
        typer.echo(f"Package digest: {report['package_digest']}")
        typer.echo("No files written.")
    elif status in {"CREATED", "REUSED"}:
        typer.echo(f"Artifact: {report['output_path']}")
        typer.echo(f"Package digest: {report['package_digest']}")
        typer.echo(f"Verified: {str(report['verified']).lower()}")
    else:
        typer.echo(f"Category: {report['error_code']}")
        typer.echo(f"Error: {report['error']}")


def _emit_package_create_diagnostics(
    snapshot: RepositorySnapshot,
    output_format: str,
) -> None:
    if output_format == "json":
        for diagnostic in snapshot.diagnostics:
            typer.echo(_format_diagnostic(diagnostic), err=True)
        return
    _emit_diagnostics(snapshot)


def _package_artifact_input_error(artifact: Path) -> str | None:
    artifact_text = str(artifact)
    if "://" in artifact_text or artifact_text.startswith(("http:/", "https:/", "file:/")):
        return "artifact must be a local file path, not a URL"
    if artifact in {Path("."), Path("..")} or artifact.is_dir():
        return "artifact path must point to a local JSON file, not a directory"
    if not artifact.exists():
        return "artifact file does not exist"
    return None


def _package_export_destination_error(destination: Path) -> str | None:
    destination_text = str(destination)
    if "://" in destination_text or destination_text.startswith(("http:/", "https:/", "file:/")):
        return "export destination must be a local directory, not a URL"
    if destination.exists() and not destination.is_dir():
        return "export destination must be a directory"
    return None


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
    with_continuity: Annotated[
        bool,
        typer.Option(
            "--with-continuity",
            help="Include fictional continuity contract examples in a new workspace.",
        ),
    ] = False,
) -> None:
    """Create a safe fictional workspace without initializing Git."""

    try:
        result = initialize_workspace(path, name, include_continuity=with_continuity)
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
    if snapshot.continuity_count:
        typer.echo(
            f"Validated {snapshot.document_count} documents and "
            f"{snapshot.continuity_count} continuity contracts with {warning_count} warnings."
        )
    else:
        typer.echo(f"Validated {snapshot.document_count} documents with {warning_count} warnings.")


@app.command("inspect")
def inspect_command(
    path: Annotated[Path, typer.Argument(help="Authority repository root.")] = Path("."),
) -> None:
    """Inspect optional continuity contracts without compiling or changing files."""

    snapshot = load_repository(path)
    _emit_diagnostics(snapshot)
    if snapshot.has_errors:
        raise typer.Exit(code=1)
    if not snapshot.continuity_count:
        typer.echo("No continuity contracts found.")
        return
    payload = [
        contract.model_dump(mode="json", by_alias=True)
        for contract in snapshot.continuity_contracts
    ]
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


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
        rendered = render_markdown(compiled, generated_at=datetime.now(UTC))
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


@package_app.command("verify")
def package_verify_command(
    artifact: Annotated[Path, typer.Argument(help="Local HandoffPackage JSON artifact.")],
    output_format: Annotated[
        str,
        typer.Option("--format", help="Output format: human or json."),
    ] = "human",
) -> None:
    """Verify one local HandoffPackage without granting approval or authority."""

    if output_format not in {"human", "json"}:
        report = _invalid_package_verification_report(
            artifact,
            "input",
            "--format must be either 'human' or 'json'",
        )
        _emit_package_verification_report(report, "json" if output_format == "json" else "human")
        raise typer.Exit(code=2)

    input_error = _package_artifact_input_error(artifact)
    if input_error is not None:
        report = _invalid_package_verification_report(
            artifact,
            "input",
            input_error,
        )
        _emit_package_verification_report(report, output_format)
        raise typer.Exit(code=2)

    try:
        package = verify_package_artifact(artifact)
    except PackageExportReadError as error:
        report = _invalid_package_verification_report(artifact, "read", str(error))
        _emit_package_verification_report(report, output_format)
        raise typer.Exit(code=5) from error
    except PackageExportVerificationError as error:
        report = _invalid_package_verification_report(artifact, "schema", str(error))
        _emit_package_verification_report(report, output_format)
        raise typer.Exit(code=4) from error
    except PackageVerificationError as error:
        code = 6 if error.category == "unsupported_schema" else 4
        report = _invalid_package_verification_report(artifact, error.category, str(error))
        _emit_package_verification_report(report, output_format)
        raise typer.Exit(code=code) from error
    except OSError as error:
        report = _invalid_package_verification_report(artifact, "read", str(error))
        _emit_package_verification_report(report, output_format)
        raise typer.Exit(code=5) from error
    except Exception as error:
        report = _invalid_package_verification_report(artifact, "internal", str(error))
        _emit_package_verification_report(report, output_format)
        raise typer.Exit(code=70) from error

    report = _package_verification_report(artifact, package)
    _emit_package_verification_report(report, output_format)


@package_app.command("adapt")
def package_adapt_command(
    artifact: Annotated[Path, typer.Argument(help="Local HandoffPackage JSON artifact.")],
    adapter: Annotated[
        str,
        typer.Option(..., "--adapter", help="Adapter identity; only local-markdown is supported."),
    ],
    output_format: Annotated[
        str,
        typer.Option("--format", help="Output format: human or json."),
    ] = "human",
) -> None:
    """Create an external representation; adapt is not send and supports local-markdown only."""

    if output_format not in {"human", "json"}:
        report = _invalid_package_adaptation_report(
            artifact,
            "input",
            "--format must be either 'human' or 'json'",
        )
        _emit_package_adaptation_report(report, "json" if output_format == "json" else "human")
        raise typer.Exit(code=2)

    input_error = _package_artifact_input_error(artifact)
    if input_error is not None:
        report = _invalid_package_adaptation_report(artifact, "input", input_error)
        _emit_package_adaptation_report(report, output_format)
        raise typer.Exit(code=2)

    if adapter != "local-markdown":
        report = _invalid_package_adaptation_report(
            artifact,
            "adapter",
            f"unsupported adapter: {adapter}; only local-markdown is available",
        )
        _emit_package_adaptation_report(report, output_format)
        raise typer.Exit(code=6)

    try:
        package = verify_package_artifact(artifact)
    except PackageExportReadError as error:
        report = _invalid_package_adaptation_report(artifact, "read", str(error))
        _emit_package_adaptation_report(report, output_format)
        raise typer.Exit(code=5) from error
    except PackageExportVerificationError as error:
        report = _invalid_package_adaptation_report(artifact, "schema", str(error))
        _emit_package_adaptation_report(report, output_format)
        raise typer.Exit(code=4) from error
    except PackageVerificationError as error:
        code = 6 if error.category == "unsupported_schema" else 4
        report = _invalid_package_adaptation_report(artifact, error.category, str(error))
        _emit_package_adaptation_report(report, output_format)
        raise typer.Exit(code=code) from error
    except OSError as error:
        report = _invalid_package_adaptation_report(artifact, "read", str(error))
        _emit_package_adaptation_report(report, output_format)
        raise typer.Exit(code=5) from error
    except Exception as error:
        report = _invalid_package_adaptation_report(artifact, "internal", str(error))
        _emit_package_adaptation_report(report, output_format)
        raise typer.Exit(code=70) from error

    try:
        representation = LocalMarkdownAdapter().adapt(package)
    except AdapterError as error:
        code = 6 if error.code == "unsupported_schema" else 4
        report = _invalid_package_adaptation_report(artifact, error.code, str(error))
        _emit_package_adaptation_report(report, output_format)
        raise typer.Exit(code=code) from error
    except Exception as error:
        report = _invalid_package_adaptation_report(artifact, "internal", str(error))
        _emit_package_adaptation_report(report, output_format)
        raise typer.Exit(code=70) from error

    report = _package_adaptation_report(artifact, representation)
    _emit_package_adaptation_report(report, output_format)


@package_app.command("export")
def package_export_command(
    artifact: Annotated[Path, typer.Argument(help="Local HandoffPackage JSON artifact.")],
    output: Annotated[
        Path,
        typer.Option(..., "--output", help="Local directory for the immutable export artifact."),
    ],
    output_format: Annotated[
        str,
        typer.Option("--format", help="Output format: human or json."),
    ] = "human",
) -> None:
    """Atomically export an existing Package locally; export is not delivery."""

    if output_format not in {"human", "json"}:
        report = _invalid_package_export_report(
            artifact,
            "input",
            "--format must be either 'human' or 'json'",
        )
        _emit_package_export_report(report, "json" if output_format == "json" else "human")
        raise typer.Exit(code=2)

    input_error = _package_artifact_input_error(artifact)
    if input_error is not None:
        report = _invalid_package_export_report(artifact, "input", input_error)
        _emit_package_export_report(report, output_format)
        raise typer.Exit(code=2)

    destination_error = _package_export_destination_error(output)
    if destination_error is not None:
        report = _invalid_package_export_report(artifact, "input", destination_error)
        _emit_package_export_report(report, output_format)
        raise typer.Exit(code=2)

    try:
        package = verify_package_artifact(artifact)
    except PackageExportReadError as error:
        report = _invalid_package_export_report(artifact, "read", str(error))
        _emit_package_export_report(report, output_format)
        raise typer.Exit(code=5) from error
    except PackageExportVerificationError as error:
        report = _invalid_package_export_report(artifact, "schema", str(error))
        _emit_package_export_report(report, output_format)
        raise typer.Exit(code=4) from error
    except PackageVerificationError as error:
        code = 6 if error.category == "unsupported_schema" else 4
        report = _invalid_package_export_report(artifact, error.category, str(error))
        _emit_package_export_report(report, output_format)
        raise typer.Exit(code=code) from error
    except OSError as error:
        report = _invalid_package_export_report(artifact, "read", str(error))
        _emit_package_export_report(report, output_format)
        raise typer.Exit(code=5) from error
    except Exception as error:
        report = _invalid_package_export_report(artifact, "internal", str(error))
        _emit_package_export_report(report, output_format)
        raise typer.Exit(code=70) from error

    try:
        result = export_package(package, output)
    except PackageExportConflictError as error:
        report = _invalid_package_export_report(artifact, "conflict", str(error))
        _emit_package_export_report(report, output_format)
        raise typer.Exit(code=5) from error
    except (PackageExportError, PackageExportVerificationError, OSError) as error:
        report = _invalid_package_export_report(artifact, "export", str(error))
        _emit_package_export_report(report, output_format)
        raise typer.Exit(code=5) from error
    except Exception as error:
        report = _invalid_package_export_report(artifact, "internal", str(error))
        _emit_package_export_report(report, output_format)
        raise typer.Exit(code=70) from error

    report = _package_export_report(artifact, result)
    _emit_package_export_report(report, output_format)


@package_app.command("create")
def package_create_command(
    path: Annotated[Path, typer.Argument(help="Workspace repository root.")],
    handoff_id: Annotated[str, typer.Option("--handoff", help="Handoff document ID.")],
    as_of: Annotated[
        str | None,
        typer.Option("--as-of", help="Context date in YYYY-MM-DD."),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Create and preview a Package in memory only."),
    ] = False,
    approval_source: Annotated[
        str | None,
        typer.Option("--approval-source", help="Explicit approval source."),
    ] = None,
    approval_handoff_id: Annotated[
        str | None,
        typer.Option("--approval-handoff-id", help="Handoff ID covered by approval."),
    ] = None,
    approval_context_date: Annotated[
        str | None,
        typer.Option("--approval-context-date", help="Approved context date."),
    ] = None,
    approval_fingerprint: Annotated[
        str | None,
        typer.Option("--approval-fingerprint", help="Approved source fingerprint."),
    ] = None,
    approval_confirmed_at: Annotated[
        str | None,
        typer.Option("--approval-confirmed-at", help="Timezone-aware approval timestamp."),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Directory for the verified local Package artifact."),
    ] = None,
    output_format: Annotated[
        str,
        typer.Option("--format", help="Output format: human or json."),
    ] = "human",
) -> None:
    """Create a preview or local artifact after explicit approval; does not deliver.

    Use ``--dry-run`` for an in-memory preview or ``--output`` for a local artifact.
    """

    if output_format not in {"human", "json"}:
        report = _invalid_package_create_report(
            "input",
            "--format must be either 'human' or 'json'",
        )
        _emit_package_create_report(report, "json" if output_format == "json" else "human")
        raise typer.Exit(code=2)
    if dry_run and output is not None:
        report = _invalid_package_create_report(
            "input",
            "--dry-run cannot be combined with --output",
        )
        _emit_package_create_report(report, output_format)
        raise typer.Exit(code=2)
    if not dry_run and output is None:
        report = _invalid_package_create_report(
            "input",
            "--output is required when --dry-run is not set",
        )
        _emit_package_create_report(report, output_format)
        raise typer.Exit(code=2)
    output_requested = output is not None
    if output is not None:
        destination_error = _package_export_destination_error(output)
        if destination_error is not None:
            report = _invalid_package_create_report(
                "input",
                destination_error,
                output_requested=True,
            )
            _emit_package_create_report(report, output_format)
            raise typer.Exit(code=2)
    if as_of is None:
        report = _invalid_package_create_report(
            "input",
            "--as-of is required",
            output_requested=output_requested,
        )
        _emit_package_create_report(report, output_format)
        raise typer.Exit(code=2)

    snapshot = load_repository(path)
    _emit_package_create_diagnostics(snapshot, output_format)
    if snapshot.has_errors:
        report = _invalid_package_create_report(
            "repository",
            "repository validation failed; Package creation refused",
            output_requested=output_requested,
        )
        _emit_package_create_report(report, output_format)
        raise typer.Exit(code=1)

    try:
        context_date = _parse_date(as_of)
        compiled = compile_context(snapshot, handoff_id, context_date)
    except CompilationError as error:
        report = _invalid_package_create_report(
            "compile",
            str(error),
            output_requested=output_requested,
        )
        _emit_package_create_report(report, output_format)
        raise typer.Exit(code=1) from error

    if (
        approval_source is None
        or approval_handoff_id is None
        or approval_context_date is None
        or approval_fingerprint is None
        or approval_confirmed_at is None
    ):
        report = _invalid_package_create_report(
            "missing_approval",
            "explicit approval source, scope, and confirmed_at are required",
            output_requested=output_requested,
        )
        _emit_package_create_report(report, output_format)
        raise typer.Exit(code=3)

    try:
        approval = ApprovalInput.model_validate(
            {
                "status": "user-approved",
                "source": approval_source,
                "confirmed_at": approval_confirmed_at,
                "scope": {
                    "handoff_id": approval_handoff_id,
                    "context_date": approval_context_date,
                    "source_fingerprint": approval_fingerprint,
                },
            }
        )
    except ValidationError as error:
        report = _invalid_package_create_report(
            "missing_approval",
            str(error),
            output_requested=output_requested,
        )
        _emit_package_create_report(report, output_format)
        raise typer.Exit(code=3) from error

    if approval.source != "explicit_user_confirmation":
        report = _invalid_package_create_report(
            "approval_source",
            "approved_record requires a validated record input; only explicit_user_confirmation "
            "is supported by this dry-run command",
            output_requested=output_requested,
        )
        _emit_package_create_report(report, output_format)
        raise typer.Exit(code=3)

    if approval.scope.handoff_id != compiled.handoff.id:
        report = _invalid_package_create_report(
            "handoff_mismatch",
            "approval scope does not match the compiled handoff",
            output_requested=output_requested,
        )
        _emit_package_create_report(report, output_format)
        raise typer.Exit(code=3)
    if approval.scope.context_date != compiled.as_of:
        report = _invalid_package_create_report(
            "context_date_mismatch",
            "approval scope does not match the compiled context date",
            output_requested=output_requested,
        )
        _emit_package_create_report(report, output_format)
        raise typer.Exit(code=3)
    if approval.scope.source_fingerprint != compiled.fingerprint:
        report = _invalid_package_create_report(
            "fingerprint_mismatch",
            "approval scope does not match the compiled fingerprint",
            output_requested=output_requested,
        )
        _emit_package_create_report(report, output_format)
        raise typer.Exit(code=3)

    rendered = render_markdown(compiled, generated_at=approval.confirmed_at)

    try:
        package = create_package(
            PackageFactoryRequest(
                compiled_context=compiled,
                rendered_content=rendered,
                provenance=HandoffProvenance(
                    producer="home-framework",
                    authority_status="reviewed",
                    approval_status=approval.status,
                ),
                created_at=approval.confirmed_at,
                rendered_generated_at=approval.confirmed_at,
            )
        )
    except (PackageFactoryError, ValidationError) as error:
        code = (
            3
            if isinstance(error, PackageFactoryError)
            and error.code
            in {
                "missing_approval",
                "handoff_mismatch",
                "fingerprint_mismatch",
            }
            else 4
        )
        category = error.code if isinstance(error, PackageFactoryError) else "package"
        report = _invalid_package_create_report(
            category,
            str(error),
            output_requested=output_requested,
        )
        _emit_package_create_report(report, output_format)
        raise typer.Exit(code=code) from error

    if output is None:
        report = _package_create_report(package, approval, compiled.documents)
        _emit_package_create_report(report, output_format)
        return

    try:
        export_result = export_package(package, output)
    except PackageExportConflictError as error:
        report = _invalid_package_create_report(
            "conflict",
            str(error),
            output_requested=True,
            status="conflict",
        )
        _emit_package_create_report(report, output_format)
        raise typer.Exit(code=5) from error
    except (PackageExportError, OSError) as error:
        report = _invalid_package_create_report(
            "export",
            str(error),
            output_requested=True,
            status="failed",
        )
        _emit_package_create_report(report, output_format)
        raise typer.Exit(code=5) from error

    report = _package_create_report(
        package,
        approval,
        compiled.documents,
        export_result,
    )
    _emit_package_create_report(report, output_format)


if __name__ == "__main__":
    app()
