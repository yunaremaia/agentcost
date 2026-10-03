"""Shared text-file reading helpers for the log parsers."""

from pathlib import Path
from typing import List, NamedTuple, Optional

_UTF16_BOMS = (b"\xff\xfe", b"\xfe\xff")


class ReadResult(NamedTuple):
    """Lines of a log file, and whether some bytes had to be replaced."""

    lines: List[str]
    lossy: bool = False


def _sniff_utf16(log_path: Path) -> Optional[str]:
    """Return the UTF-16 codec the file looks like it uses, or None.

    A BOM means "utf-16". Without one, JSON logs start with an ASCII character,
    so UTF-16 text begins with that character plus a NUL. The utf-8 attempt would
    succeed on those NUL bytes and give mojibake, so these files are tried as
    UTF-16 first.
    """
    with open(log_path, "rb") as f:
        head = f.read(2)
    if head in _UTF16_BOMS:
        return "utf-16"
    if len(head) == 2:
        if head[0] != 0 and head[1] == 0:
            return "utf-16-le"
        if head[0] == 0 and head[1] != 0:
            return "utf-16-be"
    return None


def _read_lines_with_fallback(log_path: Path) -> ReadResult:
    """Read a text log.

    UTF-16 is tried only when the file looks like UTF-16, then UTF-8. If neither
    works, the file is read as UTF-8 with the bytes it cannot decode replaced, and
    the result is marked lossy so the caller can warn. Replacing keeps the line
    structure, so lines that are still valid JSON are still counted.

    FileNotFoundError and other OSErrors propagate to the caller.
    """
    utf16 = _sniff_utf16(log_path)
    for encoding in (utf16, "utf-8") if utf16 else ("utf-8",):
        try:
            with open(log_path, encoding=encoding) as f:
                return ReadResult(f.readlines())
        except UnicodeError:
            continue
    with open(log_path, encoding="utf-8", errors="replace") as f:
        return ReadResult(f.readlines(), lossy=True)
