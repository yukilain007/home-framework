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


def _package() -> HandoffPackage:
    body = "# Approved context\n"
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


def test_package_verify_accepts_valid_artifact(tmp_path: Path) -> None:
    artifact = export_package(_package(), tmp_path / "exports").path

    result = runner.invoke(cli.app, ["package", "verify", str(artifact)])

    assert result.exit_code == 0
    assert "VALID package.verify" in result.stdout
    assert "project.execution" in result.stdout
    assert "Package digest:" in result.stdout


def test_package_verify_rejects_invalid_digest(tmp_path: Path) -> None:
    artifact = export_package(_package(), tmp_path / "exports").path
    data = json.loads(artifact.read_text(encoding="utf-8"))
    data["content"]["digest"] = "sha256:" + "0" * 64
    artifact.write_text(json.dumps(data), encoding="utf-8")

    result = runner.invoke(cli.app, ["package", "verify", str(artifact)])

    assert result.exit_code == 4
    assert "digest" in result.stdout.lower() or "digest" in result.stderr.lower()


def test_package_verify_rejects_invalid_provenance(tmp_path: Path) -> None:
    data = _package().model_dump(mode="json")
    data["provenance"]["approval_status"] = "pending"
    artifact = tmp_path / "unapproved.json"
    artifact.write_text(json.dumps(data), encoding="utf-8")

    result = runner.invoke(cli.app, ["package", "verify", str(artifact)])

    assert result.exit_code == 4
    assert "provenance" in result.stdout.lower() or "provenance" in result.stderr.lower()


def test_package_verify_rejects_unknown_fields(tmp_path: Path) -> None:
    data = _package().model_dump(mode="json")
    data["provider_session"] = {"id": "forbidden"}
    artifact = tmp_path / "unknown-field.json"
    artifact.write_text(json.dumps(data), encoding="utf-8")

    result = runner.invoke(cli.app, ["package", "verify", str(artifact)])

    assert result.exit_code == 4
    assert "unknown" in result.stdout.lower() or "extra" in result.stdout.lower()


def test_package_verify_json_output_is_structured(tmp_path: Path) -> None:
    artifact = export_package(_package(), tmp_path / "exports").path

    result = runner.invoke(
        cli.app,
        ["package", "verify", str(artifact), "--format", "json"],
    )

    assert result.exit_code == 0
    report = json.loads(result.stdout)
    assert report["operation"] == "package.verify"
    assert report["status"] == "valid"
    assert report["authority_created"] is False
    assert report["delivery_performed"] is False


def test_package_verify_rejects_workspace_directory(tmp_path: Path) -> None:
    result = runner.invoke(cli.app, ["package", "verify", str(tmp_path)])

    assert result.exit_code == 2
    assert "file" in result.stdout.lower() or "directory" in result.stdout.lower()


def test_package_verify_rejects_url_input() -> None:
    result = runner.invoke(cli.app, ["package", "verify", "https://example.test/package.json"])

    assert result.exit_code == 2
    assert "url" in result.stdout.lower()


def test_package_verify_rejects_provider_argument(tmp_path: Path) -> None:
    artifact = tmp_path / "package.json"

    result = runner.invoke(
        cli.app,
        ["package", "verify", str(artifact), "--provider", "example"],
    )

    assert result.exit_code == 2


def test_package_verify_does_not_access_workspace(
    tmp_path: Path,
    monkeypatch,
) -> None:
    artifact = export_package(_package(), tmp_path / "exports").path

    def fail(*args, **kwargs):
        raise AssertionError("workspace/compiler/renderer must not be accessed")

    monkeypatch.setattr(cli, "load_repository", fail)
    monkeypatch.setattr(cli, "compile_context", fail)
    monkeypatch.setattr(cli, "render_markdown", fail)

    result = runner.invoke(cli.app, ["package", "verify", str(artifact)])

    assert result.exit_code == 0
