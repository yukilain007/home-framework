"""Verify committed JSON Schemas match current Pydantic models."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from home_framework.quality import find_schema_drift

ROOT = Path(__file__).parents[1]


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="home-framework-schemas-") as temporary:
        generated_root = Path(temporary)
        subprocess.run(
            [sys.executable, str(ROOT / "scripts/export_schemas.py")],
            cwd=generated_root,
            check=True,
        )
        drift = find_schema_drift(ROOT / "schemas", generated_root / "schemas")
    if drift:
        for relative in drift:
            print(f"schema drift: {relative}", file=sys.stderr)
        return 1
    print("Schema files match Pydantic models.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
