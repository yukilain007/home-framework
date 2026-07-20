"""Export JSON Schema files from the Pydantic model authority."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

from pydantic import BaseModel

from home_framework.export_metadata import ExportMetadata
from home_framework.models import (
    CandidateDocument,
    CoreDocument,
    CurrentDocument,
    HandoffDocument,
    WorkspaceManifest,
)

SCHEMA_MODELS: Final[dict[str, type[BaseModel]]] = {
    "core.schema.json": CoreDocument,
    "current.schema.json": CurrentDocument,
    "candidate.schema.json": CandidateDocument,
    "handoff.schema.json": HandoffDocument,
    "workspace.schema.json": WorkspaceManifest,
    "export-metadata.schema.json": ExportMetadata,
}


def export_schemas(output_dir: Path = Path("schemas")) -> None:
    """Write deterministic schemas derived from the current Pydantic models."""

    output_dir.mkdir(parents=True, exist_ok=True)
    for filename, model in SCHEMA_MODELS.items():
        rendered = json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + "\n"
        (output_dir / filename).write_text(rendered, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    export_schemas()
