from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

import home_framework.package_export as package_export_module
from home_framework.models import HandoffPackage
from home_framework.package_export import (
    PackageExportConflictError,
    PackageExportError,
    PackageExportVerificationError,
    export_package,
    verify_export,
)


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
            "context_date": "2026-08-03",
            "created_at": "2026-08-03T12:00:00Z",
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


def test_successful_export_creates_verified_artifact(tmp_path: Path) -> None:
    package = _package()

    result = export_package(package, tmp_path / "exports")

    expected = tmp_path / "exports" / f"project.execution--{package.canonical_digest()}.json"
    assert result.path == expected
    assert result.created is True
    assert result.verified is True
    assert result.path.read_text(encoding="utf-8") == package.canonical_json()
    assert verify_export(package, result.path) is True


def test_export_bytes_are_deterministic(tmp_path: Path) -> None:
    package = _package()

    first = export_package(package, tmp_path / "first")
    second = export_package(package, tmp_path / "second")

    assert first.path.read_bytes() == second.path.read_bytes()
    assert first.path.name == second.path.name


def test_identical_artifact_export_is_idempotent(tmp_path: Path) -> None:
    package = _package()

    first = export_package(package, tmp_path / "exports")
    second = export_package(package, tmp_path / "exports")

    assert second.path == first.path
    assert second.created is False
    assert second.verified is True


def test_different_artifact_at_expected_path_is_a_conflict(tmp_path: Path) -> None:
    package = _package()
    destination = tmp_path / "exports"
    destination.mkdir()
    artifact = destination / f"project.execution--{package.canonical_digest()}.json"
    artifact.write_text('{"not":"the package"}', encoding="utf-8")

    with pytest.raises(PackageExportConflictError, match="different artifact"):
        export_package(package, destination)


def test_tampered_artifact_fails_verification(tmp_path: Path) -> None:
    package = _package()
    artifact = export_package(package, tmp_path / "exports").path
    artifact.write_text(package.canonical_json() + "\n", encoding="utf-8")

    with pytest.raises(PackageExportVerificationError, match="canonical bytes"):
        verify_export(package, artifact)


def test_failed_write_cleans_up_temporary_and_final_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = _package()
    destination = tmp_path / "exports"

    def fail_after_partial_write(path: Path, content: bytes) -> bool:
        path.write_bytes(content[:8])
        raise PackageExportError("simulated write failure")

    monkeypatch.setattr(package_export_module, "_create_artifact", fail_after_partial_write)

    with pytest.raises(PackageExportError, match="simulated write failure"):
        export_package(package, destination)

    assert not list(destination.glob("*.json"))
    assert not list(destination.glob(".*"))


def test_failed_post_write_verification_cleans_up_final_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = _package()

    def fail_verification(*args: object, **kwargs: object) -> bool:
        raise PackageExportVerificationError("simulated verification failure")

    monkeypatch.setattr(package_export_module, "verify_export", fail_verification)

    with pytest.raises(PackageExportVerificationError, match="simulated verification failure"):
        export_package(package, tmp_path / "exports")

    assert not list((tmp_path / "exports").glob("*.json"))
    assert not list((tmp_path / "exports").glob(".*"))


def test_failed_reuse_verification_leaves_existing_artifact_unchanged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = _package()
    destination = tmp_path / "exports"
    existing = export_package(package, destination).path
    original = existing.read_bytes()

    def fail_verification(*args: object, **kwargs: object) -> bool:
        raise PackageExportVerificationError("simulated verification failure")

    monkeypatch.setattr(package_export_module, "verify_export", fail_verification)

    with pytest.raises(PackageExportVerificationError, match="simulated verification failure"):
        export_package(package, destination)

    assert existing.read_bytes() == original
