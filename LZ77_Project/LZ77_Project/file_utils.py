"""
file_utils.py - small, safe file helpers shared by the other modules.
"""

import os
import subprocess
import sys
import tempfile

from lz77 import LZ77Error

TAGS_SUFFIX = ".tags.txt"
BINARY_SUFFIX = ".lz77"
RESTORED_SUFFIX = "_restored.txt"


def read_bytes(path):
    if not os.path.isfile(path):
        raise LZ77Error("File not found: %s" % path)
    try:
        with open(path, "rb") as handle:       # binary: nothing is translated
            return handle.read()
    except OSError as error:
        raise LZ77Error("Could not read %s (%s)." % (path, error.strerror or error)) from None


def write_bytes(path, data):
    """
    Write bytes safely: the data goes to a temporary file in the same folder
    and replaces the target only when it was written completely, so a failure
    never leaves a half-written or destroyed output file.
    """
    folder = os.path.dirname(os.path.abspath(path))
    if not os.path.isdir(folder):
        raise LZ77Error("The output folder does not exist: %s" % folder)

    temp_path = None
    try:
        handle = tempfile.NamedTemporaryFile(dir=folder, delete=False, suffix=".tmp")
        temp_path = handle.name
        with handle:
            handle.write(data)
        os.replace(temp_path, path)
        temp_path = None
    except OSError as error:
        raise LZ77Error("Could not write %s (%s)." % (path, error.strerror or error)) from None
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


def same_file(path_a, path_b):
    return (os.path.normcase(os.path.abspath(path_a))
            == os.path.normcase(os.path.abspath(path_b)))


def files_identical(path_a, path_b):
    """Byte-for-byte comparison of two files."""
    return read_bytes(path_a) == read_bytes(path_b)


def suggest_output_path(input_path, mode, output_format=None):
    """Pick a sensible output name that never equals the input name."""
    if not input_path:
        return ""

    folder, name = os.path.split(input_path)
    lowered = name.lower()

    if mode == "compress":
        stem = os.path.splitext(name)[0] or name
        suffix = TAGS_SUFFIX if output_format == "tags" else BINARY_SUFFIX
        candidate = stem + suffix
    else:
        stem = name
        for known in (TAGS_SUFFIX, BINARY_SUFFIX, ".txt"):
            if lowered.endswith(known):
                stem = name[:-len(known)]
                break
        candidate = (stem or name) + RESTORED_SUFFIX

    result = os.path.join(folder, candidate)
    if same_file(result, input_path):
        result = os.path.join(folder, "output_" + candidate)
    return result


def open_with_default_app(path):
    """Open a file with the operating system's default program."""
    if not os.path.isfile(path):
        raise LZ77Error("The output file does not exist yet: %s" % path)
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)                                  # noqa: windows only
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except OSError as error:
        raise LZ77Error("Could not open %s (%s)." % (path, error)) from None
