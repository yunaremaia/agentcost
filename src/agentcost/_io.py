"""Shared text-file reading helpers for the log parsers.

The parser contract is *decode and count*: a log that cannot be read with full
fidelity must still contribute whatever usages can be recovered, and must say
so. A log that contributes zero usages without saying why is the defect #185
describes, so a read always reports the reason it was not faithful.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

_UTF16_BOMS = (b"\xff\xfe", b"\xfe\xff")

# How many bytes to inspect when sniffing the encoding.
_SNIFF_BYTES = 4096

# A NUL is expected on every other byte of UTF-16 ASCII text; binary data does
# not have that shape, so a low ratio means the guess was wrong.
_UTF16_NUL_RATIO = 0.3


@dataclass(frozen=True)
class ReadResult:
    """The outcome of reading a log file.

    ``lines`` is always populated -- decoding never fails outright, because
    latin-1 maps every byte value -- so callers can parse whatever was
    recovered. ``warning`` is set when the file could not be read faithfully,
    which is what the parsers surface instead of vanishing quietly.
    ``recoverable`` is False only when the bytes are not text at all, so
    ``lines`` is meaningless; that is the case a strict parse must fail on.
    """

    lines: List[str]
    encoding: str
    warning: Optional[str] = None
    recoverable: bool = True


def _sniff_utf16(head: bytes) -> Optional[str]:
    """Return the UTF-16 variant implied by the leading bytes, if any.

    A BOM means "utf-16". Without one, JSON logs start with an ASCII character,
    so UTF-16 text begins with that character plus a NUL. The utf-8 attempt
    would succeed on those NUL bytes and give mojibake, so such files are tried
    as UTF-16 first (#185).

    The whole sample is inspected, not just the first two bytes: a two-byte
    test calls arbitrary binary data UTF-16, and that then "decodes" without
    error and gets reported as a faithful read.
    """
    if head[:2] in _UTF16_BOMS:
        return "utf-16"

    # BOM-less: UTF-16-LE of ASCII text puts a NUL on every odd byte.
    odd = head[1::2]
    if len(head) >= 2 and head[0] != 0 and odd.count(0) > len(odd) * _UTF16_NUL_RATIO:
        return "utf-16-le"
    # UTF-16-BE of ASCII text puts a NUL on every even byte.
    even = head[0::2]
    if len(head) >= 2 and head[1] != 0 and even.count(0) > len(even) * _UTF16_NUL_RATIO:
        return "utf-16-be"
    return None


def _looks_binary(head: bytes) -> bool:
    """True when the bytes do not look like text.

    A NUL byte is the giveaway: no JSONL log contains one -- a NUL inside a
    JSON string is written as the six characters ``\\u0000`` -- and latin-1
    would otherwise turn a binary file into mojibake that parses to nothing.
    """
    return b"\x00" in head


def _read_lines_with_fallback(log_path: Path) -> ReadResult:
    """Read a text log, recovering the best decoding available.

    Never raises for encoding reasons and never discards data: unusable bytes
    come back as recovered lines plus a ``warning``, so the caller can count
    what it can and report the rest. ``FileNotFoundError`` and other OSErrors
    propagate to the caller.
    """
    with open(log_path, "rb") as f:
        head = f.read(_SNIFF_BYTES)

    if not head:
        return ReadResult(lines=[], encoding="utf-8")

    utf16 = _sniff_utf16(head)
    if utf16 is not None:
        try:
            with open(log_path, encoding=utf16) as f:
                lines = f.readlines()
        except (UnicodeDecodeError, UnicodeError):
            # A NUL pattern that is not really UTF-16: fall through.
            pass
        else:
            # Binary data can decode without error under a UTF-16 codec. Real
            # UTF-16 text carries no NUL, so this rejects the guess instead of
            # reporting mojibake as a faithful read. Only the first few lines
            # are inspected: a log that is not text fails on the first one.
            if not any("\x00" in line for line in lines[:8]):
                return ReadResult(lines=lines, encoding=utf16)

    if _looks_binary(head):
        # Not text at all. A raw NUL byte cannot occur in a JSONL log -- a NUL
        # inside a JSON string is written as the six characters ``\u0000`` --
        # and these bytes are still valid UTF-8, so checking this before the
        # utf-8 attempt is what stops a binary file from being accepted as a
        # faithful read of NUL-filled mojibake that parses to nothing.
        return ReadResult(
            lines=[],
            encoding="none",
            warning=(
                f"Not read faithfully, {log_path} is not text: the file "
                f"contains NUL bytes, so it is not a JSONL log and its "
                f"entries cannot be recovered"
            ),
            recoverable=False,
        )

    try:
        with open(log_path, encoding="utf-8") as f:
            return ReadResult(lines=f.readlines(), encoding="utf-8")
    except UnicodeError:
        pass

    # latin-1 is the last resort: it maps every byte value to a code point, so
    # it cannot fail to decode and the line structure survives.
    with open(log_path, encoding="latin-1") as f:
        return ReadResult(
            lines=f.readlines(),
            encoding="latin-1",
            warning=(
                f"Not read faithfully, {log_path} is not valid UTF-8: "
                f"decoded as latin-1, so entries may be missing"
            ),
        )