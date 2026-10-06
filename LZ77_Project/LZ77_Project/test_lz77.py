"""
test_lz77.py - run with:   python test_lz77.py
Tests every workflow on disk, exactly like the application does it.
"""

import os
import random
import tempfile
import unittest

import binary_format
import tag_format
from compressor import compress_bytes, compress_file
from decompressor import (FORMAT_BINARY, FORMAT_TAGS, decompress_bytes,
                          decompress_file, detect_format, rebuild)
from lz77 import LZ77Error, Token, tokenize

SAMPLES = {
    "ABCDEF": b"ABCDEF",
    "AAAAAA": b"AAAAAA",
    "ABAABAABAABA": b"ABAABAABAABA",
    "ABAABAABAABAABA": b"ABAABAABAABAABA",
    "ABCABCABCABC": b"ABCABCABCABC",
    "HELLOHELLOHELLO": b"HELLOHELLOHELLO",
    "Hello Hello Hello": b"Hello Hello Hello",
    "A": b"A",
    "empty": b"",
    "comma": b",",
    "greater-than": b">",
    "less-than": b"<",
    "backslash": b"\\",
    "spaces": b"   a   b   ",
    "tabs": b"\t\ta\t\tb\t",
    "newlines": b"\n\n\nline\n\n",
    "carriage returns": b"\r\r\rx\r\r",
    "CRLF": b"line1\r\nline2\r\nline1\r\nline2\r\n",
    "tag lookalike": b"<1, 2, A>,<1, 2, A>\\n\\x41>>,,<<",
    "backslash runs": b"\\\\\\\\\\\\\\n\\n\\x41\\x41",
    "unicode": "héllo wörld ✓ héllo wörld ✓ 你好 你好 你好".encode("utf-8"),
    "NUL and control": b"\x00\x00\x00\x01\x02\x00\x00\x00\x01\x02\x0b\x0c\x1c\x85",
    "all bytes": bytes(range(256)) * 3,
    "long run": b"A" * 10000,
    "long repeat": b"ABC" * 5000,
}


class Base(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)

    def path(self, name):
        return os.path.join(self.folder.name, name)

    def write(self, name, data):
        with open(self.path(name), "wb") as handle:
            handle.write(data)
        return self.path(name)

    def read(self, path):
        with open(path, "rb") as handle:
            return handle.read()


class Workflows(Base):
    def test_workflow_1_and_3_txt_to_tags_to_txt(self):
        for name, data in SAMPLES.items():
            with self.subTest(name):
                source = self.write("in.txt", data)
                tags = self.path("out.tags.txt")
                compress_file(source, tags, FORMAT_TAGS)       # workflow 1 (compress)
                self.assertEqual(detect_format(self.read(tags)), FORMAT_TAGS)
                restored = self.path("back.txt")
                decompress_file(tags, restored)                # workflow 3
                self.assertEqual(self.read(restored), data)

    def test_workflow_2_and_4_txt_to_binary_to_txt(self):
        for name, data in SAMPLES.items():
            with self.subTest(name):
                source = self.write("in.txt", data)
                packed = self.path("out.lz77")
                compress_file(source, packed, FORMAT_BINARY)   # workflow 2 (compress)
                self.assertEqual(detect_format(self.read(packed)), FORMAT_BINARY)
                restored = self.path("back.txt")
                decompress_file(packed, restored)              # workflow 4
                self.assertEqual(self.read(restored), data)

    def test_detection_does_not_depend_on_extension(self):
        data = b"ABCABCABCABC hello hello"
        source = self.write("in.txt", data)
        for fmt in (FORMAT_TAGS, FORMAT_BINARY):
            out = self.path("weird_name.dat")
            compress_file(source, out, fmt)
            restored = self.path("r.bin")
            result = decompress_file(out, restored)
            self.assertEqual(result.detected_format, fmt)
            self.assertEqual(self.read(restored), data)

    def test_random_data(self):
        rng = random.Random(1234)
        for trial in range(200):
            alphabet = rng.choice([b"AB", b"ABC", b"ab ,>\\\n\r\t", bytes(range(256))])
            data = bytes(rng.choice(alphabet) for _ in range(rng.randint(0, 400)))
            for fmt in (FORMAT_TAGS, FORMAT_BINARY):
                compressed, _ = compress_bytes(data, fmt)
                self.assertEqual(decompress_bytes(compressed), data)

    def test_window_boundary(self):
        rng = random.Random(7)
        block = bytes(rng.randrange(256) for _ in range(4094))
        data = block + b"XYZ" + block + b"XYZ" + block[:100]
        for fmt in (FORMAT_TAGS, FORMAT_BINARY):
            compressed, _ = compress_bytes(data, fmt)
            self.assertEqual(decompress_bytes(compressed), data)


class Algorithm(unittest.TestCase):
    def test_uses_real_matches_and_overlap(self):
        tokens = tokenize(b"AAAAAA")
        self.assertEqual(tokens, [Token(0, 0, 65), Token(1, 4, 65)])  # length 4 > position 1
        tokens = tokenize(b"ABAABAABAABAABA")
        self.assertTrue(any(t.length > t.position > 0 for t in tokens)
                        or any(t.length >= 3 for t in tokens))
        self.assertLess(len(tokens), 15)

    def test_repeated_sequences_compress(self):
        data = b"ABC" * 1000
        compressed, _ = compress_bytes(data, FORMAT_BINARY)
        self.assertLess(len(compressed), len(data) // 4)

    def test_every_token_has_next_symbol_and_valid_limits(self):
        rng = random.Random(5)
        data = bytes(rng.choice(b"ab") for _ in range(5000))
        tokens = tokenize(data)
        self.assertEqual(sum(t.length + 1 for t in tokens), len(data))
        for t in tokens:
            self.assertTrue(0 <= t.position <= 4095 and 0 <= t.length <= 15)

    def test_overlapping_decode_is_byte_by_byte(self):
        self.assertEqual(rebuild([Token(0, 0, 65), Token(1, 5, 66)], 7), b"AAAAAAB")
        self.assertEqual(rebuild([Token(0, 0, 65), Token(0, 0, 66), Token(2, 7, 67)], 10),
                         b"ABABABABAC")


class Formats(unittest.TestCase):
    def test_tag_symbols_round_trip(self):
        for value in range(256):
            text = tag_format.format_symbol(value)
            self.assertNotIn(text, ("", None))
            self.assertTrue(all(c not in text for c in " ,<>\n\r\t"))
            self.assertEqual(tag_format.parse_symbol(text), value)

    def test_tag_file_looks_like_tags(self):
        data, _ = compress_bytes(b"ABAABAABAABAABA", FORMAT_TAGS)
        lines = data.decode("ascii").splitlines()
        self.assertTrue(lines[0].startswith("LZ77-TAGS"))
        for line in lines[1:]:
            self.assertRegex(line, r"^<\d+, \d+, [^\s<>,]+>$")

    def test_binary_is_really_binary_not_text_of_bits(self):
        data, _ = compress_bytes(b"ABCABCABCABC" * 50, FORMAT_BINARY)
        self.assertTrue(data.startswith(b"LZ77BIN"))
        self.assertNotEqual(set(data[binary_format.HEADER_SIZE:]) <= set(b"01\n"), True)
        self.assertLess(len(data), 600)

    def test_bitwriter_reader(self):
        writer = binary_format.BitWriter()
        values = [(1, 1), (4095, 12), (15, 4), (200, 8), (0, 1), (7, 3)]
        for value, bits in values:
            writer.write(value, bits)
        reader = binary_format.BitReader(writer.to_bytes())
        for value, bits in values:
            self.assertEqual(reader.read(bits), value)


class BadFiles(Base):
    def test_invalid_inputs_raise_friendly_errors(self):
        good_tags, _ = compress_bytes(b"hello hello hello", FORMAT_TAGS)
        good_bin, _ = compress_bytes(b"hello hello hello", FORMAT_BINARY)
        bad = {
            "random text": b"just some normal text",
            "empty file": b"",
            "bad tag": good_tags + b"<1, 2>\n",
            "bad symbol": good_tags.replace(b"<0, 0, h>", b"<0, 0, hh>"),
            "truncated tags": good_tags[:-20],
            "tampered tags": good_tags.replace(b"<0, 0, h>", b"<0, 0, j>"),
            "truncated binary": good_bin[:-3],
            "extra binary": good_bin + b"\x00\x00",
            "short header": b"LZ77BIN\x01",
            "bad version": b"LZ77BIN\x09" + good_bin[8:],
            "tampered binary": good_bin[:-1] + bytes([good_bin[-1] ^ 0xFF]),
            "non-ascii tags": b"LZ77-TAGS 1 size=1 crc32=00000000\n\xff",
        }
        for name, data in bad.items():
            with self.subTest(name):
                with self.assertRaises(LZ77Error):
                    decompress_bytes(data)

    def test_bad_positions_rejected(self):
        with self.assertRaises(LZ77Error):
            rebuild([Token(5, 3, 65)], 10)           # points before the start
        with self.assertRaises(LZ77Error):
            rebuild([Token(3, 0, 65)], 10)           # position without length

    def test_missing_input_file(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(LZ77Error):
                decompress_file(os.path.join(folder, "nope.lz77"),
                                os.path.join(folder, "out.txt"))
            with self.assertRaises(LZ77Error):
                compress_file(os.path.join(folder, "nope.txt"),
                              os.path.join(folder, "out.txt"), FORMAT_TAGS)

    def test_bad_output_folder_and_no_partial_output(self):
        source = self.write("in.txt", b"abc")
        with self.assertRaises(LZ77Error):
            compress_file(source, os.path.join(self.folder.name, "missing", "o.txt"),
                          FORMAT_TAGS)
        bad = self.write("bad.lz77", b"not a compressed file")
        target = self.path("should_not_exist.txt")
        with self.assertRaises(LZ77Error):
            decompress_file(bad, target)
        self.assertFalse(os.path.exists(target))

    def test_does_not_leave_temp_files(self):
        source = self.write("in.txt", b"abc abc abc")
        compress_file(source, self.path("o.lz77"), FORMAT_BINARY)
        self.assertFalse([n for n in os.listdir(self.folder.name) if n.endswith(".tmp")])


if __name__ == "__main__":
    unittest.main(verbosity=1)
