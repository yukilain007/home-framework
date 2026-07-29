import re
import tomllib
from pathlib import Path

import yaml

from home_framework import __version__
from home_framework.initializer import initialize_workspace

ROOT = Path(__file__).parents[1]


def test_version_uses_hatch_file_source() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert __version__ == "0.1.0a5"
    assert pyproject["project"]["dynamic"] == ["version"]
    assert "version" not in pyproject["project"]
    assert pyproject["tool"]["hatch"]["version"]["path"] == "src/home_framework/__init__.py"


def test_initializer_uses_current_framework_version(tmp_path: Path) -> None:
    initialize_workspace(tmp_path, "example-home")
    manifest = yaml.safe_load((tmp_path / "home.yaml").read_text(encoding="utf-8"))

    assert manifest["framework"]["minimum_version"] == __version__


def test_development_version_and_example_stay_distinct_from_frozen_release_records() -> None:
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    checklist = (ROOT / "docs/release-checklist.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    freeze_path = ROOT / "docs/releases/v0.1.0-alpha.4-freeze.md"
    example = yaml.safe_load(
        (ROOT / "examples/fictional-assistant/home.yaml").read_text(encoding="utf-8")
    )

    assert "## Unreleased" in changelog
    assert "## [0.1.0a5] - 2026-07-28" in changelog
    assert "## [0.1.0a4] - 2026-07-22" in changelog
    unreleased = changelog.split("## Unreleased", maxsplit=1)[1].split("## [", maxsplit=1)[0]
    assert __version__ not in unreleased
    assert "Current development version: `0.1.0a5`" in readme
    assert "Latest published PyPI release: `0.1.0a4`" in readme
    assert "pip install home-framework" in readme
    assert "v0.1.0-alpha.5" in checklist
    previous_tag = "v0.1.0-alpha" + ".4"
    assert previous_tag not in checklist
    assert example["framework"]["minimum_version"] == __version__
    assert freeze_path.exists()
    freeze = freeze_path.read_text(encoding="utf-8")
    assert "Alpha.4 is frozen." in freeze
    assert "13c3e76373902db71f2eeb16d3945f2af1ad4a99" in freeze
    assert "Published via Trusted Publishing" in freeze


def test_previous_version_only_appears_in_historical_records() -> None:
    previous_version = "0.1.0" + "a3"
    previous_tag = "v0.1.0-alpha" + ".3"
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


def test_chinese_readme_provides_current_quickstart() -> None:
    readme_zh = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")

    assert "HOME Framework" in readme_zh
    assert "中文 Quickstart" in readme_zh
    assert "pip install home-framework" in readme_zh
    assert "home init example-home --name example-home" in readme_zh
    assert "home validate examples/fictional-assistant" in readme_zh
    assert "home build examples/fictional-assistant" in readme_zh
    assert "home doctor examples/fictional-assistant --as-of 2026-07-20" in readme_zh
    assert "不是自动记忆系统" in readme_zh
    assert "不会把候选记忆编译进上下文" in readme_zh


# Install entry points must never pin: a reader arriving at a README wants the current release,
# and a pinned entry point permanently strands them on whatever version was current when it
# was written.
INSTALL_ENTRY_POINTS = ("README.md", "README.zh-CN.md")


def test_install_entry_points_are_unpinned() -> None:
    install_command = re.compile(r"pip install home-framework(==\S+)?")

    for name in INSTALL_ENTRY_POINTS:
        content = (ROOT / name).read_text(encoding="utf-8")
        assert "pip install home-framework\n" in content, name
        pins = [suffix for suffix in install_command.findall(content) if suffix]
        assert not pins, (name, pins)


def test_fixed_artifact_documents_keep_their_verified_versions() -> None:
    demo = (ROOT / "docs/demo.md").read_text(encoding="utf-8")
    zero_tech_guide = (ROOT / "docs/guides/zero-tech-user-guide.zh-CN.md").read_text(
        encoding="utf-8"
    )
    fingerprint = "fcae86c77892749362faf3eba7d8a2a281bdba528f09c7bbab176ceaa2b882dd"

    assert "home-framework==0.1.0a4" in demo
    assert "**Verified PyPI artifact:** `0.1.0a4`" in demo
    assert f"**Context fingerprint:** `{fingerprint}`" in demo
    assert "home-framework==0.1.0a4" in zero_tech_guide


def test_public_documentation_has_no_local_links_or_agent_instructions() -> None:
    local_user_prefix = "/" + "Users" + "/"
    local_file_scheme = "file:" + "//"
    internal_instruction = "REQUIRED " + "SUB-SKILL"
    paths = [
        ROOT / "README.md",
        ROOT / "README.zh-CN.md",
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


def _public_markdown() -> list[Path]:
    """Markdown that gets rendered outside GitHub: PyPI, mirrors, scrapers."""
    return [
        *sorted(ROOT.glob("README*.md")),
        ROOT / "SECURITY.md",
        ROOT / "CONTRIBUTING.md",
        *sorted((ROOT / "docs").rglob("*.md")),
    ]


def test_public_markdown_uses_absolute_links() -> None:
    """Relative links resolve to 404 off GitHub, so every translation must be absolute."""
    relative_link = re.compile(r"]\((?!https?://|#|mailto:)([^)]*)\)")

    for path in _public_markdown():
        found = relative_link.findall(path.read_text(encoding="utf-8"))
        assert not found, (path.name, found)


def test_public_markdown_images_are_served_from_raw_not_blob_urls() -> None:
    """A blob URL returns an HTML page, so an image referencing one renders broken."""
    image = re.compile(r"!\[[^\]]*]\(([^)]+)\)")

    for path in _public_markdown():
        for url in image.findall(path.read_text(encoding="utf-8")):
            assert "/blob/" not in url, (path.name, url)
