from pathlib import Path

import yaml

from home_framework.repository import load_repository


def write_yaml(root: Path, relative: str, data: object) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def manifest_data() -> dict[str, object]:
    return {
        "kind": "workspace",
        "schema_version": "1.0",
        "name": "example-home",
        "framework": {"minimum_version": "0.1.0a2"},
        "defaults": {"export_directory": "exports"},
    }


def create_authority_directories(root: Path) -> None:
    for relative in ("sources/core", "sources/current", "candidates", "handoffs"):
        (root / relative).mkdir(parents=True, exist_ok=True)


def test_repository_loads_workspace_manifest(tmp_path: Path) -> None:
    create_authority_directories(tmp_path)
    write_yaml(tmp_path, "home.yaml", manifest_data())

    snapshot = load_repository(tmp_path)

    assert not snapshot.has_errors
    assert snapshot.manifest is not None
    assert snapshot.manifest.name == "example-home"


def test_repository_requires_workspace_manifest(tmp_path: Path) -> None:
    create_authority_directories(tmp_path)

    snapshot = load_repository(tmp_path)

    assert snapshot.has_errors
    assert any(item.code == "missing_manifest" for item in snapshot.diagnostics)


def test_repository_reports_invalid_workspace_manifest(tmp_path: Path) -> None:
    create_authority_directories(tmp_path)
    data = manifest_data()
    data["unexpected"] = True
    write_yaml(tmp_path, "home.yaml", data)

    snapshot = load_repository(tmp_path)

    assert snapshot.has_errors
    assert any(item.code == "manifest_schema_validation" for item in snapshot.diagnostics)
    assert snapshot.manifest is None


def test_repository_rejects_symlinked_workspace_manifest(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    create_authority_directories(repository)
    outside = tmp_path / "outside.yaml"
    outside.write_text(yaml.safe_dump(manifest_data()), encoding="utf-8")
    (repository / "home.yaml").symlink_to(outside)

    snapshot = load_repository(repository)

    assert snapshot.has_errors
    assert any(item.code == "manifest_symlink" for item in snapshot.diagnostics)


def test_repository_rejects_workspace_root_with_symlinked_ancestor(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    repository = outside / "repository"
    create_authority_directories(repository)
    write_yaml(repository, "home.yaml", manifest_data())
    link = tmp_path / "linked-parent"
    link.symlink_to(outside, target_is_directory=True)

    snapshot = load_repository(link / "repository")

    assert snapshot.document_count == 0
    assert [item.code for item in snapshot.diagnostics] == ["repository_root_symlink"]
    assert snapshot.manifest is None


def test_repository_rejects_symlinked_export_directory(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    create_authority_directories(repository)
    write_yaml(repository, "home.yaml", manifest_data())
    outside = tmp_path / "outside"
    outside.mkdir()
    (repository / "exports").symlink_to(outside, target_is_directory=True)

    snapshot = load_repository(repository)

    assert snapshot.has_errors
    assert any(item.code == "symlink_export_directory" for item in snapshot.diagnostics)
