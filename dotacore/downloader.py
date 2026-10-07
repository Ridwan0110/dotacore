from __future__ import annotations

import bz2
import gzip
import io
import os
from pathlib import Path
import re
import shutil
import time
from typing import Any, Callable, Optional
import requests

from .config import DEFAULT_USER_AGENT
from .exceptions import DownloadError, ReplayExpiredError


class Downloader:
    """Handles streaming download and multi-format decompression of replay files."""

    def __init__(self, chunk_size: int = 1024 * 512):
        self.chunk_size = chunk_size

    def download(
        self,
        url: str,
        dest_path: Path,
        progress_cb: Optional[Callable[[int, Optional[int], float, Optional[float]], None]] = None,
    ) -> Path:
        """
        Download a file over HTTP with live progress metrics.
        progress_cb receives: (downloaded_bytes, total_bytes, speed_bytes_per_sec, eta_seconds).
        """
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        temp_dest = dest_path.with_suffix(dest_path.suffix + ".part")

        headers = {"User-Agent": DEFAULT_USER_AGENT}

        try:
            with requests.get(url, stream=True, headers=headers, timeout=30) as resp:
                if resp.status_code in (404, 502, 403, 410):
                    raise ReplayExpiredError(
                        f"Valve server returned HTTP {resp.status_code}. "
                        "The replay file has expired from Valve's storage cluster."
                    )
                resp.raise_for_status()

                total_header = resp.headers.get("content-length")
                total_bytes = int(total_header) if total_header and total_header.isdigit() else None

                downloaded = 0
                start_time = time.time()
                last_time = start_time
                last_downloaded = 0
                current_speed = 0.0

                with open(temp_dest, "wb") as f_out:
                    for chunk in resp.iter_content(chunk_size=self.chunk_size):
                        if not chunk:
                            continue
                        f_out.write(chunk)
                        downloaded += len(chunk)

                        now = time.time()
                        time_delta = now - last_time
                        if time_delta >= 0.4:
                            bytes_delta = downloaded - last_downloaded
                            current_speed = bytes_delta / time_delta
                            last_time = now
                            last_downloaded = downloaded

                            eta: Optional[float] = None
                            if total_bytes and current_speed > 0:
                                remaining_bytes = max(0, total_bytes - downloaded)
                                eta = remaining_bytes / current_speed

                            if progress_cb:
                                progress_cb(downloaded, total_bytes, current_speed, eta)

                # Final completion callback
                if progress_cb:
                    elapsed = max(0.001, time.time() - start_time)
                    avg_speed = downloaded / elapsed
                    progress_cb(downloaded, total_bytes or downloaded, avg_speed, 0.0)

            # Atomically move temp file to final destination
            if temp_dest.exists():
                temp_dest.replace(dest_path)

            return dest_path

        except (requests.ConnectionError, requests.Timeout) as exc:
            if temp_dest.exists():
                temp_dest.unlink(missing_ok=True)
            raise DownloadError(f"Network interruption while downloading: {exc}") from exc
        except Exception:
            if temp_dest.exists():
                temp_dest.unlink(missing_ok=True)
            raise

    @staticmethod
    def detect_format(archive_path: Path) -> str:
        """
        Inspect file magic bytes to determine compression algorithm regardless
        of filename extension (e.g. Valve serving Zstandard under .bz2 extension).
        """
        try:
            with open(archive_path, "rb") as f:
                header = f.read(8)
        except OSError as exc:
            raise DownloadError(f"Cannot read file header from {archive_path.name}: {exc}") from exc

        # Zstandard magic: 0xFD2FB528 -> \x28\xb5/\xfd
        if header.startswith(b"\x28\xb5/\xfd"):
            return "zstd"
        # BZip2 magic: BZh
        if header.startswith(b"BZh"):
            return "bz2"
        # GZip magic: \x1f\x8b
        if header.startswith(b"\x1f\x8b"):
            return "gzip"
        # Uncompressed Dota 2 demo file
        if header.startswith(b"PBDEMS2"):
            return "uncompressed"

        return "unknown"

    def decompress(
        self,
        archive_file: Path,
        output_file: Optional[Path] = None,
        delete_archive: bool = False,
        progress_cb: Optional[Callable[[int, int], None]] = None,
    ) -> Path:
        """
        Auto-detect compression format and decompress into a standard .dem file.
        Supports Zstandard (zstd), BZip2 (bz2), and GZip transparently.
        """
        if not archive_file.is_file():
            raise DownloadError(f"Source file {archive_file} not found for decompression.")

        if output_file is None:
            stem = archive_file.name
            for ext in (".bz2", ".zst", ".gz"):
                if stem.endswith(ext):
                    stem = stem[: -len(ext)]
                    break
            if not stem.endswith(".dem"):
                stem = f"{stem}.dem"
            output_file = archive_file.with_name(stem)

        fmt = self.detect_format(archive_file)
        temp_output = output_file.with_suffix(output_file.suffix + ".dpart")
        total_compressed_size = archive_file.stat().st_size
        written_bytes = 0

        try:
            if fmt == "uncompressed":
                # File is already uncompressed, just copy or move
                if delete_archive:
                    archive_file.replace(output_file)
                else:
                    shutil.copyfile(archive_file, output_file)
                return output_file

            reader = self._open_decompression_stream(archive_file, fmt)
            with reader as fin, open(temp_output, "wb") as fout:
                while True:
                    chunk = fin.read(self.chunk_size)
                    if not chunk:
                        break
                    fout.write(chunk)
                    written_bytes += len(chunk)
                    if progress_cb:
                        progress_cb(written_bytes, total_compressed_size)

            if temp_output.exists():
                temp_output.replace(output_file)

            if delete_archive and archive_file.exists():
                archive_file.unlink(missing_ok=True)

            return output_file

        except Exception as exc:
            if temp_output.exists():
                temp_output.unlink(missing_ok=True)
            raise DownloadError(f"Failed decompressing {archive_file.name}: {exc}") from exc

    def _open_decompression_stream(self, path: Path, detected_format: str):
        """Open appropriate decompressor stream based on detected magic bytes."""
        if detected_format == "zstd":
            try:
                from compression import zstd
                return zstd.open(path, "rb")
            except ImportError:
                pass

            try:
                import zstandard
                cctx = zstandard.ZstdDecompressor()
                raw_stream = open(path, "rb")
                return cctx.stream_reader(raw_stream)
            except ImportError:
                raise DownloadError(
                    "Replay is compressed with Zstandard (zstd), which requires "
                    "Python 3.14+ or the 'zstandard' library (pip install zstandard)."
                )

        if detected_format == "bz2":
            return bz2.open(path, "rb")

        if detected_format == "gzip":
            return gzip.open(path, "rb")

        try:
            return bz2.open(path, "rb")
        except Exception:
            try:
                from compression import zstd
                return zstd.open(path, "rb")
            except Exception:
                raise DownloadError(
                    f"Unknown or unsupported compression header in {path.name}."
                )

    @staticmethod
    def inspect_demo_header(dem_path: Path) -> dict[str, Any]:
        """
        Inspect Source 2 .dem file header to retrieve Valve server and engine build metadata.
        Returns dict with keys: server_version, engine_build, network_protocol.
        """
        info: dict[str, Any] = {
            "server_version": None,
            "engine_build": None,
            "network_protocol": None,
        }
        if not dem_path.is_file():
            return info

        try:
            with open(dem_path, "rb") as f:
                if not f.read(8).startswith(b"PBDEMS2"):
                    return info
                f.seek(16)

                def read_varint_stream(stream) -> Optional[int]:
                    res = 0
                    shift = 0
                    while True:
                        raw = stream.read(1)
                        if not raw:
                            return None
                        b = raw[0]
                        res |= (b & 0x7F) << shift
                        if not (b & 0x80):
                            break
                        shift += 7
                    return res

                cmd = read_varint_stream(f)
                tick = read_varint_stream(f)
                size = read_varint_stream(f)
                if not size or size <= 0:
                    return info

                data = f.read(size)

                # Search server directory tag (e.g. /opt/srcds/dota/dota_v6944/dota)
                m = re.search(rb"/dota_(v\d+)/", data)
                if m:
                    info["server_version"] = m.group(1).decode("utf-8", errors="ignore")

                # Parse protobuf fields in CDemoFileHeader
                bio = io.BytesIO(data)
                while bio.tell() < len(data):
                    tag = read_varint_stream(bio)
                    if tag is None:
                        break
                    field_num = tag >> 3
                    wire_type = tag & 0x7

                    if wire_type == 0:  # Varint
                        val = read_varint_stream(bio)
                        if field_num == 2:
                            info["network_protocol"] = val
                        elif field_num == 13:
                            info["engine_build"] = val
                    elif wire_type == 2:  # Length-delimited
                        length = read_varint_stream(bio)
                        if length and length > 0:
                            bio.read(length)
                    elif wire_type == 5:  # 32-bit fixed
                        bio.read(4)
                    elif wire_type == 1:  # 64-bit fixed
                        bio.read(8)
                    else:
                        break
        except Exception:
            pass

        return info
