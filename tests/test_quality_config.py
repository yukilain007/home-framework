import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from home_framework.quality import extract_fingerprint, find_schema_drift, run_command

ROOT = Path(__file__).parents[1]


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
