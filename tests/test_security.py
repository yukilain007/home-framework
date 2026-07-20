import socket
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from home_framework import security
from home_framework.security import scan_workspace


@pytest.mark.parametrize(
    ("rule", "content"),
    [
        ("credential_assignment", 'api_key: "fictional-value-123456789"\n'),
        ("pem_private_key", "-----BEGIN PRIVATE KEY-----\nfictional\n"),
        ("github_token", "ghp_abcdefghijklmnopqrstuvwxyz1234567890\n"),
        ("openai_api_key", "sk-proj-abcdefghijklmnopqrstuvwxyz1234567890\n"),
    ],
)
def test_high_confidence_secret_patterns_are_reported_without_values(
    tmp_path: Path,
    rule: str,
    content: str,
) -> None:
    authority = tmp_path / "sources/core/authority.yaml"
    authority.parent.mkdir(parents=True)
    authority.write_text(content, encoding="utf-8")

    diagnostics = scan_workspace(tmp_path)

    finding = next(item for item in diagnostics if item.location == rule)
    assert finding.severity == "error"
    assert finding.code == "secret_pattern"
    assert finding.path == "sources/core/authority.yaml"
    assert content.strip() not in finding.message
    assert "redacted" in finding.message


def test_exact_path_and_rule_allowlist_suppresses_only_that_finding(tmp_path: Path) -> None:
    first = tmp_path / "first.yaml"
    second = tmp_path / "second.yaml"
    token = "sk-proj-abcdefghijklmnopqrstuvwxyz1234567890"
    first.write_text(token + "\n", encoding="utf-8")
    second.write_text(token + "\n", encoding="utf-8")
    allowlist = tmp_path / ".home-secret-scan-allowlist"
    allowlist.write_text("first.yaml:openai_api_key\n", encoding="utf-8")

    diagnostics = scan_workspace(tmp_path)

    findings = [item for item in diagnostics if item.code == "secret_pattern"]
    assert [item.path for item in findings] == ["second.yaml"]


def test_symlinked_directory_is_reported_and_not_scanned(tmp_path: Path) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    secret = outside / "secret.yaml"
    secret.write_text("sk-proj-abcdefghijklmnopqrstuvwxyz1234567890\n", encoding="utf-8")
    link = tmp_path / "linked"
    link.symlink_to(outside, target_is_directory=True)

    diagnostics = scan_workspace(tmp_path)

    assert any(
        item.code == "symlink_scan_directory" and item.path == "linked" for item in diagnostics
    )
    assert not any(item.code == "secret_pattern" for item in diagnostics)


def test_symlinked_file_is_reported_and_not_read(tmp_path: Path) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-outside.yaml"
    outside.write_text("sk-proj-abcdefghijklmnopqrstuvwxyz1234567890\n", encoding="utf-8")
    (tmp_path / "linked.yaml").symlink_to(outside)

    diagnostics = scan_workspace(tmp_path)

    assert any(
        item.code == "symlink_scan_file" and item.path == "linked.yaml" for item in diagnostics
    )
    assert not any(item.code == "secret_pattern" for item in diagnostics)


def test_symlinked_scan_root_is_rejected_without_scanning_target(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.yaml").write_text(
        "sk-proj-abcdefghijklmnopqrstuvwxyz1234567890\n",
        encoding="utf-8",
    )
    root = tmp_path / "root"
    root.symlink_to(outside, target_is_directory=True)

    diagnostics = scan_workspace(root)

    assert [item.code for item in diagnostics] == ["scan_root_symlink"]
    assert not any(item.code == "secret_pattern" for item in diagnostics)


def test_scan_root_with_symlinked_ancestor_is_rejected(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    workspace = outside / "workspace"
    workspace.mkdir(parents=True)
    (workspace / "secret.yaml").write_text(
        "sk-proj-abcdefghijklmnopqrstuvwxyz1234567890\n",
        encoding="utf-8",
    )
    link = tmp_path / "linked-parent"
    link.symlink_to(outside, target_is_directory=True)

    diagnostics = scan_workspace(link / "workspace")

    assert [item.code for item in diagnostics] == ["scan_root_symlink"]
    assert not any(item.code == "secret_pattern" for item in diagnostics)


def test_special_file_is_skipped_without_read_attempt(tmp_path: Path) -> None:
    short_base = Path("/private/tmp") if Path("/private/tmp").is_dir() else Path("/tmp")
    socket_root = Path(tempfile.mkdtemp(prefix="hf-", dir=short_base))
    socket_path = socket_root / "s"
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as local_socket:
            local_socket.bind(str(socket_path))

            diagnostics = scan_workspace(socket_root)
    finally:
        if socket_path.exists():
            socket_path.unlink()
        socket_root.rmdir()

    assert any(item.code == "scan_special_file" and item.path == "s" for item in diagnostics)
    assert not any(item.code == "scan_file_read" for item in diagnostics)


def test_special_file_cannot_be_used_as_allowlist() -> None:
    short_base = Path("/private/tmp") if Path("/private/tmp").is_dir() else Path("/tmp")
    socket_root = Path(tempfile.mkdtemp(prefix="hf-", dir=short_base))
    socket_path = socket_root / "allow.sock"
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as local_socket:
            local_socket.bind(str(socket_path))

            diagnostics = scan_workspace(socket_root, socket_path)
    finally:
        if socket_path.exists():
            socket_path.unlink()
        socket_root.rmdir()

    assert any(item.code == "secret_allowlist_invalid" for item in diagnostics)


def test_oversized_regular_file_is_rejected_before_reading(tmp_path: Path) -> None:
    oversized = tmp_path / "oversized.txt"
    oversized.write_bytes(b"x" * (1024 * 1024 + 1))

    diagnostics = scan_workspace(tmp_path)

    assert any(
        item.code == "scan_file_too_large" and item.path == "oversized.txt" for item in diagnostics
    )
    assert not any(item.code == "scan_file_read" for item in diagnostics)


def test_file_replaced_by_symlink_during_scan_is_not_followed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "target.txt"
    target.write_text("safe content\n", encoding="utf-8")
    outside = tmp_path.parent / f"{tmp_path.name}-outside-secret.txt"
    outside.write_text("sk-proj-abcdefghijklmnopqrstuvwxyz1234567890\n", encoding="utf-8")
    real_open = security.os.open
    replaced = False

    def replace_before_open(path: Path, flags: int) -> int:
        nonlocal replaced
        if Path(path) == target and not replaced:
            target.unlink()
            target.symlink_to(outside)
            replaced = True
        return real_open(path, flags)

    monkeypatch.setattr(security.os, "open", replace_before_open)

    diagnostics = scan_workspace(tmp_path)

    assert replaced
    assert any(item.code == "scan_file_read" and item.path == "target.txt" for item in diagnostics)
    assert not any(item.code == "secret_pattern" for item in diagnostics)


def test_scanner_fails_closed_without_no_follow_support(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "target.txt"
    target.write_text("sk-proj-abcdefghijklmnopqrstuvwxyz1234567890\n", encoding="utf-8")
    monkeypatch.delattr(security.os, "O_NOFOLLOW", raising=False)

    diagnostics = scan_workspace(tmp_path)

    assert any(item.code == "scan_file_read" and item.path == "target.txt" for item in diagnostics)
    assert not any(item.code == "secret_pattern" for item in diagnostics)


def test_binary_file_is_skipped(tmp_path: Path) -> None:
    (tmp_path / "binary.dat").write_bytes(b"\x00sk-proj-abcdefghijklmnopqrstuvwxyz1234567890")

    diagnostics = scan_workspace(tmp_path)

    assert not any(item.code == "secret_pattern" for item in diagnostics)


def test_secret_scan_script_propagates_findings_without_printing_values(tmp_path: Path) -> None:
    script = Path(__file__).parents[1] / "scripts/scan_secrets.py"
    secret_value = "fictional-value-123456789"
    (tmp_path / "notes.txt").write_text(f'api_key: "{secret_value}"\n', encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(script), str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "secret_pattern" in result.stderr
    assert secret_value not in result.stderr
