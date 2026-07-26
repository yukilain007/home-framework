"""Build temporary distributions and verify Apache-2.0 provenance metadata."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from email.parser import BytesParser
from email.policy import default
from importlib.util import find_spec
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).parents[1]
LICENSE_FILES = ["LICENSE", "NOTICE"]
LICENSE_EXPRESSION = "Apache-2.0"
EXPECTED_RUNTIME_REQUIREMENTS = {"packaging", "pydantic", "pyyaml", "typer"}
EXPECTED_REQUIRES_PYTHON = ">=3.11"
SPDX_HEADER = "# SPDX-FileCopyrightText: 2026 Yuki\n# SPDX-License-Identifier: Apache-2.0\n"
ENCODING_DECLARATION = re.compile(r"^#.*coding[:=]\s*[-\w.]+")
IGNORED_BUILD_INPUTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "venv",
}


def _package_version() -> str:
    source = (ROOT / "src/home_framework/__init__.py").read_text(encoding="utf-8")
    match = re.search(r'^__version__ = "([^"]+)"$', source, re.MULTILINE)
    if match is None:
        raise RuntimeError(
            "could not determine package version from src/home_framework/__init__.py"
        )
    return match.group(1)


def _ignore_build_inputs(_directory: str, names: list[str]) -> set[str]:
    return {name for name in names if name in IGNORED_BUILD_INPUTS or name.endswith(".egg-info")}


def _has_complete_spdx_header(source: str) -> bool:
    lines = source.splitlines(keepends=True)
    header_index = 0
    if lines and lines[0].startswith("#!"):
        header_index += 1
    if header_index < len(lines) and ENCODING_DECLARATION.match(lines[header_index]):
        header_index += 1
    return "".join(lines[header_index : header_index + 2]) == SPDX_HEADER


def _run_build(project_directory: Path, output_directory: Path) -> None:
    if find_spec("build") is None or find_spec("hatchling") is None:
        raise RuntimeError(
            "distribution provenance requires build and hatchling; install the development "
            "dependencies with python -m pip install -e '.[dev]'"
        )
    subprocess.run(
        [sys.executable, "-m", "build", "--no-isolation", "--outdir", str(output_directory)],
        cwd=project_directory,
        check=True,
    )


def _single_artifact(directory: Path, pattern: str) -> Path:
    artifacts = sorted(directory.glob(pattern))
    if len(artifacts) != 1:
        raise RuntimeError(f"expected one {pattern} artifact, found {artifacts}")
    return artifacts[0]


def _assert_metadata(metadata: bytes, artifact: Path, version: str) -> None:
    message = BytesParser(policy=default).parsebytes(metadata)
    if message["Version"] != version:
        raise RuntimeError(f"{artifact.name} has incorrect package version")
    if message["Requires-Python"] != EXPECTED_REQUIRES_PYTHON:
        raise RuntimeError(f"{artifact.name} has incorrect Python requirement")
    if message["License-Expression"] != LICENSE_EXPRESSION:
        raise RuntimeError(f"{artifact.name} has incorrect License-Expression")
    if message.get_all("License-File") != LICENSE_FILES:
        raise RuntimeError(f"{artifact.name} has incorrect License-File metadata")
    requirements = [Requirement(value) for value in message.get_all("Requires-Dist", [])]
    runtime_requirements = {
        canonicalize_name(requirement.name)
        for requirement in requirements
        if requirement.marker is None
    }
    if runtime_requirements != EXPECTED_RUNTIME_REQUIREMENTS:
        raise RuntimeError(
            f"{artifact.name} has unexpected runtime requirements: {runtime_requirements}"
        )
    for development_dependency in ("build", "hatchling"):
        matching_requirements = [
            requirement
            for requirement in requirements
            if canonicalize_name(requirement.name) == development_dependency
        ]
        if (
            len(matching_requirements) != 1
            or str(matching_requirements[0].marker) != 'extra == "dev"'
        ):
            raise RuntimeError(
                f"{artifact.name} does not keep {development_dependency} limited to the dev extra"
            )


def _check_wheel(wheel: Path, version: str) -> None:
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        metadata_paths = [name for name in names if name.endswith(".dist-info/METADATA")]
        if len(metadata_paths) != 1:
            raise RuntimeError(f"{wheel.name} has invalid metadata paths: {metadata_paths}")
        _assert_metadata(archive.read(metadata_paths[0]), wheel, version)

        license_prefix = metadata_paths[0].removesuffix("METADATA") + "licenses/"
        expected_license_paths = {license_prefix + filename for filename in LICENSE_FILES}
        if not expected_license_paths <= set(names):
            raise RuntimeError(f"{wheel.name} does not include all declared license files")
        entry_point_path = metadata_paths[0].removesuffix("METADATA") + "entry_points.txt"
        if entry_point_path not in names:
            raise RuntimeError(f"{wheel.name} does not include console entry points")
        if "home = home_framework.cli:app" not in archive.read(entry_point_path).decode("utf-8"):
            raise RuntimeError(f"{wheel.name} has an incorrect home console entry point")


def _check_sdist(sdist: Path, version: str) -> None:
    with tarfile.open(sdist) as archive:
        names = archive.getnames()
        roots = {name.split("/", maxsplit=1)[0] for name in names if "/" in name}
        if len(roots) != 1:
            raise RuntimeError(f"{sdist.name} has invalid root entries: {sorted(roots)}")
        root = roots.pop()
        expected_license_paths = {f"{root}/{filename}" for filename in LICENSE_FILES}
        if not expected_license_paths <= set(names):
            raise RuntimeError(f"{sdist.name} does not include all declared license files")

        metadata_member = archive.extractfile(f"{root}/PKG-INFO")
        if metadata_member is None:
            raise RuntimeError(f"{sdist.name} does not include PKG-INFO")
        _assert_metadata(metadata_member.read(), sdist, version)

        pyproject_member = archive.extractfile(f"{root}/pyproject.toml")
        if pyproject_member is None:
            raise RuntimeError(f"{sdist.name} does not include pyproject.toml")
        pyproject = pyproject_member.read().decode("utf-8")
        if 'license = "Apache-2.0"' not in pyproject:
            raise RuntimeError(f"{sdist.name} has incorrect project license metadata")

        source_names = sorted(
            name
            for name in names
            if name.startswith(f"{root}/src/home_framework/") and name.endswith(".py")
        )
        if not source_names:
            raise RuntimeError(f"{sdist.name} does not include package source files")
        for source_name in source_names:
            source_member = archive.extractfile(source_name)
            if source_member is None or not _has_complete_spdx_header(
                source_member.read().decode("utf-8")
            ):
                raise RuntimeError(f"{sdist.name} has a package source without an SPDX header")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="home-framework-provenance-") as temporary:
        temporary_root = Path(temporary)
        project_directory = temporary_root / "project"
        output_directory = temporary_root / "dist"
        shutil.copytree(ROOT, project_directory, ignore=_ignore_build_inputs)
        version = _package_version()
        _run_build(project_directory, output_directory)
        _check_wheel(_single_artifact(output_directory, "*.whl"), version)
        _check_sdist(_single_artifact(output_directory, "*.tar.gz"), version)
    print(f"Distribution provenance check passed for {version}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
