from datetime import date
from pathlib import Path

import yaml

from home_framework import __version__

ROOT = Path(__file__).parents[1]


def test_citation_metadata_is_current_and_public() -> None:
    citation = yaml.safe_load((ROOT / "CITATION.cff").read_text(encoding="utf-8"))

    assert citation["cff-version"] == "1.2.0"
    assert citation["title"] == "HOME Framework"
    assert citation["version"] == __version__
    assert date.fromisoformat(citation["date-released"]) == date(2026, 7, 29)
    assert citation["license"] == "Apache-2.0"
    assert citation["repository-code"] == "https://github.com/yukilain007/home-framework"
    assert citation["authors"] == [
        {
            "given-names": "Yuki",
            "email": "293018124+yukilain007@users.noreply.github.com",
        }
    ]
