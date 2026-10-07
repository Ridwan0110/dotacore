# AGENTS.md — Developer & AI Agent Guide for DotaCore

Welcome to the **DotaCore** codebase. This guide provides AI agents and human developers with the essential architecture, domain concepts, development workflows, and testing patterns needed to maintain and extend this project.

---

## 1. Project Overview & Philosophy

**DotaCore** is an interactive CLI utility for Dota 2 players and analysts that:
1. Queries match metadata and 10-player scoreboards via the **OpenDota API**.
2. Displays formatted match overview cards and full player statistics in the terminal.
3. Verifies availability on Valve's edge CDN servers and downloads replay archives (`.dem.bz2` / `.dem.zst`).
4. Transparently detects compression algorithms via binary magic bytes (handling Valve's modern Zstandard stream format) and decompresses them into Source 2 `.dem` demos.
5. Locates the local Dota 2 installation across Windows, Linux, and macOS, checks version compatibility against the local `steam.inf`, and copies the replay directly into `game/dota/replays/`.

### Core Design Rules
* **Single-Run Interactive Experience**: After processing a match ID (or exiting early), the CLI finishes and exits cleanly. It does **not** loop or ask the user if they want to process another match.
* **Non-Blocking / Graceful Degradation**: If an older match replay has expired on Valve's servers, the CLI still renders the full match card and player scoreboard while advising the user about Valve's retention window.
* **Safe Terminal Output**: Windows consoles default to legacy encodings (like `cp1252`). All terminal output is guarded via `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` and ASCII/ANSI fallbacks to avoid `UnicodeEncodeError`.

---

## 2. Directory Layout & Module Responsibilities

```text
dotacore/
├── main.py                     # CLI entry point; initializes and runs DotaCoreApp
├── README.md                   # User-facing documentation and Dota 2 console instructions
├── requirements.txt            # Package dependencies (requests, zstandard for Python < 3.14)
├── requirements-dev.txt        # Development dependencies (pytest)
├── pytest.ini                  # Pytest configuration and defaults
├── .gitignore                  # Ignores pyvenv, replays, __pycache__, and cache files
├── replays/                    # Default download destination for match replay files
├── tests/                      # Pytest test suite covering all units and edge cases
│   ├── test_models.py          # PlayerScore, MatchDetails, ReplaySource
│   ├── test_ui.py              # Parsing, formatting, colors, scoreboard rendering
│   ├── test_downloader.py      # Decompression (zstd, bz2, gz, raw), downloads, headers
│   ├── test_api.py             # OpenDota endpoints, parse polling, error handling
│   ├── test_game_finder.py     # Steam library detection & version compatibility
│   └── test_app.py             # Application flow integration tests
└── dotacore/                   # Core Python package
    ├── __init__.py             # Package definition and __version__
    ├── config.py               # Constants, timeouts, URLs, and default paths
    ├── exceptions.py           # Domain exception hierarchy (DotaCoreError base)
    ├── models.py               # Dataclasses: MatchDetails, PlayerScore, ReplaySource
    ├── api.py                  # OpenDota API client and Valve CDN status checker
    ├── downloader.py           # Streaming chunk downloader, decompressor, and .dem header inspector
    ├── game_finder.py          # Cross-platform Steam / Dota 2 installation discovery and version check
    ├── ui.py                   # Terminal rendering: ANSI styles, match card, scoreboard table, progress bar
    ├── app.py                  # Orchestrator / state controller managing user prompts and execution flow
    └── .constants_cache.json   # Auto-generated cache for hero and item ID-to-name definitions
```

### Detailed Module Descriptions

- **`dotacore/config.py`**:
  Stores base URLs (`OPENDOTA_BASE_URL`), User-Agent (`DotaCore/2.0`), network timeouts, poll intervals for match parsing, and the Valve retention threshold (`VALVE_EXPIRY_THRESHOLD_DAYS = 14`).
- **`dotacore/exceptions.py`**:
  Defines `DotaCoreError` and specific subclasses: `MatchNotFoundError`, `ReplayExpiredError`, `ReplayNotAvailableError`, `RateLimitExceededError`, `NetworkError`, `DownloadError`, and `ParseTimeoutError`.
- **`dotacore/models.py`**:
  - `PlayerScore`: Player stats (K/D/A, LH/DN, Net Worth, GPM/XPM, 6 items, neutral item).
  - `MatchDetails`: Match-level metadata, durations, radiant/dire scores, game mode, lobby type, patch info, and player lists.
  - `ReplaySource`: Download URL, cluster, replay salt, and filename resolvers.
- **`dotacore/api.py`**:
  `OpenDotaClient` handles `GET /matches/{id}`, `GET /replays`, `POST /request/{id}`, `GET /request/{job_id}`, and `GET /constants/patch`. Fetches and caches hero/item dictionaries to disk. Also conducts `HEAD` probes against Valve's replay CDN (`replay{cluster}.valve.net`).
- **`dotacore/downloader.py`**:
  `Downloader` handles streaming HTTP GET requests with live progress callbacks. Contains `detect_format()` to determine compression from file magic bytes, `decompress()` supporting Zstandard, BZip2, and GZip, and `inspect_demo_header()` which parses Source 2 demo binary headers.
- **`dotacore/game_finder.py`**:
  `DotaGameFinder` locates Dota 2 installations on Windows (Registry + multi-drive scans + `libraryfolders.vdf`), Linux (`~/.local/share/Steam`, Flatpak, Snap), and macOS (`~/Library/Application Support/Steam`). Reads `steam.inf` to obtain `ClientVersion` and compares against the replay's build tag (`vXXXX`).
- **`dotacore/ui.py`**:
  `TerminalUI` and `Style` handle ANSI coloring, input prompts, regex-based match ID / URL parsing, match cards, full scoreboard tables, and progress bars.
- **`dotacore/app.py`**:
  `DotaCoreApp` drives the single-match interactive session: match selection -> card view -> scoreboard prompt -> download prompt -> decompression -> game folder copy.

---

## 3. Key Technical Domain Details

### 1. The Valve `.dem.bz2` vs `Zstandard` Compression Anomaly
* **Historical Behavior**: Valve historically compressed Source 1 and early Source 2 replays using BZip2 (magic bytes `BZh` / `0x42 0x5A 0x68`).
* **Modern Behavior**: Valve migrated replay compression to **Zstandard** (magic bytes `0x28 0xB5 0x2F 0xFD`), but **retained the `.dem.bz2` URL extension** on CDN servers for backward compatibility.
* **Implementation Note**: Never trust the file extension for decompression. Always use `Downloader.detect_format()` which checks the first 4–8 magic bytes:
  - `b"\x28\xb5/\xfd"` -> Zstandard (`zstd`)
  - `b"BZh"` -> BZip2 (`bz2`)
  - `b"\x1f\x8b"` -> GZip (`gzip`)
  - `b"PBDEMS2"` -> Raw uncompressed Source 2 demo

### 2. Source 2 Replay Binary Structure (`.dem`)
A decompressed Dota 2 replay starts with an 8-byte file header: `PBDEMS2\x00`.
At offset 16 lies the first command packet (`CDemoFileHeader` protobuf stream):
* Packet framing: `cmd` (varint), `tick` (varint), `size` (varint), followed by protobuf payload.
* Inside this payload:
  - Field 6 (`wire 2`): Server path, e.g. `/opt/srcds/dota/dota_v6944/dota` (reveals the internal server build tag `v6944`).
  - Field 13 (`wire 0`): Source 2 engine build number (e.g. `10836`).
  - Field 2 (`wire 0`): Network protocol number (e.g. `48`).
`Downloader.inspect_demo_header()` extracts these fields without external protobuf dependencies.

### 3. OpenDota Match Parsing Lifecycle
* Recent matches might not have `cluster` and `replay_salt` immediately populated in `/matches/{id}`.
* In such cases, query the fallback endpoint `GET /replays?match_id={id}`.
* If still absent and the match is under `VALVE_EXPIRY_THRESHOLD_DAYS` (14 days), enqueue a parse job via `POST /request/{id}` and poll `GET /request/{job_id}` until the job completes.

### 4. Game Compatibility Verification
Dota 2 replays are input recordings, not video files. Matches recorded on major legacy updates (e.g., 6.88 or pre-7.33) cannot be loaded by modern clients.
* `DotaGameFinder.read_steam_inf()` parses `game/dota/steam.inf` from the installed game directory to find `ClientVersion` (e.g. `6951`).
* `DotaGameFinder.check_compatibility()` compares this with the replay's build tag (e.g. `v6944`).
* If the difference is small (within ~20 builds), playback is considered compatible. If large, a descriptive warning is displayed before copying.

---

## 4. Development & Testing Guidelines

### Virtual Environment & Dependencies
```powershell
# Windows
.\pyvenv\Scripts\Activate.ps1
pip install -r requirements-dev.txt

# Linux / macOS
source venv/bin/activate
pip install -r requirements-dev.txt
```

### Running the Pytest Test Suite
To run the full suite of unit and integration tests:
```bash
pytest
```

The test suite covers:
- **`test_models.py`**: Model calculation, formatting, and filtering.
- **`test_ui.py`**: Regex parsing for match IDs/URLs, formatting, terminal styling, and scoreboard tables.
- **`test_downloader.py`**: Format detection, Zstandard/BZip2/GZip decompression, streaming download, expired replay error handling, and binary `.dem` header inspection.
- **`test_api.py`**: OpenDota API client endpoints, rate limiting, timeout handling, parse job enqueuing, and CDN status checks.
- **`test_game_finder.py`**: Steam library location, `steam.inf` parsing, and version compatibility evaluation.
- **`test_app.py`**: End-to-end interactive CLI controller flows.

---

## 5. Coding Standards & Conventions

1. **Type Hints**: Use standard type annotations (`from __future__ import annotations`, `Optional`, `tuple`, `list`, `Path`).
2. **Error Handling**: Raise domain exceptions defined in `exceptions.py` rather than generic `Exception` or `RuntimeError`.
3. **No External Heavy Dependencies**: Keep the project lightweight. Avoid heavy protobuf compilation libraries or pandas; use standard library modules (`struct`, `io`, `re`, `json`, `pathlib`, `bz2`, `gzip`, `compression.zstd`) wherever possible.
4. **Preserve User Autonomy**: The CLI should inform and advise (e.g. warning on version mismatch), but allow the user to make the final choice when copying or downloading.
