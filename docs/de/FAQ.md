# ❓ Häufige Fragen

---

## Allgemein

### Steht das in Verbindung zu SCS Software oder Steam?

Nein. Easy SCSModManager ist ein unabhängiges Werkzeug. Es bearbeitet nur deine
eigene `profile.sii` und liest deine eigenen installierten Mods.

### Welche Spiele werden unterstützt?

Euro Truck Simulator 2 und American Truck Simulator. Wechsel zwischen ihnen über
das **Spiel**-Menü.

### Funktioniert es mit Workshop-Mods?

Ja - es liest sowohl deinen lokalen `mod/`-Ordner als auch den Steam-Workshop des
Spiels.

## Aktivierung und Reihenfolge

### Warum ist mein aktivierter Mod nicht nach oben gesprungen?

Absicht. Beim Aktivieren landet ein Mod am Ende seiner eigenen
Load-Order-Gruppe, damit er nie unter der Überschrift einer anderen Gruppe
rendert. Oben in der Liste ist die höchste Priorität.

### Ein Mod hat einen orangen Rand - was bedeutet das?

Er sitzt in der falschen Load-Order-Gruppe. Rechtsklick, **Verschieben nach** ->
seine Gruppe, oder **Automatisch (eigene Kategorie)**. In den richtigen
Abschnitt gezogen, passiert dasselbe.

## Konflikte

### Was bedeuten die Glyphen ⚠ und ⊘?

Ein Konflikt heißt, zwei aktive Mods ändern dieselbe `def/`-Datei; der höhere
gewinnt. **⚠ (gelb)** = der Mod verliert einige Dateien gegen Mods darüber.
**⊘ (rot)** = er verliert alle und bewirkt an seiner Stelle effektiv nichts.
**= (grau)** = er fasst Dateien an, die viele Mods gleichzeitig ändern - meist
Absicht und nie als Konflikt gezählt. Kein Glyph = er gewinnt alles. Maus drüber
zeigt die Dateiliste samt Gewinner.

### Ist ein Konflikt ein Fehler?

Nein, ein Hinweis. Bei Maps ist eine Überschneidung oft Absicht und die
Load-Order löst sie auf.

### Im Tooltip steht "... und 82 weitere Dateien". Wie sehe ich alle?

Rechtsklick auf den Mod und **Alle Konflikte anzeigen...** wählen. Der Dialog
listet jede überschriebene Datei ohne Deckel und kann auf alle markierten Mods
umschalten. Mit **Alles kopieren** oder **Als Datei speichern...** kannst du die
Liste weitergeben.

## Löschen

### Wohin gehen gelöschte Mods?

In deinen System-Papierkorb, also wiederherstellbar. Nur lokale Mods -
Workshop-Mods verwaltet Steam (im Workshop das Abo beenden).

## Speichern

### Warum muss das Spiel beim Speichern geschlossen sein?

Das Spiel schreibt die `profile.sii` beim Beenden neu, was deine gespeicherte
Reihenfolge überschreiben würde. Schließ das Spiel zuerst.

## Fehlersuche

### Mein Spiel / meine Workshop-Mods werden nicht erkannt.

Öffne **Datei -> Einstellungen** und setz die Pfad-Overrides für die Dokumente-
und Workshop-Ordner. Unter Windows liest die App die Registry, um Steam und den
Dokumente-Ordner zu finden; hast du sie verschoben, hilft ein manueller
Override. **Werkzeuge -> Log-Ordner öffnen** zeigt ein Log, das nennt, was
gefunden wurde und was nicht.
