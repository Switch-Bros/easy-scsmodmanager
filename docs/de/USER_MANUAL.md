# 📖 Easy SCSModManager - Handbuch

**Plattform:** Linux (AppImage, deb, rpm, AUR, tar.gz) und Windows (.exe)
**Spiele:** Euro Truck Simulator 2 und American Truck Simulator

---

## Inhaltsverzeichnis

1. [Was es macht](#was-es-macht)
2. [Die zwei Bereiche](#die-zwei-bereiche)
3. [Profile](#profile)
4. [Mods aktivieren und sortieren](#mods-aktivieren-und-sortieren)
5. [Load-Order-Gruppen](#load-order-gruppen)
6. [Konflikte](#konflikte)
7. [Mods löschen](#mods-löschen)
8. [Backups](#backups)
9. [Modlisten teilen](#modlisten-teilen)
10. [Spiel wechseln](#spiel-wechseln)
11. [Einstellungen](#einstellungen)
12. [Updates](#updates)

---

## Was es macht

Easy SCSModManager liest die Mods, die du schon besitzt (lokaler `mod/`-Ordner
**und** Steam Workshop), zeigt sie mit echten Namen und Icons und lässt dich die
aktive Ladereihenfolge für ein Profil bauen - und schreibt sie dann im Klartext
direkt in die `profile.sii` des Spiels, damit das Spiel genau mit deiner
Reihenfolge startet.

Es bearbeitet nur deine eigene `profile.sii` und liest deine eigenen
installierten Mods. Es steht in keiner Verbindung zu SCS Software oder Valve.

## Die zwei Bereiche

- **Links - die Mod-Bibliothek:** jeder installierte Mod als Karte mit Icon,
  Name, Autor und Kategorie. Suchen, sortieren und filtern über die Leiste oben.
- **Rechts - die Aktiv-Liste:** die Ladereihenfolge des gewählten Profils, in
  Load-Order-Gruppen unterteilt, oben nach unten (oben = höchste Priorität).

Zieh die Trennlinie zum Anpassen. Maximierst du das Fenster, füllt das Raster
den Platz mit mehr Spalten.

## Profile

Das Profil-Dropdown im Aktiv-Listen-Kopf zeigt alle Profile des aktuellen
Spiels. Wähl eins, um seine aktiven Mods zu laden. **Speichern** schreibt deine
Änderungen zurück in die `profile.sii` - das Spiel muss dabei geschlossen sein,
sonst überschreibt es die Datei beim Beenden.

## Mods aktivieren und sortieren

- **Doppelklick** auf eine Mod-Karte aktiviert sie. Sie landet am Ende des
  Blocks ihrer eigenen Load-Order-Gruppe und wird ausgewählt.
- **Ziehen** einer Karte aus der Bibliothek in die Aktiv-Liste setzt sie an eine
  genaue Position. In einen Abschnitt gezogen, übernimmt sie auch dessen Gruppe.
- **Ziehen** von Zeilen in der Aktiv-Liste sortiert um. **Doppelklick** auf eine
  Zeile in der Aktiv-Liste entfernt sie.

## Load-Order-Gruppen

Die Aktiv-Liste ist in Gruppen unterteilt (Finanzen, Sound, Physik, Trucks,
Trailer, Maps usw.) mit Überschriften, damit ein Mod bei seinesgleichen sitzt.
Die Gruppen-Reihenfolge folgt der Lade-Reihenfolge des Spiels.

- Ein Mod in der falschen Gruppe bekommt einen **orangen linken Rand**.
  Rechtsklick, **Verschieben nach** -> eine Gruppe, um ihn dort zu pinnen, oder
  **Automatisch (eigene Kategorie)**, um ihn in seine natürliche Gruppe
  zurückzuschicken.
- **Verschieben nach** wirkt auf deine ganze Auswahl.
- Ein Mod in einen Abschnitt gezogen wird dort gepinnt; zurück in seinen
  Heimat-Abschnitt gezogen, löst sich der Pin.

## Konflikte

Zwei aktive Mods kollidieren, wenn sie dieselbe `def/`-Datei ändern - der höhere
in der Liste gewinnt. Konflikte sind ein Hinweis, kein Fehler (bei Maps ist eine
Überschneidung oft Absicht).

Ein kollidierender Mod bekommt einen Glyph vor dem Namen:

- **⚠ gelbes Dreieck - teilweise überschrieben:** einige Dateien verlieren gegen
  Mods darüber.
- **⊘ roter durchgestrichener Kreis - komplett überschrieben:** alle Dateien
  verlieren - der Mod bewirkt an seiner Stelle effektiv nichts.
- **Kein Glyph:** er gewinnt alle geteilten Dateien.

Fahr mit der Maus über den Mod für die volle Liste der überschriebenen Dateien
samt Gewinner. Eine Legende erscheint unten im Panel, solange ein Konflikt
existiert.

## Mods löschen

Rechtsklick auf einen Mod (oder mehrere auswählen, oder **Entf** drücken) und
**Löschen...** verschiebt lokale Mods in den System-Papierkorb - von dort
wiederherstellbar. Workshop-Mods bleiben bei Steam (Eintrag sichtbar, aber
deaktiviert). Nutzt ein gespeichertes Profil den Mod noch, nennt die Bestätigung
die betroffenen Profile zuerst.

Tipp: Setz den **Quelle**-Filter auf **Lokal**, drück **Strg+A**, um alle
sichtbaren Mods zu wählen, dann löschen - schnelles Aufräumen.

## Backups

Der Profil-Kopf hat **Sichern** und **Wiederherstellen**. Ein Backup ist ein Zip
des Profils, außerhalb des Spiel-Baums gespeichert, damit das Spiel es nie
anfasst. Wiederherstellen holt ein früheres Backup zurück.

## Modlisten teilen

Das **Teilen**-Menü im Hauptfenster bietet fünf Aktionen.

### Liste als Code teilen

**Teilen -> Modliste als Code teilen...** erzeugt einen 6-stelligen
alphanumerischen Code (z.B. `A3F7KQ`), der 90 Tage gültig ist. Gib den Code
einem Freund; er löst ihn unter **Teilen -> Code einlösen...** ein und sieht
sofort eine Vorschau (s.u.). Diese Funktion braucht ein konfiguriertes Supabase-Backend - steht
das Backend noch nicht bereit, meldet die App es und du kannst stattdessen
eine Datei exportieren.

### Liste als Datei exportieren / importieren

**Teilen -> Modliste exportieren...** speichert die aktive Liste in eine
`.modshare.json`-Datei, die du per Messenger oder Forum weitergeben kannst.
**Teilen -> Modliste importieren...** lädt eine solche Datei.

### Aus einem fremden Profil übernehmen

**Teilen -> Aus profile.sii übernehmen...** liest eine `profile.sii` direkt ein -
egal ob vom Spiel unverschlüsselt gespeichert oder mit dem ScsC-Format
verschlüsselt. Du musst kein Backup ziehen; die App macht das automatisch
(s. Backup-Hinweis unten).

### Import-Vorschau

Egal woher die Liste kommt (Code, Datei oder Profil) - es erscheint immer
zuerst eine Vorschau:

- **Installiert / Fehlend** - jeder Mod ist als vorhanden (grün) oder fehlend
  (grau) markiert.
- **Workshop-Mods abonnieren** - bei fehlenden Workshop-Mods erscheint ein
  klickbarer **Abonnieren**-Link, der die Steam-Workshop-Seite des Mods öffnet.
  Abonnier die Mods dort und lass Steam sie herunterladen. Sobald Steam fertig
  ist, drücke in der Vorschau **Erneut prüfen** - die App scannt neu, ohne
  das Fenster zu schliessen, und markiert die gerade installierten Mods als
  vorhanden.
- **Fehlende lokale Mods** - bei lokalen Mods, die auf dem Rechner des
  Absenders lagen, siehst du den Dateinamen kopierbereit in der Liste.
- **Fehlende einbeziehen** - die Checkbox (Standard: aktiviert) legt fest,
  ob fehlende Einträge trotzdem in die Liste übernommen werden. Deaktiviere
  sie, wenn du nur die Mods willst, die du schon hast.
- **Versionshinweis** - ist ein Mod bei dir auf einem älteren Stand als in
  der geteilten Liste angegeben, bekommst du einen Hinweis. Das blockiert das
  Übernehmen nicht.
- **Spiel-Mismatch** - kommt die Liste von ETS2 und du hast ATS geöffnet
  (oder umgekehrt), blockiert die App das Übernehmen mit einer klaren
  Meldung. Wechsle zuerst ins richtige Spiel.

Sind alle gewünschten Mods vorhanden, klicke **Übernehmen**. Die App legt
vorher automatisch ein Backup des aktuellen Profils an (wie **Sichern** im
Profil-Kopf), damit du jederzeit zurück kannst.

### Gruppen-Pins werden mitgeteilt

Wenn du mit Easy SCSModManager arbeitest und einem anderen Easy-SCSModManager-
Nutzer eine Liste schickst, werden die Load-Order-Gruppen-Pins mitübertragen.
Der Empfänger sieht nach dem Übernehmen dieselbe Gruppen-Einteilung wie du.

## Spiel wechseln

Das **Spiel**-Menü wechselt zwischen ETS2 und ATS (nur installierte Spiele
wählbar). Deine Wahl wird für den nächsten Start gemerkt.

## Einstellungen

**Datei -> Einstellungen** umfasst die Oberflächen-Sprache, manuelle
Pfad-Overrides (falls die Auto-Erkennung einen Install verfehlt), die
Map-Basis-Begriffsliste und Verhaltens-Schalter (Klick springt zur Aktiv-Liste,
beim Start nach Updates suchen).

## Updates

**Hilfe -> Nach Updates suchen** fragt GitHub nach einer neueren Version. Die
AppImage- und Windows-Builds können ein verifiziertes Update herunterladen und
installieren; Paket-Installationen (deb/rpm/AUR/tar.gz) bekommen einen Hinweis
und aktualisieren über ihren Paketmanager.
