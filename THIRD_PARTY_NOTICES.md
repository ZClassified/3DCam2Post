# Third-party components

3DCam2Post is licensed under the GNU General Public License v3.0 (see `LICENSE`).
The Windows executable bundles the following components:

| Component | License | Source |
|---|---|---|
| [FFmpeg](https://ffmpeg.org) (`ffmpeg.exe`, static build) | GPL-3.0-or-later (build configured with `--enable-gpl --enable-version3`) | https://ffmpeg.org/download.html — the exact source archive is attached to each release |
| [Flet](https://flet.dev) | Apache-2.0 | https://github.com/flet-dev/flet |
| [Flutter](https://flutter.dev) engine (part of the Flet desktop client) | BSD-3-Clause | https://github.com/flutter/flutter |
| [python-xxhash](https://github.com/ifduyue/python-xxhash) / [xxHash](https://github.com/Cyan4973/xxHash) | BSD-2-Clause | see links |
| [Python](https://www.python.org) runtime | PSF License | https://www.python.org |
| [PyInstaller](https://pyinstaller.org) bootloader | GPL-2.0 with bootloader exception | https://github.com/pyinstaller/pyinstaller |

FFmpeg is called as a separate program (`ffmpeg.exe`) and is not modified.
The release archive contains the FFmpeg license text (`licenses/FFmpeg-LICENSE.txt`) and the
FFmpeg source code of the bundled version.
