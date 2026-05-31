# easy-scsmodmanager - Dateiuebersicht (2026-05-31)

> Zweck: Ueberblick welche Dateien Richtung Refactor gehen, um bei ca. 500 Zeilen
> pro Datei zu bleiben. Directive 0: Zeilenzahlen gemessen, nicht geschaetzt.
> Mess-Befehl pro Verzeichnis: find <dir> -name "*.py" | xargs wc -l

**Gesamt: 138 Python-Dateien - 13.696 Zeilen**
- Source (`easy_scsmodmanager/`): 82 Dateien, 8.314 Zeilen
- Tests (`tests/`): 56 Dateien, 5.382 Zeilen

---

## Aenderungen in v-Load-Order-Reife (Identitaet, Content, Kompatibilitaet, Konflikte, MapCombo v2)

> Neueste Aenderungen zuerst. Phasen 1-4, 7, 8 des grossen Load-Order-Tasks.
> Phase 6 (Auto-Sort) bewusst weggelassen: Daten nur fuer map+physics verlaesslich,
> Rest haengt am Manifest - das Risiko (falsch deklarierte Mods) war nicht vertretbar.

| Datei | Beschreibung |
|-------|--------------|
| `services/mod_identity.py` | NEU. Stabile Identitaet (mod_name) rein aus dem Pfad, zirkelfrei |
| `integrations/scs/content_category.py` | NEU. Content-Kategorie aus def-Liste, ehrlich nur physics |
| `services/conflict_detect.py` | NEU. Mods die dieselbe def-Datei ueberschreiben (invertierter Index) |
| `core/version_compat.py` | NEU. 4-Zustands-Kompatibilitaet (mirror des Spiels) |
| `core/game_version.py` | NEU. Spielversion aus game.log.txt (`[ufs] Loaded pack set version`) |
| `core/version_compare.py` | NEU. Numerischer Versionsvergleich (2.10>2.2, unparsebar->None) |
| `services/map_combo.py` | Erweitert auf Format v2 (package_version + outdated-Hinweis) |
| `services/mod_scanner.py` | ScannedMod.mod_name (property) + def_files (einmalige Listung) |
| `core/db/scan_cache.py` | Schema 6: def_files-Spalte; Alt-Zeilen werden neu gescannt |
| `core/mod_categories.py` | effective_categories: override > content > map > manifest |
| `ui/widgets/mod_card.py` | Roter Rand + Tooltip fuer inkompatible Mods |
| `ui/widgets/active_mod_list.py` | Konflikt-Glyph + groessere Einzeiler-Spacer |

---

## Source-Dateien (`easy_scsmodmanager/`)

> Dateien >= 500 Zeilen mit (!) markiert = Refactor-Kandidat. 400-499 mit (~) = beobachten.

### `easy_scsmodmanager/` (Root)

| Datei | Zeilen |
|-------|-------:|
| `__init__.py` | 2 |
| `__main__.py` | 33 |
| `app.py` | 45 |

### `core/`

| Datei | Zeilen |
|-------|-------:|
| `game_paths.py` | 209 |
| `settings_store.py` | 100 |
| `mod_categories.py` | 86 |
| `load_order.py` | 76 |
| `category_overrides.py` | 65 |
| `version_compat.py` | 49 |
| `load_order_layout.py` | 43 |
| `version_compare.py` | 38 |
| `game_version.py` | 35 |
| `map_base_mods.py` | 25 |

### `core/models/`

| Datei | Zeilen |
|-------|-------:|
| `mod_manifest.py` | 51 |

### `core/db/`

| Datei | Zeilen |
|-------|-------:|
| `scan_cache.py` | 303 |
| `workshop_meta_cache.py` | 123 |

### `integrations/scs/`

| Datei | Zeilen |
|-------|-------:|
| `hashfs_reader.py` | 336 |
| `cityhash.py` | 183 |
| `workshop_versions.py` | 122 |
| `aem_reader.py` | 110 |
| `raw_zip_reader.py` | 95 |
| `manifest_bundle.py` | 85 |
| `mod_source.py` | 82 |
| `zip_reader.py` | 43 |
| `detector.py` | 37 |
| `content_category.py` | 33 |
| `map_detect.py` | 18 |
| `file_listing.py` | 17 |

### `integrations/sii/`

| Datei | Zeilen |
|-------|-------:|
| `parser.py` | 268 |
| `crypto.py` | 74 |

### `integrations/steam/`

| Datei | Zeilen |
|-------|-------:|
| `workshop_api.py` | 139 |
| `library_detector.py` | 109 |

### `services/`

| Datei | Zeilen |
|-------|-------:|
| `mod_scanner.py` | 432 (~) |
| `profile_backup.py` | 157 |
| `profile_reader.py` | 151 |
| `mod_matching.py` | 133 |
| `profile_writer.py` | 130 |
| `map_combo.py` | 121 |
| `scs_extractor.py` | 117 |
| `conflict_detect.py` | 74 |
| `mod_identity.py` | 46 |

### `ui/`

| Datei | Zeilen |
|-------|-------:|
| `main_window.py` | 874 (!) |
| `font_helper.py` | 68 |
| `theme.py` | 62 |

### `ui/widgets/`

| Datei | Zeilen |
|-------|-------:|
| `active_mod_list.py` | 645 (!) |
| `mod_card.py` | 358 |
| `profile_header.py` | 194 |
| `mod_card_grid.py` | 191 |
| `filter_toolbar.py` | 154 |

### `ui/dialogs/`

| Datei | Zeilen |
|-------|-------:|
| `settings_dialog.py` | 217 |
| `extract_dialog.py` | 199 |
| `restore_backup_dialog.py` | 179 |
| `mod_info_dialog.py` | 104 |

### `ui/threads/`

| Datei | Zeilen |
|-------|-------:|
| `workshop_fetch_thread.py` | 118 |
| `scan_thread.py` | 74 |
| `extract_thread.py` | 66 |

### `utils/`

| Datei | Zeilen |
|-------|-------:|
| `i18n.py` | 110 |
| `scs_markup.py` | 81 |
| `logging_setup.py` | 19 |

### `cli/`

| Datei | Zeilen |
|-------|-------:|
| `scan.py` | 206 |

---

## Zusammenfassung nach Verzeichnis

| Verzeichnis | Zeilen |
|-------------|-------:|
| `easy_scsmodmanager/` (Root) | 80 |
| `core/` | 726 |
| `core/models/` | 51 |
| `core/db/` | 426 |
| `integrations/scs/` | 1.161 |
| `integrations/sii/` | 342 |
| `integrations/steam/` | 248 |
| `services/` | 1.361 |
| `ui/` | 1.004 |
| `ui/widgets/` | 1.542 |
| `ui/dialogs/` | 699 |
| `ui/threads/` | 258 |
| `utils/` | 210 |
| `cli/` | 206 |
| **Source gesamt** | **8.314** |
| `tests/` | 5.382 |
| **Projekt gesamt** | **13.696** |

---

## Refactor-Beobachtungsliste

> Dateien >= 500 Zeilen (Split faellig) und 400-499 (beobachten).

| Datei | Zeilen | Status |
|-------|-------:|--------|
| `ui/main_window.py` | 874 | (!) Split faellig - waehrend Load-Order-Task stark gewachsen |
| `ui/widgets/active_mod_list.py` | 645 | (!) Split faellig - Spacer/Konflikt/Combo/DnD in einer Datei |
| `services/mod_scanner.py` | 432 | (~) beobachten |
