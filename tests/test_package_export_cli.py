from __future__ import annotations

import hashlib
import json
from pathlib import Path

from typer.testing import CliRunner

from home_framework import cli
from home_framework.models import HandoffPackage
from home_framework.package_export import export_package

runner = CliRunner()


def _content_digest(body: str) -> str:
    canonical_body = body.replace("\r\n", "\n").replace("\r", "\n")
    return "sha256:" + hashlib.sha256(canonical_body.encode("utf-8")).hexdigest()


def _package(body: str = "# Approved context\n") -> HandoffPackage:
    return HandoffPackage.model_validate(
        {
            "package_schema": "1.0",
            "handoff_id": "project.execution",
            "handoff_schema": "1.0",
            "purpose": "Continue one approved project task",
            "context_date": "2026-08-04",
            "created_at": "2026-08-04T12:00:00Z",
            "source_fingerprint": "a" * 64,
            "content": {
                "media_type": "text/markdown",
                "body": body,
                "digest": _content_digest(body),
            },
            "provenance": {
                "producer": "home-framework",
                "authority_status": "reviewed",
                "approval_status": "user-approved",
            },
        }
    )


def test_package_export_cli_creates_verified_artifact(tmp_path: Path) -> None:
    package = _package()
    source = export_package(package, tmp_path / "source").path
    destination = tmp_path / "exports"

    result = runner.invoke(
        cli.app,
        ["package", "export", str(source), "--output", str(destination)],
    )

    expected = destination / f"project.execution--{package.canonical_digest()}.json"
    assert result.exit_code == 0
    assert expected.is_file()
    assert "EXPORTED package.export" in result.stdout
    assert str(expected) in result.stdout
    assert package.canonical_digest() in result.stdout


def test_package_export_cli_is_idempotent(tmp_path: Path) -> None:
    package = _package()
    source = export_package(package, tmp_path / "source").path
    destination = tmp_path / "exports"
    arguments = [
        "package",
        "export",
        str(source),
        "--output",
        str(destination),
        "--format",
        "json",
    ]

    first = runner.invoke(cli.app, arguments)
    second = runner.invoke(cli.app, arguments)

    assert first.exit_code == 0
    assert second.exit_code == 0
    assert json.loads(first.stdout)["created"] is True
    assert json.loads(second.stdout)["created"] is False
    assert json.loads(second.stdout)["verified"] is True


def test_package_export_cli_rejects_conflicting_artifact(tmp_path: Path) -> None:
    package = _package()
    source = export_package(package, tmp_path / "source").path
    destination = tmp_path / "exports"
    destination.mkdir()
    expected = destination / f"project.execution--{package.canonical_digest()}.json"
    expected.write_text('{"not":"the package"}', encoding="utf-8")

    result = runner.invoke(
        cli.app,
        ["package", "export", str(source), "--output", str(destination)],
    )

    assert result.exit_code == 5
    assert "conflict" in result.stdout.lower()


def test_package_export_cli_rejects_invalid_package(tmp_path: Path) -> None:
    package = _package()
    source = export_package(package, tmp_path / "source").path
    data = json.loads(source.read_text(encoding="utf-8"))
    data["content"]["digest"] = "sha256:" + "0" * 64
    source.write_text(json.dumps(data), encoding="utf-8")

    result = runner.invoke(
        cli.app,
        ["package", "export", str(source), "--output", str(tmp_path / "exports")],
    )

    assert result.exit_code == 4
    assert "digest" in result.stdout.lower()


def test_package_export_cli_does_not_access_workspace(
    tmp_path: Path,
    monkeypatch,
) -> None:
    package = _package()
    source = export_package(package, tmp_path / "source").path

    def fail(*args, **kwargs):
        raise AssertionError("workspace/compiler/renderer must not be accessed")

    monkeypatch.setattr(cli, "load_repository", fail)
    monkeypatch.setattr(cli, "compile_context", fail)
    monkeypatch.setattr(cli, "render_markdown", fail)

    result = runner.invoke(
        cli.app,
        ["package", "export", str(source), "--output", str(tmp_path / "exports")],
    )

    assert result.exit_code == 0
