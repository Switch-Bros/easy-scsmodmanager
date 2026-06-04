# Changelog

## [1.1.3] - 2026-06-04

- Detect Steam Workshop mods for native installs (Windows, macOS and native
  Linux), not just Proton - fixes Workshop mods staying invisible in the
  Windows build even when the game itself was found.
- A manual documents-folder override no longer switches the Workshop off: the
  Workshop is auto-detected unless you pin it yourself, and the Settings dialog
  now has its own Workshop-folder override per game.
- The language list is now driven entirely by which translations ship, so a new
  translation only needs to add its folder - groundwork for an upcoming Russian
  translation.

## [1.1.2] - 2026-06-04

- Write a rotating log file under a per-platform location (Windows
  `%LOCALAPPDATA%`, Linux `$XDG_STATE_HOME`), so problems are diagnosable even
  in the windowed Windows build where there is no console.
- Catch uncaught exceptions into the log instead of crashing silently.
- Log each mod's path before scanning it, so a scan that hangs leaves the
  culprit as the last line in the log.
- New **Tools - Open Log Folder** menu entry.
- New **.rpm** package for Fedora / openSUSE / RHEL.

## [1.1.1] - 2026-06-01

Initial release.

- Browse all installed mods in a grid with icons, full-text search and category
  filters; activate them with drag and drop and multi-select.
- Switch between Euro Truck Simulator 2 and American Truck Simulator from a
  single window.
- Active load order grouped by section with clear headers, a marker for mods in
  the wrong group, a compatibility check against the detected game version, and
  conflict hints when two active mods touch the same files.
- Export and import a map combo to share or reproduce a map setup.
- Favourites with a favourites-only filter.
- Profile backup and restore.
- Fully bilingual interface (English and German).
- Available as AppImage, Windows .exe, .deb, portable tar.gz and on the AUR.
