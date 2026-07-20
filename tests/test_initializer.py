from datetime import date
from pathlib import Path

import pytest

from home_framework.compiler import compile_context
from home_framework.initializer import InitializationError, _atomic_write, initialize_workspace
from home_framework.repository import load_repository

EXPECTED_DIRECTORIES = (
    "sources/core",
    "sources/current",
    "candidates",
    "handoffs",
    "exports",
)


def test_initializes_nonexistent_directory(tmp_path: Path) -> None:
    target = tmp_path / "new-workspace"

    result = initialize_workspace(target, "example-home")

    assert result.root == target.resolve()
    assert not result.already_initialized
    assert (target / "home.yaml").is_file()
    assert all((target / relative).is_dir() for relative in EXPECTED_DIRECTORIES)
    assert not (target / ".git").exists()


def test_initializes_existing_empty_directory(tmp_path: Path) -> None:
    target = tmp_path / "empty"
    target.mkdir()

    initialize_workspace(target, "example-home")

    assert (target / "home.yaml").is_file()
    assert all((target / relative).is_dir() for relative in EXPECTED_DIRECTORIES)


def test_repeated_initialization_is_idempotent_and_preserves_files(tmp_path: Path) -> None:
    target = tmp_path / "workspace"
    initialize_workspace(target, "example-home")
    gitignore = target / ".gitignore"
    gitignore.write_text(gitignore.read_text(encoding="utf-8") + "custom.local\n", encoding="utf-8")
    before = gitignore.read_bytes()

    result = initialize_workspace(target, "different-name")

    assert result.already_initialized
    assert gitignore.read_bytes() == before


def test_nonempty_unknown_directory_is_rejected_without_overwrite(tmp_path: Path) -> None:
    target = tmp_path / "unknown"
    target.mkdir()
    existing = target / "keep.txt"
    existing.write_text("preserve me\n", encoding="utf-8")

    with pytest.raises(InitializationError, match="non-empty"):
        initialize_workspace(target, "example-home")

    assert existing.read_text(encoding="utf-8") == "preserve me\n"
    assert not (target / "home.yaml").exists()


def test_symlink_target_is_rejected(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    target = tmp_path / "workspace"
    target.symlink_to(outside, target_is_directory=True)

    with pytest.raises(InitializationError, match="symbolic link"):
        initialize_workspace(target, "example-home")

    assert not list(outside.iterdir())


@pytest.mark.parametrize(
    "relative_target",
    ["existing", "missing", "existing-parent/missing"],
)
def test_symlinked_target_ancestor_is_rejected_without_external_write(
    tmp_path: Path,
    relative_target: str,
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    if relative_target == "existing":
        (outside / relative_target).mkdir()
    elif relative_target.startswith("existing-parent/"):
        (outside / "existing-parent").mkdir()
    link = tmp_path / "linked-parent"
    link.symlink_to(outside, target_is_directory=True)

    with pytest.raises(InitializationError, match="symbolic link"):
        initialize_workspace(link / relative_target, "example-home")

    assert not (outside / relative_target / "home.yaml").exists()


def test_symlinked_key_directory_is_rejected_without_external_write(tmp_path: Path) -> None:
    target = tmp_path / "workspace"
    initialize_workspace(target, "example-home")
    core_directory = target / "sources/core"
    for path in core_directory.iterdir():
        path.unlink()
    core_directory.rmdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    core_directory.symlink_to(outside, target_is_directory=True)

    with pytest.raises(InitializationError, match="valid workspace"):
        initialize_workspace(target, "example-home")

    assert not list(outside.iterdir())


def test_invalid_name_is_rejected_before_creating_target(tmp_path: Path) -> None:
    target = tmp_path / "workspace"

    with pytest.raises(InitializationError, match="workspace name"):
        initialize_workspace(target, "../escape")

    assert not target.exists()


def test_write_failure_rolls_back_new_workspace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "workspace"
    writes = 0

    from home_framework import initializer

    real_atomic_write = initializer._atomic_write

    def fail_second_write(path: Path, content: str) -> None:
        nonlocal writes
        writes += 1
        if writes == 2:
            raise OSError("injected initialization failure")
        real_atomic_write(path, content)

    monkeypatch.setattr(initializer, "_atomic_write", fail_second_write)

    with pytest.raises(InitializationError, match="injected initialization failure"):
        initialize_workspace(target, "example-home")

    assert not target.exists()


def test_write_failure_rolls_back_all_new_ancestor_directories(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = tmp_path / "new-parent"
    target = parent / "workspace"

    from home_framework import initializer

    real_atomic_write = initializer._atomic_write
    writes = 0

    def fail_second_write(path: Path, content: str) -> None:
        nonlocal writes
        writes += 1
        if writes == 2:
            raise OSError("injected nested initialization failure")
        real_atomic_write(path, content)

    monkeypatch.setattr(initializer, "_atomic_write", fail_second_write)

    with pytest.raises(InitializationError, match="injected nested initialization failure"):
        initialize_workspace(target, "example-home")

    assert not parent.exists()


def test_ancestor_creation_failure_rolls_back_already_created_parent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = tmp_path / "new-parent"
    target = parent / "workspace"
    real_mkdir = Path.mkdir

    def fail_target_mkdir(path: Path, *args: object, **kwargs: object) -> None:
        if path == target:
            raise OSError("injected ancestor creation failure")
        real_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", fail_target_mkdir)

    with pytest.raises(InitializationError, match="injected ancestor creation failure"):
        initialize_workspace(target, "example-home")

    assert not parent.exists()


def test_atomic_write_never_replaces_existing_file(tmp_path: Path) -> None:
    target = tmp_path / "existing.txt"
    target.write_text("preserve me\n", encoding="utf-8")

    with pytest.raises(FileExistsError):
        _atomic_write(target, "replacement\n")

    assert target.read_text(encoding="utf-8") == "preserve me\n"


def test_initialized_workspace_validates_and_builds(tmp_path: Path) -> None:
    initialize_workspace(tmp_path, "example-home")

    snapshot = load_repository(tmp_path)
    compiled = compile_context(snapshot, "project.execution", date(2026, 7, 20))

    assert not snapshot.has_errors
    assert [document.id for document in compiled.documents] == [
        "workflow.clear",
        "project.status",
    ]
