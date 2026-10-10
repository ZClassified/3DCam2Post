# 3DCam2Post

*[English](#english) | [Deutsch](#deutsch)*

---

<a id="english"></a>
## English

Ingest tool for the Panasonic stereo 3D camcorders **AG-3DP1** (P2, MXF) and **AG-3DA1** (AVCHD, MTS): copies both eyes from the cards, renames them by scene/shot/take and prepares them for DaVinci Resolve.

I built it for my own workflow. Hardly anyone shoots stereo 3D with these cameras today, but if you still work with them or need to rescue old footage, it may help.

### Features

- Pairs left and right eye automatically (P2 via the clip UMID, AVCHD via recording time and timecode)
- Logging with hotkeys, files are renamed to `Project_S01_E02_T003_L`
- Copy with progress, optional checksum verification (MD5, xxHash, SHA-256) with MHL and HTML report
- Lossless MOV output with timecode and audio, readable by Resolve without extra steps
- Timecode CSV for Resolve when copying the camera files 1:1
- Manifest per project: clips already copied are recognised, a missing eye can be added later
- Checks before start: free space, existing files, duplicate names

### Installation

Download `3DCam2Post.exe` from **Releases** and run it. FFmpeg is included, nothing else needs to be installed.

From source (Python 3.10+), `ffmpeg` must be in the system path or next to `main.py`:

```
pip install -r requirements.txt
python main.py
```

Build the executable yourself with `.\build.ps1` (bundles the `ffmpeg.exe` found in the path).

### Usage

1. Choose root folder, project name and shooting day at the top.
2. **Add source**: select a card or folder (searched for `CONTENTS/VIDEO` and `PRIVATE/AVCHD/BDMV/STREAM`).
3. Log the clips: set scene/shot/take, confirm with `→`.
4. **Start ingest**.

| Key | Action |
|---|---|
| `→` | Confirm clip with current scene/shot/take, next clip, take +1 |
| `S` | Next scene (shot and take reset to 1) |
| `E` | Next shot (take resets to 1) |
| `T` | Take +1 |
| `↑` / `↓` | Select clip |
| `Del` / `Backspace` | Toggle transfer |
| `Enter` / `Esc` | Leave a text field (hotkeys are paused while typing) |

### Output modes (Settings)

| Mode | Result |
|---|---|
| 1:1 copy | Camera files renamed, P2 card structure kept. Timecode for Resolve via `Resolve_Timecode_Import.csv` |
| 1:1 copy + MOV | Additionally one `.mov` per eye in `SCHNITT/` |
| MOV only | Only `.mov` files (saves space, no 1:1 copy of the camera files) |

The MOV contains picture and audio rewrapped without re-encoding, plus a timecode track.
Background: Resolve shows timecode `00:00:00:00` for both cameras. With the 3DP1 this happens as soon as Resolve links the video MXF with its separate audio MXFs (also on untouched cards). The 3DA1 stores timecode only inside the H.264 stream.

**Importing the CSV in Resolve** (1:1 mode): add the clips to the Media Pool, then `File → Import Metadata To → Media Pool`, select the CSV, *Match using: File Name*.

### Folder structure

```
<root>/<project>/
  Tag_01/                  (or Szene_01, see settings)
    LINKS/   RECHTS/       left / right eye
    SCHNITT/               MOV files in mode "1:1 copy + MOV"
  ingest_manifest.json
  Resolve_Timecode_Import.csv
  Report_<project>_<date>.html, Transfer_<date>.mhl   (with verification)
```

Settings are stored in `%APPDATA%\3DCam2Post\ingest_config.json`, the log file next to it.

### License

GPL-3.0, see [LICENSE](LICENSE). Bundled third-party components are listed in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

---

<a id="deutsch"></a>
## Deutsch

Ingest-Tool für die Panasonic-Stereo-3D-Camcorder **AG-3DP1** (P2, MXF) und **AG-3DA1** (AVCHD, MTS): kopiert beide Augen von den Karten, benennt sie nach Szene/Einstellung/Take um und bereitet sie für DaVinci Resolve vor.

Ich habe es für meinen eigenen Workflow gebaut. Mit diesen Kameras dreht heute kaum noch jemand in 3D, aber wer noch damit arbeitet oder altes Material retten muss, kann es vielleicht brauchen.

### Funktionen

- Ordnet linkes und rechtes Auge automatisch zu (P2 über die Clip-UMID, AVCHD über Aufnahmezeit und Timecode)
- Loggen per Hotkeys, Umbenennung nach `Projekt_S01_E02_T003_L`
- Kopieren mit Fortschritt, optional Prüfsummen-Verifizierung (MD5, xxHash, SHA-256) mit MHL- und HTML-Report
- Verlustfreie MOV-Ausgabe mit Timecode und Ton, die Resolve ohne Zusatzschritt liest
- Timecode-CSV für Resolve bei 1:1-Kopie der Kameradateien
- Manifest pro Projekt: bereits kopierte Clips werden erkannt, ein fehlendes Auge kann später ergänzt werden
- Prüfungen vor dem Start: freier Speicher, vorhandene Dateien, doppelte Namen

### Installation

`3DCam2Post.exe` unter **Releases** herunterladen und starten. FFmpeg ist enthalten, sonst muss nichts installiert werden.

Aus dem Quellcode (Python 3.10+) muss `ffmpeg` im Systempfad oder neben `main.py` liegen:

```
pip install -r requirements.txt
python main.py
```

Die EXE selbst bauen: `.\build.ps1` (packt das `ffmpeg.exe` aus dem Systempfad mit ein).

### Bedienung

1. Oben Stammordner, Projektname und Drehtag festlegen.
2. **Quelle hinzufügen**: Karte oder Ordner wählen (gesucht wird nach `CONTENTS/VIDEO` und `PRIVATE/AVCHD/BDMV/STREAM`).
3. Clips loggen: Szene/Einstellung/Take setzen, mit `→` bestätigen.
4. **Ingest starten**.

| Taste | Aktion |
|---|---|
| `→` | Clip mit aktueller Szene/Einst./Take bestätigen, nächster Clip, Take +1 |
| `S` | Nächste Szene (Einst. und Take auf 1) |
| `E` | Nächste Einstellung (Take auf 1) |
| `T` | Take +1 |
| `↑` / `↓` | Clip wählen |
| `Entf` / `Backspace` | Transfer an/aus |
| `Enter` / `Esc` | Textfeld verlassen (beim Tippen sind die Hotkeys pausiert) |

### Ausgabe-Modi (Einstellungen)

| Modus | Ergebnis |
|---|---|
| 1:1-Kopie | Kameradateien umbenannt, P2-Kartenstruktur bleibt erhalten. Timecode für Resolve über `Resolve_Timecode_Import.csv` |
| 1:1-Kopie + MOV | Zusätzlich pro Auge eine `.mov` in `SCHNITT/` |
| Nur MOV | Nur `.mov`-Dateien (spart Platz, keine 1:1-Kopie der Kameradateien) |

Die MOV enthält Bild und Ton ohne Neukodierung umverpackt, dazu eine Timecode-Spur.
Hintergrund: Resolve zeigt bei beiden Kameras Timecode `00:00:00:00`. Bei der 3DP1 passiert das, sobald Resolve die Video-MXF mit den separaten Ton-MXFs verknüpft (auch bei unveränderten Karten). Die 3DA1 speichert den Timecode nur im H.264-Datenstrom.

**CSV in Resolve importieren** (1:1-Modus): Clips in den Media Pool legen, dann `File → Import Metadata To → Media Pool`, CSV wählen, *Match using: File Name*.

### Ordnerstruktur

```
<Stammordner>/<Projekt>/
  Tag_01/                  (oder Szene_01, siehe Einstellungen)
    LINKS/   RECHTS/       linkes / rechtes Auge
    SCHNITT/               MOV-Dateien im Modus „1:1-Kopie + MOV“
  ingest_manifest.json
  Resolve_Timecode_Import.csv
  Report_<Projekt>_<Datum>.html, Transfer_<Datum>.mhl   (mit Verifizierung)
```

Die Einstellungen liegen unter `%APPDATA%\3DCam2Post\ingest_config.json`, die Logdatei daneben.

### Lizenz

GPL-3.0, siehe [LICENSE](LICENSE). Mitgelieferte Fremdkomponenten stehen in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
