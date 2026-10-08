# AGENTS.md — Developer & AI Agent Guide for DotaCore

Welcome to the **DotaCore** codebase. This guide provides AI agents and human developers with the essential architecture, domain concepts, development workflows, and testing patterns needed to maintain and extend this project.

---

## 1. Project Overview & Philosophy

**DotaCore** is an interactive application and backend utility for Dota 2 players and analysts that:
1. Queries match metadata and 10-player scoreboards via the **OpenDota API**.
2. Displays formatted match overview cards and full player statistics across plug-and-play frontends (CLI, and future GUI/Web interfaces).
3. Verifies availability on Valve's edge CDN servers and downloads replay archives (`.dem.bz2` / `.dem.zst`).
4. Transparently detects compression algorithms via binary magic bytes (handling Valve's modern Zstandard stream format) and decompresses them into Source 2 `.dem` demos.
5. Locates the local Dota 2 installation across Windows, Linux, and macOS, checks version compatibility against the local `steam.inf`, and copies the replay directly into `game/dota/replays/`.

### Core Design Rules
* **Decoupled Architecture**: The `backend/` package is completely independent of the frontend/UI. The `frontend/` package depends on the backend.
* **Plug-and-Play Frontends**: UIs implement the `backend.interfaces.BaseUI` contract and can be registered in `frontend.registry` (`cli`, `web`, `gui`, etc.).
* **Single-Run Interactive Experience**: After processing a match ID (or exiting early), the CLI finishes and exits cleanly. It does **not** loop or ask the user if they want to process another match.
* **Non-Blocking / Graceful Degradation**: If an older match replay has expired on Valve's servers, the CLI still renders the full match card and player scoreboard while advising the user about Valve's retention window.
* **Safe Terminal Output**: Windows consoles default to legacy encodings (like `cp1252`). All terminal output is guarded via `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` and ASCII/ANSI fallbacks to avoid `UnicodeEncodeError`.

---

## 2. Directory Layout & Module Responsibilities

```text
dotacore/
├── .github/
│   └── workflows/
│       └── ci.yml              # GitHub Actions matrix CI (Ubuntu, Windows, macOS across Python 3.8, 3.11)
├── main.py                     # Application entry point; supports --ui {cli, ...}
├── README.md                   # User-facing documentation and Dota 2 console instructions
├── requirements.txt            # Package dependencies (requests, zstandard for Python < 3.14)
├── requirements-dev.txt        # Development dependencies (pytest)
├── pytest.ini                  # Pytest configuration and defaults
├── .gitignore                  # Ignores pyvenv, replays, __pycache__, and cache files
├── replays/                    # Default download destination for match replay files
├── tests/                      # Pytest test suite covering backend, frontend, models, and registry
│   ├── test_models.py          # PlayerScore, MatchDetails, ReplaySource
│   ├── test_ui.py              # Parsing, formatting, colors, scoreboard rendering
│   ├── test_downloader.py      # Decompression (zstd, bz2, gz, raw), downloads, headers
│   ├── test_api.py             # OpenDota endpoints, parse polling, error handling
│   ├── test_game_finder.py     # Steam library detection & version compatibility
│   ├── test_app.py             # CLI application flow integration tests
│   ├── test_service.py         # DotaCoreService, WorkflowEngine, and backend independence checks
│   └── test_registry.py       # Plug-and-play UI registration and dispatch tests
├── backend/                    # Independent backend package (zero frontend dependencies)
│   ├── __init__.py             # Exports models, services, exceptions, downloader, game-finder
│   ├── config.py               # Constants, timeouts, URLs, and default paths
│   ├── exceptions.py           # Domain exception hierarchy (DotaCoreError base)
│   ├── models.py               # Dataclasses: MatchDetails, PlayerScore, ReplaySource
│   ├── api.py                  # OpenDota API client and Valve CDN status checker
│   ├── downloader.py           # Streaming chunk downloader, decompressor, and .dem header inspector
│   ├── game_finder.py          # Cross-platform Steam / Dota 2 installation discovery and version check
│   ├── interfaces.py           # BaseUI abstract interface for plug-and-play UI frontends
│   ├── service.py              # Headless DotaCoreService API
│   ├── workflow.py             # Headless WorkflowEngine orchestrating BaseUI and DotaCoreService
│   └── .constants_cache.json   # Auto-generated cache for hero and item ID-to-name definitions
├── frontend/                   # Frontend package (dependent on backend)
│   ├── __init__.py             # Exports registry helpers and CLI components
│   ├── registry.py             # Plug-and-play UI registry (register_ui, get_ui, launch_ui)
│   └── cli/                    # CLI frontend implementation
│       ├── __init__.py
│       ├── styles.py           # ANSI color styles and text painter
│       ├── ui.py               # TerminalUI implementing BaseUI
│       └── app.py              # CLIApp / DotaCoreApp runner
└── dotacore/                   # Backward-compatibility shims forwarding to backend & frontend
```

### Detailed Module Descriptions

- **`backend/interfaces.py`**:
  Defines `BaseUI`, the contract that all UI implementations must fulfill to plug into `WorkflowEngine`.
- **`backend/service.py`**:
  `DotaCoreService` provides a headless Python API for match inspection, downloading, decompression, and game folder integration without requiring any terminal or UI.
- **`backend/workflow.py`**:
  `WorkflowEngine` runs the interactive match workflow using an injected `BaseUI` implementation and `DotaCoreService`.
- **`frontend/registry.py`**:
  Central UI plugin registry. Allows registering new frontends (e.g. `register_ui("web", WebApp)`) and launching them dynamically via `launch_ui()`.
- **`frontend/cli/ui.py`**:
  `TerminalUI` implements `BaseUI` for rich ANSI terminal rendering, player tables, progress bars, and input prompts.
- **`frontend/cli/app.py`**:
  `CLIApp` wires `TerminalUI` and `DotaCoreService` into `WorkflowEngine` for command-line execution.

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

---

## 5. Coding Standards & Conventions

1. **Backend Independence**: Modules under `backend/` must never import from `frontend/` or UI modules.
2. **Type Hints**: Use standard type annotations (`from __future__ import annotations`, `Optional`, `tuple`, `list`, `Path`).
3. **Error Handling**: Raise domain exceptions defined in `backend.exceptions` rather than generic `Exception` or `RuntimeError`.
4. **No External Heavy Dependencies**: Keep the project lightweight. Avoid heavy protobuf compilation libraries or pandas; use standard library modules (`struct`, `io`, `re`, `json`, `pathlib`, `bz2`, `gzip`, `compression.zstd`) wherever possible.
5. **Preserve User Autonomy**: The CLI should inform and advise (e.g. warning on version mismatch), but allow the user to make the final choice when copying or downloading.
