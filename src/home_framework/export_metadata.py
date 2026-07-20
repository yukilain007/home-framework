"""Machine-readable export metadata and deterministic stale classification."""

from __future__ import annotations

import json
import os
import stat
from datetime import date
from pathlib import Path
from typing import Annotated, Literal

from pydantic import StringConstraints, ValidationError

from home_framework.compiler import CompiledContext
from home_framework.models import DocumentId, StrictModel
from home_framework.path_safety import no_follow_read_flags
from home_framework.repository import Diagnostic

EXPORT_METADATA_PREFIX = "<!-- home-framework-export: "
EXPORT_METADATA_SUFFIX = " -->"
MAX_EXPORT_METADATA_LINE_BYTES = 4096


class ExportMetadata(StrictModel):
    """Strict data embedded in the first line of every Markdown export."""

    schema_version: Literal["1.0"]
    handoff_id: DocumentId
    context_date: date
    fingerprint: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class ExportMetadataError(Exception):
    """Raised when an export marker cannot be parsed safely."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def metadata_for_context(compiled: CompiledContext) -> ExportMetadata:
    """Create protocol metadata from an immutable compilation result."""

    return ExportMetadata(
        schema_version="1.0",
        handoff_id=compiled.handoff.id,
        context_date=compiled.as_of,
        fingerprint=compiled.fingerprint,
    )


def serialize_export_metadata(metadata: ExportMetadata) -> str:
    """Serialize metadata as one canonical HTML comment line."""

    payload = json.dumps(
        metadata.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return f"{EXPORT_METADATA_PREFIX}{payload}{EXPORT_METADATA_SUFFIX}"


def parse_export_metadata(content: str) -> ExportMetadata:
    """Parse only the fixed metadata marker on the first line."""

    first_line = content.splitlines()[0] if content else ""
    if not first_line.startswith(EXPORT_METADATA_PREFIX) or not first_line.endswith(
        EXPORT_METADATA_SUFFIX
    ):
        raise ExportMetadataError(
            "missing_export_metadata",
            "supported export metadata is missing from the first line",
        )
    payload = first_line[len(EXPORT_METADATA_PREFIX) : -len(EXPORT_METADATA_SUFFIX)]
    try:
        raw = json.loads(payload)
    except json.JSONDecodeError as error:
        raise ExportMetadataError(
            "invalid_export_metadata", "export metadata is not valid JSON"
        ) from error
    if not isinstance(raw, dict):
        raise ExportMetadataError(
            "invalid_export_metadata",
            "export metadata root must be an object",
        )
    schema_version = raw.get("schema_version")
    if schema_version is not None and schema_version != "1.0":
        raise ExportMetadataError(
            "unsupported_export_metadata",
            f"unsupported export metadata schema version {schema_version!r}",
        )
    try:
        return ExportMetadata.model_validate(raw)
    except ValidationError as error:
        raise ExportMetadataError(
            "invalid_export_metadata",
            "export metadata does not match schema version 1.0",
        ) from error


def _read_export_first_line(path: Path) -> str:
    """Read one bounded line from a no-follow regular-file descriptor."""

    path_stat = path.lstat()
    if stat.S_ISLNK(path_stat.st_mode):
        raise ExportMetadataError(
            "invalid_export_metadata",
            "export target is a symbolic link and was not read",
        )
    if not stat.S_ISREG(path_stat.st_mode):
        raise ExportMetadataError(
            "invalid_export_metadata",
            "export path is not a regular file",
        )

    descriptor: int | None = None
    try:
        descriptor = os.open(path, no_follow_read_flags())
        opened_stat = os.fstat(descriptor)
        if not stat.S_ISREG(opened_stat.st_mode):
            raise ExportMetadataError(
                "invalid_export_metadata",
                "export changed to a non-regular file and was not read",
            )
        with os.fdopen(descriptor, "rb", closefd=True) as opened:
            descriptor = None
            first_line = opened.readline(MAX_EXPORT_METADATA_LINE_BYTES + 1)
    finally:
        if descriptor is not None:
            os.close(descriptor)

    if len(first_line) > MAX_EXPORT_METADATA_LINE_BYTES:
        raise ExportMetadataError(
            "invalid_export_metadata",
            f"export metadata first line exceeds {MAX_EXPORT_METADATA_LINE_BYTES} bytes",
        )
    return first_line.decode("utf-8")


def classify_export(
    path: Path,
    diagnostic_path: str,
    compiled: CompiledContext,
) -> Diagnostic:
    """Classify one expected export without parsing arbitrary Markdown."""

    try:
        content = _read_export_first_line(path)
    except FileNotFoundError:
        return Diagnostic(
            "warning",
            "missing_export",
            diagnostic_path,
            None,
            "expected handoff export is missing",
        )
    except ExportMetadataError as error:
        return Diagnostic(
            "error",
            "invalid_export_metadata",
            diagnostic_path,
            None,
            f"{error.code}: {error}",
        )
    except (OSError, UnicodeError) as error:
        return Diagnostic("error", "export_read", diagnostic_path, None, str(error))
    try:
        metadata = parse_export_metadata(content)
    except ExportMetadataError as error:
        return Diagnostic(
            "error",
            "invalid_export_metadata",
            diagnostic_path,
            None,
            f"{error.code}: {error}",
        )

    expected = metadata_for_context(compiled)
    if metadata != expected:
        return Diagnostic(
            "warning",
            "stale_export",
            diagnostic_path,
            None,
            "export metadata does not match the current handoff, context date, or fingerprint",
        )
    return Diagnostic(
        "info",
        "current_export",
        diagnostic_path,
        None,
        "export metadata matches the current compiled context",
    )
