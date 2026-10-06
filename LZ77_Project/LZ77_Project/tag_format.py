"""
tag_format.py - the "LZ77 Text Tags" file format.

The file is plain ASCII text:

    LZ77-TAGS 1 size=<original byte count> crc32=<8 hex digits>
    <position, length, symbol>
    <position, length, symbol>
    ...

The first line is the header: it identifies the format (so the decompressor
never has to guess) and stores the original size and CRC-32 so the result can
be verified.

The symbol is always written in a way that can NOT contain a space, comma,
'<', '>' or a line break, so every tag can be parsed unambiguously:

    printable ASCII except space , < > \\     -> the character itself
    backslash                                  -> \\\\
    newline / carriage return / tab / NUL      -> \\n  \\r  \\t  \\0
    anything else (space, , < >, non-ASCII...) -> \\xHH  (two hex digits)

Non-ASCII characters are written byte by byte (UTF-8 bytes), so Unicode text
is restored exactly.
"""

import re

from lz77 import LZ77Error, Token

MAGIC = b"LZ77-TAGS"
VERSION = 1

_HEADER_RE = re.compile(r"^LZ77-TAGS (\d+) size=(\d+) crc32=([0-9A-Fa-f]{8})$")
_TAG_RE = re.compile(r"^<\s*(\d+)\s*,\s*(\d+)\s*,\s*([^\s<>,]+)\s*>$")
_HEX_ESCAPE_RE = re.compile(r"^\\x([0-9A-Fa-f]{2})$")

_SHORT_ESCAPES = {10: r"\n", 13: r"\r", 9: r"\t", 0: r"\0", 92: r"\\"}
_SHORT_UNESCAPES = {value: key for key, value in _SHORT_ESCAPES.items()}


# ---------------------------------------------------------------------------
# Symbols
# ---------------------------------------------------------------------------
def format_symbol(byte_value):
    """Byte (0..255) -> unambiguous text for one tag."""
    if byte_value in _SHORT_ESCAPES:
        return _SHORT_ESCAPES[byte_value]
    if 33 <= byte_value <= 126 and byte_value not in (44, 60, 62):  # , < >
        return chr(byte_value)
    return "\\x%02X" % byte_value


def parse_symbol(text):
    """Inverse of format_symbol(). Raises LZ77Error on anything else."""
    if text in _SHORT_UNESCAPES:
        return _SHORT_UNESCAPES[text]
    hex_match = _HEX_ESCAPE_RE.match(text)
    if hex_match:
        return int(hex_match.group(1), 16)
    if len(text) == 1 and 33 <= ord(text) <= 126 and text not in "\\,<>":
        return ord(text)
    raise LZ77Error("Unable to parse token symbol: %r" % text)


# ---------------------------------------------------------------------------
# Whole files
# ---------------------------------------------------------------------------
def dumps(tokens, original_size, crc32):
    """Build the text of a tag file (returned as ASCII bytes)."""
    lines = ["LZ77-TAGS %d size=%d crc32=%08X" % (VERSION, original_size, crc32)]
    for position, length, symbol in tokens:
        lines.append("<%d, %d, %s>" % (position, length, format_symbol(symbol)))
    return ("\n".join(lines) + "\n").encode("ascii")


def is_tag_file(data):
    return _strip_bom(data).startswith(MAGIC)


def loads(data):
    """Parse tag-file bytes -> (tokens, original_size, crc32)."""
    try:
        text = _strip_bom(data).decode("ascii")
    except UnicodeDecodeError:
        raise LZ77Error("Invalid compressed file: a tag file must be plain "
                        "ASCII text.") from None

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        raise LZ77Error("Invalid compressed file: the tag file is empty.")

    header = _HEADER_RE.match(lines[0])
    if not header:
        raise LZ77Error("Invalid compressed file: bad tag-file header.")
    if int(header.group(1)) != VERSION:
        raise LZ77Error("Unsupported tag-file version: %s." % header.group(1))
    original_size = int(header.group(2))
    crc32 = int(header.group(3), 16)

    tokens = []
    for line_number, line in enumerate(lines[1:], start=2):
        tag = _TAG_RE.match(line)
        if not tag:
            raise LZ77Error("Unable to parse token on line %d: %r"
                            % (line_number, line[:60]))
        try:
            symbol = parse_symbol(tag.group(3))
        except LZ77Error as error:
            raise LZ77Error("%s (line %d)" % (error, line_number)) from None
        tokens.append(Token(int(tag.group(1)), int(tag.group(2)), symbol))

    return tokens, original_size, crc32


def _strip_bom(data):
    return data[3:] if data.startswith(b"\xef\xbb\xbf") else data
