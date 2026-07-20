"""Run HOME Framework's bounded, redacted local secret scanner."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from home_framework.repository import Diagnostic
from home_framework.security import scan_workspace


def _format_diagnostic(diagnostic: Diagnostic) -> str:
    location = f":{diagnostic.location}" if diagnostic.location else ""
    return (
        f"{diagnostic.severity.upper()} {diagnostic.code} "
        f"{diagnostic.path}{location}: {diagnostic.message}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan one local workspace for secret patterns.")
    parser.add_argument("path", nargs="?", type=Path, default=Path("."))
    parser.add_argument("--allowlist", type=Path, default=None)
    arguments = parser.parse_args()

    diagnostics = scan_workspace(arguments.path, arguments.allowlist)
    for diagnostic in diagnostics:
        stream = sys.stderr if diagnostic.severity == "error" else sys.stdout
        print(_format_diagnostic(diagnostic), file=stream)
    return 1 if any(item.severity == "error" for item in diagnostics) else 0


if __name__ == "__main__":
    raise SystemExit(main())
