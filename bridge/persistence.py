import json
import threading
from pathlib import Path

_lock = threading.Lock()


def load(path: Path, default):
    """Load JSON from path; return default if file missing or corrupt."""
    with _lock:
        try:
            return json.loads(path.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            return default


def save(path: Path, data) -> None:
    """Atomically write JSON to path (write to .tmp then rename)."""
    with _lock:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data))
        tmp.rename(path)
