"""Read the running game version from the profile's game.log.txt.

Verified line (near the top of the log)::

    00:00:00.061 : [ufs] Loaded pack set version 1.59.1.3 created at ...

That ``1.59.1.3`` is the version mods declare compatibility against. If the
log is absent or the line is missing we return None - the compat check then
treats every mod as UNKNOWN_GAME_VERSION (never red), never guessing.
"""

from __future__ import annotations

import re
from pathlib import Path

_VERSION_RE = re.compile(r"Loaded pack set version ([0-9][0-9.]*)")
_MAX_LINES = 300  # the line sits in the first ~25; cap the read for big logs


def read_game_version(documents_dir: Path) -> str | None:
    """Game version from ``<documents_dir>/game.log.txt``, or None."""
    log_path = documents_dir / "game.log.txt"
    try:
        with log_path.open(encoding="utf-8", errors="replace") as handle:
            for _ in range(_MAX_LINES):
                line = handle.readline()
                if not line:
                    break
                match = _VERSION_RE.search(line)
                if match:
                    return match.group(1)
    except OSError:
        return None
    return None
