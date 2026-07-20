from pathlib import Path

import yaml

from home_framework.repository import load_repository


def create_layout(root: Path) -> None:
    for relative in ("sources/core", "sources/current", "candidates", "handoffs"):
        (root / relative).mkdir(parents=True, exist_ok=True)
    write_yaml(root, "home.yaml", manifest_data())


def write_yaml(root: Path, relative: str, data: object) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def manifest_data() -> dict[str, object]:
    return {
        "kind": "workspace",
        "schema_version": "1.0",
        "name": "test-workspace",
        "framework": {"minimum_version": "0.1.0a2"},
        "defaults": {"export_directory": "exports"},
    }


def core_data(document_id: str = "communication.clear") -> dict[str, object]:
    return {
        "kind": "core",
        "schema_version": "1.0",
        "id": document_id,
        "content": "Use clear language for fictional project work.",
        "status": "active",
        "sensitivity": "public",
        "scope": ["project"],
        "priority": 70,
        "source": {"type": "human_authored", "reference": None},
        "created_at": "2026-07-20",
        "updated_at": "2026-07-20",
    }


def current_data(document_id: str = "project.milestone") -> dict[str, object]:
    return {
        **core_data(document_id),
        "kind": "current",
        "content": "The fictional release milestone is active.",
        "valid_from": "2026-07-20",
        "expires_at": None,
    }


def candidate_data(document_id: str = "candidate.wording") -> dict[str, object]:
    return {
        "kind": "candidate",
        "schema_version": "1.0",
        "id": document_id,
        "proposed_kind": "core",
        "content": "A fictional wording proposal awaiting review.",
        "sensitivity": "private",
        "scope": ["conversation"],
        "source": {"type": "human_authored", "reference": None},
        "created_at": "2026-07-20",
        "decision": {"reviewed": False, "action": None, "reviewed_at": None},
    }


def handoff_data() -> dict[str, object]:
    return {
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
    }


def test_valid_repository_loads_all_document_types(tmp_path: Path) -> None:
    create_layout(tmp_path)
    write_yaml(tmp_path, "sources/core/clear.yaml", core_data())
    write_yaml(tmp_path, "sources/current/milestone.yml", current_data())
    write_yaml(tmp_path, "candidates/wording.yaml", candidate_data())
    write_yaml(tmp_path, "handoffs/project.yaml", handoff_data())

    snapshot = load_repository(tmp_path)

    assert not snapshot.has_errors
    assert len(snapshot.core) == 1
    assert len(snapshot.current) == 1
    assert len(snapshot.candidates) == 1
    assert len(snapshot.handoffs) == 1
    assert snapshot.document_count == 4


def test_yaml_syntax_error_is_reported_with_relative_path(tmp_path: Path) -> None:
    create_layout(tmp_path)
    (tmp_path / "sources/core/broken.yaml").write_text("kind: [core\n", encoding="utf-8")

    snapshot = load_repository(tmp_path)

    diagnostic = next(item for item in snapshot.diagnostics if item.code == "yaml_syntax")
    assert diagnostic.severity == "error"
    assert diagnostic.path == "sources/core/broken.yaml"
    assert diagnostic.location is not None


def test_non_mapping_root_is_reported(tmp_path: Path) -> None:
    create_layout(tmp_path)
    write_yaml(tmp_path, "sources/core/list.yaml", [core_data()])

    snapshot = load_repository(tmp_path)

    assert any(item.code == "root_not_mapping" for item in snapshot.diagnostics)


def test_kind_mismatch_is_reported(tmp_path: Path) -> None:
    create_layout(tmp_path)
    write_yaml(tmp_path, "sources/core/wrong.yaml", current_data())

    snapshot = load_repository(tmp_path)

    assert any(item.code == "kind_mismatch" for item in snapshot.diagnostics)


def test_duplicate_id_across_directories_is_reported(tmp_path: Path) -> None:
    create_layout(tmp_path)
    write_yaml(tmp_path, "sources/core/one.yaml", core_data("shared.identifier"))
    write_yaml(tmp_path, "candidates/two.yaml", candidate_data("shared.identifier"))

    snapshot = load_repository(tmp_path)

    duplicate = next(item for item in snapshot.diagnostics if item.code == "duplicate_id")
    assert "sources/core/one.yaml" in duplicate.message
    assert duplicate.path == "candidates/two.yaml"


def test_handoff_dangling_references_are_reported(tmp_path: Path) -> None:
    create_layout(tmp_path)
    handoff = handoff_data()
    include = handoff["include"]
    assert isinstance(include, dict)
    include["core_ids"] = ["missing.core"]
    include["current_ids"] = ["missing.current"]
    write_yaml(tmp_path, "handoffs/project.yaml", handoff)

    snapshot = load_repository(tmp_path)

    codes = {item.code for item in snapshot.diagnostics}
    assert "missing_core_reference" in codes
    assert "missing_current_reference" in codes


def test_multiple_independent_errors_are_collected(tmp_path: Path) -> None:
    create_layout(tmp_path)
    (tmp_path / "sources/core/broken.yaml").write_text("kind: [core\n", encoding="utf-8")
    write_yaml(tmp_path, "sources/current/wrong.yaml", core_data())
    invalid = candidate_data("candidate.invalid")
    invalid["unknown"] = True
    write_yaml(tmp_path, "candidates/invalid.yaml", invalid)
    handoff = handoff_data()
    include = handoff["include"]
    assert isinstance(include, dict)
    include["core_ids"] = ["missing.core"]
    write_yaml(tmp_path, "handoffs/project.yaml", handoff)

    snapshot = load_repository(tmp_path)

    codes = {item.code for item in snapshot.diagnostics}
    assert {"yaml_syntax", "kind_mismatch", "schema_validation", "missing_core_reference"} <= codes


def test_missing_directories_are_warnings(tmp_path: Path) -> None:
    write_yaml(tmp_path, "home.yaml", manifest_data())

    snapshot = load_repository(tmp_path)

    assert not snapshot.has_errors
    assert len(snapshot.diagnostics) == 4
    assert {item.severity for item in snapshot.diagnostics} == {"warning"}
    assert {item.code for item in snapshot.diagnostics} == {"missing_directory"}


def test_nonexistent_repository_root_is_an_error(tmp_path: Path) -> None:
    snapshot = load_repository(tmp_path / "missing")

    assert snapshot.has_errors
    assert [item.code for item in snapshot.diagnostics] == ["repository_root_invalid"]


def test_symlinked_authority_file_is_rejected(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    create_layout(repository)
    outside = tmp_path / "outside.yaml"
    outside.write_text(yaml.safe_dump(core_data()), encoding="utf-8")
    (repository / "sources/core/link.yaml").symlink_to(outside)

    snapshot = load_repository(repository)

    assert snapshot.has_errors
    assert any(item.code == "symlink_file" for item in snapshot.diagnostics)
    assert snapshot.document_count == 0


def test_symlinked_recognized_directory_is_rejected(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    (repository / "sources").mkdir(parents=True)
    for relative in ("sources/current", "candidates", "handoffs"):
        (repository / relative).mkdir(parents=True)
    outside = tmp_path / "outside-core"
    outside.mkdir()
    write_yaml(outside, "authority.yaml", core_data())
    (repository / "sources/core").symlink_to(outside, target_is_directory=True)

    snapshot = load_repository(repository)

    assert snapshot.has_errors
    assert any(item.code == "symlink_directory" for item in snapshot.diagnostics)
    assert snapshot.document_count == 0


def test_symlinked_ancestor_of_recognized_directory_is_rejected(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    for relative in ("candidates", "handoffs"):
        (repository / relative).mkdir()
    outside_sources = tmp_path / "outside-sources"
    (outside_sources / "core").mkdir(parents=True)
    (outside_sources / "current").mkdir()
    write_yaml(outside_sources, "core/authority.yaml", core_data())
    (repository / "sources").symlink_to(outside_sources, target_is_directory=True)

    snapshot = load_repository(repository)

    assert snapshot.has_errors
    symlink = next(item for item in snapshot.diagnostics if item.code == "symlink_directory")
    assert symlink.path == "sources"
    assert not any(item.code == "path_outside_repository" for item in snapshot.diagnostics)
    assert snapshot.document_count == 0
