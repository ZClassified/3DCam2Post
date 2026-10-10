# Changelog - 3DCam2Post Bridge

Alle nennenswerten Änderungen an diesem Projekt werden in dieser Datei mit Datum und Uhrzeit dokumentiert.

Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.0.0/).

---

## [1.2.0] - 2026-10-10

### Behoben (Datensicherheit)
- **Fehlgeschlagene Kopien wurden als fertig markiert:** Ein Auge gilt jetzt nur noch als `done`, wenn Video und alle Audiospuren fehlerfrei (und ggf. verifiziert) kopiert wurden. Fehler erscheinen als `failed` im Manifest und in der Liste.
- **Überschreibschutz wiederhergestellt:** Vor dem Start wird geprüft, ob Zieldateien existieren (Rückfrage) und ob zwei Clips denselben Zielnamen hätten (Abbruch).
- **Resolve-Timecodes für P2:** Fehlender `Path`-Import in `metadata.py` führte dazu, dass P2-Metadaten nie gelesen wurden und die CSV `-` statt Timecodes enthielt.
- **Resolve-CSV wird zusammengeführt** statt bei jedem Ingest überschrieben (Tag 2 löscht Tag 1 nicht mehr). Ungültige Timecodes werden ignoriert.
- **Clip-Liste stürzte mit Flet 0.84 ab** (`Colors.SURFACE_VARIANT` existiert nicht mehr).
- **Fortschritt über 100 % / negative ETA:** Audiospuren werden jetzt in die Gesamtgröße eingerechnet.
- **Clip-Identität:** Größe und Aufnahmezeit jeder Quelldatei werden im Manifest gespeichert. Eine recycelte Clip-Nummer (z.B. nach dem Formatieren) bekommt automatisch einen eigenen Eintrag (`00001~2`) statt fälschlich als „Komplett“ übersprungen zu werden. L/R werden bei gleicher Nummer anhand der Aufnahmezeit gepaart (auch bei mehreren Kartensätzen in beliebiger Reihenfolge). Ohne verwertbare Zeitstempel bzw. bei alten Manifesten gilt das bisherige Verhalten.
- **Einstellungen in der EXE gingen verloren:** Config liegt jetzt in `%APPDATA%\3DCam2Post` (alte Config wird einmalig übernommen).
- **Thumbnail-Cache** pro Datei statt pro Clip-ID (keine falschen Vorschauen/Report-Bilder mehr).
- **Cam-ID** wird pro Clip gespeichert. Teilweise kopierte Clips behalten ihren Namen, damit L/R zusammenpassen.
- **Thread-Sicherheit:** Alle UI-Updates aus Hintergrund-Threads laufen über den Flet-Event-Loop.
- **Hotkeys nach Textfeld/Dialog:** Esc/Enter verlassen ein Textfeld, nach Dialogen geht der Fokus zurück an die Hotkeys.
- MHL: korrekter Tag `xxhash64be`, Pfade mit `/`. HTML-Report escaped Namen und listet Fehler.

### Hinzugefügt (Resolve-Timecode ohne CSV)
- **Ausgabe-Modus für P2 (3DP1):** „Nur P2-Kopie (1:1)“, „P2-Kopie + MOV“ (Ordner `SCHNITT`) oder „Nur MOV“.
  Die MOV enthält Bild und alle Tonspuren verlustfrei umverpackt (ohne Neukodierung) plus Timecode-Spur.
  Hintergrund (an Originalkarten getestet): Resolve zeigt bei P2-Clips der 3DP1 den Timecode 00:00:00:00, sobald es Video und separate Tondateien verknüpft – unabhängig von Umbenennung/XML. Aus der MOV liest Resolve Timecode, Ton und Codec korrekt.
- MOV-Prüfung: mit Verifizierung paketgenauer Vergleich (Bild + jede Tonspur) gegen die Quelle, sonst Framezahl-Kontrolle. Unvollständige MOVs werden gelöscht, Abbruch wird sauber behandelt.
- **L/R-Paarung über UMID:** Die 3DP1 schreibt für L und R dieselbe UMID-Materialnummer; Paarung und Manifest-Abgleich nutzen sie (an zwei Karten mit 42 Clips verifiziert).
- XML wird erst nach erfolgreichem Video/MOV geschrieben; Reports nur, wenn mindestens ein Clip fertig wurde.
- **AVCHD (3DA1):** Timecode und Aufnahmebeginn werden aus dem MDPM-Block im Videostream gelesen (Resolve liest beides nicht).
  Der Timecode landet in der Resolve-CSV, die Aufnahmezeit im Report. Datum + Timecode dienen als Aufnahme-ID für
  L/R-Paarung und Manifest (frame-genau identisch für L und R, an Originalkarten verifiziert).
- AVCHD: Dateien, die laut Kamera-Playlist Fortsetzung einer geteilten langen Aufnahme sind, werden als „Fortsetzung“ markiert.

### Geändert (UI)
- Neues Layout: Ziel (Stammordner/Projekt/Tag) oben mit Pfadvorschau, kompakte Clip-Tabelle mit L/R-Badges, Stereo-Vorschau L+R nebeneinander, Live-Vorschau des nächsten Dateinamens.
- Hotkeys unverändert (`→`, `S`, `E`, `T`, `↑/↓`, `Entf`), Hotkey-Status in der Statusleiste.
- Ingest-Zusammenfassung vor dem Start (Clips, Größe, freier Speicher, Hinweis auf ungeloggte Clips) und Abschlussdialog mit Fehlerliste, „Zielordner öffnen“ und „Report öffnen“.
- Bestätigung vor „Liste leeren“. Einstellungen mit Benennungsbeispiel und Schalter für P2-Audio.
- Verifizierung hasht die Quelle während des Kopierens (ein Lesedurchgang weniger).
- `requirements.txt`: `flet==0.84.*` (Pillow entfernt, wurde nicht genutzt).

---

## [1.1.0] - 2026-08-25 15:00:00 +02:00

### Behoben & Optimiert (Flet Migration Fixes)
- **Thread-sichere UI-Updates:** Asynchrone Threading-Blockaden (`page.run_task` mit synchronen Lambdas) behoben. Scannen, Vorschaubilder, Clip-Status und Ingest-Abschluss aktualisieren die Benutzeroberfläche nun sofort.
- **Manifest-Persistenz:** Automatische Speicherung von `ingest_manifest.json` beim Ingest hinzugefügt. Stereo-3D Matching (`MATCH: Ergänze L/R`) funktioniert nun auch nach App-Neustart oder separatem Kartendurchlauf zuverlässig.
- **Pfadauflösung (`resource_path`):** Pfadermittlung korrigiert, sodass Konfigurationsdateien (`ingest_config.json`), Assets (`icon.ico`, `logo.svg`), Handbücher und `ffmpeg` zuverlässig gefunden und gespeichert werden.
- **Tastatur-Hotkeys & Fokus-Schutz:** Tastatur-Shortcuts pausieren nun bei aktiver Bearbeitung von Textfeldern (Projektname, Szene, Einstellung etc.) und unterstützen sowohl Klein- als auch Großbuchstaben (`s`/`S`, `e`/`E`, `t`/`T`).
- **Audio-Quellenauswahl:** P2-Audio-Ingest respektiert jetzt die Einstellung `audio_source` ("Links", "Rechts", "Beide").
- **Freispeicher- & Sicherheitschecks:** Überprüfung des freien Festplattenspeichers vor Ingest-Start mit Warnhinweis bei < 100 GB freiem Speicherplatz implementiert.
- **Statusanzeige bei Abbruch:** Korrekte Statusmeldung `Ingest abgebrochen!` bei Betätigung des Abbruch-Buttons statt irreführender Erfolgsmeldung.
- **P2-XML Case-Sensitivity:** Metadaten-Extraktion aus P2-XML-Dateien case-insensitiv gestaltet (`.xml` und `.XML`).
- **Dokumentation:** `README.md` auf Flet und `requirements.txt` aktualisiert.

---

## [1.0.0] - 2026-08-17 15:45:00 +02:00

### Hinzugefügt & Geändert
- **Migration auf Flet:** Kompletter Umbau der Benutzeroberfläche von CustomTkinter auf moderne, plattformunabhängige Flet-UI (Flutter-basiert).
- Modernes Dark-Theme, native Dateidialoge und responsive Layout-Struktur.
- Eigener Assets-Ordner mit Vektor-Logo und Anwendungs-Icon (`icon.ico`).

---

## [0.9.0] - 2026-06-26 09:30:00 +02:00

### Hinzugefügt & Geändert
- **CustomTkinter Refactoring:** Überarbeitung der UI auf dunkles Layout mit CustomTkinter.
- Erweiterte Datensicherheitschecks und Layout-Verbesserungen.
- Integrierter Einstellungsdialog für Padding, Hash-Algorithmen (MD5, xxHash, SHA-256) und Sortiermodi.

---

## [0.8.0] - 2026-06-25 23:55:00 +02:00

### Hinzugefügt
- Standalone-Skript `resolve_tc_export.py` zur nachträglichen Timecode-Extraktion für DaVinci Resolve.
- Automatische Erstellung der `Resolve_Timecode_Import.csv` nach jedem Ingest-Durchlauf.
- Automatischer Fallback auf systemweites FFmpeg, falls keine lokale Binary beiliegt.
- Option zum Umschalten von Thumbnails in HTML-Reports zur Performance-Steigerung.

---

## [0.1.0] - 2026-05-16 18:15:00 +02:00

### Hinzugefügt
- Initialer Release von 3DCam2Post.
- Unterstützung für Panasonic AG-3DP1 (P2 MXF) und AG-3DA1 (AVCHD MTS).
- Automatische Umbenennung (`Szene_Einstellung_Take_L/R`), Chunked-Copy und Checksummen-Verifizierung (MHL/HTML).
