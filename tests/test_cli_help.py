import re
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import home_framework

_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def _module_help(*arguments: str) -> str:
    """Capture both output streams from the active Python environment."""

    result = subprocess.run(
        [sys.executable, "-m", "home_framework.cli", *arguments, "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return _ANSI_ESCAPE_RE.sub("", f"{result.stdout}\n{result.stderr}").lower()


def test_package_help_lists_all_artifact_operations() -> None:
    help_text = _module_help("package")
    for command in ("verify", "export", "adapt", "create"):
        assert command in help_text
    assert "verify local handoffpackage artifacts" not in help_text


def test_package_subcommand_help_describes_boundaries() -> None:
    cases = {
        "create": (
            "--dry-run",
            "--output",
            "explicit approval",
            "does not deliver",
        ),
        "verify": ("local HandoffPackage", "without granting approval"),
        "export": ("atomic", "not delivery"),
        "adapt": ("external representation", "not send", "local-markdown"),
    }

    for command, phrases in cases.items():
        help_text = " ".join(_module_help("package", command).split())
        for phrase in phrases:
            assert phrase.lower() in help_text, (command, phrase)


def test_cli_module_is_current_checkout_or_installed_distribution() -> None:
    module_path = Path(home_framework.__file__).resolve()
    source_root = Path(__file__).parents[1].resolve() / "src"
    if module_path.is_relative_to(source_root):
        return

    try:
        installed_version = version("home-framework")
    except PackageNotFoundError as error:
        raise AssertionError(
            "home_framework is neither from this checkout nor an installed package"
        ) from error
    assert installed_version == home_framework.__version__
