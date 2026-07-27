import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).parents[1]
SPDX_HEADER = "# SPDX-FileCopyrightText: 2026 Yuki\n# SPDX-License-Identifier: Apache-2.0\n"
ENCODING_DECLARATION = re.compile(r"^#.*coding[:=]\s*[-\w.]+")


def _pyproject() -> dict[str, object]:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def _has_complete_spdx_header(source: Path) -> bool:
    lines = source.read_text(encoding="utf-8").splitlines(keepends=True)
    header_index = 0
    if lines and lines[0].startswith("#!"):
        header_index += 1
    if header_index < len(lines) and ENCODING_DECLARATION.match(lines[header_index]):
        header_index += 1
    return "".join(lines[header_index : header_index + 2]) == SPDX_HEADER


def test_all_package_sources_have_complete_apache_spdx_headers() -> None:
    sources = sorted((ROOT / "src/home_framework").rglob("*.py"))

    assert sources
    for source in sources:
        assert _has_complete_spdx_header(source), source


def test_public_provenance_records_agree_on_apache_identity() -> None:
    project = _pyproject()["project"]
    notice = (ROOT / "NOTICE").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    checklist = (ROOT / "docs/release-checklist.md").read_text(encoding="utf-8")
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")

    assert project["license"] == "Apache-2.0"
    assert project["license-files"] == ["LICENSE", "NOTICE"]
    assert license_text.lstrip().startswith("Apache License\n")
    assert "Version 2.0, January 2004" in license_text
    assert notice == (
        "HOME Framework\n"
        "Copyright (c) 2026 Yuki\n"
        "Official repository: https://github.com/yukilain007/home-framework\n"
    )
    assert "Apache License, Version 2.0" in readme
    assert "https://github.com/yukilain007/home-framework/blob/main/LICENSE" in readme
    assert "Apache-2.0 provenance" in checklist
    assert all(
        f"`{filename}`" in checklist
        for filename in ("LICENSE", "NOTICE", "README.md", "pyproject.toml")
    )


def test_standard_quality_gate_runs_distribution_provenance_check() -> None:
    runner = (ROOT / "scripts/check.py").read_text(encoding="utf-8")

    assert "scripts/check_distribution_provenance.py" in runner


def test_distribution_provenance_build_is_dev_only_and_uses_an_offline_temp_copy() -> None:
    project = _pyproject()["project"]
    script = (ROOT / "scripts/check_distribution_provenance.py").read_text(encoding="utf-8")

    assert "build>=1.2,<2" in project["optional-dependencies"]["dev"]
    assert "hatchling>=1.27,<2" in project["optional-dependencies"]["dev"]
    assert not any(dependency.startswith("build") for dependency in project["dependencies"])
    assert '"--no-isolation"' in script
    assert "shutil.copytree" in script
    assert "TemporaryDirectory" in script
    for excluded in (".git", "dist", "build", ".egg-info"):
        assert excluded in script
    assert "/Users/" not in script
