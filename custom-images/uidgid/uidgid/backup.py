"""This module contains functions used for encoding and decoding binary data
for communication as JSON string values. 

The functions use:

1.  The `bz2` module for compression.                          bytes <-> bytes
2.  The `base64` module for encoding binary data as base64.    bytes <-> bytes
3.  utf-8 encoding for unicode strings.                        str <-> bytes

A basic principle is that a JSON string used to represent data must
be formatted as utf-8.   Hence the overall thrust of the code is to
transform arbitrary byte strings into the fewest number of utf-8 encoded
characters needed to represent it.
"""

import bz2
import base64
import time
from pathlib import Path

# =============================================================================


def encode(data: bytes, encoding="utf-8") -> str:
    """Given a bytes object `data`, compress it and return the base64 encoded
    compressed string which has been decoded to unicode using the given `encoding`.
    """
    return base64.b64encode(bz2.compress(data)).decode(encoding)


def decode(data: str, encoding="utf-8") -> bytes:
    """Given the a unicode string of base64 encoded compressed `data`, encode
    the unicode to a bytes string using the given `encoding`, convert the
    decoded bytes to binary using base64 decoding,  and decompress the binary.
    """
    return bz2.decompress(base64.b64decode(data.encode(encoding)))


def encode_from_file(file_path: str, encoding="utf-8") -> str:
    """Given a file path `file_path`,  read the file contents, compress it,
    and return the base64 encoded compressed string which has been decoded to
    unicode using the given `encoding`.
    """
    with open(file_path, "rb") as file:
        return encode(file.read(), encoding=encoding)


def decode_to_file(file_path: str, data: str, encoding="utf-8") -> None:
    """Given a file path `file_path`,  write the base64 encoded compressed
    string `data` to the file,  decode the unicode to a bytes string using
    the given `encoding`, convert the decoded bytes to binary using base64
    decoding,  and decompress the binary.
    """
    with open(file_path, "wb+") as file:
        file.write(decode(data, encoding=encoding))


# =============================================================================


def backup_file(
    file_path: Path | str, where: Path | str, max_copies: int = 100
) -> Path:
    """Given a file path `file_path`,  give it an additional dated seconds count
    extension and store it in directory `where`.
    """
    file_path, where = Path(file_path), Path(where)
    basename = file_path.name
    backup_file_path = where / (basename + f".{int(time.time())}")

    where.mkdir(parents=True, exist_ok=True)

    text = file_path.read_text(encoding="utf-8")
    backup_file_path.write_text(text, encoding="utf-8")

    old_copies = sorted(where.glob(f"{basename}.*"))
    while len(old_copies) > max_copies:
        old_copies.pop(0).unlink()

    return backup_file_path
