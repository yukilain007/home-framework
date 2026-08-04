# SPDX-FileCopyrightText: 2026 Yuki
# SPDX-License-Identifier: Apache-2.0

"""Local-only export of immutable, verified HandoffPackage artifacts."""

from __future__ import annotations

import hashlib
import os
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from home_framework.models import HandoffPackage
from home_framework.path_safety import no_follow_read_flags


class PackageExportError(Exception):
    """Base error for local HandoffPackage export and verification failures."""


class PackageExportConflictError(PackageExportError):
    """Raised when the expected artifact already contains different bytes."""


class PackageExportVerificationError(PackageExportError):
    """Raised when an artifact cannot be verified against its HandoffPackage."""


class PackageExportReadError(PackageExportVerificationError):
    """Raised when an artifact cannot be read from the local filesystem."""


@dataclass(frozen=True, slots=True)
class ExportResult:
    """Result of creating or reusing one verified local artifact."""

    path: Path
    package_digest: str
    created: bool
    verified: bool


def _artifact_name(package: HandoffPackage) -> str:
    return f"{package.handoff_id}--{package.canonical_digest()}.json"


def _canonical_bytes(package: HandoffPackage) -> bytes:
    return package.canonical_json().encode("utf-8")


def _prepare_destination(destination: Path) -> Path:
    if not isinstance(destination, Path):
        raise TypeError("destination must be a pathlib.Path")

    path = destination.absolute()
    try:
        path.mkdir(parents=True, exist_ok=True)
    except FileExistsError as error:
        raise PackageExportError("destination exists and is not a directory") from error
    except OSError as error:
        raise PackageExportError(f"could not create export destination: {error}") from error

    try:
        path_stat = path.lstat()
    except OSError as error:
        raise PackageExportError(f"could not inspect export destination: {error}") from error
    if stat.S_ISLNK(path_stat.st_mode):
        raise PackageExportError("export destination must not be a symbolic link")
    if not stat.S_ISDIR(path_stat.st_mode):
        raise PackageExportError("export destination must be a directory")
    return path


def _read_artifact(path: Path) -> bytes:
    try:
        path_stat = path.lstat()
    except FileNotFoundError as error:
        raise PackageExportReadError("artifact does not exist") from error
    except OSError as error:
        raise PackageExportReadError(f"artifact could not be inspected: {error}") from error

    if stat.S_ISLNK(path_stat.st_mode):
        raise PackageExportVerificationError("artifact must not be a symbolic link")
    if not stat.S_ISREG(path_stat.st_mode):
        raise PackageExportVerificationError("artifact must be a regular file")

    descriptor: int | None = None
    try:
        descriptor = os.open(path, no_follow_read_flags())
        opened_stat = os.fstat(descriptor)
        if not stat.S_ISREG(opened_stat.st_mode):
            raise PackageExportVerificationError("artifact changed to a non-regular file")
        with os.fdopen(descriptor, "rb", closefd=True) as opened:
            descriptor = None
            return opened.read()
    except PackageExportVerificationError:
        raise
    except (OSError, UnicodeError) as error:
        raise PackageExportReadError(f"artifact could not be read safely: {error}") from error
    finally:
        if descriptor is not None:
            os.close(descriptor)


def read_package_artifact(artifact: Path) -> bytes:
    """Read one local Package artifact without following filesystem links."""

    if not isinstance(artifact, Path):
        raise TypeError("artifact must be a pathlib.Path")
    return _read_artifact(artifact)


def verify_export(package: HandoffPackage, artifact: Path) -> bool:
    """Verify one artifact's name, bytes, digest, and model before it is reused."""

    if not isinstance(package, HandoffPackage):
        raise TypeError("package must be a HandoffPackage")
    if not isinstance(artifact, Path):
        raise TypeError("artifact must be a pathlib.Path")

    expected_path = artifact.parent / _artifact_name(package)
    if artifact.name != expected_path.name:
        raise PackageExportVerificationError("artifact filename does not match package digest")

    actual = _read_artifact(artifact)
    _verify_canonical_bytes(package, actual)
    return True


def _verify_canonical_bytes(package: HandoffPackage, actual: bytes) -> None:
    """Verify canonical package bytes before they are published at a final path."""

    expected = _canonical_bytes(package)
    if actual != expected:
        raise PackageExportVerificationError("artifact canonical bytes do not match package")
    if hashlib.sha256(actual).hexdigest() != package.canonical_digest():
        raise PackageExportVerificationError("artifact digest does not match package")

    try:
        parsed = HandoffPackage.model_validate_json(actual)
    except (ValidationError, ValueError, TypeError) as error:
        raise PackageExportVerificationError(
            "artifact does not contain a valid HandoffPackage"
        ) from error
    if parsed.canonical_json().encode("utf-8") != actual:
        raise PackageExportVerificationError("artifact is not canonical JSON")


def _temporary_artifact_path(destination: Path, artifact: Path) -> Path:
    """Reserve a same-directory temporary pathname without exposing it as final output."""

    descriptor, name = tempfile.mkstemp(
        prefix=f".{artifact.name}.",
        suffix=".tmp",
        dir=destination,
    )
    os.close(descriptor)
    temporary = Path(name)
    try:
        temporary.unlink()
    except OSError as error:
        raise PackageExportError("temporary artifact path could not be prepared") from error
    return temporary


def _remove_created_artifact(path: Path, canonical: bytes) -> None:
    """Remove only an artifact whose bytes still match the bytes published by us."""

    try:
        if _read_artifact(path) == canonical:
            path.unlink()
    except (FileNotFoundError, OSError, PackageExportVerificationError):
        return


def _create_artifact(path: Path, content: bytes) -> bool:
    no_follow = getattr(os, "O_NOFOLLOW", None)
    if no_follow is None:
        raise PackageExportError("platform does not support no-follow artifact creation")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | no_follow
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags, 0o644)
    except FileExistsError:
        return False
    except OSError as error:
        raise PackageExportError(f"artifact could not be created: {error}") from error

    try:
        with os.fdopen(descriptor, "wb", closefd=True) as opened:
            descriptor = None
            opened.write(content)
            opened.flush()
            os.fsync(opened.fileno())
    except OSError as error:
        raise PackageExportError(f"artifact could not be written: {error}") from error
    finally:
        if descriptor is not None:
            os.close(descriptor)
    return True


def export_package(package: HandoffPackage, destination: Path) -> ExportResult:
    """Create or reuse one verified JSON artifact in a local destination directory.

    The exporter accepts only an already validated HandoffPackage. It never reads a
    workspace, invokes compilation, or transmits the resulting artifact.
    """

    if not isinstance(package, HandoffPackage):
        raise TypeError("package must be a HandoffPackage")
    destination_path = _prepare_destination(destination)
    package_digest = package.canonical_digest()
    artifact = destination_path / f"{package.handoff_id}--{package_digest}.json"
    canonical = _canonical_bytes(package)
    temporary: Path | None = None
    created = False
    try:
        temporary = _temporary_artifact_path(destination_path, artifact)
        if not _create_artifact(temporary, canonical):
            raise PackageExportError("temporary artifact path unexpectedly exists")
        _verify_canonical_bytes(package, _read_artifact(temporary))

        try:
            os.link(temporary, artifact)
            created = True
        except FileExistsError:
            try:
                existing = _read_artifact(artifact)
            except PackageExportVerificationError as error:
                raise PackageExportConflictError(
                    f"existing artifact is not reusable: {error}"
                ) from error
            if existing != canonical:
                raise PackageExportConflictError(
                    "existing artifact contains a different artifact"
                ) from None

        try:
            verified = verify_export(package, artifact)
        except PackageExportVerificationError as error:
            if created:
                _remove_created_artifact(artifact, canonical)
            raise PackageExportVerificationError(
                f"exported artifact failed verification: {error}"
            ) from error
        return ExportResult(
            path=artifact,
            package_digest=package_digest,
            created=created,
            verified=verified,
        )
    finally:
        if temporary is not None:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                pass
