from pathlib import Path

import pytest

from home_framework.path_safety import PathSafetyError, first_symlink_component


def test_path_inspection_oserror_becomes_structured_safety_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "workspace"
    target.mkdir()
    real_lstat = Path.lstat

    def deny_target(path: Path) -> object:
        if path == target:
            raise PermissionError("injected permission denial")
        return real_lstat(path)

    monkeypatch.setattr(Path, "lstat", deny_target)

    with pytest.raises(PathSafetyError, match="could not be inspected safely"):
        first_symlink_component(target)
