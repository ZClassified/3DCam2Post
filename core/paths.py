import os
import sys
import hashlib
import tempfile
from pathlib import Path

APP_NAME = "3DCam2Post"
CONFIG_FILE = "ingest_config.json"


def app_base_dir() -> Path:
    """Directory holding bundled resources (PyInstaller temp dir or project root)."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def exe_dir() -> Path:
    """Directory of the running executable (or project root when run from source)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def resource_path(relative_path) -> Path:
    for base in (exe_dir(), app_base_dir()):
        for sub in ("", "assets", "ui"):
            p = base / sub / relative_path
            if p.exists():
                return p
    return app_base_dir() / relative_path


def user_data_dir() -> Path:
    """Writable per-user directory for config and logs (survives EXE restarts)."""
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA") or Path.home())
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    d = base / APP_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def config_path() -> Path:
    return user_data_dir() / CONFIG_FILE


def legacy_config_paths():
    """Old config locations (next to the app), used once for migration."""
    seen = set()
    for base in (exe_dir(), app_base_dir()):
        p = base / CONFIG_FILE
        if p not in seen:
            seen.add(p)
            yield p


def thumb_dir() -> Path:
    d = Path(tempfile.gettempdir()) / "3D_Ingest_Thumbs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def file_key(path) -> str:
    """Stable short key for a concrete file (path + size + mtime), used for thumbnail caching."""
    p = Path(path)
    try:
        st = p.stat()
        raw = f"{p.resolve()}|{st.st_size}|{st.st_mtime_ns}"
    except OSError:
        raw = str(p)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
