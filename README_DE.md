<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="easy_scsmodmanager/resources/images/readme_header_dark.webp">
    <source media="(prefers-color-scheme: light)" srcset="easy_scsmodmanager/resources/images/readme_header_light.webp">
    <img src="easy_scsmodmanager/resources/images/readme_header_light.webp" alt="" width="800">
  </picture>
</p>

<h1 align="center">🚚 Easy SCSModManager</h1>

[![Python 3.13+](https://img.shields.io/badge/Python-3.13%2B-E67E22?style=plastic&logo=python&logoColor=E67E22&labelColor=000000)](https://www.python.org/)
[![Plattform](https://img.shields.io/badge/Plattform-Linux%20%7C%20Windows-E67E22?style=plastic&logo=linux&logoColor=E67E22&labelColor=000000)](https://www.python.org/)
[![Spiele](https://img.shields.io/badge/Spiele-ETS2%20%7C%20ATS-E67E22?style=plastic&labelColor=000000)](https://www.scssoft.com/)
[![Lizenz](https://img.shields.io/badge/Lizenz-GPL--3.0-E67E22?style=plastic&labelColor=000000)](https://github.com/Switch-Bros/easy-scsmodmanager/blob/main/LICENSE)
[![Tests](https://img.shields.io/badge/Tests-664%20bestanden-E67E22?style=plastic&labelColor=000000)](https://github.com/Switch-Bros/easy-scsmodmanager)
[![i18n](https://img.shields.io/badge/i18n-🇬🇧%20🇩🇪-E67E22?style=plastic&labelColor=000000)](https://github.com/Switch-Bros/easy-scsmodmanager)
[![Docs](https://img.shields.io/badge/Docs-DeepWiki-E67E22?style=plastic&labelColor=000000)](https://deepwiki.com/Switch-Bros/easy-scsmodmanager)
[![Downloads](https://img.shields.io/github/downloads/Switch-Bros/easy-scsmodmanager/total?style=plastic&color=E67E22&labelColor=000000)](https://github.com/Switch-Bros/easy-scsmodmanager/releases)

> **Ein richtiger Mod-Manager für Euro Truck Simulator 2 und American Truck Simulator.**
> Mods durchstöbern wie im Spiel, die Ladereihenfolge per echtem Drag and Drop sortieren und direkt ins Profil zurückschreiben - mit den Komfort-Funktionen, die das Spiel selbst nie hatte.

<p align="center">
  <a href="README.md">
    <img src="https://img.shields.io/badge/🇬🇧_Read_in_English-E67E22?style=for-the-badge&labelColor=000000" alt="Read in English" height="35">
  </a>
</p>

<!-- Hero-Screenshot -->
<p align="center">
  <img src="easy_scsmodmanager/resources/screenshots/01_de_main_window.webp" alt="Easy SCSModManager - Hauptfenster" width="900">
</p>


<h3 align="center">💛 Projekt unterstützen</h3>

Wenn dir dieser Manager das Zurechtklicken einer 300-Mod-Liste Zeile für Zeile erspart, BITTE denk über eine Spende nach um die Entwicklung zu unterstützen. Jeder Beitrag - egal wie klein - hält das Projekt am Leben.

<p align="center">
  <a href="https://www.paypal.com/donate/?hosted_button_id=HWPG6YAGXAWJJ">
    <img src="easy_scsmodmanager/resources/images/paypal_de.webp" alt="Unterstütze uns auf PayPal" height="80">
  </a>
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
  <a href="https://ko-fi.com/S6S51T9G3Y">
    <img src="easy_scsmodmanager/resources/images/ko-fi_de.webp" alt="Unterstütze uns auf Ko-fi" height="80">
  </a>
</p>

<p align="center"><i>Danke an alle, die schon beigetragen haben - ihr seid großartig! 🙏</i></p>

<p align="center">Spenden ist gerade nicht drin? <b>Ein ⭐ für dieses Repo hilft genauso</b> - es macht das Projekt für andere Trucker sichtbar und kostet nichts.</p>

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="easy_scsmodmanager/resources/images/readme_divider_dark.webp">
    <source media="(prefers-color-scheme: light)" srcset="easy_scsmodmanager/resources/images/readme_divider_light.webp">
    <img src="easy_scsmodmanager/resources/images/readme_divider_light.webp" alt="" width="800">
  </picture>
</p>


<h2 align="center">✨ Funktionen</h2>

<h3 align="center">🚚 Jeder Mod, den du hast - <i>auch die sperrigen</i></h3>

Easy SCSModManager liest deinen lokalen `mod/`-Ordner und deine Steam-Workshop-Abos für ETS2 und ATS und zeigt alles in einem Karten-Raster, das aussieht wie der Mod-Manager im Spiel - nur besser.

- **Jedes Container-Format** - einfache `.scs`, ZIP-basierte `.scs`, HashFS v1 und v2 (mit reinem Python-Reader dekodiert, ohne externe Tools) und entpackte Mod-Ordner
- **Liest die Daten, die auch der In-Game-Browser zeigt** - Name, Icon und Beschreibung direkt aus der `manifest.sii` jedes Mods, sodass auch ein Workshop-Mod namens `universal.scs` seinen echten Namen zeigt
- **Workshop-Vorschau** - hat ein Mod kein lesbares lokales Icon, springt das Steam-Workshop-Vorschaubild ein
- **Suche, Sortierung und Filter** - Volltextsuche über Name, Ersteller und Kategorie, Sortierung nach Name oder Installationsdatum, Filter nach Kategorie, nur Workshop oder nur Favoriten
- **Mehrfachauswahl** mit Strg / Shift (oder Strg+A für alles Sichtbare), um ganze Stapel auf einmal zu aktivieren, zu deaktivieren oder zu löschen
- **Mods in den Papierkorb löschen** - Rechtsklick (oder Entf) entfernt lokale Mods, mit Warnung falls ein gespeichertes Profil sie noch nutzt; Workshop-Mods bleiben bei Steam
- **Nach Quelle filtern** - alle Mods, nur Workshop oder nur deine lokalen anzeigen
- **Responsives Raster** - maximier das Fenster und das Raster fügt Spalten hinzu, statt einen leeren Streifen zu lassen; die Karten behalten ihre Größe
- **BVB-gelber Akzent** - das verfeinerte dunkle Theme malt Modnamen in Borussia-Dortmund-Gelb

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="easy_scsmodmanager/resources/images/readme_divider_dark.webp">
    <source media="(prefers-color-scheme: light)" srcset="easy_scsmodmanager/resources/images/readme_divider_light.webp">
    <img src="easy_scsmodmanager/resources/images/readme_divider_light.webp" alt="" width="800">
  </picture>
</p>

<h3 align="center">🖱️ Ladereihenfolge per Drag and Drop - <i>der ganze Grund für die App</i></h3>

Der Mod-Manager im Spiel lässt dich einen Mod nur Zeile für Zeile nach oben oder unten schieben. Bei 300 Mods heißt das: einen Mod in die Mitte der Liste bekommen = 150-mal *nach oben* klicken. Easy SCSModManager ersetzt das durch echtes Drag and Drop: zur Stelle scrollen, Mod reinziehen, fertig.

- **Ziehen zwischen den Panels** - Mods aus der Bibliothek in die aktive Liste ziehen und zurück
- **Umsortieren per Ziehen** - die aktive Ladereihenfolge direkt umordnen, mit sanftem Auto-Scrollen und klarer Einfügemarkierung
- **Nach Load-Order-Abschnitt gruppiert** - die aktive Liste ist in Ladereihenfolge-Gruppen unterteilt (Finanzen, Sound, Trucks, Trailer, Maps usw.) mit klaren Überschriften, sodass ein Mod in der Nähe seinesgleichen landet
- **Fehlplatzierungs-Markierung** - ein Mod in der falschen Gruppe wird markiert, mit Rechtsklick-*Verschieben nach*, um ihn dahin zu pinnen, wo er hingehört
- **Ganze Auswahlen in eine Gruppe verschieben** - das *Verschieben nach*-Menü wirkt auf alle markierten Mods auf einmal, plus ein *Automatisch*-Eintrag, der sie in ihre natürliche Gruppe zurückschickt; auch ein Drag in einen Abschnitt behält den Mod dort
- **Schreibt direkt in die `profile.sii`** - deine Reihenfolge wird im Klartext ins Profil gespeichert (das Format, das das Spiel ohne Signaturprüfung liest), damit ETS2/ATS genau mit deiner Reihenfolge startet

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="easy_scsmodmanager/resources/images/readme_divider_dark.webp">
    <source media="(prefers-color-scheme: light)" srcset="easy_scsmodmanager/resources/images/readme_divider_light.webp">
    <img src="easy_scsmodmanager/resources/images/readme_divider_light.webp" alt="" width="800">
  </picture>
</p>

<h3 align="center">🗺️ Map-Combos - <i>teile ein Setup, kein Screenshot</i></h3>

Map-Combo-Ersteller reichen ihre Ladereihenfolge meist als Screenshot oder getippte Liste herum, die dann jeder von Hand nachklickt. Easy SCSModManager macht daraus eine Datei. **Rechtsklick auf die Maps-Gruppenüberschrift** in der aktiven Liste exportiert oder importiert eine Combo.

- **Export** des Map-Blocks deiner Ladereihenfolge in eine kleine JSON-Datei zum Teilen
- **Import** einer Combo: die App scannt zuerst neu und setzt dann deine Maps in genau die Reihenfolge des Erstellers - deine Trucks, Sounds und alles andere bleiben unangetastet
- **Fehlende-Map-Prüfung** - braucht die Combo eine Map, die du nicht hast, listet ein Dialog genau diese Maps mit Namen auf, damit du weißt, was du noch besorgen musst
- **Update-Hinweis** - hast du eine Map, aber die Combo wurde mit einer neueren Version gebaut (du hast RusMap 2.2, die Combo nutzte 2.4), sagt die App es dir - als Hinweis, nie als Blockade

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="easy_scsmodmanager/resources/images/readme_divider_dark.webp">
    <source media="(prefers-color-scheme: light)" srcset="easy_scsmodmanager/resources/images/readme_divider_light.webp">
    <img src="easy_scsmodmanager/resources/images/readme_divider_light.webp" alt="" width="800">
  </picture>
</p>

<h3 align="center">🔗 Teile deine ganze Modliste - <i>per Code, Datei oder direkt aus einer profile.sii</i></h3>

Map-Combos teilen nur den Map-Block. Das **Teilen-Menü** teilt deine *komplette* aktive Ladereihenfolge - jeden Mod, in Reihenfolge - auf drei Wegen: als kurzen **6-Zeichen-Online-Code** (90 Tage gültig), als `.modshare.json`-**Datei** oder direkt **aus der `profile.sii` eines Freundes** (verschlüsselt oder Klartext, wird für dich entschlüsselt).

- **Installations-Vorschau, bevor irgendetwas übernommen wird** - du siehst, welche Mods du schon hast und welche fehlen. Fehlende Workshop-Mods bekommen einen klickbaren **Abonnieren**-Link; ein **Erneut-prüfen**-Knopf scannt neu, ohne den Dialog zu schließen, sodass du abonnieren, Steam herunterladen lassen und bestätigen kannst - alles in einem Ablauf
- **Fehlende lokale Mods** werden mit kopierbarem Namen aufgelistet, damit du weißt, was du besorgen musst
- **Gruppen-Pins reisen mit** - nutzen beide Seiten Easy SCSModManager, kommen auch deine Ladereihenfolge-Gruppen mit
- **Sicher konzipiert** - geteilt wird nur die Modliste, nie deine Spielstände oder Einstellungen; ein Spiel-Mismatch (ETS2 vs ATS) sperrt das Übernehmen; und vor jedem Import wird automatisch ein Profil-Backup angelegt
- **Online-Codes brauchen ein winziges optionales Backend** (selbst hostbares Supabase, siehe [`packaging/SUPABASE_SETUP.md`](packaging/SUPABASE_SETUP.md)); Teilen per Datei und profile.sii geht immer

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="easy_scsmodmanager/resources/images/readme_divider_dark.webp">
    <source media="(prefers-color-scheme: light)" srcset="easy_scsmodmanager/resources/images/readme_divider_light.webp">
    <img src="easy_scsmodmanager/resources/images/readme_divider_light.webp" alt="" width="800">
  </picture>
</p>

<h3 align="center">⚠️ Kompatibilität und Konflikte - <i>Ärger sehen, bevor das Spiel abstürzt</i></h3>

- **Kompatibilitäts-Prüfung** - Mods werden gegen die erkannte Spielversion geprüft, genau so wie es das Spiel macht: markiert wird nur ein Mod, dessen `manifest.sii` tatsächlich eine inkompatible Version angibt. Ein Mod ohne Versionsangabe wird nie fälschlich markiert - der 1.58-Mod, den du bewusst auf 1.59 fährst, bleibt also in Ruhe
- **Konflikt-Schwere auf einen Blick** - überschreiben zwei aktive Mods dieselbe `def/`-Datei, gewinnt der höhere. Jeder betroffene Mod wird eingestuft: ein **gelbes ⚠ Dreieck**, wenn er *einige* Dateien verliert (teilweise überschrieben), ein **roter ⊘ durchgestrichener Kreis**, wenn er *alle* verliert (komplett überschrieben - er bewirkt an seiner Stelle nichts), und kein Zeichen, wenn er alles gewinnt. Die zwei Formen bleiben in Graustufen unterscheidbar, also lesbar ohne Farbe
- **Voller Konflikt-Tooltip + Legende** - fahr über einen markierten Mod für jede überschriebene Datei samt Gewinner; eine einzeilige Legende erscheint unter der Aktiv-Liste, solange ein Konflikt existiert. Es ist ein Hinweis, keine Blockade - bei Maps ist eine Überschneidung oft gewollt
- **Dreistufige Überlappungs-Ansicht** - Dateien, die viele Mods gleichzeitig anfassen (Physik, Klima ...), erscheinen als neutraler grauer "häufig geteilt"-Marker statt versteckt zu werden - nichts geht still verloren, während echte rot/gelbe Konflikte klar bleiben
- **1.48-Paketstruktur erkannt** - Mods, die ihren Inhalt unter einem Wurzel-`base/`- oder einem besessenen `dlc_<name>/`-Ordner ausliefern, werden wie alle anderen gelesen und so auch auf Konflikte, Maps und Physik geprüft

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="easy_scsmodmanager/resources/images/readme_divider_dark.webp">
    <source media="(prefers-color-scheme: light)" srcset="easy_scsmodmanager/resources/images/readme_divider_light.webp">
    <img src="easy_scsmodmanager/resources/images/readme_divider_light.webp" alt="" width="800">
  </picture>
</p>

<h3 align="center">🎮 Beide Spiele, ein Fenster - <i>ETS2 und ATS nebeneinander</i></h3>

- **Spiel-Umschalter** - wechsle zwischen Euro Truck Simulator 2 und American Truck Simulator aus einem Fenster; nur installierte Spiele sind wählbar, und deine Wahl wird für den nächsten Start gemerkt
- **Automatische Erkennung** - findet deine Installation und Profile automatisch unter Linux (nativ und Proton) und Windows, oder setze die Pfade selbst in den Einstellungen
- **Favoriten** - markiere die Mods, die du wieder nutzt, und filtere auf nur Favoriten
- **Profil-Verwaltung** - wechsle zwischen deinen Profilen und sieh, welche Mods jedes nutzt
- **Backup und Wiederherstellung** - vor jedem Speichern kann ein Backup angelegt werden, und jedes frühere Profil ist einen Klick von der Wiederherstellung entfernt

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="easy_scsmodmanager/resources/images/readme_divider_dark.webp">
    <source media="(prefers-color-scheme: light)" srcset="easy_scsmodmanager/resources/images/readme_divider_light.webp">
    <img src="easy_scsmodmanager/resources/images/readme_divider_light.webp" alt="" width="800">
  </picture>
</p>

<h3 align="center">🌍 Zweisprachig und nativ - <i>für Linux und Windows gebaut</i></h3>

Vollständige Oberfläche auf **Englisch 🇬🇧** und **Deutsch 🇩🇪** mit kompletter i18n - keine hartkodierten Strings. Gebaut mit **PyQt6** und der mitgelieferten Inter-Schrift, damit es überall gleich aussieht.

- **Linux und Windows** von Anfang an - native und Proton-Installationen werden beide erkannt
- **Steam-Deck-tauglich** - läuft im Desktop-Modus
- **Sechs Distributions-Formate** - AppImage, Windows-EXE, .deb, .rpm, tar.gz und AUR


<h2 align="center">📦 Herunterladen & Installieren</h2>

| Format | Download | Hinweise |
|--------|----------|----------|
| 🐧 **AppImage** | [Neueste laden](https://github.com/Switch-Bros/easy-scsmodmanager/releases) | Läuft auf jeder Distro - laden, chmod +x, starten |
| 🪟 **Windows-EXE** | [Neueste laden](https://github.com/Switch-Bros/easy-scsmodmanager/releases) | Eigenständig, kein Python nötig |
| 🏗️ **AUR** | `yay -S easy-scsmodmanager` | Arch / Manjaro / CachyOS / EndeavourOS |
| 🍥 **.deb** | [Neueste laden](https://github.com/Switch-Bros/easy-scsmodmanager/releases) | Debian / Ubuntu / Linux Mint (nutzt System-PyQt6) |
| 🎩 **.rpm** | [Neueste laden](https://github.com/Switch-Bros/easy-scsmodmanager/releases) | Fedora / openSUSE / RHEL (nutzt System-PyQt6) |
| 📁 **tar.gz** | [Neueste laden](https://github.com/Switch-Bros/easy-scsmodmanager/releases) | Portabel mit Installationsskript |

<details>
<summary>🔧 Aus dem Quellcode bauen (für Entwickler)</summary>

```bash
# Klonen
git clone https://github.com/Switch-Bros/easy-scsmodmanager.git
cd easy-scsmodmanager

# Virtuelle Umgebung
python3 -m venv .venv
source .venv/bin/activate

# Installieren (editierbar) und starten
pip install -e .
python -m easy_scsmodmanager
```

Benötigt **Python 3.13+** und **PyQt6**.

</details>


<h2 align="center">🗺️ Roadmap</h2>

| Meilenstein | Status |
|-------------|--------|
| SCS-Reader (ZIP, HashFS v1/v2, Fake-Lock, AEM), SII-Parser, Scan-Cache | ✅ Fertig |
| Mod-Browser, Suche/Filter, Profil-Header, i18n, Einstellungen | ✅ Fertig |
| Drag and Drop, Ladereihenfolge umsortieren, `profile.sii`-Writer, Backups | ✅ Fertig |
| Load-Order-Gruppen, Map-Basis-Pinning, Fehlplatzierungs-Markierung | ✅ Fertig |
| Map-Combo Export/Import mit Fehlende-Map- und Versions-Hinweis | ✅ Fertig |
| Kompatibilitäts-Prüfung (4 Zustände) und def-Überschneidungs-Konflikte | ✅ Fertig |
| Favoriten, ETS2/ATS-Spiel-Umschalter | ✅ Fertig |
| Multi-Format-Pakete (AppImage, EXE, .deb, .rpm, tar.gz, AUR) | ✅ Fertig |
| **v1.1.1 - Erste öffentliche Version** | ✅ **Veröffentlicht** |
| Komplette Modliste teilen (Online-Code, Datei, profile.sii) mit Installations-Vorschau | ✅ Fertig |
| Workshop-Update-Benachrichtigungen und Ein-Klick-Links zur Workshop-Seite | 📋 Geplant |
| Flatpak (Flathub-Einreichung) | 📋 Geplant |


<h2 align="center">🌍 Übersetzungen</h2>

Easy SCSModManager kommt mit **Englisch** und **Deutsch**. Du willst es in deiner Sprache?

**Eine Übersetzung beizutragen braucht kein Programmieren.**

1. Kopiere den Ordner `easy_scsmodmanager/resources/i18n/en/` nach `easy_scsmodmanager/resources/i18n/<dein-code>/` (z.B. `ru/`)
2. Übersetze die Werte - ändere niemals die Schlüssel
3. Lass Platzhalter wie `{count}` und `{name}` unangetastet
4. Prüfe `easy_scsmodmanager/resources/i18n/languages.json`: Fehlt dein Sprachcode dort, ergänze eine Zeile mit Code und dem Namen in der Sprache selbst
5. Reiche einen Pull Request ein

Ein fehlender Schlüssel erscheint als nackter Schlüssel in der Oberfläche, sodass Lücken beim Arbeiten leicht auffallen.

<details>
<summary>🧪 Übersetzung vor dem PR testen (optional, auch ohne Programmieren)</summary>

Die App erkennt jeden Sprachordner automatisch - du musst sie nur einmal aus dem Quellcode starten:

```bash
# Quellcode holen: grüner "Code"-Knopf auf GitHub -> Download ZIP -> entpacken
# (oder: git clone https://github.com/Switch-Bros/easy-scsmodmanager.git)

# Im entpackten Ordner:
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e .

# Deine Übersetzung nach easy_scsmodmanager/resources/i18n/<dein-code>/main.json legen, dann:
python -m easy_scsmodmanager
```

Deine Sprache erscheint unter **Einstellungen -> Sprache**; auswählen und die App neu starten. Jeder Text, der noch als nackter Schlüssel wie `menu.file.refresh` erscheint, ist noch nicht übersetzt.

Benötigt **Python 3.13+** (von [python.org](https://www.python.org/), unter Windows im Installer "Add python.exe to PATH" anhaken).

</details>


<h2 align="center">🤝 Mitmachen</h2>

- 🐛 **Bug gefunden?** -> [Issue öffnen](https://github.com/Switch-Bros/easy-scsmodmanager/issues)
- 💡 **Eine Idee?** -> [Diskussion starten](https://github.com/Switch-Bros/easy-scsmodmanager/discussions)
- 🌍 **Sprichst du eine andere Sprache?** -> [Hilf beim Übersetzen!](#-übersetzungen)
- 🔧 **Du willst coden?** -> Lies den [Contributing-Leitfaden](CONTRIBUTING_DE.md), forke das Repo, sieh dir die Issues an und reiche einen PR ein
- 📖 **Neu hier?** -> Schau in die Doku: [Handbuch](docs/de/USER_MANUAL.md) · [FAQ](docs/de/FAQ.md) · [Tastenkürzel](docs/de/KEYBOARD_SHORTCUTS.md) · [Tipps & Tricks](docs/de/TIPS_AND_TRICKS.md) (auch unter **Hilfe -> Dokumentation** in der App)

Mit deiner Teilnahme stimmst du unserem [Verhaltenskodex](CODE_OF_CONDUCT_DE.md) zu.


<h2 align="center">⚖️ Rechtlicher Hinweis</h2>

Diese Software wird **"WIE BESEHEN"** bereitgestellt, ohne jegliche ausdrückliche oder stillschweigende Gewährleistung.

Easy SCSModManager bearbeitet nur deine eigene `profile.sii` und liest deine eigenen installierten Mods. Es steht in **keiner Verbindung zu SCS Software** oder Valve Corporation und wird von diesen nicht unterstützt. Euro Truck Simulator 2 und American Truck Simulator sind Marken von SCS Software.


<h2 align="center">📜 Lizenz</h2>

<p align="center">
  <a href="LICENSE">GPL-3.0-or-later</a> - Copyright © 2026 Switch Bros.
</p>

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="easy_scsmodmanager/resources/images/readme_footer_dark.webp">
    <source media="(prefers-color-scheme: light)" srcset="easy_scsmodmanager/resources/images/readme_footer_light.webp">
    <img src="easy_scsmodmanager/resources/images/readme_footer_light.webp" alt="" width="800">
  </picture>
</p>

<p align="center">
  Mit ❤️ auf Linux gebaut von <a href="https://github.com/Switch-Bros">Switch Bros</a>
</p>
