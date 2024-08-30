from uidgid import backup
from pathlib import Path
import time

import pytest


def test_encode_empty_bytes():
    assert backup.decode(backup.encode(b"")) == b""


def test_encode_decode_roundtrip():
    data = b"Hello, World!"
    encoded = backup.encode(data)
    decoded = backup.decode(encoded)
    assert decoded == data


def test_encode_from_file_nonexistent(tmp_path):
    file_path = tmp_path / "nonexistent.txt"
    with pytest.raises(FileNotFoundError):
        backup.encode_from_file(str(file_path))


def test_decode_to_file_invalid_data(tmp_path):
    file_path = tmp_path / "output.txt"
    invalid_data = "invalid"
    with pytest.raises(ValueError):
        backup.decode_to_file(str(file_path), invalid_data)


def test_encode_decode_roundtrip_file(tmp_path):
    file_path = tmp_path / "input.txt"
    file_path.write_bytes(b"Hello, World!")
    encoded = backup.encode_from_file(str(file_path))
    output_path = tmp_path / "output.txt"
    backup.decode_to_file(str(output_path), encoded)
    assert output_path.read_bytes() == b"Hello, World!"


def test_encode_decode_large_data():
    data = b"x" * (1024 * 1024)  # 1 MB
    encoded = backup.encode(data)
    decoded = backup.decode(encoded)
    assert decoded == data


def test_encode_decode_unicode():
    data = "Héllö, Wörld!".encode("utf-8")
    encoded = backup.encode(data, encoding="utf-8")
    decoded = backup.decode(encoded, encoding="utf-8")
    assert decoded == data


def test_backup_file_existing(tmp_path):
    file_path = tmp_path / "input.txt"
    file_path.write_text("Hello, World!", encoding="utf-8")
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    backup_path = backup.backup_file(str(file_path), str(backup_dir))
    assert Path(backup_path).exists()
    assert Path(backup_path).read_text(encoding="utf-8") == "Hello, World!"


def test_backup_file_max_copies(tmp_path):
    file_path = tmp_path / "input.txt"
    file_path.write_text("Hello, World!", encoding="utf-8")
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    for _ in range(4):
        time.sleep(1.1)
        backup.backup_file(str(file_path), str(backup_dir), max_copies=3)
    backup_files = list(backup_dir.glob("input.txt.*"))
    assert len(backup_files) == 3
    oldest_backup = min(backup_files, key=lambda p: int(p.name.split(".")[-1]))
    assert oldest_backup.read_text(encoding="utf-8") == "Hello, World!"
