from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from home_framework.cli import app

runner = CliRunner()


def write_yaml(root: Path, relative: str, data: object) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def create_repository(
    root: Path,
    *,
    current_valid_from: str = "2026-07-20",
    export_directory: str = "exports",
) -> None:
    write_yaml(
        root,
        "home.yaml",
        {
            "kind": "workspace",
            "schema_version": "1.0",
            "name": "test-workspace",
            "framework": {"minimum_version": "0.1.0a2"},
            "defaults": {"export_directory": export_directory},
        },
    )
    write_yaml(
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
    write_yaml(
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
            "valid_from": current_valid_from,
            "expires_at": None,
        },
    )
    (root / "candidates").mkdir(parents=True, exist_ok=True)
    write_yaml(
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


def test_validate_success_returns_zero_and_document_count(tmp_path: Path) -> None:
    create_repository(tmp_path)

    result = runner.invoke(app, ["validate", str(tmp_path)])

    assert result.exit_code == 0
    assert "Validated 3 documents" in result.stdout
    assert "0 warnings" in result.stdout


def test_validate_rejects_workspace_requiring_newer_framework(tmp_path: Path) -> None:
    create_repository(tmp_path)
    manifest_path = tmp_path / "home.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["framework"]["minimum_version"] = "9.0.0"
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")

    result = runner.invoke(app, ["validate", str(tmp_path)])

    assert result.exit_code == 1
    assert "framework_version_too_old" in result.stderr


def test_validate_failure_returns_one_and_all_diagnostics(tmp_path: Path) -> None:
    (tmp_path / "sources/core").mkdir(parents=True)
    (tmp_path / "sources/core/one.yaml").write_text("kind: [core\n", encoding="utf-8")

    result = runner.invoke(app, ["validate", str(tmp_path)])

    assert result.exit_code == 1
    assert "yaml_syntax" in result.stderr
    assert result.stdout.count("missing_directory") == 3


def test_validate_nonexistent_root_returns_one(tmp_path: Path) -> None:
    result = runner.invoke(app, ["validate", str(tmp_path / "missing")])

    assert result.exit_code == 1
    assert "repository_root_invalid" in result.stderr


def test_build_success_creates_default_export(tmp_path: Path) -> None:
    create_repository(tmp_path)

    result = runner.invoke(
        app,
        [
            "build",
            str(tmp_path),
            "--handoff",
            "project.execution",
            "--as-of",
            "2026-07-20",
        ],
    )

    output = tmp_path / "exports/project.execution.md"
    assert result.exit_code == 0
    assert output.is_file()
    assert "Selected 2 documents" in result.stdout
    assert "Fingerprint:" in result.stdout
    assert "<!-- generated file: do not edit -->" in output.read_text(encoding="utf-8")
    assert not list(output.parent.glob("*.tmp"))


def test_build_rejects_workspace_requiring_newer_framework_without_output(
    tmp_path: Path,
) -> None:
    create_repository(tmp_path)
    manifest_path = tmp_path / "home.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["framework"]["minimum_version"] = "9.0.0"
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")

    result = runner.invoke(
        app,
        ["build", str(tmp_path), "--handoff", "project.execution", "--as-of", "2026-07-20"],
    )

    assert result.exit_code == 1
    assert "framework_version_too_old" in result.stderr
    assert not (tmp_path / "exports/project.execution.md").exists()


def test_build_supports_custom_output(tmp_path: Path) -> None:
    create_repository(tmp_path)
    output = tmp_path / "custom/context.md"

    result = runner.invoke(
        app,
        [
            "build",
            str(tmp_path),
            "--handoff",
            "project.execution",
            "--as-of",
            "2026-07-20",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0
    assert output.is_file()


def test_build_uses_manifest_export_directory(tmp_path: Path) -> None:
    create_repository(tmp_path, export_directory="generated/context")

    result = runner.invoke(
        app,
        [
            "build",
            str(tmp_path),
            "--handoff",
            "project.execution",
            "--as-of",
            "2026-07-20",
        ],
    )

    assert result.exit_code == 0
    assert (tmp_path / "generated/context/project.execution.md").is_file()
    assert not (tmp_path / "exports/project.execution.md").exists()


def test_build_invalid_repository_does_not_write_export(tmp_path: Path) -> None:
    create_repository(tmp_path)
    invalid = tmp_path / "sources/core/invalid.yaml"
    invalid.write_text("kind: core\nunknown: true\n", encoding="utf-8")

    result = runner.invoke(
        app,
        ["build", str(tmp_path), "--handoff", "project.execution", "--as-of", "2026-07-20"],
    )

    assert result.exit_code == 1
    assert "schema_validation" in result.stderr
    assert not (tmp_path / "exports/project.execution.md").exists()


def test_build_missing_handoff_returns_nonzero_without_export(tmp_path: Path) -> None:
    create_repository(tmp_path)

    result = runner.invoke(
        app,
        ["build", str(tmp_path), "--handoff", "missing.handoff", "--as-of", "2026-07-20"],
    )

    assert result.exit_code == 1
    assert "was not found" in result.stderr
    assert not (tmp_path / "exports/missing.handoff.md").exists()


def test_as_of_controls_current_selection(tmp_path: Path) -> None:
    create_repository(tmp_path, current_valid_from="2026-07-21")
    before = tmp_path / "exports/before.md"
    active = tmp_path / "exports/active.md"

    first = runner.invoke(
        app,
        [
            "build",
            str(tmp_path),
            "--handoff",
            "project.execution",
            "--as-of",
            "2026-07-20",
            "--output",
            str(before),
        ],
    )
    second = runner.invoke(
        app,
        [
            "build",
            str(tmp_path),
            "--handoff",
            "project.execution",
            "--as-of",
            "2026-07-21",
            "--output",
            str(active),
        ],
    )

    assert first.exit_code == second.exit_code == 0
    assert "Selected 1 documents" in first.stdout
    assert "Selected 2 documents" in second.stdout
    assert "project.release" not in before.read_text(encoding="utf-8")
    assert "project.release" in active.read_text(encoding="utf-8")


def test_invalid_as_of_returns_nonzero_without_output(tmp_path: Path) -> None:
    create_repository(tmp_path)

    result = runner.invoke(
        app,
        ["build", str(tmp_path), "--handoff", "project.execution", "--as-of", "not-a-date"],
    )

    assert result.exit_code == 1
    assert "must use YYYY-MM-DD" in result.stderr
    assert not (tmp_path / "exports/project.execution.md").exists()


def test_default_export_directory_symlink_is_rejected(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    create_repository(repository)
    outside = tmp_path / "outside"
    outside.mkdir()
    external_output = outside / "project.execution.md"
    external_output.write_text("preserve me\n", encoding="utf-8")
    (repository / "exports").symlink_to(outside, target_is_directory=True)

    result = runner.invoke(
        app,
        [
            "build",
            str(repository),
            "--handoff",
            "project.execution",
            "--as-of",
            "2026-07-20",
        ],
    )

    assert result.exit_code == 1
    assert "symlink_export_directory" in result.stderr
    assert external_output.read_text(encoding="utf-8") == "preserve me\n"


def test_default_export_target_symlink_is_rejected(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    create_repository(repository)
    output_directory = repository / "exports"
    output_directory.mkdir()
    external_output = tmp_path / "external.md"
    external_output.write_text("preserve me\n", encoding="utf-8")
    target = output_directory / "project.execution.md"
    target.symlink_to(external_output)

    result = runner.invoke(
        app,
        [
            "build",
            str(repository),
            "--handoff",
            "project.execution",
            "--as-of",
            "2026-07-20",
        ],
    )

    assert result.exit_code == 1
    assert "symbolic link" in result.stderr
    assert target.is_symlink()
    assert external_output.read_text(encoding="utf-8") == "preserve me\n"


def test_custom_output_parent_symlink_escape_is_rejected(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    create_repository(repository)
    outside = tmp_path / "outside"
    outside.mkdir()
    (repository / "custom").symlink_to(outside, target_is_directory=True)

    result = runner.invoke(
        app,
        [
            "build",
            str(repository),
            "--handoff",
            "project.execution",
            "--as-of",
            "2026-07-20",
            "--output",
            str(repository / "custom/context.md"),
        ],
    )

    assert result.exit_code == 1
    assert "symbolic link" in result.stderr
    assert not (outside / "context.md").exists()


def test_custom_absolute_output_outside_repository_is_rejected(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    create_repository(repository)
    outside = tmp_path / "outside.md"

    result = runner.invoke(
        app,
        [
            "build",
            str(repository),
            "--handoff",
            "project.execution",
            "--as-of",
            "2026-07-20",
            "--output",
            str(outside),
        ],
    )

    assert result.exit_code == 1
    assert "inside the repository" in result.stderr
    assert not outside.exists()


def test_custom_output_parent_traversal_is_rejected(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    create_repository(repository)
    outside = tmp_path / "escaped.md"

    result = runner.invoke(
        app,
        [
            "build",
            str(repository),
            "--handoff",
            "project.execution",
            "--as-of",
            "2026-07-20",
            "--output",
            str(repository / "../escaped.md"),
        ],
    )

    assert result.exit_code == 1
    assert "inside the repository" in result.stderr
    assert not outside.exists()


def test_invalid_repository_preserves_existing_export(tmp_path: Path) -> None:
    create_repository(tmp_path)
    output = tmp_path / "exports/project.execution.md"
    output.parent.mkdir()
    output.write_text("preserve me\n", encoding="utf-8")
    (tmp_path / "sources/core/invalid.yaml").write_text(
        "kind: core\nunknown: true\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["build", str(tmp_path), "--handoff", "project.execution", "--as-of", "2026-07-20"],
    )

    assert result.exit_code == 1
    assert output.read_text(encoding="utf-8") == "preserve me\n"


def test_atomic_replace_failure_preserves_existing_export(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_repository(tmp_path)
    output = tmp_path / "exports/project.execution.md"
    output.parent.mkdir()
    output.write_text("preserve me\n", encoding="utf-8")

    def fail_replace(source: object, destination: object) -> None:
        raise OSError("injected replace failure")

    monkeypatch.setattr("home_framework.cli.os.replace", fail_replace)

    result = runner.invoke(
        app,
        ["build", str(tmp_path), "--handoff", "project.execution", "--as-of", "2026-07-20"],
    )

    assert result.exit_code == 1
    assert "injected replace failure" in result.stderr
    assert output.read_text(encoding="utf-8") == "preserve me\n"
    assert not list(output.parent.glob("*.tmp"))


def test_init_command_creates_buildable_workspace(tmp_path: Path) -> None:
    target = tmp_path / "workspace"

    initialized = runner.invoke(app, ["init", str(target), "--name", "example-home"])
    validated = runner.invoke(app, ["validate", str(target)])
    built = runner.invoke(
        app,
        ["build", str(target), "--handoff", "project.execution", "--as-of", "2026-07-20"],
    )

    assert initialized.exit_code == 0
    assert "Initialized" in initialized.stdout
    assert validated.exit_code == 0
    assert built.exit_code == 0


def test_init_command_is_idempotent(tmp_path: Path) -> None:
    target = tmp_path / "workspace"
    first = runner.invoke(app, ["init", str(target), "--name", "example-home"])

    second = runner.invoke(app, ["init", str(target), "--name", "ignored-name"])

    assert first.exit_code == 0
    assert second.exit_code == 0
    assert "already initialized" in second.stdout


def test_init_command_rejects_nonempty_unknown_directory(tmp_path: Path) -> None:
    target = tmp_path / "unknown"
    target.mkdir()
    existing = target / "keep.txt"
    existing.write_text("preserve me\n", encoding="utf-8")

    result = runner.invoke(app, ["init", str(target), "--name", "example-home"])

    assert result.exit_code == 1
    assert "non-empty" in result.stderr
    assert existing.read_text(encoding="utf-8") == "preserve me\n"
