import tomllib
from pathlib import Path

import yaml

from home_framework import __version__
from home_framework.initializer import initialize_workspace

ROOT = Path(__file__).parents[1]


def test_version_uses_hatch_file_source() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert __version__ == "0.1.0a3"
    assert pyproject["project"]["dynamic"] == ["version"]
    assert "version" not in pyproject["project"]
    assert pyproject["tool"]["hatch"]["version"]["path"] == "src/home_framework/__init__.py"


def test_initializer_uses_current_framework_version(tmp_path: Path) -> None:
    initialize_workspace(tmp_path, "example-home")
    manifest = yaml.safe_load((tmp_path / "home.yaml").read_text(encoding="utf-8"))

    assert manifest["framework"]["minimum_version"] == __version__


def test_release_documents_and_example_use_current_version() -> None:
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    checklist = (ROOT / "docs/release-checklist.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    example = yaml.safe_load(
        (ROOT / "examples/fictional-assistant/home.yaml").read_text(encoding="utf-8")
    )

    assert "## Unreleased" in changelog
    assert f"### {__version__} release candidate" in changelog
    assert f"## {__version__} -" not in changelog
    assert "Pre-release / not yet published" in readme
    assert "v0.1.0-alpha.3" in checklist
    previous_tag = "v0.1.0-alpha" + ".2"
    assert previous_tag not in checklist
    assert example["framework"]["minimum_version"] == __version__


def test_previous_version_only_appears_in_historical_records() -> None:
    previous_version = "0.1.0" + "a2"
    previous_tag = "v0.1.0-alpha" + ".2"
    current_paths = [
        ROOT / "README.md",
        ROOT / "pyproject.toml",
        ROOT / "docs/release-checklist.md",
        *sorted((ROOT / "src").rglob("*.py")),
        *sorted((ROOT / "tests").rglob("*.py")),
        *sorted((ROOT / "examples").rglob("*.yaml")),
    ]

    for path in current_paths:
        content = path.read_text(encoding="utf-8")
        assert previous_version not in content, path
        assert previous_tag not in content, path


def test_public_documentation_has_no_local_links_or_agent_instructions() -> None:
    local_user_prefix = "/" + "Users" + "/"
    local_file_scheme = "file:" + "//"
    internal_instruction = "REQUIRED " + "SUB-SKILL"
    paths = [
        ROOT / "README.md",
        ROOT / "SECURITY.md",
        ROOT / "CONTRIBUTING.md",
        ROOT / "CHANGELOG.md",
        *sorted((ROOT / "docs").rglob("*.md")),
    ]

    for path in paths:
        content = path.read_text(encoding="utf-8")
        assert local_user_prefix not in content, path
        assert local_file_scheme not in content, path
        assert internal_instruction not in content, path
