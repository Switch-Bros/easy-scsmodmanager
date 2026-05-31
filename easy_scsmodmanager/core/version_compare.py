"""Compare two mod package_version strings numerically.

Used by the MapCombo import to hint "you have 2.2, the combo used 2.4". The
package_version is third-party data and unreliable, so the comparison is
deliberately strict: every dot-segment must be a plain integer. Anything else
(``1.59.b``, ``v2.4-final``, empty) yields None = "not comparable" - we never
guess a mod is older or newer. Verified against real values like ``1.0``,
``1.4.1``, ``1.6.5.3`` (parseable) and ``1.59.b`` (not).

Segments compare numerically, so ``2.10`` > ``2.2`` (NOT a string compare),
and a shorter version is zero-padded (``2.0`` == ``2.0.0``).
"""

from __future__ import annotations


def _parse(version: str) -> list[int] | None:
    if not version:
        return None
    try:
        return [int(part) for part in version.split(".")]
    except ValueError:
        return None


def compare_versions(a: str, b: str) -> int | None:
    """-1 if a<b, 0 if equal, 1 if a>b, None if either is not comparable."""
    pa, pb = _parse(a), _parse(b)
    if pa is None or pb is None:
        return None
    length = max(len(pa), len(pb))
    pa += [0] * (length - len(pa))
    pb += [0] * (length - len(pb))
    if pa < pb:
        return -1
    if pa > pb:
        return 1
    return 0
