"""
compressor.py - compresses data into one of the two output formats.

    FORMAT_TAGS    readable text file of <position, length, symbol> tags
    FORMAT_BINARY  real binary file (bit-packed tokens)

Both formats are built from the SAME token list produced by lz77.tokenize().
"""

import zlib
from dataclasses import dataclass

import binary_format
import file_utils
import tag_format
from decompressor import FORMAT_BINARY, FORMAT_TAGS, decompress_bytes
from lz77 import LZ77Error, tokenize


@dataclass
class CompressResult:
    output_format: str
    original_size: int
    compressed_size: int
    token_count: int
    verified: bool


def compress_bytes(data, output_format):
    """Compress bytes into the chosen format. Returns (compressed, token_count)."""
    data = bytes(data)
    tokens = tokenize(data)
    crc32 = zlib.crc32(data) & 0xFFFFFFFF

    if output_format == FORMAT_TAGS:
        return tag_format.dumps(tokens, len(data), crc32), len(tokens)
    if output_format == FORMAT_BINARY:
        return binary_format.dumps(tokens, len(data), crc32), len(tokens)
    raise LZ77Error("Unknown output format: %r" % (output_format,))


def compress_file(input_path, output_path, output_format, verify=True):
    """
    Compress a file. With verify=True the result is decompressed again and
    compared byte-for-byte with the original BEFORE it is written, and the
    written file is read back and compared once more afterwards.
    """
    data = file_utils.read_bytes(input_path)
    compressed, token_count = compress_bytes(data, output_format)

    if verify:
        _check_identical(data, decompress_bytes(compressed))

    file_utils.write_bytes(output_path, compressed)

    if verify:
        _check_identical(data, decompress_bytes(file_utils.read_bytes(output_path)))

    return CompressResult(output_format, len(data), len(compressed),
                          token_count, verify)


def _check_identical(original, restored):
    if original != restored:
        raise LZ77Error("Lossless verification failed: the restored data is "
                        "not identical to the original.")
