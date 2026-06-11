# ModShare-Backend einrichten (Supabase)

Die **Online-Code**-Funktion im Teilen-Menü (eine Modliste per 6-Zeichen-Code
weitergeben) braucht ein kleines Supabase-Backend. **Datei-Export/-Import und
das Übernehmen aus einer `profile.sii` funktionieren ohne Backend** - nur die
Code-Aktionen sind ohne diese Einrichtung inaktiv und melden "nicht
konfiguriert".

Das ganze Setup dauert ~10 Minuten und ist einmalig. Der kostenlose Supabase-
Tarif reicht locker.

---

## Was am Ende rauskommt

Zwei Werte, die in `easy_scsmodmanager/integrations/supabase/share_api.py`
eingetragen werden:

- `SUPABASE_URL` - die Projekt-URL, z. B. `https://abcdxyz.supabase.co`
- `SUPABASE_KEY` - der **publishable** (anon) Key, der öffentlich sein darf

> **Wichtig:** Es ist bewusst der *publishable/anon* Key, nicht der
> `service_role`-Key. Der Schutz liegt nicht im Geheimhalten des Keys, sondern
> darin, dass die Tabelle per Row Level Security komplett gesperrt ist und nur
> zwei `security definer`-Funktionen Zugriff geben (kein Auflisten fremder
> Codes, kein Schreiben/Löschen von außen). Den **`service_role`-Key niemals**
> in die App, ins Repo oder in einen Chat geben.

---

## Schritt 1 - Projekt anlegen

1. Auf <https://supabase.com> einloggen (GitHub-Login geht).
2. **New project**.
   - Name: z. B. `escsmm-modshare`
   - Region: eine in der Nähe der meisten Nutzer (für DE/EU: **Frankfurt /
     `eu-central-1`**).
   - Ein **Datenbank-Passwort** wird verlangt - sicheres nehmen und im
     Passwortmanager speichern. (Für den Betrieb brauchen wir es nicht wieder,
     aber verlieren willst du es nicht.)
3. Projekt erstellen lassen (ein, zwei Minuten warten, bis es "ready" ist).

## Schritt 2 - pg_cron aktivieren (VOR dem SQL)

Das Schema legt einen täglichen Aufräum-Job an (Codes verfallen nach 90 Tagen).
Dafür muss die Extension **vorher** an sein, sonst bricht das SQL ab.

1. Linke Sidebar: **Database -> Extensions**.
2. Nach **`pg_cron`** suchen und **aktivieren**.

## Schritt 3 - Das Schema einspielen

1. Linke Sidebar: **SQL Editor -> New query**.
2. Den **kompletten Inhalt von `packaging/supabase.sql`** (liegt im Repo neben
   dieser Datei) hineinkopieren.
3. **Run**.

Erwartung: Läuft ohne Fehler durch. Es entstehen die Tabelle `mod_shares`, die
zwei Funktionen `create_share` / `get_share` und der Cron-Job
`modshare-cleanup`.

Falls eine Meldung wie `schema "cron" does not exist` kommt: Schritt 2 wurde
übersprungen - pg_cron aktivieren und das SQL erneut ausführen.

## Schritt 4 - URL und Key auslesen

1. Linke Sidebar: **Project Settings (Zahnrad) -> API**.
2. **Project URL** kopieren -> das ist `SUPABASE_URL`.
3. Bei den **API Keys** den **`anon` / `publishable`** Key kopieren -> das ist
   `SUPABASE_KEY`. (NICHT `service_role`.)

## Schritt 5 - Werte an mich (Oliver) geben

Mir einfach die zwei Zeilen schicken, z. B.:

```
SUPABASE_URL = https://abcdxyz.supabase.co
SUPABASE_KEY = eyJhbGciOi... (anon/publishable)
```

Ich trage sie in `share_api.py` ein (eigener kleiner Commit), und die Online-
Codes sind ab dem nächsten Build live. Mehr ist auf deiner Seite nicht zu tun.

---

## Optional - selbst testen, ob es geht

Im SQL-Editor:

```sql
-- einen Test-Share anlegen (gibt einen 6-Zeichen-Code zurück):
select create_share('ets2', 'Test', '{"mods": []}'::jsonb);

-- denselben Code wieder abrufen (gibt das JSON zurück):
select get_share('DEINCODE');

-- Cron-Job prüfen:
select * from cron.job;
```

Wenn `create_share` einen Code liefert und `get_share` das JSON zurückgibt, ist
das Backend fertig.

---

## Hinweise

- **Kosten:** Im Free-Tier reicht das dauerhaft; die Payloads sind winzig
  (< 256 KiB pro Code, hartes DB-Limit) und Codes verfallen nach 90 Tagen
  automatisch.
- **Eigener Server (Self-Hosting):** Dieselbe `supabase.sql` läuft auf jeder
  Supabase-Instanz. Wer ESCSMM forkt und einen eigenen Code-Server will, macht
  exakt diese fünf Schritte und trägt seine eigene URL + Key ein.
- **Rotation:** Sollte der publishable Key je rotiert werden, einfach den neuen
  Wert in `share_api.py` eintragen und neu bauen - die Daten bleiben.
