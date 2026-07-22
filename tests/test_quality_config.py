import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
import yaml

from home_framework.quality import extract_fingerprint, find_schema_drift, run_command

ROOT = Path(__file__).parents[1]

EXPECTED_CLASSIFIERS = [
    "Development Status :: 3 - Alpha",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Intended Audience :: Developers",
    "Topic :: Software Development :: Libraries :: Python Modules",
]


def _pyproject() -> dict[str, object]:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_public_package_identity_uses_reviewed_github_metadata() -> None:
    project = _pyproject()["project"]

    assert project["authors"] == [
        {
            "name": "Yuki",
            "email": "293018124+yukilain007@users.noreply.github.com",
        }
    ]
    assert project["urls"] == {
        "Homepage": "https://github.com/yukilain007/home-framework",
        "Repository": "https://github.com/yukilain007/home-framework",
        "Issues": "https://github.com/yukilain007/home-framework/issues",
    }


def test_public_package_classifiers_are_reviewed_and_do_not_duplicate_license() -> None:
    project = _pyproject()["project"]

    assert project["classifiers"] == EXPECTED_CLASSIFIERS
    assert not any(item.startswith("License ::") for item in project["classifiers"])


def test_sdist_excludes_internal_development_records() -> None:
    hatch = _pyproject()["tool"]["hatch"]

    assert hatch["build"]["targets"]["sdist"]["exclude"] == ["/docs/superpowers"]


def test_publish_workflow_is_manual_oidc_template() -> None:
    workflow_path = ROOT / ".github/workflows/publish.yml"
    source = workflow_path.read_text(encoding="utf-8")
    workflow = yaml.load(source, Loader=yaml.BaseLoader)

    assert set(workflow["on"]) == {"workflow_dispatch"}
    assert workflow["permissions"] == {"contents": "read", "id-token": "write"}
    assert set(workflow["jobs"]) == {"publish"}
    publish = workflow["jobs"]["publish"]
    assert publish["if"] == "github.ref_type == 'tag'"
    assert publish["environment"] == {
        "name": "pypi",
        "url": "https://pypi.org/p/home-framework",
    }
    uses = [step.get("uses") for step in publish["steps"] if "uses" in step]
    assert uses == [
        "actions/checkout@v4",
        "actions/setup-python@v5",
        "pypa/gh-action-pypi-publish@release/v1",
    ]
    assert publish["steps"][0]["with"]["ref"] == "${{ github.ref }}"
    commands = "\n".join(step.get("run", "") for step in publish["steps"])
    assert "python -m pip install build twine" in commands
    assert "python -m build" in commands
    assert "python -m twine check dist/*" in commands
    lowered = source.lower()
    for prohibited in (
        "release:",
        "twine upload",
        "uv publish",
        "poetry publish",
        "pypi_token",
        "twine_password",
        "twine_username",
        "api-token",
        "secrets.",
    ):
        assert prohibited not in lowered
    assert all(
        not line.strip().startswith(("password:", "token:")) for line in lowered.splitlines()
    )


def test_publishing_guide_keeps_publication_disabled_until_external_approval() -> None:
    guide = (ROOT / "docs/publishing.md").read_text(encoding="utf-8")

    assert "Trusted Publisher configured." in guide
    assert "PyPI publication remains pending explicit approval." in guide
    assert "Trusted Publishing" in guide
    assert "OIDC" in guide
    assert "workflow_dispatch" in guide
    assert "Alpha" in guide
    assert "Beta" in guide
    assert "Stable" in guide
    previous_tag = "v0.1.0-alpha" + ".3"
    assert previous_tag in guide
    assert "predates this workflow" in guide
    assert "does not yet exist" not in guide


def test_pre_commit_uses_required_local_hooks() -> None:
    config = yaml.safe_load((ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8"))

    assert [repository["repo"] for repository in config["repos"]] == ["local"]
    hooks = {hook["id"]: hook for hook in config["repos"][0]["hooks"]}
    assert {
        "schema-drift",
        "ruff-format-check",
        "ruff-check",
        "mypy",
        "pytest",
        "secret-scan",
    } <= set(hooks)
    assert all(hook["language"] == "system" for hook in hooks.values())
    assert all(hook["pass_filenames"] is False for hook in hooks.values())


def test_ci_workflow_has_minimal_permissions_and_required_checks() -> None:
    workflow_path = ROOT / ".github/workflows/ci.yml"
    workflow = yaml.load(workflow_path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)

    assert set(workflow["on"]) == {"push", "pull_request"}
    assert workflow["permissions"] == {"contents": "read"}
    quality = workflow["jobs"]["quality"]
    assert quality["strategy"]["matrix"]["python-version"] == ["3.11"]
    uses = [step.get("uses") for step in quality["steps"] if "uses" in step]
    assert "actions/checkout@v4" in uses
    assert "actions/setup-python@v5" in uses
    commands = "\n".join(step.get("run", "") for step in quality["steps"])
    assert 'python -m pip install -e ".[dev]"' in commands
    assert "python scripts/check.py" in commands
    assert "python scripts/scan_secrets.py ." in commands
    assert "publish" not in commands.lower()


def test_schema_drift_comparison_detects_changed_and_extra_files(tmp_path: Path) -> None:
    expected = tmp_path / "expected"
    generated = tmp_path / "generated"
    expected.mkdir()
    generated.mkdir()
    (expected / "one.json").write_text("same\n", encoding="utf-8")
    (generated / "one.json").write_text("changed\n", encoding="utf-8")
    (generated / "extra.json").write_text("extra\n", encoding="utf-8")

    assert find_schema_drift(expected, generated) == ["extra.json", "one.json"]


def test_main_quality_runner_uses_complete_schema_drift_checker() -> None:
    runner_source = (ROOT / "scripts/check.py").read_text(encoding="utf-8")

    assert "scripts/check_schema_drift.py" in runner_source
    assert '"git", "diff"' not in runner_source


def test_quality_runner_propagates_child_failure() -> None:
    with pytest.raises(subprocess.CalledProcessError) as caught:
        run_command("intentional failure", [sys.executable, "-c", "raise SystemExit(7)"])

    assert caught.value.returncode == 7


def test_fingerprint_extraction_is_strict() -> None:
    fingerprint = "a" * 64

    assert (
        extract_fingerprint(f"Selected 2 documents.\nFingerprint: {fingerprint}\n") == fingerprint
    )
    with pytest.raises(ValueError, match="fingerprint"):
        extract_fingerprint("Fingerprint: not-valid\n")
