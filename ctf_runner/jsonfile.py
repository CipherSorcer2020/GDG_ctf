"""Tiny helper: mtime-cached reads and atomic writes of one JSON file.

Why: the web app reads ``event.json`` / ``lobby.json`` on every request, and
many players poll at once.  Re-parsing an unchanged file each time is wasted
work, and a crash in the middle of a plain ``write_text`` can leave a
half-written (corrupt) file.  This class

* re-reads the file only when its modification stamp changed, and
* writes through a temp file + ``os.replace`` so readers never see a torn file.
"""

from __future__ import annotations

import copy
import json
import os
import threading
import time
from pathlib import Path
from typing import Any


class JsonFile:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.lock = threading.RLock()
        self._stamp: tuple[int, int] | None = None
        self._data: Any = None

    def read(self) -> Any:
        """Parsed JSON (a private copy). Raises FileNotFoundError / JSONDecodeError."""
        with self.lock:
            st = self.path.stat()  # FileNotFoundError propagates
            stamp = (st.st_mtime_ns, st.st_size)
            if stamp != self._stamp:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
                self._stamp = stamp
            return copy.deepcopy(self._data)

    def write(self, data: Any) -> None:
        text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
        with self.lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_name(self.path.name + ".tmp")
            tmp.write_text(text, encoding="utf-8")
            # On Windows an antivirus / editor can briefly lock the target.
            for attempt in range(5):
                try:
                    os.replace(tmp, self.path)
                    break
                except PermissionError:
                    if attempt == 4:
                        raise
                    time.sleep(0.05 * (attempt + 1))
            st = self.path.stat()
            self._stamp = (st.st_mtime_ns, st.st_size)
            self._data = copy.deepcopy(data)
