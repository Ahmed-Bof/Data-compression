"""
binary_format.py - the "LZ77 Binary" file format (a real binary file).

Layout (all numbers big-endian):

    bytes 0-6    magic  b"LZ77BIN"
    byte  7      format version (1)
    bytes 8-15   original size in bytes        (unsigned 64-bit)
    bytes 16-19  CRC-32 of the original data   (unsigned 32-bit)
    bytes 20-    the tokens, packed as a bit stream (MSB first)

Token encoding:

    literal (position 0, length 0)   0 | next_symbol(8)                      =  9 bits
    match                            1 | position(12) | length(4) | next_symbol(8) = 25 bits

The last byte is padded with zero bits. The decoder knows exactly when to stop
because the header holds the original size, so padding is never mistaken for
data.
"""

import struct

from lz77 import LZ77Error, Token

MAGIC = b"LZ77BIN"
VERSION = 1

_HEADER = struct.Struct(">7sBQI")
HEADER_SIZE = _HEADER.size

POSITION_BITS = 12
LENGTH_BITS = 4
SYMBOL_BITS = 8


# ---------------------------------------------------------------------------
# Bit-level helpers
# ---------------------------------------------------------------------------
class BitWriter:
    """Collects bits (most significant bit first) and returns them as bytes."""

    def __init__(self):
        self._bytes = bytearray()
        self._pending = 0         # bits that do not fill a whole byte yet
        self._pending_count = 0   # how many bits are in _pending (always < 8)

    def write(self, value, bit_count):
        if value < 0 or value >= (1 << bit_count):
            raise ValueError("%d does not fit in %d bits" % (value, bit_count))
        self._pending = (self._pending << bit_count) | value
        self._pending_count += bit_count
        while self._pending_count >= 8:
            self._pending_count -= 8
            self._bytes.append((self._pending >> self._pending_count) & 0xFF)
        self._pending &= (1 << self._pending_count) - 1

    def to_bytes(self):
        result = bytearray(self._bytes)
        if self._pending_count > 0:   # pad the last byte with zero bits
            result.append((self._pending << (8 - self._pending_count)) & 0xFF)
        return bytes(result)


class BitReader:
    """Reads bits (most significant bit first) from a bytes object."""

    def __init__(self, data):
        self._data = data
        self._position = 0                 # position in BITS
        self._total_bits = len(data) * 8

    def bits_left(self):
        return self._total_bits - self._position

    def read(self, bit_count):
        if bit_count > self.bits_left():
            raise LZ77Error("Invalid compressed file: the data ends too early.")
        first_byte = self._position >> 3
        last_byte = (self._position + bit_count - 1) >> 3
        chunk = int.from_bytes(self._data[first_byte:last_byte + 1], "big")
        unused_low_bits = (last_byte + 1) * 8 - (self._position + bit_count)
        self._position += bit_count
        return (chunk >> unused_low_bits) & ((1 << bit_count) - 1)


# ---------------------------------------------------------------------------
# Whole files
# ---------------------------------------------------------------------------
def dumps(tokens, original_size, crc32):
    """Build the bytes of a binary compressed file."""
    writer = BitWriter()
    for position, length, symbol in tokens:
        if length == 0:
            writer.write(0, 1)
            writer.write(symbol, SYMBOL_BITS)
        else:
            writer.write(1, 1)
            writer.write(position, POSITION_BITS)
            writer.write(length, LENGTH_BITS)
            writer.write(symbol, SYMBOL_BITS)
    header = _HEADER.pack(MAGIC, VERSION, original_size, crc32)
    return header + writer.to_bytes()


def is_binary_file(data):
    return data.startswith(MAGIC)


def loads(data):
    """Parse binary-file bytes -> (tokens, original_size, crc32)."""
    if len(data) < HEADER_SIZE or not is_binary_file(data):
        raise LZ77Error("Invalid compressed file: bad binary header.")
    magic, version, original_size, crc32 = _HEADER.unpack_from(data)
    if version != VERSION:
        raise LZ77Error("Unsupported binary-file version: %d." % version)

    reader = BitReader(data[HEADER_SIZE:])
    tokens = []
    produced = 0                       # bytes the tokens rebuild so far

    while produced < original_size:
        if reader.read(1) == 0:
            tokens.append(Token(0, 0, reader.read(SYMBOL_BITS)))
            produced += 1
        else:
            position = reader.read(POSITION_BITS)
            length = reader.read(LENGTH_BITS)
            symbol = reader.read(SYMBOL_BITS)
            tokens.append(Token(position, length, symbol))
            produced += length + 1

    if produced != original_size:
        raise LZ77Error("Invalid compressed file: the tokens rebuild more "
                        "data than the header says.")
    if reader.bits_left() >= 8:
        raise LZ77Error("Invalid compressed file: unexpected extra data "
                        "after the last token.")
    return tokens, original_size, crc32
