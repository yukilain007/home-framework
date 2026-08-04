from __future__ import annotations

import json
import time
from datetime import date
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from home_framework import cli
from home_framework.compiler import compile_context
from home_framework.package_verification import verify_package_artifact
from home_framework.repository import load_repository

runner = CliRunner()


def _write_yaml(root: Path, relative: str, data: object) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def _create_repository(root: Path) -> None:
    _write_yaml(
        root,
        "home.yaml",
        {
            "kind": "workspace",
            "schema_version": "1.0",
            "name": "test-workspace",
            "framework": {"minimum_version": "0.1.0a4"},
            "defaults": {"export_directory": "exports"},
        },
    )
    _write_yaml(
        root,
        "sources/core/communication.yaml",
        {
            "kind": "core",
            "schema_version": "1.0",
            "id": "communication.clear",
            "content": "Use clear language for the fictional project.",
            "status": "active",
            "sensitivity": "public",
            "scope": ["project"],
            "priority": 80,
            "source": {"type": "human_authored", "reference": None},
            "created_at": "2026-07-20",
            "updated_at": "2026-07-20",
        },
    )
    _write_yaml(
        root,
        "sources/current/release.yaml",
        {
            "kind": "current",
            "schema_version": "1.0",
            "id": "project.release",
            "content": "The fictional release milestone is active.",
            "status": "active",
            "sensitivity": "public",
            "scope": ["project"],
            "priority": 70,
            "source": {"type": "human_authored", "reference": None},
            "created_at": "2026-07-20",
            "updated_at": "2026-07-20",
            "valid_from": "2026-07-20",
            "expires_at": None,
        },
    )
    _write_yaml(
        root,
        "handoffs/project.yaml",
        {
            "kind": "handoff",
            "schema_version": "1.0",
            "id": "project.execution",
            "title": "Fictional project execution",
            "purpose": "Continue a fictional implementation.",
            "include": {
                "scopes": ["project"],
                "core_ids": [],
                "current_ids": [],
                "sensitivities": ["public"],
            },
            "output": {"format": "markdown"},
        },
    )


def _approval_args(root: Path, *, fingerprint: str | None = None) -> list[str]:
    snapshot = load_repository(root)
    compiled = compile_context(snapshot, "project.execution", date(2026, 8, 4))
    return [
        "--approval-source",
        "explicit_user_confirmation",
        "--approval-handoff-id",
        "project.execution",
        "--approval-context-date",
        "2026-08-04",
        "--approval-fingerprint",
        fingerprint or compiled.fingerprint,
        "--approval-confirmed-at",
        "2026-08-04T12:00:00Z",
    ]


def _create_args(root: Path, *approval: str, dry_run: bool = True) -> list[str]:
    args = [
        "package",
        "create",
        str(root),
        "--handoff",
        "project.execution",
        "--as-of",
        "2026-08-04",
        *approval,
    ]
    if dry_run:
        args.insert(7, "--dry-run")
    return args


def test_package_create_dry_run_previews_deterministic_package(tmp_path: Path) -> None:
    _create_repository(tmp_path)
    approval = _approval_args(tmp_path)

    first = runner.invoke(cli.app, _create_args(tmp_path, *approval, "--format", "json"))
    second = runner.invoke(cli.app, _create_args(tmp_path, *approval, "--format", "json"))

    assert first.exit_code == 0
    assert second.exit_code == 0
    first_report = json.loads(first.stdout)
    second_report = json.loads(second.stdout)
    assert first_report == second_report
    assert first_report["operation"] == "package.create"
    assert first_report["status"] == "preview"
    assert first_report["dry_run"] is True
    assert first_report["output_path"] is None
    assert first_report["authority_created"] is False
    assert first_report["delivery_performed"] is False


def test_package_create_dry_run_is_deterministic_across_execution_time(
    tmp_path: Path,
) -> None:
    _create_repository(tmp_path)
    approval = _approval_args(tmp_path)

    first = runner.invoke(cli.app, _create_args(tmp_path, *approval, "--format", "json"))
    time.sleep(1.1)
    second = runner.invoke(cli.app, _create_args(tmp_path, *approval, "--format", "json"))

    assert first.exit_code == 0
    assert second.exit_code == 0
    assert json.loads(first.stdout)["package_digest"] == json.loads(second.stdout)["package_digest"]


def test_package_create_requires_explicit_approval(tmp_path: Path) -> None:
    _create_repository(tmp_path)

    result = runner.invoke(
        cli.app,
        _create_args(tmp_path, "--format", "json"),
    )

    assert result.exit_code == 3
    report = json.loads(result.stdout)
    assert report["error_code"] == "missing_approval"


def test_package_create_rejects_fingerprint_mismatch(tmp_path: Path) -> None:
    _create_repository(tmp_path)
    approval = _approval_args(tmp_path, fingerprint="0" * 64)

    result = runner.invoke(cli.app, _create_args(tmp_path, *approval))

    assert result.exit_code == 3
    assert "fingerprint" in result.stdout.lower()


def test_package_create_rejects_handoff_mismatch(tmp_path: Path) -> None:
    _create_repository(tmp_path)
    approval = _approval_args(tmp_path)
    index = approval.index("--approval-handoff-id") + 1
    approval[index] = "other.handoff"

    result = runner.invoke(cli.app, _create_args(tmp_path, *approval))

    assert result.exit_code == 3
    assert "handoff" in result.stdout.lower()


def test_package_create_dry_run_does_not_write_or_call_external_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _create_repository(tmp_path)
    approval = _approval_args(tmp_path)

    def fail(*args: object, **kwargs: object) -> object:
        raise AssertionError("dry-run must not export, adapt, or access network")

    monkeypatch.setattr(cli, "export_package", fail)
    monkeypatch.setattr(cli, "LocalMarkdownAdapter", fail)

    result = runner.invoke(cli.app, _create_args(tmp_path, *approval))

    assert result.exit_code == 0
    assert not list(tmp_path.rglob("*.json"))
    assert not (tmp_path / "exports").exists()


def test_package_create_output_creates_verifiable_artifact(tmp_path: Path) -> None:
    _create_repository(tmp_path)
    approval = _approval_args(tmp_path)
    destination = tmp_path / "package-exports"

    result = runner.invoke(
        cli.app,
        _create_args(
            tmp_path,
            *approval,
            "--output",
            str(destination),
            "--format",
            "json",
            dry_run=False,
        ),
    )

    assert result.exit_code == 0
    report = json.loads(result.stdout)
    assert report["status"] == "created"
    assert report["output_path"] is not None
    artifact = Path(report["output_path"])
    assert artifact.is_file()
    verify_package_artifact(artifact)


def test_package_create_output_is_idempotent(tmp_path: Path) -> None:
    _create_repository(tmp_path)
    approval = _approval_args(tmp_path)
    destination = tmp_path / "package-exports"
    args = _create_args(
        tmp_path,
        *approval,
        "--output",
        str(destination),
        "--format",
        "json",
        dry_run=False,
    )

    first = runner.invoke(cli.app, args)
    second = runner.invoke(cli.app, args)

    assert first.exit_code == 0
    assert second.exit_code == 0
    assert json.loads(first.stdout)["status"] == "created"
    assert json.loads(second.stdout)["status"] == "reused"
    assert json.loads(first.stdout)["output_path"] == json.loads(second.stdout)["output_path"]


def test_package_create_output_reports_conflict(tmp_path: Path) -> None:
    _create_repository(tmp_path)
    approval = _approval_args(tmp_path)
    destination = tmp_path / "package-exports"
    args = _create_args(
        tmp_path,
        *approval,
        "--output",
        str(destination),
        "--format",
        "json",
        dry_run=False,
    )

    first = runner.invoke(cli.app, args)
    artifact = Path(json.loads(first.stdout)["output_path"])
    artifact.write_text('{"not":"the package"}', encoding="utf-8")

    second = runner.invoke(cli.app, args)

    assert first.exit_code == 0
    assert second.exit_code == 5
    report = json.loads(second.stdout)
    assert report["status"] == "conflict"
    assert artifact.read_text(encoding="utf-8") == '{"not":"the package"}'


def test_package_create_output_invalid_approval_fails_without_artifact(tmp_path: Path) -> None:
    _create_repository(tmp_path)
    destination = tmp_path / "package-exports"

    result = runner.invoke(
        cli.app,
        _create_args(
            tmp_path,
            "--output",
            str(destination),
            "--format",
            "json",
            dry_run=False,
        ),
    )

    assert result.exit_code == 3
    report = json.loads(result.stdout)
    assert report["status"] == "failed"
    assert report["error_code"] == "missing_approval"
    assert not list(destination.rglob("*.json")) if destination.exists() else True


def test_package_create_output_does_not_call_adapter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _create_repository(tmp_path)
    approval = _approval_args(tmp_path)

    def fail(*args: object, **kwargs: object) -> object:
        raise AssertionError("package create must not invoke an adapter")

    monkeypatch.setattr(cli, "LocalMarkdownAdapter", fail)
    result = runner.invoke(
        cli.app,
        _create_args(
            tmp_path,
            *approval,
            "--output",
            str(tmp_path / "package-exports"),
            "--format",
            "json",
            dry_run=False,
        ),
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout)["status"] == "created"
