"""Shared text-file reading helpers for the log parsers."""

from pathlib import Path
from typing import List, Optional

# Logs are normally UTF-8; UTF-16 and latin-1 are fallbacks for odd exports.
_ENCODINGS = ("utf-8", "utf-16", "latin-1")


def _read_lines_with_fallback(log_path: Path) -> Optional[List[str]]:
    """Read a text log, retrying with fallback encodings.

    Returns the lines, or None if no encoding could decode the file.
    FileNotFoundError and other OSErrors propagate to the caller.
    """
    for encoding in _ENCODINGS:
        try:
            with open(log_path, encoding=encoding) as f:
                return f.readlines()
        except UnicodeDecodeError:
            continue
    return None
