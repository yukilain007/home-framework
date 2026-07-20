"""Run the complete local HOME Framework quality gate."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from home_framework.quality import extract_fingerprint, run_command

ROOT = Path(__file__).parents[1]
EXAMPLE = ROOT / "examples/fictional-assistant"
AS_OF = "2026-07-20"


def main() -> int:
    python = sys.executable
    run_command(
        "schema drift",
        [python, str(ROOT / "scripts/check_schema_drift.py")],
        cwd=ROOT,
    )
    run_command("ruff format", [python, "-m", "ruff", "format", "--check", "."], cwd=ROOT)
    run_command("ruff lint", [python, "-m", "ruff", "check", "."], cwd=ROOT)
    run_command("mypy", [python, "-m", "mypy", "src", "scripts"], cwd=ROOT)
    run_command("pytest", [python, "-m", "pytest"], cwd=ROOT)
    run_command(
        "fictional example validate",
        [python, "-m", "home_framework.cli", "validate", str(EXAMPLE)],
        cwd=ROOT,
    )

    with tempfile.TemporaryDirectory(prefix=".home-framework-check-", dir=EXAMPLE) as temporary:
        output_directory = Path(temporary)
        fingerprints: list[str] = []
        for build_number in (1, 2):
            output = run_command(
                f"fictional example build {build_number}",
                [
                    python,
                    "-m",
                    "home_framework.cli",
                    "build",
                    str(EXAMPLE),
                    "--handoff",
                    "project.execution",
                    "--as-of",
                    AS_OF,
                    "--output",
                    str(output_directory / f"build-{build_number}.md"),
                ],
                cwd=ROOT,
                capture_output=True,
            )
            fingerprints.append(extract_fingerprint(output))
        if fingerprints[0] != fingerprints[1]:
            raise RuntimeError("repeated fictional builds produced different fingerprints")
        print(f"Repeated-build fingerprint: {fingerprints[0]}")

    run_command(
        "secret scan",
        [python, str(ROOT / "scripts/scan_secrets.py"), str(ROOT)],
        cwd=ROOT,
    )
    print("All HOME Framework checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
