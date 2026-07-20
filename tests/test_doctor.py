import subprocess
from datetime import date
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from home_framework.cli import app
from home_framework.compiler import compile_context
from home_framework.doctor import diagnose_workspace
from home_framework.initializer import initialize_workspace
from home_framework.renderer import render_markdown
from home_framework.repository import load_repository

runner = CliRunner()
AS_OF = date(2026, 7, 20)


def write_yaml(root: Path, relative: str, data: object) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def build_export(root: Path) -> Path:
    snapshot = load_repository(root)
    compiled = compile_context(snapshot, "project.execution", AS_OF)
    assert snapshot.manifest is not None
    output = root / snapshot.manifest.defaults.export_directory / "project.execution.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_markdown(compiled), encoding="utf-8")
    return output


def candidate_data(document_id: str, *, reviewed: bool = False) -> dict[str, object]:
    return {
        "kind": "candidate",
        "schema_version": "1.0",
        "id": document_id,
        "proposed_kind": "core",
        "content": "A fictional candidate for local testing.",
        "sensitivity": "public",
        "scope": ["project"],
        "source": {"type": "human_authored", "reference": None},
        "created_at": "2026-07-20",
        "decision": {
            "reviewed": reviewed,
            "action": "approve" if reviewed else None,
            "reviewed_at": "2026-07-20" if reviewed else None,
        },
    }


def current_data(
    document_id: str,
    *,
    status: str = "active",
    valid_from: str = "2026-07-20",
    expires_at: str | None = None,
) -> dict[str, object]:
    return {
        "kind": "current",
        "schema_version": "1.0",
        "id": document_id,
        "content": f"Fictional lifecycle content for {document_id}.",
        "status": status,
        "sensitivity": "public",
        "scope": ["lifecycle"],
        "priority": 50,
        "source": {"type": "human_authored", "reference": None},
        "created_at": "2026-07-01",
        "updated_at": "2026-07-20",
        "valid_from": valid_from,
        "expires_at": expires_at,
    }


def core_data(document_id: str, status: str) -> dict[str, object]:
    return {
        "kind": "core",
        "schema_version": "1.0",
        "id": document_id,
        "content": f"Fictional lifecycle content for {document_id}.",
        "status": status,
        "sensitivity": "public",
        "scope": ["lifecycle"],
        "priority": 50,
        "source": {"type": "human_authored", "reference": None},
        "created_at": "2026-07-01",
        "updated_at": "2026-07-20",
    }


def diagnostic_codes(root: Path) -> list[str]:
    return [item.code for item in diagnose_workspace(root, AS_OF).diagnostics]


def test_clean_non_git_workspace_reports_current_export(tmp_path: Path) -> None:
    initialize_workspace(tmp_path, "example-home")
    build_export(tmp_path)

    report = diagnose_workspace(tmp_path, AS_OF)

    assert not report.has_errors
    assert report.warning_count == 0
    assert "current_export" in [item.code for item in report.diagnostics]
    assert not any(item.code.startswith("git_") for item in report.diagnostics)


def test_repository_validation_error_is_preserved(tmp_path: Path) -> None:
    initialize_workspace(tmp_path, "example-home")
    (tmp_path / "sources/core/broken.yaml").write_text("kind: [core\n", encoding="utf-8")

    report = diagnose_workspace(tmp_path, AS_OF)

    assert report.has_errors
    assert "yaml_syntax" in [item.code for item in report.diagnostics]


def test_missing_required_directory_is_reported(tmp_path: Path) -> None:
    initialize_workspace(tmp_path, "example-home")
    (tmp_path / "candidates").rmdir()

    assert "missing_directory" in diagnostic_codes(tmp_path)


def test_missing_export_directory_is_reported(tmp_path: Path) -> None:
    initialize_workspace(tmp_path, "example-home")
    (tmp_path / "exports").rmdir()

    assert "missing_export_directory" in diagnostic_codes(tmp_path)


def test_candidate_lifecycle_is_reported(tmp_path: Path) -> None:
    initialize_workspace(tmp_path, "example-home")
    write_yaml(tmp_path, "candidates/pending.yaml", candidate_data("candidate.pending"))
    write_yaml(
        tmp_path,
        "candidates/approved.yaml",
        candidate_data("candidate.approved", reviewed=True),
    )

    codes = diagnostic_codes(tmp_path)

    assert "pending_candidate" in codes
    assert "approved_candidate" in codes


def test_lifecycle_diagnostic_uses_actual_nested_authority_path(tmp_path: Path) -> None:
    initialize_workspace(tmp_path, "example-home")
    write_yaml(
        tmp_path,
        "candidates/review/pending.yaml",
        candidate_data("candidate.nested"),
    )

    report = diagnose_workspace(tmp_path, AS_OF)

    finding = next(item for item in report.diagnostics if item.code == "pending_candidate")
    assert finding.path == "candidates/review/pending.yaml"


def test_current_and_authority_lifecycle_is_reported(tmp_path: Path) -> None:
    initialize_workspace(tmp_path, "example-home")
    write_yaml(
        tmp_path,
        "sources/current/future.yaml",
        current_data("lifecycle.future", valid_from="2026-07-21"),
    )
    write_yaml(
        tmp_path,
        "sources/current/expired.yaml",
        current_data("lifecycle.expired", valid_from="2026-07-01", expires_at="2026-07-19"),
    )
    write_yaml(
        tmp_path,
        "sources/current/expiring.yaml",
        current_data("lifecycle.expiring", expires_at="2026-07-27"),
    )
    write_yaml(
        tmp_path,
        "sources/core/inactive.yaml",
        core_data("lifecycle.inactive", "inactive"),
    )
    write_yaml(
        tmp_path,
        "sources/core/archived.yaml",
        core_data("lifecycle.archived", "archived"),
    )

    codes = diagnostic_codes(tmp_path)

    assert "future_current" in codes
    assert "expired_current" in codes
    assert "expiring_current" in codes
    assert "inactive_authority" in codes
    assert "archived_authority" in codes


def test_missing_export_is_reported(tmp_path: Path) -> None:
    initialize_workspace(tmp_path, "example-home")

    assert "missing_export" in diagnostic_codes(tmp_path)


def test_stale_export_is_reported_after_authority_change(tmp_path: Path) -> None:
    initialize_workspace(tmp_path, "example-home")
    build_export(tmp_path)
    authority_path = tmp_path / "sources/core/workflow.yaml"
    authority = yaml.safe_load(authority_path.read_text(encoding="utf-8"))
    authority["content"] = "Changed fictional authority content."
    authority_path.write_text(yaml.safe_dump(authority, sort_keys=False), encoding="utf-8")

    assert "stale_export" in diagnostic_codes(tmp_path)


def test_invalid_export_metadata_is_reported(tmp_path: Path) -> None:
    initialize_workspace(tmp_path, "example-home")
    output = tmp_path / "exports/project.execution.md"
    output.write_text("<!-- generated file: do not edit -->\n", encoding="utf-8")

    report = diagnose_workspace(tmp_path, AS_OF)

    assert report.has_errors
    assert "invalid_export_metadata" in [item.code for item in report.diagnostics]


def test_export_for_unknown_handoff_is_reported(tmp_path: Path) -> None:
    initialize_workspace(tmp_path, "example-home")
    build_export(tmp_path)
    (tmp_path / "exports/unknown.handoff.md").write_text("old export\n", encoding="utf-8")

    assert "unknown_handoff_export" in diagnostic_codes(tmp_path)


def test_git_tracked_export_is_reported_without_modifying_git(tmp_path: Path) -> None:
    initialize_workspace(tmp_path, "example-home")
    output = build_export(tmp_path)
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "add", "-f", str(output)], check=True)

    report = diagnose_workspace(tmp_path, AS_OF)

    assert "tracked_export" in [item.code for item in report.diagnostics]
    assert output.is_file()


def test_doctor_ignores_git_repository_above_workspace(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    workspace = tmp_path / "workspace"
    initialize_workspace(workspace, "example-home")
    output = build_export(workspace)
    subprocess.run(["git", "-C", str(tmp_path), "add", "-f", str(output)], check=True)

    report = diagnose_workspace(workspace, AS_OF)

    assert "tracked_export" not in [item.code for item in report.diagnostics]
    assert not any(item.code.startswith("git_") for item in report.diagnostics)


def test_doctor_git_commands_disable_optional_locks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from home_framework import doctor

    initialize_workspace(tmp_path, "example-home")
    build_export(tmp_path)
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "add", "home.yaml"], check=True)
    index = tmp_path / ".git/index"
    before_bytes = index.read_bytes()
    before_mtime = index.stat().st_mtime_ns
    observed: list[list[str]] = []
    real_run = subprocess.run

    def recording_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        observed.append(command)
        return real_run(command, **kwargs)  # type: ignore[call-overload,return-value]

    monkeypatch.setattr(doctor.subprocess, "run", recording_run)

    diagnose_workspace(tmp_path, AS_OF)

    assert observed
    assert all(command[:2] == ["git", "--no-optional-locks"] for command in observed)
    assert index.read_bytes() == before_bytes
    assert index.stat().st_mtime_ns == before_mtime


def test_doctor_disables_repository_fsmonitor_program(tmp_path: Path) -> None:
    initialize_workspace(tmp_path, "example-home")
    build_export(tmp_path)
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "add", "home.yaml"], check=True)
    sentinel = tmp_path / "fsmonitor-invoked"
    monitor = tmp_path / "fsmonitor.sh"
    monitor.write_text(
        '#!/bin/sh\nprintf invoked > "$1"\n',
        encoding="utf-8",
    )
    monitor.chmod(0o700)
    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "config",
            "core.fsmonitor",
            f"{monitor} {sentinel}",
        ],
        check=True,
    )

    diagnose_workspace(tmp_path, AS_OF)

    assert not sentinel.exists()


def test_secret_finding_is_aggregated_and_redacted(tmp_path: Path) -> None:
    initialize_workspace(tmp_path, "example-home")
    secret_value = "fictional-value-123456789"
    (tmp_path / "notes.txt").write_text(f'api_key: "{secret_value}"\n', encoding="utf-8")

    report = diagnose_workspace(tmp_path, AS_OF)

    finding = next(item for item in report.diagnostics if item.code == "secret_pattern")
    assert report.has_errors
    assert secret_value not in finding.message


def test_doctor_warning_exit_codes_depend_on_strict(tmp_path: Path) -> None:
    initialize_workspace(tmp_path, "example-home")

    normal = runner.invoke(app, ["doctor", str(tmp_path), "--as-of", "2026-07-20"])
    strict = runner.invoke(
        app,
        ["doctor", str(tmp_path), "--as-of", "2026-07-20", "--strict"],
    )

    assert normal.exit_code == 0
    assert strict.exit_code == 1
    assert "Check date: 2026-07-20" in normal.stdout
    assert "missing_export" in normal.stdout


def test_doctor_error_returns_one(tmp_path: Path) -> None:
    initialize_workspace(tmp_path, "example-home")
    (tmp_path / "home.yaml").write_text("kind: workspace\nunknown: true\n", encoding="utf-8")

    result = runner.invoke(app, ["doctor", str(tmp_path), "--as-of", "2026-07-20"])

    assert result.exit_code == 1
    assert "manifest_schema_validation" in result.stderr


def test_doctor_clean_workspace_returns_zero_under_strict(tmp_path: Path) -> None:
    initialize_workspace(tmp_path, "example-home")
    build_export(tmp_path)

    result = runner.invoke(
        app,
        ["doctor", str(tmp_path), "--as-of", "2026-07-20", "--strict"],
    )

    assert result.exit_code == 0
    assert "current_export" in result.stdout


def test_doctor_rejects_workspace_requiring_newer_framework(tmp_path: Path) -> None:
    initialize_workspace(tmp_path, "example-home")
    manifest_path = tmp_path / "home.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["framework"]["minimum_version"] = "9.0.0"
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")

    report = diagnose_workspace(tmp_path, AS_OF)

    assert report.has_errors
    assert "framework_version_too_old" in [item.code for item in report.diagnostics]
