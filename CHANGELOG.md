# Changelog - 3DCam2Post Bridge

Alle nennenswerten Änderungen an diesem Projekt werden in dieser Datei mit Datum und Uhrzeit dokumentiert.

Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.0.0/).

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
