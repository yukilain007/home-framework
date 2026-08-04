from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from typer.testing import CliRunner

import home_framework
from home_framework.cli import app

runner = CliRunner()


def _help_text(result: object) -> str:
    """Read help from every stream used by supported Typer/Click versions."""

    streams = [getattr(result, "stdout", ""), getattr(result, "output", "")]
    try:
        streams.append(getattr(result, "stderr", ""))
    except ValueError:
        # Older Click versions only expose the combined output stream.
        pass
    return " ".join(stream for stream in streams if stream).lower()


def test_package_help_lists_all_artifact_operations() -> None:
    result = runner.invoke(app, ["package", "--help"])

    assert result.exit_code == 0
    help_text = _help_text(result)
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
        result = runner.invoke(app, ["package", command, "--help"])

        assert result.exit_code == 0
        help_text = " ".join(_help_text(result).split())
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
