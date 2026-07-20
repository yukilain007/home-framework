"""Bounded, high-confidence local secret scanning."""

from __future__ import annotations

import os
import re
import stat
from pathlib import Path

from home_framework.path_safety import (
    PathSafetyError,
    first_symlink_component,
    no_follow_read_flags,
)
from home_framework.repository import Diagnostic

MAX_SCANNED_FILE_BYTES = 1024 * 1024

_EXCLUDED_DIRECTORIES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
}
_PATTERNS = (
    (
        "credential_assignment",
        re.compile(
            r"(?i)\b(?:api[_-]?key|password|access[_-]?token|private[_-]?key)\b"
            r"\s*[:=]\s*[\"']?[A-Za-z0-9_./+=-]{8,}"
        ),
    ),
    (
        "pem_private_key",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    ),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("openai_api_key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b")),
)


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _load_allowlist(path: Path, root: Path, diagnostics: list[Diagnostic]) -> set[tuple[str, str]]:
    try:
        allowlist_relative = _relative(path.absolute(), root)
    except ValueError:
        diagnostics.append(
            Diagnostic(
                "error",
                "secret_allowlist_outside_workspace",
                ".",
                None,
                "secret-scan allowlist must remain inside the workspace",
            )
        )
        return set()
    if path.is_symlink():
        diagnostics.append(
            Diagnostic(
                "error",
                "secret_allowlist_symlink",
                allowlist_relative,
                None,
                "secret-scan allowlist must not be a symbolic link",
            )
        )
        return set()
    if not path.exists():
        return set()
    try:
        allowlist_stat = path.lstat()
    except OSError as error:
        diagnostics.append(
            Diagnostic("error", "secret_allowlist_read", allowlist_relative, None, str(error))
        )
        return set()
    if not stat.S_ISREG(allowlist_stat.st_mode):
        diagnostics.append(
            Diagnostic(
                "error",
                "secret_allowlist_invalid",
                allowlist_relative,
                None,
                "secret-scan allowlist must be a regular file",
            )
        )
        return set()
    if allowlist_stat.st_size > MAX_SCANNED_FILE_BYTES:
        diagnostics.append(
            Diagnostic(
                "error",
                "secret_allowlist_too_large",
                allowlist_relative,
                None,
                f"secret-scan allowlist exceeds {MAX_SCANNED_FILE_BYTES} bytes",
            )
        )
        return set()
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        diagnostics.append(Diagnostic("error", "secret_allowlist_read", ".", None, str(error)))
        return set()
    if not resolved.is_relative_to(root):
        diagnostics.append(
            Diagnostic(
                "error",
                "secret_allowlist_outside_workspace",
                ".",
                None,
                "secret-scan allowlist must remain inside the workspace",
            )
        )
        return set()
    descriptor: int | None = None
    try:
        descriptor = os.open(path, no_follow_read_flags())
        opened_stat = os.fstat(descriptor)
        if not stat.S_ISREG(opened_stat.st_mode):
            diagnostics.append(
                Diagnostic(
                    "error",
                    "secret_allowlist_invalid",
                    allowlist_relative,
                    None,
                    "secret-scan allowlist changed to a non-regular file",
                )
            )
            return set()
        if opened_stat.st_size > MAX_SCANNED_FILE_BYTES:
            diagnostics.append(
                Diagnostic(
                    "error",
                    "secret_allowlist_too_large",
                    allowlist_relative,
                    None,
                    f"secret-scan allowlist exceeds {MAX_SCANNED_FILE_BYTES} bytes",
                )
            )
            return set()
        with os.fdopen(descriptor, "rb", closefd=True) as opened:
            descriptor = None
            raw_allowlist = opened.read(MAX_SCANNED_FILE_BYTES + 1)
        if len(raw_allowlist) > MAX_SCANNED_FILE_BYTES:
            diagnostics.append(
                Diagnostic(
                    "error",
                    "secret_allowlist_too_large",
                    allowlist_relative,
                    None,
                    f"secret-scan allowlist exceeds {MAX_SCANNED_FILE_BYTES} bytes",
                )
            )
            return set()
        lines = raw_allowlist.decode("utf-8").splitlines()
    except (OSError, UnicodeError) as error:
        diagnostics.append(
            Diagnostic("error", "secret_allowlist_read", allowlist_relative, None, str(error))
        )
        return set()
    finally:
        if descriptor is not None:
            os.close(descriptor)

    entries: set[tuple[str, str]] = set()
    known_rules = {name for name, _ in _PATTERNS}
    for line_number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        entry_path, separator, rule = stripped.rpartition(":")
        if not separator or not entry_path or rule not in known_rules:
            diagnostics.append(
                Diagnostic(
                    "warning",
                    "invalid_secret_allowlist_entry",
                    allowlist_relative,
                    f"line {line_number}",
                    "allowlist entry must use relative/path:known_rule",
                )
            )
            continue
        entries.add((entry_path, rule))
    return entries


def scan_workspace(
    root: Path | str,
    allowlist_path: Path | None = None,
) -> tuple[Diagnostic, ...]:
    """Scan regular files under root without following symbolic links."""

    requested_root = Path(root).absolute()
    try:
        symlink_component = first_symlink_component(requested_root)
    except PathSafetyError as error:
        return (
            Diagnostic(
                "error",
                "scan_root_inspection",
                ".",
                None,
                str(error),
            ),
        )
    if symlink_component is not None:
        return (
            Diagnostic(
                "error",
                "scan_root_symlink",
                ".",
                None,
                "secret-scan root path must not contain a symbolic link",
            ),
        )
    if not requested_root.is_dir():
        return (
            Diagnostic(
                "error",
                "scan_root_invalid",
                ".",
                None,
                "secret-scan root does not exist or is not a directory",
            ),
        )

    workspace_root = requested_root.resolve()
    diagnostics: list[Diagnostic] = []
    configured_allowlist = allowlist_path or workspace_root / ".home-secret-scan-allowlist"
    if not configured_allowlist.is_absolute():
        configured_allowlist = workspace_root / configured_allowlist
    allowlist = _load_allowlist(configured_allowlist, workspace_root, diagnostics)

    for current_root, directory_names, filenames in os.walk(workspace_root, followlinks=False):
        current = Path(current_root)
        safe_directories: list[str] = []
        for name in sorted(directory_names):
            child = current / name
            if name in _EXCLUDED_DIRECTORIES:
                continue
            if child.is_symlink():
                diagnostics.append(
                    Diagnostic(
                        "warning",
                        "symlink_scan_directory",
                        _relative(child, workspace_root),
                        None,
                        "symbolic-link directory was not scanned",
                    )
                )
            else:
                safe_directories.append(name)
        directory_names[:] = safe_directories

        for name in sorted(filenames):
            path = current / name
            relative_path = _relative(path, workspace_root)
            try:
                path_stat = path.lstat()
            except OSError as error:
                diagnostics.append(
                    Diagnostic("warning", "scan_file_read", relative_path, None, str(error))
                )
                continue
            if stat.S_ISLNK(path_stat.st_mode):
                diagnostics.append(
                    Diagnostic(
                        "warning",
                        "symlink_scan_file",
                        relative_path,
                        None,
                        "symbolic-link file was not scanned",
                    )
                )
                continue
            if not stat.S_ISREG(path_stat.st_mode):
                diagnostics.append(
                    Diagnostic(
                        "warning",
                        "scan_special_file",
                        relative_path,
                        None,
                        "non-regular file was not scanned",
                    )
                )
                continue
            if path_stat.st_size > MAX_SCANNED_FILE_BYTES:
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "scan_file_too_large",
                        relative_path,
                        None,
                        f"regular file exceeds the {MAX_SCANNED_FILE_BYTES}-byte scan limit",
                    )
                )
                continue
            try:
                resolved = path.resolve(strict=True)
            except OSError as error:
                diagnostics.append(
                    Diagnostic("warning", "scan_file_read", relative_path, None, str(error))
                )
                continue
            if not resolved.is_relative_to(workspace_root):
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "scan_path_outside_workspace",
                        relative_path,
                        None,
                        "file resolved outside the workspace and was not scanned",
                    )
                )
                continue
            descriptor: int | None = None
            try:
                descriptor = os.open(path, no_follow_read_flags())
                opened_stat = os.fstat(descriptor)
                if not stat.S_ISREG(opened_stat.st_mode):
                    diagnostics.append(
                        Diagnostic(
                            "warning",
                            "scan_special_file",
                            relative_path,
                            None,
                            "file changed to a non-regular file and was not scanned",
                        )
                    )
                    continue
                if opened_stat.st_size > MAX_SCANNED_FILE_BYTES:
                    diagnostics.append(
                        Diagnostic(
                            "error",
                            "scan_file_too_large",
                            relative_path,
                            None,
                            f"regular file exceeds the {MAX_SCANNED_FILE_BYTES}-byte scan limit",
                        )
                    )
                    continue
                with os.fdopen(descriptor, "rb", closefd=True) as opened:
                    descriptor = None
                    raw = opened.read(MAX_SCANNED_FILE_BYTES + 1)
            except OSError as error:
                diagnostics.append(
                    Diagnostic("warning", "scan_file_read", relative_path, None, str(error))
                )
                continue
            finally:
                if descriptor is not None:
                    os.close(descriptor)
            if len(raw) > MAX_SCANNED_FILE_BYTES:
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "scan_file_too_large",
                        relative_path,
                        None,
                        f"regular file exceeds the {MAX_SCANNED_FILE_BYTES}-byte scan limit",
                    )
                )
                continue
            if b"\x00" in raw:
                continue
            try:
                content = raw.decode("utf-8")
            except UnicodeDecodeError:
                continue
            for rule, pattern in _PATTERNS:
                if (relative_path, rule) in allowlist:
                    continue
                if pattern.search(content):
                    diagnostics.append(
                        Diagnostic(
                            "error",
                            "secret_pattern",
                            relative_path,
                            rule,
                            f"potential secret matched rule {rule}; value redacted",
                        )
                    )

    return tuple(
        sorted(
            diagnostics,
            key=lambda item: (item.path, item.code, item.location or "", item.message),
        )
    )
