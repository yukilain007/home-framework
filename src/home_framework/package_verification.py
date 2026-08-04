# SPDX-FileCopyrightText: 2026 Yuki
# SPDX-License-Identifier: Apache-2.0

"""Read-only verification of local HandoffPackage artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from home_framework.models import HandoffPackage
from home_framework.package_export import (
    PackageExportReadError,
    PackageExportVerificationError,
    read_package_artifact,
    verify_export,
)

VerificationCategory = Literal[
    "input",
    "read",
    "schema",
    "unsupported_schema",
    "digest",
    "fingerprint",
    "provenance",
    "unknown_field",
]


class PackageVerificationError(ValueError):
    """Raised when a Package artifact fails a verification check."""

    def __init__(self, category: VerificationCategory, message: str) -> None:
        super().__init__(message)
        self.category = category


def _validation_category(error: ValidationError) -> VerificationCategory:
    message = str(error).lower()
    if "approval_status" in message or "authority_status" in message or "provenance" in message:
        return "provenance"
    if "source_fingerprint" in message:
        return "fingerprint"
    if "digest" in message:
        return "digest"
    if "extra_forbidden" in message or "extra inputs are not permitted" in message:
        return "unknown_field"
    return "schema"


def _validate_schema_versions(data: object) -> None:
    if not isinstance(data, dict):
        raise PackageVerificationError("schema", "artifact JSON must contain an object")
    for field in ("package_schema", "handoff_schema"):
        value = data.get(field)
        if value != "1.0":
            raise PackageVerificationError(
                "unsupported_schema",
                f"unsupported {field}: {value!r}; expected '1.0'",
            )


def verify_package_artifact(artifact: Path) -> HandoffPackage:
    """Verify and return one immutable HandoffPackage from a local artifact."""

    if not isinstance(artifact, Path):
        raise TypeError("artifact must be a pathlib.Path")

    raw = read_package_artifact(artifact)

    try:
        decoded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PackageVerificationError("schema", "artifact is not valid UTF-8 JSON") from error

    _validate_schema_versions(decoded)

    try:
        package = HandoffPackage.model_validate(decoded)
    except ValidationError as error:
        raise PackageVerificationError(_validation_category(error), str(error)) from error

    try:
        verify_export(package, artifact)
    except PackageExportReadError:
        raise
    except PackageExportVerificationError as error:
        raise PackageVerificationError("digest", str(error)) from error

    return package
