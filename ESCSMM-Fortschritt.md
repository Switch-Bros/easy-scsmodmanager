# Projektfortschritt: easy-scsmodmanager

> Stand 2026-05-31. Directive 0: Zahlen gemessen, nicht geraten. Diese Datei ist privat.

┌────────┬──────────────────────────┬──────────────────────────────────────┐
│ Phase  │       Fortschritt        │               Status                 │
├────────┼──────────────────────────┼──────────────────────────────────────┤
│ GESAMT │ ██████████████░░░░░░ 70% │ Load-Order-Reife fertig, Build offen  │
└────────┴──────────────────────────┴──────────────────────────────────────┘

---

## Phasen-Chronik

### Phase 0 - Grundgeruest ████████████████████ 100%
Details: Scaffold, Modul-Layout, pyproject, pre-commit (black/ruff/mypy/pytest).

---

### Phase 1 - Read-Only Foundation ████████████████████ 100%
Details: SCS-Reader (ZIP/HashFS/Fake-Lock/AEM, 313/313 lesbar), SII-Parser (Klartext +
ScsC-Crypto), Mod-Scanner mit SQLite-Cache, eigener CityHash64 + HashFS V1/V2 (externes
Binary entfernt).

---

### Phase 2 - UI ████████████████████ 100%
Details: PyQt6-Hauptfenster, Mod-Grid mit Icons, Filter/Suche, Profil-Header, Inter-Font,
i18n (de/en, 1 Datei je Sprache + emoji/languages global), Settings-Dialog.

---

### Phase 2.5 / 3 - Drag&Drop + profile.sii-Writer ████████████████████ 100%
Details: DnD Grid<->aktive Liste, Reorder, Multi-Select, sanftes Scrollen. profile.sii-Writer
(IMMER Klartext, im Spiel bestaetigt). Backup/Restore. 18 offizielle Kategorien, Farbtags.

---

### Load-Order-Struktur + MapCombos ████████████████████ 100%
Details: feste Gruppen-Spacer in der aktiven Liste, Auto-Erkennung Map-Basis (editierbare
Liste in Settings), Misplaced-Markierung (oranger Rand + Tooltip), "Verschieben nach X"
(physisch), MapCombo Export/Import am MAPS-Spacer (Auto-Scan vor Import).

---

### Load-Order-Reife (dieser grosse Task) ██████████████████░░ 90%
Sub-Phase: Phase 1 Identitaet - 100% (mod_name, mod_identity, DRY ueber active_name_for)
Sub-Phase: Phase 2 Content-Kategorie - 100% (def-Liste gecacht Schema 6, ehrlich nur physics)
Sub-Phase: Phase 3 Kompatibilitaet - 100% (4 Zustaende, game.log-Version, rote Mods)
Sub-Phase: Phase 4 Konflikte - 100% (geteilte def-Dateien, Hinweis-Tooltip, kein Block)
Sub-Phase: Phase 7 Spacer-Optik - 100% (Einzeiler 30px, map_base bleibt 14px)
Sub-Phase: Phase 8 MapCombo v2 - 100% (package_version, Versions-Hinweis beim Import)
Sub-Phase: Phase 6 Auto-Sort - BEWUSST WEGGELASSEN (Daten nur fuer map+physics verlaesslich,
  Risiko falsch deklarierter Mods nicht vertretbar; manuelle Markierung + Verschieben reicht)

---

### Phase 4 (Roadmap) - Komfort ████████░░░░░░░░░░░░ 40%
Details: Konflikt-Erkennung fertig. Offen: Presets, Update-Check via Workshop API.

---

### Phase 6 (Roadmap) - Build-Pipeline ░░░░░░░░░░░░░░░░░░░░ 0%
Details: PyInstaller -> Linux AppImage + Windows EXE. Noch nicht begonnen.

---

## Zahlen auf einen Blick

┌─────────────────────┬───────────────────────────────────────────┐
│       Metrik        │                   Wert                    │
├─────────────────────┼───────────────────────────────────────────┤
│ Python-Quelldateien │ 82                                        │
│ Quellcode (LOC)     │ 8.314                                     │
│ Testdateien         │ 56                                        │
│ Tests (passed)      │ 454                                       │
│ DB-Schema (scan_cache) │ v6                                     │
│ i18n-Sprachen       │ 2 (de / en)                               │
│ Container-Reader    │ 5 (zip, raw_zip, hashfs, aem, directory)  │
│ Aktuelle Version    │ 0.1.0                                     │
└─────────────────────┴───────────────────────────────────────────┘
