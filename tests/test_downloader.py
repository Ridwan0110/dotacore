from __future__ import annotations

import bz2
import gzip
import io
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
import requests

from backend.downloader import Downloader
from backend.exceptions import DownloadError, ReplayExpiredError

try:
    from compression import zstd
except ImportError:
    try:
        import zstandard as zstd
    except ImportError:
        zstd = None


@pytest.fixture
def downloader():
    return Downloader()


def test_detect_format(downloader: Downloader, tmp_path: Path):
    bz2_file = tmp_path / "test.bz2"
    bz2_file.write_bytes(b"BZh91AY&SY")
    assert downloader.detect_format(bz2_file) == "bz2"

    zstd_file = tmp_path / "test.zst"
    zstd_file.write_bytes(b"\x28\xb5/\xfd\x00\x00")
    assert downloader.detect_format(zstd_file) == "zstd"

    gzip_file = tmp_path / "test.gz"
    gzip_file.write_bytes(b"\x1f\x8b\x08\x00")
    assert downloader.detect_format(gzip_file) == "gzip"

    dem_file = tmp_path / "test.dem"
    dem_file.write_bytes(b"PBDEMS2\x00")
    assert downloader.detect_format(dem_file) == "uncompressed"

    unknown_file = tmp_path / "test.bin"
    unknown_file.write_bytes(b"RANDOMDATA")
    assert downloader.detect_format(unknown_file) == "unknown"


def test_decompress_bz2(downloader: Downloader, tmp_path: Path):
    raw_payload = b"PBDEMS2\x00fake demo data"
    archive = tmp_path / "match.dem.bz2"
    with bz2.open(archive, "wb") as f:
        f.write(raw_payload)

    decompressed = downloader.decompress(archive, delete_archive=True)
    assert decompressed.name == "match.dem"
    assert decompressed.read_bytes() == raw_payload
    assert not archive.exists()


def test_decompress_gzip(downloader: Downloader, tmp_path: Path):
    raw_payload = b"PBDEMS2\x00fake demo data gzip"
    archive = tmp_path / "match.dem.gz"
    with gzip.open(archive, "wb") as f:
        f.write(raw_payload)

    decompressed = downloader.decompress(archive, delete_archive=False)
    assert decompressed.name == "match.dem"
    assert decompressed.read_bytes() == raw_payload
    assert archive.exists()


@pytest.mark.skipif(zstd is None, reason="Zstandard not available in test environment")
def test_decompress_zstd(downloader: Downloader, tmp_path: Path):
    raw_payload = b"PBDEMS2\x00fake zstd payload"
    archive = tmp_path / "match.dem.bz2"  # Valve naming convention: .bz2 extension but zstd payload

    if hasattr(zstd, "compress"):
        archive.write_bytes(zstd.compress(raw_payload))
    else:
        cctx = zstd.ZstdCompressor()
        archive.write_bytes(cctx.compress(raw_payload))

    decompressed = downloader.decompress(archive, delete_archive=False)
    assert decompressed.name == "match.dem"
    assert decompressed.read_bytes() == raw_payload


def test_decompress_uncompressed_dem(downloader: Downloader, tmp_path: Path):
    raw_payload = b"PBDEMS2\x00uncompressed demo"
    archive = tmp_path / "match.dem"
    archive.write_bytes(raw_payload)

    out = downloader.decompress(archive, delete_archive=False)
    assert out.name == "match.dem"
    assert out.read_bytes() == raw_payload


def test_decompress_corrupted_stream(downloader: Downloader, tmp_path: Path):
    archive = tmp_path / "corrupt.dem.bz2"
    archive.write_bytes(b"BZh9corrupted_bytes_here")

    with pytest.raises(DownloadError):
        downloader.decompress(archive)


def test_decompress_non_existent_file(downloader: Downloader, tmp_path: Path):
    archive = tmp_path / "missing.dem.bz2"
    with pytest.raises(DownloadError):
        downloader.decompress(archive)


def test_download_success(downloader: Downloader, tmp_path: Path):
    target = tmp_path / "downloaded.dem.bz2"
    payload = b"TestReplayBytes" * 100

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-length": str(len(payload))}
    mock_resp.iter_content.return_value = [payload[:50], payload[50:]]
    mock_resp.__enter__.return_value = mock_resp

    with patch("requests.get", return_value=mock_resp):
        result = downloader.download("http://example.com/replay.dem.bz2", target)

    assert result.is_file()
    assert result.read_bytes() == payload


@pytest.mark.parametrize("status_code", [404, 502, 403, 410])
def test_download_expired_error(downloader: Downloader, tmp_path: Path, status_code: int):
    target = tmp_path / "expired.dem.bz2"

    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.__enter__.return_value = mock_resp

    with patch("requests.get", return_value=mock_resp):
        with pytest.raises(ReplayExpiredError):
            downloader.download("http://example.com/replay.dem.bz2", target)


def test_download_network_error(downloader: Downloader, tmp_path: Path):
    target = tmp_path / "fail.dem.bz2"

    with patch("requests.get", side_effect=requests.ConnectionError("Network drop")):
        with pytest.raises(DownloadError):
            downloader.download("http://example.com/replay.dem.bz2", target)

    assert not target.exists()
    assert not target.with_suffix(target.suffix + ".part").exists()


def test_inspect_demo_header_valid(downloader: Downloader, tmp_path: Path):
    dem_file = tmp_path / "sample.dem"
    # Construct synthetic Source 2 demo header:
    # 8 bytes: PBDEMS2\0
    # 8 bytes: dummy offset
    # CDemoFileHeader command: cmd=1 (varint), tick=0 (varint), size=length (varint), payload
    header = b"PBDEMS2\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    payload = b"data /dota_v6944/dota extra"
    # cmd=1 -> \x01, tick=0 -> \x00, size=len(payload) -> \x1b
    packet = b"\x01\x00" + bytes([len(payload)]) + payload
    dem_file.write_bytes(header + packet)

    info = downloader.inspect_demo_header(dem_file)
    assert info["server_version"] == "v6944"


def test_inspect_demo_header_non_demo_file(downloader: Downloader, tmp_path: Path):
    fake_file = tmp_path / "random.dem"
    fake_file.write_bytes(b"NOT_A_SOURCE2_DEMO")

    info = downloader.inspect_demo_header(fake_file)
    assert info["server_version"] is None
