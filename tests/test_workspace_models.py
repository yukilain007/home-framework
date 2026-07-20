import pytest
from pydantic import ValidationError

from home_framework.models import WorkspaceManifest


def manifest_data() -> dict[str, object]:
    return {
        "kind": "workspace",
        "schema_version": "1.0",
        "name": "example-home",
        "framework": {"minimum_version": "0.1.0a2"},
        "defaults": {"export_directory": "exports"},
    }


def test_valid_workspace_manifest() -> None:
    manifest = WorkspaceManifest.model_validate(manifest_data())

    assert manifest.name == "example-home"
    assert manifest.framework.minimum_version == "0.1.0a2"
    assert manifest.defaults.export_directory == "exports"


@pytest.mark.parametrize(
    "path",
    ["", "/absolute/exports", "../exports", "exports/../outside", ".", "exports\\other"],
)
def test_workspace_manifest_rejects_unsafe_export_directory(path: str) -> None:
    data = manifest_data()
    data["defaults"] = {"export_directory": path}

    with pytest.raises(ValidationError):
        WorkspaceManifest.model_validate(data)


@pytest.mark.parametrize("name", ["", "Example Home", "../escape", "UPPER", "-leading"])
def test_workspace_manifest_rejects_unsafe_name(name: str) -> None:
    data = manifest_data()
    data["name"] = name

    with pytest.raises(ValidationError):
        WorkspaceManifest.model_validate(data)


def test_workspace_manifest_rejects_unknown_fields() -> None:
    data = manifest_data()
    data["unexpected"] = True

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        WorkspaceManifest.model_validate(data)


def test_workspace_manifest_rejects_unknown_nested_fields() -> None:
    data = manifest_data()
    data["defaults"] = {"export_directory": "exports", "unexpected": True}

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        WorkspaceManifest.model_validate(data)
