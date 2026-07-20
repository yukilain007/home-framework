"""Small reusable primitives for local and CI quality gates."""

from __future__ import annotations

import re
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import cast

_FINGERPRINT_LINE = re.compile(r"^Fingerprint: ([0-9a-f]{64})$", re.MULTILINE)


def run_command(
    label: str,
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    capture_output: bool = False,
) -> str:
    """Run one quality command and propagate any nonzero exit status."""

    print(f"==> {label}", flush=True)
    result = subprocess.run(
        list(command),
        cwd=cwd,
        check=True,
        capture_output=capture_output,
        text=True,
    )
    if capture_output:
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="")
    return cast(str | None, result.stdout) or ""


def extract_fingerprint(output: str) -> str:
    """Extract exactly one valid fingerprint line from CLI output."""

    matches = _FINGERPRINT_LINE.findall(output)
    if len(matches) != 1:
        raise ValueError("build output must contain exactly one valid fingerprint")
    return str(matches[0])


def find_schema_drift(expected: Path, generated: Path) -> list[str]:
    """Return sorted schema paths that are missing, extra, or byte-different."""

    expected_paths = {
        path.relative_to(expected).as_posix(): path for path in expected.rglob("*.json")
    }
    generated_paths = {
        path.relative_to(generated).as_posix(): path for path in generated.rglob("*.json")
    }
    drift: list[str] = []
    for relative in sorted(set(expected_paths) | set(generated_paths)):
        expected_path = expected_paths.get(relative)
        generated_path = generated_paths.get(relative)
        if expected_path is None or generated_path is None:
            drift.append(relative)
        elif expected_path.read_bytes() != generated_path.read_bytes():
            drift.append(relative)
    return drift
