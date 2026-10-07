# DotaCore ⚔️
[![Python](https://img.shields.io/badge/python-3.11%2B-blue?logo=python)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](https://opensource.org/license/mit/)
[![Version](https://img.shields.io/badge/version-0.1.0-blue)](https://github.com/Ridwan0110/redu_logger/releases)
[![GitHub](https://img.shields.io/badge/source-GitHub-blue?logo=github)](https://github.com/Ridwan0110/dotacore)

A modern, interactive Python CLI utility to look up match scoreboards, download, and decompress Dota 2 match replays (`.dem`) directly from Valve's CDN servers using the OpenDota API.

## Features

- **🎮 Full Interactive Single-Match Mode**: Prompts for a Match ID or URL, pulls all game data and scoreboards, and exits cleanly once finished without looping.
- **📊 Detailed Terminal Scoreboard**: Renders full 10-player detailed scoreboards (Radiant vs Dire) with player names, heroes, levels, K/D/A, net worth, LH/DN, GPM/XPM, 6 slotted items, and neutral items.
- **🔗 Smart URL Detection**: Accepts pure Match IDs (e.g. `9032315904`, `2809696622`) or pasted match links from **Dotabuff**, **OpenDota**, or **Stratz**.
- **🎮 Cross-OS Dota 2 Integration**: Automatically detects Dota 2 installations on Windows, Linux, and macOS, and offers to copy downloaded replays directly to `game/dota/replays/`.
- **🔍 Patch Compatibility Verification**: Checks the replay's engine build against your installed Dota 2 version before copying:
  - If builds match / are compatible: copies silently without warnings.
  - If builds mismatch: displays an explicit warning about potential playback glitches/crashes.
- **📜 Version Identification**: Displays the gameplay patch (**e.g. `Dota 7.41`, `Dota 6.88`**) and extracts Valve engine build metadata directly from `.dem` file headers.
- **⚡ Pre-Flight Expiration Verification**: Checks if the replay archive is still hosted on Valve's cluster servers before downloading.
- **📦 Multi-Format Auto-Decompression**: Transparently detects magic byte headers to decompress both **Zstandard (`zstd`)** and legacy **BZip2 (`bz2`)** archives into ready-to-watch `.dem` files.
- **🛡️ Cross-Platform Terminal Support**: Safe UTF-8 encoding handling and ANSI styling for Windows PowerShell, Command Prompt, and modern terminals.

## Installation

Ensure you have Python 3.8+ (recommended 3.11+) installed.

```bash
pip install -r requirements.txt
```

## Usage

Simply run:

```bash
python main.py
```

Type `q` or press `Ctrl+C` at any prompt to exit cleanly.

## Running Tests

To run the full unit and integration test suite:

```bash
pip install -r requirements-dev.txt
pytest
```

## Disclaimer

This project is an independent open-source tool and is not affiliated with, authorized, maintained, sponsored, or endorsed by Valve Corporation. Dota and Dota 2 are registered trademarks of Valve Corporation.
