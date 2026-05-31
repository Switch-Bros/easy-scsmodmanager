"""Return a container's file list regardless of which reader produced it.

Readers grew inconsistent method names (list_files vs iter_files); this
hides that behind one call used by content-based detection.
"""

from __future__ import annotations


def list_archive_files(source: object) -> list[str]:
    lister = getattr(source, "list_files", None)
    if callable(lister):
        return list(lister())
    iterator = getattr(source, "iter_files", None)
    if callable(iterator):
        return list(iterator())
    return []
