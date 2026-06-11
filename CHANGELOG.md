# Changelog

## [1.5.1] - 2026-06-11

### Added

- **Online share codes are now live.** The optional Supabase backend behind the
  "share as code" and "redeem code" actions is configured, so sharing your mod
  list as a 6-character code works out of the box - no setup needed. File and
  `profile.sii` sharing were already available in 1.5.0 and are unchanged.

## [1.5.0] - 2026-06-11

### Added

- **Share mod lists (Teilen menu).** A new Share menu offers five actions:
  share the active list as a short 6-character online code (valid 90 days,
  requires the optional Supabase backend - the UI explains when it is not
  configured); redeem a code someone sent you; export the full list to a
  `.modshare.json` file; import such a file; and take over a list straight
  from another player's `profile.sii` (ScsC-encrypted or plain text).
- **Import preview with install-status check.** Before applying any shared
  list you see a preview that shows which mods are installed and which are
  missing. Missing Workshop mods get a clickable Subscribe link to the Steam
  Workshop page. A "Check again" button re-scans without closing the dialog, so
  you can subscribe, wait for Steam downloads, and confirm they are ready -
  all in one flow. Missing local mods are listed with copyable names. An
  "include missing entries" toggle (default on) controls whether unresolved
  entries are still written. A game mismatch (ETS2 vs ATS) blocks applying.
  A profile backup is created automatically before every apply.
- **Group pins travel with the list.** When sender and receiver both use Easy
  SCSModManager, load-order group assignments are embedded in the shared list
  and applied for installed mods on import.
- **`packaging/supabase.sql`** - a self-hostable share backend schema with
  RPC-only access and automatic 90-day TTL cleanup, for anyone who wants to
  run their own code server.

### Fixed

- **App reopens the last selected profile per game on startup.** Previously
  the app reopened the most recently modified profile, which could silently
  switch your active profile after saving. It now remembers which profile you
  had selected.
- **Profile header and chooser mod-count refreshes after save and share
  apply.** The count could stay stale until the next full rescan.

## [1.4.1] - 2026-06-10

- **Fixed: local mod icons disappeared.** A caching change in 1.4.0 made local
  mod icons stop showing after a rescan (Workshop icons were unaffected). They
  are back.
- **Windows auto-update is more robust.** The update helper now handles
  non-ASCII install paths (e.g. Chinese Windows), retries a locked swap, and
  restores the previous version if the swap cannot complete, so an interrupted
  update never leaves you without a runnable app. Thanks to LLBBC.

## [1.4.0] - 2026-06-09

- **The extractor now unpacks textures too.** SCS archives store textures
  (.tobj/.dds) with their pixel data GDeflate-compressed and the DDS header
  stripped, which the extractor used to skip - base.scs lost about a fifth of
  its files. It now ships its own GDeflate decompressor and rebuilds a real
  .dds for every packed texture, so an extract is complete (models, defs,
  materials and textures).
- **Mods using the 1.48 `dlc_<name>/` layout are recognised.** Building on the
  1.3.6 `base/` support, content under a `dlc_<name>/` folder is now read when
  the matching game DLC is owned, so such mods (e.g. the PGRS Scania pack) are
  checked for conflicts, maps and physics. Buying a DLC re-scans automatically.
- **A third "frequently shared" conflict tier.** Files touched by many mods at
  once (physics.sii, climate ...) used to be hidden; they now show as a neutral
  grey marker with a count - informative, never an alarm - so nothing is
  silently dropped. Resolves the physics.sii report (#42).
- **Windows auto-update now restarts into the new version.** The update could
  download but not swap itself in on Windows; it now hands off to the helper
  and restarts cleanly. AppImage was unaffected.
- Thanks to LLBBC (#42/#43/#47).

## [1.3.6] - 2026-06-09

- **Mods with the SCS 1.48 `base/` layout are now detected correctly.** A mod
  that ships its content under a top-level `base/` folder (the DLC-aware package
  layout the game always mounts) was previously invisible to conflict, map and
  physics detection. Such mods are now checked just like any other. Thanks to
  LLBBC (#43).

## [1.3.5] - 2026-06-08

- **Conflict severity at a glance.** A mod whose files are overwritten by mods
  above it now shows how badly: a yellow warning triangle when it loses some
  files (partly overwritten), a red crossed circle when it loses all of them
  (fully overwritten - it does nothing where it sits), and no glyph when it wins
  everything. The tooltip lists every overwritten file and which mod wins it,
  and a small legend appears under the active list while any conflict exists.
  Thanks to LLBBC (#37/#38).
- **Responsive grid.** Maximising the window now fills the extra width with more
  columns instead of an empty strip; card size stays the same. Thanks to
  00player00 (#40).
- **Documentation in the app.** A new Help -> Documentation menu opens the user
  manual, FAQ, keyboard shortcuts and tips in your language, now kept under
  `docs/`. Contributing and the Code of Conduct are available in German too.
- Carries the refined palette from 1.3.4 (Borussia Dortmund yellow accent, mod
  names in the club colour), which reaches everyone with this release.

## [1.3.4] - 2026-06-08

- Refined the colour palette and switched the accent to Borussia Dortmund
  yellow, so mod names now show in the club colour. Internally the theme is now
  a clean two-layer palette (raw marks vs. semantic tokens) with no stray
  hardcoded colours left.

## [1.3.3] - 2026-06-07

- **Move several mods to a group at once.** The active-list right-click "Move
  to" now acts on your whole selection, with a new "Automatic (own category)"
  entry that sends mods back to their natural group.
- **Dragging adopts the target section.** Dropping a mod into a load-order
  section now keeps it there (same as the right-click move) instead of snapping
  back to its manifest category. Dragging a mod back to its home section clears
  the pin.
- **Source filter.** A new Source dropdown (All / Workshop / Local) replaces the
  "Workshop only" checkbox, so you can show just your local mods - handy with
  Ctrl+A in the grid to select everything visible and, say, delete it in one go.
- **Fewer false conflicts.** Two mods that merely share the same folder
  structure are no longer reported as conflicting.
- Thanks to TwinShadow, 00player00 and LLBBC for the reports.

## [1.3.2] - 2026-06-06

- **Activating a mod now sorts it into its own group.** Double-clicking a mod
  in the grid dropped it at the very top of the active list, so a mod from an
  earlier group could end up rendered under a later group's header. It now
  lands at the bottom of its own group's block, and the newly activated row is
  selected so you can see where it went. Thanks to LLBBC for the reproduction.

## [1.3.1] - 2026-06-06

- **Delete local mods from the app.** Right-click a mod (or select several) and
  choose "Delete..." to move it to the system trash - restore it from there if
  you change your mind. Workshop mods stay managed by Steam (the entry is shown
  but disabled). If a mod is still used by a saved load order, the confirmation
  names the affected profiles first. Thanks to 00player00 for the request.

## [1.3.0] - 2026-06-06

- **Self-contained dark theme.** The app now ships its own dark palette and
  stylesheet instead of relying on the OS theme. This fixes a hard-to-read
  interface (barely visible menu bar, invisible checkbox labels, a white
  map-base list) reported on Windows 11 with "system dark / apps light".
  The look no longer depends on your OS light/dark setting. Scrollbars are
  now styled consistently everywhere too.

## [1.2.0] - 2026-06-05

- **Auto-update.** The app can now check GitHub for a newer release. The
  AppImage and the Windows build can download a verified update (checked
  against the release SHA256SUMS) and restart into it; deb/rpm/AUR/tar.gz get
  a notice with the release notes and a link, and keep updating through their
  package manager. Toggle the startup check under Settings - Behaviour, or run
  it any time from Help - Check for Updates.
- **Windows: find Steam and the Documents folder via the registry.** Steam
  installed outside Program Files, and a moved (redirected) Documents folder,
  are now detected, so Workshop mods and profiles show up where earlier builds
  missed them.
- Save and restore dialogs now name the game you are actually using (ATS no
  longer warns about ETS2).
- **Jump from the grid to the active list.** Right-click a mod and choose
  "Show in active list", or enable click-to-jump under Settings - Behaviour
  (off by default).
- Live scan progress in the status bar, and a faster grid rebuild for very
  large libraries.
- More diagnostic logging around install detection, to make "game found but
  no Workshop" reports easier to pin down.
- New CONTRIBUTING and CODE_OF_CONDUCT, a committed `uv.lock` for reproducible
  contributor setups, and groundwork for community translations.

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
