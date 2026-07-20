import json
import subprocess
import sys
from pathlib import Path

from home_framework.export_metadata import ExportMetadata
from home_framework.models import (
    CandidateDocument,
    CoreDocument,
    CurrentDocument,
    HandoffDocument,
    WorkspaceManifest,
)


def test_export_schemas_matches_pydantic_models(tmp_path: Path) -> None:
    script = Path(__file__).parents[1] / "scripts/export_schemas.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    output_dir = tmp_path / "schemas"

    expected = {
        "core.schema.json": CoreDocument.model_json_schema(),
        "current.schema.json": CurrentDocument.model_json_schema(),
        "candidate.schema.json": CandidateDocument.model_json_schema(),
        "handoff.schema.json": HandoffDocument.model_json_schema(),
        "workspace.schema.json": WorkspaceManifest.model_json_schema(),
        "export-metadata.schema.json": ExportMetadata.model_json_schema(),
    }
    assert {path.name for path in output_dir.iterdir()} == set(expected)
    committed_dir = Path(__file__).parents[1] / "schemas"
    for filename, schema in expected.items():
        assert json.loads((output_dir / filename).read_text(encoding="utf-8")) == schema
        assert (output_dir / filename).read_bytes().endswith(b"\n")
        assert (committed_dir / filename).read_bytes() == (output_dir / filename).read_bytes()
