# 3DCam2Post

Ein DIT Ingest-Tool für (fast ausgestorbenes) Stereo 3D Kameramaterial. 

Ich habe dieses Tool ursprünglich für meinen eigenen Workflow gebaut. Mir ist völlig bewusst, dass heutzutage vermutlich niemand mehr ernsthaft in Stereo 3D dreht. Aber da es da draußen vielleicht doch noch den einen oder anderen gibt, der mit alten 3D Kameras experimentiert oder alte Archivdaten retten muss, veröffentliche ich das Projekt.

## Worum geht's?

3DCam2Post ist eine Bridge, um Material von 3D Kameras (wie z.B. der Panasonic AG-3DP1 oder AG-3DA1) sicher auf Festplatten zu kopieren und direkt für die Postproduktion – insbesondere für DaVinci Resolve – vorzubereiten. 

Die alten P2 (MXF) und AVCHD (MTS) Formate haben gerade in Stereo 3D ihre Tücken, vor allem wenn es um Timecodes und Left/Right-Zuordnungen geht. Dieses Tool nimmt diese Handarbeit ein Stück weit ab.

## Was das Tool macht

- **Automatisches Umbenennen:** Dateien (Video, Audio, XML) werden beim Ingest direkt sinnvoll nach `Szene_Einstellung_Take_L/R` umbenannt. Die UI bietet dafür praktische Hotkeys, um das Material nach dem Dreh schnell durchzuwinken.
- **Sicheres Kopieren:** Chunked-Copy mit flüssiger Fortschrittsanzeige und MB/s-Berechnung. Optionale MD5-Prüfsummen-Verifizierung, damit kein Bit verloren geht.
- **DaVinci Resolve Timecode-Fix:** Resolve weigert sich oft, die Timecodes der alten AG-3DP1 Kameras nativ zu lesen. Das Tool generiert nach dem Kopieren automatisch eine `Resolve_Timecode_Import.csv`, womit man dieses Problem umgehen kann.
- **Reporting:** Erzeugt auf Wunsch MHL-Dateien und übersichtliche HTML-Reports mit Thumbnails (via FFmpeg).
- **Safety First:** Warnt zum Beispiel, wenn bei P2-Karten mal wieder eine Audiospur fehlt, und schützt durch Warnhinweise davor, bereits gesichertes Material versehentlich zu überschreiben.

## Wie importiere ich die Timecodes in Resolve?

Da Resolve den nativen Timecode der alten Kameras oft ignoriert, hilft die generierte `Resolve_Timecode_Import.csv`:
1. Ziehe alle kopierten Videoclips ganz normal in den **Media Pool** von DaVinci Resolve.
2. Wähle im oberen Menü: `File` -> `Import Metadata To` -> `Media Pool...`
3. Wähle die vom Tool generierte `Resolve_Timecode_Import.csv` aus.
4. Achte darauf, dass im Import-Dialog als Abgleich-Kriterium **"Match using: File Name"** ausgewählt ist.
5. Klicke auf OK. Resolve übernimmt nun den korrekten Start-Timecode für alle betroffenen Clips.

## Installation & Nutzung

Das Tool ist in Python geschrieben und nutzt `customtkinter` für eine dunkle, aufgeräumte Oberfläche. Aktuell lässt es sich als reines Python-Skript ausführen, es sind für die Zukunft aber auch fertig kompilierte Standalone-Versionen (`.exe`) geplant.

1. Repository klonen.
2. Abhängigkeiten installieren: `pip install customtkinter Pillow` (optional auch `xxhash` für schnelleres Hashing).
3. Sicherstellen, dass `ffmpeg` auf dem System installiert bzw. im Systempfad verfügbar ist (wird für Thumbnails und Metadaten-Extraktion benötigt).
4. Die App über `python main.py` starten.

## Warum das Ganze?

Die Grundidee für das Tool entstand aus reiner Notwehr: Das ständige, händische Umbenennen der vielen Videodateien nach dem Dreh war nicht nur unglaublich nervig, sondern auch fehleranfällig. Wer will schon riskieren, beim Backup aus Versehen die Left- und Right-Dateien zu vertauschen oder durcheinanderzubringen? 

Das Umbenennen war also der eigentliche Startpunkt. Alle anderen Features – die Checksummen, die MHL-Reports und die Timecode-Reparatur – haben sich dann erst im Laufe der Zeit aus der Praxis heraus ganz natürlich dazugesellt.

Fühlt euch frei, den Code zu forken, ihn für ganz andere Zwecke auseinanderzunehmen oder als Basis für eigene Ingest-Projekte zu nutzen.
