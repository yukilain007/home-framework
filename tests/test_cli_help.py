from typer.testing import CliRunner

from home_framework.cli import app

runner = CliRunner()


def test_package_help_lists_all_artifact_operations() -> None:
    result = runner.invoke(app, ["package", "--help"])

    assert result.exit_code == 0
    for command in ("verify", "export", "adapt", "create"):
        assert command in result.stdout
    assert "Verify local HandoffPackage artifacts" not in result.stdout


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
        help_text = " ".join(result.stdout.split()).lower()
        for phrase in phrases:
            assert phrase.lower() in help_text, (command, phrase)
