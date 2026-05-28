from __future__ import annotations

from enum import Enum
from pathlib import Path

ZIP_LOCAL_FILE_HEADER = b"PK\x03\x04"
HASHFS_MAGIC = b"SCS#"
HEADER_PROBE_BYTES = 6


class ScsFormat(Enum):
    ZIP = "zip"
    HASHFS_V1 = "hashfs_v1"
    HASHFS_V2 = "hashfs_v2"
    UNKNOWN = "unknown"


def detect_format(scs_path: Path) -> ScsFormat:
    with scs_path.open("rb") as f:
        head = f.read(HEADER_PROBE_BYTES)

    if head.startswith(ZIP_LOCAL_FILE_HEADER):
        return ScsFormat.ZIP

    if head.startswith(HASHFS_MAGIC) and len(head) >= 6:
        version = int.from_bytes(head[4:6], "little")
        if version == 2:
            return ScsFormat.HASHFS_V2
        if version == 1:
            return ScsFormat.HASHFS_V1

    return ScsFormat.UNKNOWN
