"""
decompressor.py - rebuilds the original data from LZ77 tokens.

The format (text tags or binary) is detected from the file's own signature, so
the user never has to say which one it is and nothing is guessed.
"""

import zlib
from dataclasses import dataclass

import binary_format
import file_utils
import tag_format
from lz77 import LZ77Error, MAX_MATCH_LENGTH, WINDOW_SIZE

FORMAT_TAGS = "tags"
FORMAT_BINARY = "binary"


@dataclass
class DecompressResult:
    detected_format: str
    compressed_size: int
    restored_size: int


def detect_format(data):
    """Look at the signature at the start of the file."""
    if binary_format.is_binary_file(data):
        return FORMAT_BINARY
    if tag_format.is_tag_file(data):
        return FORMAT_TAGS
    raise LZ77Error("Invalid compressed file: this is not an LZ77 Text Tags "
                    "file or an LZ77 Binary file.")


def rebuild(tokens, expected_size):
    """Tokens -> bytes. Validates every token before using it."""
    output = bytearray()

    for number, (position, length, symbol) in enumerate(tokens, start=1):
        if not 0 <= symbol <= 255:
            raise LZ77Error("Invalid token %d: bad next symbol." % number)

        if length == 0:
            if position != 0:
                raise LZ77Error("Invalid token %d: a token without a match "
                                "must have position 0." % number)
        else:
            if length > MAX_MATCH_LENGTH:
                raise LZ77Error("Invalid token %d: length %d is too large."
                                % (number, length))
            if position < 1 or position > WINDOW_SIZE or position > len(output):
                raise LZ77Error("Invalid token %d: position %d points outside "
                                "the data rebuilt so far." % (number, position))
            # Copy ONE byte at a time. When length > position the match
            # overlaps the bytes it is itself producing (e.g. AAAAAA), so each
            # new byte may be the source of the next one.
            for _ in range(length):
                output.append(output[-position])

        output.append(symbol)

        if len(output) > expected_size:
            raise LZ77Error("Invalid compressed file: the tokens rebuild more "
                            "data than the header says.")

    return bytes(output)


def decompress_bytes(data):
    """Decompress either format. Raises LZ77Error on any problem."""
    data = bytes(data)
    detected = detect_format(data)
    if detected == FORMAT_BINARY:
        tokens, expected_size, expected_crc = binary_format.loads(data)
    else:
        tokens, expected_size, expected_crc = tag_format.loads(data)

    restored = rebuild(tokens, expected_size)

    if len(restored) != expected_size:
        raise LZ77Error("Lossless verification failed: restored %d bytes but "
                        "expected %d." % (len(restored), expected_size))
    if zlib.crc32(restored) & 0xFFFFFFFF != expected_crc:
        raise LZ77Error("Lossless verification failed: the checksum of the "
                        "restored data does not match (corrupt file?).")
    return restored


def decompress_file(input_path, output_path):
    """Decompress a file; the output is written only if everything checks out."""
    data = file_utils.read_bytes(input_path)
    restored = decompress_bytes(data)
    file_utils.write_bytes(output_path, restored)
    return DecompressResult(detect_format(data), len(data), len(restored))
