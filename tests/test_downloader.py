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

from dotacore.downloader import Downloader
from dotacore.exceptions import DownloadError, ReplayExpiredError

# For creating test zstd payload
try:
    from compression import zstd
except ImportError:
    try:
        import zstandard as zstd
    except ImportError:
        zstd = None


@pytest.fixture
def tmp_dir():
    d = Path(tempfile.mkdtemp())
    yield d
    shutil.rmtree(d, ignore_errors=True)


def test_detect_format(tmp_dir: Path):
    d = Downloader()

    # Zstandard
    f_zstd = tmp_dir / "sample.dem.bz2"
    f_zstd.write_bytes(b"\x28\xb5\x2f\xfd\x00\x00\x00\x00")
    assert d.detect_format(f_zstd) == "zstd"

    # BZip2
    f_bz2 = tmp_dir / "sample.bz2"
    f_bz2.write_bytes(b"BZh91AY&SY\x00\x00\x00")
    assert d.detect_format(f_bz2) == "bz2"

    # GZip
    f_gz = tmp_dir / "sample.gz"
    f_gz.write_bytes(b"\x1f\x8b\x08\x00\x00\x00\x00\x00")
    assert d.detect_format(f_gz) == "gzip"

    # Uncompressed Dota 2 Demo
    f_dem = tmp_dir / "sample.dem"
    f_dem.write_bytes(b"PBDEMS2\x00\x00\x00\x00\x00")
    assert d.detect_format(f_dem) == "uncompressed"

    # Unknown
    f_unk = tmp_dir / "unknown.bin"
    f_unk.write_bytes(b"\x00\x01\x02\x03\x04\x05\x06\x07")
    assert d.detect_format(f_unk) == "unknown"


def test_decompress_bz2(tmp_dir: Path):
    d = Downloader()
    payload = b"PBDEMS2_BZ2_TEST_PAYLOAD"
    archive = tmp_dir / "test.dem.bz2"
    archive.write_bytes(bz2.compress(payload))

    # Keep archive
    out = d.decompress(archive, delete_archive=False)
    assert out.is_file()
    assert out.read_bytes() == payload
    assert archive.is_file()

    # Delete archive
    out2 = d.decompress(archive, delete_archive=True)
    assert out2.is_file()
    assert not archive.exists()


def test_decompress_gzip(tmp_dir: Path):
    d = Downloader()
    payload = b"PBDEMS2_GZIP_TEST_PAYLOAD"
    archive = tmp_dir / "test.dem.gz"
    archive.write_bytes(gzip.compress(payload))

    out = d.decompress(archive, delete_archive=True)
    assert out.read_bytes() == payload
    assert not archive.exists()


def test_decompress_zstd(tmp_dir: Path):
    if zstd is None:
        pytest.skip("zstd library not installed in this environment")

    d = Downloader()
    payload = b"PBDEMS2_ZSTD_TEST_PAYLOAD"
    archive = tmp_dir / "test.dem.bz2"  # Note: .bz2 extension with zstd content

    compressed = zstd.compress(payload)
    archive.write_bytes(compressed)

    progress_ticks = []
    def on_prog(written, total):
        progress_ticks.append((written, total))

    out = d.decompress(archive, delete_archive=False, progress_cb=on_prog)
    assert out.read_bytes() == payload
    assert len(progress_ticks) > 0


def test_decompress_uncompressed_dem(tmp_dir: Path):
    d = Downloader()
    payload = b"PBDEMS2_RAW_DATA"
    raw_file = tmp_dir / "raw.dem"
    raw_file.write_bytes(payload)

    target_dem = tmp_dir / "copied.dem"
    out = d.decompress(raw_file, output_file=target_dem, delete_archive=False)
    assert out == target_dem
    assert out.read_bytes() == payload


def test_decompress_corrupted_stream(tmp_dir: Path):
    d = Downloader()
    # Invalid bzip2 file header followed by garbage
    corrupt = tmp_dir / "corrupted.dem.bz2"
    corrupt.write_bytes(b"BZh91AY&SY_INVALID_STREAM_DATA_HERE")

    with pytest.raises(DownloadError):
        d.decompress(corrupt)

    # Verify temp part file cleaned up
    temp_part = corrupt.with_name("corrupted.dem.dpart")
    assert not temp_part.exists()


def test_decompress_non_existent_file(tmp_dir: Path):
    d = Downloader()
    with pytest.raises(DownloadError):
        d.decompress(tmp_dir / "does_not_exist.dem.bz2")


def test_download_success(tmp_dir: Path):
    d = Downloader()
    dest = tmp_dir / "out.bin"

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-length": "12"}
    mock_resp.iter_content.return_value = [b"chunk1", b"chunk2"]
    mock_resp.__enter__.return_value = mock_resp

    with patch("requests.get", return_value=mock_resp):
        res = d.download("http://example.com/test", dest)
        assert res == dest
        assert dest.read_bytes() == b"chunk1chunk2"


@pytest.mark.parametrize("status_code", [404, 502, 403, 410])
def test_download_expired_error(tmp_dir: Path, status_code: int):
    d = Downloader()
    dest = tmp_dir / "out.bin"

    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.__enter__.return_value = mock_resp

    with patch("requests.get", return_value=mock_resp):
        with pytest.raises(ReplayExpiredError):
            d.download("http://example.com/expired", dest)

    assert not dest.exists()


def test_download_network_error(tmp_dir: Path):
    d = Downloader()
    dest = tmp_dir / "out.bin"

    with patch("requests.get", side_effect=requests.ConnectionError("Offline")):
        with pytest.raises(DownloadError):
            d.download("http://example.com/offline", dest)

    assert not dest.exists()


def test_inspect_demo_header_valid(tmp_dir: Path):
    # Construct a synthetic Source 2 demo header
    # Magic (8 bytes): PBDEMS2\0
    # Offset dummy (8 bytes)
    # Packet header: cmd=1 (varint), tick=0 (varint), size (varint)
    # Packet body: Protobuf fields with server path: /opt/srcds/dota/dota_v6944/dota
    dem = tmp_dir / "sample.dem"

    body = b"\x12\x20/opt/srcds/dota/dota_v6944/dota\x10\x30\x68\xd4\x54"
    # Field 2 = 48 (protocol), Field 13 = 10836 (engine_build)

    header = io.BytesIO()
    header.write(b"PBDEMS2\x00")
    header.write(b"\x00" * 8)
    header.write(bytes([1, 0, len(body)]))  # cmd=1, tick=0, size
    header.write(body)

    dem.write_bytes(header.getvalue())

    info = Downloader.inspect_demo_header(dem)
    assert info["server_version"] == "v6944"


def test_inspect_demo_header_non_demo_file(tmp_dir: Path):
    non_dem = tmp_dir / "text.txt"
    non_dem.write_text("Hello World")

    info = Downloader.inspect_demo_header(non_dem)
    assert info == {"server_version": None, "engine_build": None, "network_protocol": None}
