"""Replace reports only after a complete JSON checkpoint has been written."""

import json
import os
import tempfile
import time
from pathlib import Path


def atomic_write_json(path, data):
    def write(stream):
        json.dump(data, stream, indent=2, allow_nan=False)
        stream.write("\n")
    _atomic_write(path, write)


def atomic_write_text(path, text):
    """Replace a text export atomically without platform newline translation."""
    _atomic_write(path, lambda stream: stream.write(text))


def _atomic_write(path, write):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                         dir=path.parent, prefix=f".{path.name}.",
                                         suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            write(stream)
            stream.flush()
            os.fsync(stream.fileno())
        for attempt in range(6):
            try:
                os.replace(temporary, path)
                if os.name == "posix" and hasattr(os, "O_DIRECTORY"):
                    directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
                    try:
                        os.fsync(directory_fd)
                    finally:
                        os.close(directory_fd)
                break
            except PermissionError as error:
                # Windows readers/AV scanners can briefly deny replacement.
                # Keep the old complete file and retry only those native errors.
                if getattr(error, "winerror", None) not in (5, 32, 33) or attempt == 5:
                    raise
                time.sleep(0.01 * 2 ** attempt)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
