"""Where PlacePilot AI keeps the files it writes: the SQLite database, the trained readiness
model, its training CSV and the session key.

Normally that is the data/ folder next to the code. Some hosts (Vercel and other serverless
platforms) do not let an app write to its own folder, so there the app falls back to the
system temp folder. Temp storage is wiped whenever the host restarts the app, which means the
site returns to the sample data. EPHEMERAL is True in that case and the page says so.

Set PLACEPILOT_DATA_DIR to choose the folder yourself, for example a mounted persistent disk.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write-test"
        probe.write_text("ok")
        probe.unlink()
        return True
    except OSError:
        return False


def _choose() -> tuple[Path, bool]:
    chosen = os.environ.get("PLACEPILOT_DATA_DIR")
    if chosen:
        path = Path(chosen).expanduser().resolve()
        if not _writable(path):
            raise RuntimeError(f"PLACEPILOT_DATA_DIR is not writable: {path}")
        return path, False
    local = BASE_DIR / "data"
    if not os.environ.get("VERCEL") and _writable(local):
        return local, False
    temp = Path(tempfile.gettempdir()) / "placepilot"
    temp.mkdir(parents=True, exist_ok=True)
    return temp, True


DATA_DIR, EPHEMERAL = _choose()
