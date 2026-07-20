from datetime import date
from pathlib import Path

import pytest

from home_framework.compiler import CompiledContext
from home_framework.export_metadata import (
    ExportMetadata,
    ExportMetadataError,
    classify_export,
    parse_export_metadata,
    serialize_export_metadata,
)
from home_framework.models import HandoffDocument

FINGERPRINT = "a" * 64


def metadata() -> ExportMetadata:
    return ExportMetadata(
        schema_version="1.0",
        handoff_id="project.execution",
        context_date=date(2026, 7, 20),
        fingerprint=FINGERPRINT,
    )


def handoff() -> HandoffDocument:
    return HandoffDocument.model_validate(
        {
            "kind": "handoff",
            "schema_version": "1.0",
            "id": "project.execution",
            "title": "Fictional project execution",
            "purpose": "Continue a fictional implementation.",
            "include": {
                "scopes": [],
                "core_ids": [],
                "current_ids": [],
                "sensitivities": ["public"],
            },
            "output": {"format": "markdown"},
        }
    )


def compiled() -> CompiledContext:
    return CompiledContext(
        handoff=handoff(),
        documents=(),
        as_of=date(2026, 7, 20),
        fingerprint=FINGERPRINT,
    )


def test_export_metadata_serialization_round_trip_is_stable() -> None:
    rendered = serialize_export_metadata(metadata())

    assert rendered == (
        '<!-- home-framework-export: {"context_date":"2026-07-20",'
        '"fingerprint":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",'
        '"handoff_id":"project.execution","schema_version":"1.0"} -->'
    )
    assert parse_export_metadata(rendered + "\nbody\n") == metadata()
    assert serialize_export_metadata(parse_export_metadata(rendered)) == rendered


def test_export_metadata_must_be_on_first_line() -> None:
    content = "<!-- generated file: do not edit -->\n" + serialize_export_metadata(metadata())

    with pytest.raises(ExportMetadataError) as caught:
        parse_export_metadata(content)

    assert caught.value.code == "missing_export_metadata"


def test_missing_export_metadata_is_reported() -> None:
    with pytest.raises(ExportMetadataError) as caught:
        parse_export_metadata("# Old export\n")

    assert caught.value.code == "missing_export_metadata"


def test_invalid_export_metadata_json_is_reported() -> None:
    with pytest.raises(ExportMetadataError) as caught:
        parse_export_metadata("<!-- home-framework-export: {broken} -->\n")

    assert caught.value.code == "invalid_export_metadata"


def test_unsupported_export_metadata_schema_is_reported() -> None:
    content = (
        '<!-- home-framework-export: {"schema_version":"2.0",'
        '"handoff_id":"project.execution","context_date":"2026-07-20",'
        f'"fingerprint":"{FINGERPRINT}"}} -->\n'
    )

    with pytest.raises(ExportMetadataError) as caught:
        parse_export_metadata(content)

    assert caught.value.code == "unsupported_export_metadata"


def test_export_metadata_rejects_invalid_fingerprint() -> None:
    with pytest.raises(ValueError):
        ExportMetadata(
            schema_version="1.0",
            handoff_id="project.execution",
            context_date=date(2026, 7, 20),
            fingerprint="not-a-fingerprint",
        )


def test_missing_export_is_classified(tmp_path: Path) -> None:
    diagnostic = classify_export(tmp_path / "missing.md", "exports/missing.md", compiled())

    assert diagnostic.code == "missing_export"
    assert diagnostic.severity == "warning"


def test_current_export_is_classified(tmp_path: Path) -> None:
    export = tmp_path / "project.execution.md"
    export.write_text(serialize_export_metadata(metadata()) + "\nbody\n", encoding="utf-8")

    diagnostic = classify_export(export, "exports/project.execution.md", compiled())

    assert diagnostic.code == "current_export"
    assert diagnostic.severity == "info"


@pytest.mark.parametrize(
    "changed",
    [
        {"handoff_id": "other.handoff"},
        {"context_date": date(2026, 7, 21)},
        {"fingerprint": "b" * 64},
    ],
)
def test_valid_but_mismatched_metadata_is_stale(
    tmp_path: Path,
    changed: dict[str, object],
) -> None:
    export = tmp_path / "project.execution.md"
    stale = metadata().model_copy(update=changed)
    export.write_text(serialize_export_metadata(stale) + "\nbody\n", encoding="utf-8")

    diagnostic = classify_export(export, "exports/project.execution.md", compiled())

    assert diagnostic.code == "stale_export"
    assert diagnostic.severity == "warning"


def test_invalid_metadata_is_classified(tmp_path: Path) -> None:
    export = tmp_path / "project.execution.md"
    export.write_text("<!-- generated file: do not edit -->\n", encoding="utf-8")

    diagnostic = classify_export(export, "exports/project.execution.md", compiled())

    assert diagnostic.code == "invalid_export_metadata"
    assert diagnostic.severity == "error"


def test_symlinked_export_is_not_read(tmp_path: Path) -> None:
    outside = tmp_path / "outside.md"
    outside.write_text(serialize_export_metadata(metadata()) + "\n", encoding="utf-8")
    export = tmp_path / "project.execution.md"
    export.symlink_to(outside)

    diagnostic = classify_export(export, "exports/project.execution.md", compiled())

    assert diagnostic.code == "invalid_export_metadata"
    assert "symbolic link" in diagnostic.message


def test_export_replaced_by_symlink_during_open_is_not_followed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from home_framework import export_metadata

    export = tmp_path / "project.execution.md"
    export.write_text(serialize_export_metadata(metadata()) + "\n", encoding="utf-8")
    outside = tmp_path / "outside.md"
    stale = metadata().model_copy(update={"fingerprint": "b" * 64})
    outside.write_text(serialize_export_metadata(stale) + "\n", encoding="utf-8")
    real_open = export_metadata.os.open
    replaced = False

    def replace_before_open(path: Path, flags: int) -> int:
        nonlocal replaced
        if Path(path) == export and not replaced:
            export.unlink()
            export.symlink_to(outside)
            replaced = True
        return real_open(path, flags)

    monkeypatch.setattr(export_metadata.os, "open", replace_before_open)

    diagnostic = classify_export(export, "exports/project.execution.md", compiled())

    assert replaced
    assert diagnostic.code == "export_read"
    assert diagnostic.code not in {"current_export", "stale_export"}


def test_export_reader_does_not_use_unbounded_path_read_text(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    export = tmp_path / "project.execution.md"
    export.write_text(
        serialize_export_metadata(metadata()) + "\n" + ("body\n" * 300_000),
        encoding="utf-8",
    )

    def reject_unbounded_read(*args: object, **kwargs: object) -> str:
        raise AssertionError("unbounded Path.read_text was used")

    monkeypatch.setattr(Path, "read_text", reject_unbounded_read)

    diagnostic = classify_export(export, "exports/project.execution.md", compiled())

    assert diagnostic.code == "current_export"


def test_oversized_export_metadata_line_is_rejected(tmp_path: Path) -> None:
    export = tmp_path / "project.execution.md"
    export.write_bytes(b"<" + (b"x" * 5000) + b"\nbody\n")

    diagnostic = classify_export(export, "exports/project.execution.md", compiled())

    assert diagnostic.code == "invalid_export_metadata"
    assert "exceeds" in diagnostic.message


def test_export_reader_fails_closed_without_no_follow_support(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from home_framework import export_metadata

    export = tmp_path / "project.execution.md"
    export.write_text(serialize_export_metadata(metadata()) + "\n", encoding="utf-8")
    monkeypatch.delattr(export_metadata.os, "O_NOFOLLOW", raising=False)

    diagnostic = classify_export(export, "exports/project.execution.md", compiled())

    assert diagnostic.code == "export_read"
    assert "no-follow" in diagnostic.message
