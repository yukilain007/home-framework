"""Lexical path checks shared by workspace readers and writers."""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import cast


class PathSafetyError(OSError):
    """Raised when a path component cannot be inspected without ambiguity."""


def first_symlink_component(path: Path | str) -> Path | None:
    """Return the first existing symbolic-link component in an absolute path."""

    absolute = Path(path).absolute()
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError:
            break
        except OSError as error:
            raise PathSafetyError("path component could not be inspected safely") from error
        if stat.S_ISLNK(mode):
            return current
    return None


def no_follow_read_flags() -> int:
    """Return safe read flags or fail closed when no-follow opening is unavailable."""

    no_follow = cast(int | None, getattr(os, "O_NOFOLLOW", None))
    if no_follow is None:
        raise PathSafetyError("platform does not support no-follow file opening")
    return os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | no_follow
