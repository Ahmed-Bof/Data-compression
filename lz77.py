"""
lz77.py - the LZ77 algorithm itself (compression side) plus shared constants.

Everything works on BYTES, so any file (ASCII, UTF-8 text, tabs, CR/LF, even
images) is handled without any encoding problems.

A token is the classic LZ77 triple:

    Token(position, length, next_symbol)

    position     distance BACK from the current spot to the start of the match
                 (1 = the byte just before). 0 when there is no match.
    length       how many bytes are copied from that earlier spot (0 = none).
    next_symbol  the literal byte (0..255) that follows the match.

A byte with no useful match is simply Token(0, 0, byte).

Every token ends with a real next_symbol, so a match never runs to the very
end of the data: the last byte of the input is always the next_symbol of the
last token. That keeps the format free of any "end of file" special case.
"""

from typing import List, NamedTuple

# Limits come from the binary format: position uses 12 bits, length uses 4 bits.
WINDOW_SIZE = 4095        # largest allowed position (search buffer size)
MAX_MATCH_LENGTH = 15     # largest allowed length
MIN_MATCH_LENGTH = 3      # shorter matches cost more bits than plain literals
MAX_CANDIDATES = 512      # how many earlier spots are checked per position


class LZ77Error(Exception):
    """Any problem the user should be told about (bad file, corrupt data...)."""


class Token(NamedTuple):
    position: int
    length: int
    next_symbol: int


def tokenize(data, window_size=WINDOW_SIZE):
    """Turn bytes into a list of LZ77 tokens."""
    data = bytes(data)
    if not 1 <= window_size <= WINDOW_SIZE:
        raise ValueError("window_size must be between 1 and %d" % WINDOW_SIZE)

    total = len(data)
    index = {}            # 3-byte key -> earlier start positions (ascending)
    indexed_until = 0     # every start < indexed_until is already in `index`
    tokens: List[Token] = []
    cursor = 0

    while cursor < total:
        # Make every start position before the cursor searchable.
        while indexed_until < cursor:
            _add_to_index(index, data, indexed_until)
            indexed_until += 1

        position, length = _longest_match(data, cursor, index, window_size)
        next_cursor = cursor + length          # always < total, see _longest_match
        tokens.append(Token(position, length, data[next_cursor]))
        cursor = next_cursor + 1

    return tokens


def _add_to_index(index, data, start):
    if start + MIN_MATCH_LENGTH <= len(data):
        index.setdefault(data[start:start + MIN_MATCH_LENGTH], []).append(start)


def _longest_match(data, cursor, index, window_size):
    """Return (position, length) of the longest earlier match, or (0, 0)."""
    # Keep one byte in reserve: it becomes the token's next_symbol.
    max_length = min(MAX_MATCH_LENGTH, len(data) - cursor - 1)
    if max_length < MIN_MATCH_LENGTH:
        return 0, 0

    candidates = index.get(data[cursor:cursor + MIN_MATCH_LENGTH])
    if not candidates:
        return 0, 0

    oldest_start = cursor - window_size
    best_position = 0
    best_length = 0
    checked = 0

    for start in reversed(candidates):         # nearest candidate first
        if start < oldest_start or checked >= MAX_CANDIDATES:
            break
        checked += 1

        # The first MIN_MATCH_LENGTH bytes are equal (same dictionary key).
        # start + length may pass `cursor`: overlapping matches are allowed.
        length = MIN_MATCH_LENGTH
        while length < max_length and data[start + length] == data[cursor + length]:
            length += 1

        if length > best_length:               # ties keep the nearer match
            best_length = length
            best_position = cursor - start
            if best_length == max_length:
                break

    return best_position, best_length
