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


def test_package_adapt_local_markdown_succeeds(tmp_path: Path) -> None:
    artifact = export_package(_package(), tmp_path / "exports").path

    result = runner.invoke(
        cli.app,
        ["package", "adapt", str(artifact), "--adapter", "local-markdown"],
    )

    assert result.exit_code == 0
    assert "VALID package.adapt" in result.stdout
    assert "local-markdown" in result.stdout
    assert "Artifact digest:" in result.stdout
    assert "Package digest:" in result.stdout


def test_package_adapt_rejects_invalid_package(tmp_path: Path) -> None:
    artifact = export_package(_package(), tmp_path / "exports").path
    data = json.loads(artifact.read_text(encoding="utf-8"))
    data["content"]["digest"] = "sha256:" + "0" * 64
    artifact.write_text(json.dumps(data), encoding="utf-8")

    result = runner.invoke(
        cli.app,
        ["package", "adapt", str(artifact), "--adapter", "local-markdown"],
    )

    assert result.exit_code == 4
    assert "digest" in result.stdout.lower()


def test_package_adapt_rejects_unsupported_adapter(tmp_path: Path) -> None:
    artifact = export_package(_package(), tmp_path / "exports").path

    result = runner.invoke(
        cli.app,
        ["package", "adapt", str(artifact), "--adapter", "example-provider"],
    )

    assert result.exit_code == 6
    assert "adapter" in result.stdout.lower()


def test_package_adapt_json_preserves_provenance(tmp_path: Path) -> None:
    artifact = export_package(_package(), tmp_path / "exports").path

    result = runner.invoke(
        cli.app,
        [
            "package",
            "adapt",
            str(artifact),
            "--adapter",
            "local-markdown",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    report = json.loads(result.stdout)
    assert report["operation"] == "package.adapt"
    assert report["status"] == "valid"
    assert report["adapter_id"] == "local-markdown"
    assert report["package_digest"] == _package().canonical_digest()
    assert report["source_provenance"]["approval_status"] == "user-approved"
    assert report["delivery_performed"] is False


def test_package_adapt_output_is_deterministic(tmp_path: Path) -> None:
    artifact = export_package(_package(), tmp_path / "exports").path
    arguments = [
        "package",
        "adapt",
        str(artifact),
        "--adapter",
        "local-markdown",
        "--format",
        "json",
    ]

    first = runner.invoke(cli.app, arguments)
    second = runner.invoke(cli.app, arguments)

    assert first.exit_code == 0
    assert second.exit_code == 0
    assert json.loads(first.stdout) == json.loads(second.stdout)


def test_package_adapt_does_not_access_workspace(
    tmp_path: Path,
    monkeypatch,
) -> None:
    artifact = export_package(_package(), tmp_path / "exports").path

    def fail(*args, **kwargs):
        raise AssertionError("workspace/compiler/renderer must not be accessed")

    monkeypatch.setattr(cli, "load_repository", fail)
    monkeypatch.setattr(cli, "compile_context", fail)
    monkeypatch.setattr(cli, "render_markdown", fail)

    result = runner.invoke(
        cli.app,
        ["package", "adapt", str(artifact), "--adapter", "local-markdown"],
    )

    assert result.exit_code == 0
