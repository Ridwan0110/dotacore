from __future__ import annotations

import os
from pathlib import Path
import re
import sys
from typing import Optional


class DotaGameFinder:
    """Discovers local Dota 2 installations across Windows, Linux, and macOS."""

    @classmethod
    def find_installation(self) -> Optional[Path]:
        """Search all Steam library roots for Dota 2 installation."""
        for root in self.find_steam_library_folders():
            dota_dir = root / "steamapps" / "common" / "dota 2 beta"
            if (dota_dir / "game" / "dota").is_dir():
                return dota_dir.resolve()
        return None

    @classmethod
    def find_steam_library_folders(cls) -> list[Path]:
        """Discover Steam library roots across supported platforms."""
        primary_steam_paths: list[Path] = []

        # 1. Platform-specific Steam root detection
        if sys.platform == "win32":
            # Registry check
            try:
                import winreg

                for subkey in (r"Software\Valve\Steam", r"SOFTWARE\WOW6432Node\Valve\Steam"):
                    for root_hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                        try:
                            with winreg.OpenKey(root_hive, subkey) as key:
                                path_val, _ = winreg.QueryValueEx(key, "SteamPath")
                                if path_val:
                                    p = Path(path_val)
                                    if p.is_dir() and p not in primary_steam_paths:
                                        primary_steam_paths.append(p)
                        except Exception:
                            pass
            except Exception:
                pass

            # Standard Windows directories
            standard_candidates = [
                Path("C:/Program Files (x86)/Steam"),
                Path("C:/Program Files/Steam"),
            ]
            for drive in "CDEFGHIJKLMNOPQRSTUVWXYZ":
                standard_candidates.append(Path(f"{drive}:/SteamLibrary"))
                standard_candidates.append(Path(f"{drive}:/Steam"))
                standard_candidates.append(Path(f"{drive}:/Games/Steam"))

            for cand in standard_candidates:
                if cand.is_dir() and cand not in primary_steam_paths:
                    primary_steam_paths.append(cand)

        elif sys.platform == "darwin":
            # macOS default
            mac_path = Path.home() / "Library/Application Support/Steam"
            if mac_path.is_dir():
                primary_steam_paths.append(mac_path)

        else:
            # Linux (Standard, Flatpak, Snap)
            linux_candidates = [
                Path.home() / ".local/share/Steam",
                Path.home() / ".steam/steam",
                Path.home() / ".steam/root",
                Path.home() / ".var/app/com.valvesoftware.Steam/data/Steam",
                Path.home() / ".var/app/com.valvesoftware.Steam/.local/share/Steam",
            ]
            for cand in linux_candidates:
                if cand.is_dir() and cand not in primary_steam_paths:
                    primary_steam_paths.append(cand)

        # 2. Parse libraryfolders.vdf for extra libraries on all mounted drives
        all_library_folders: list[Path] = list(primary_steam_paths)

        for steam_root in primary_steam_paths:
            vdf_file = steam_root / "steamapps" / "libraryfolders.vdf"
            if not vdf_file.is_file():
                continue

            try:
                content = vdf_file.read_text(encoding="utf-8", errors="ignore")
                # Matches: "path" "D:\\SteamLibrary" or "path" "/mnt/storage/SteamLibrary"
                pattern = re.compile(r'"path"\s+"([^"]+)"')
                for match in pattern.finditer(content):
                    raw_path = match.group(1).replace("\\\\", "/")
                    lib_path = Path(raw_path)
                    if lib_path.is_dir() and lib_path not in all_library_folders:
                        all_library_folders.append(lib_path)
            except Exception:
                pass

        return all_library_folders

    @staticmethod
    def get_replays_directory(dota_path: Path) -> Path:
        """Return the target replays directory under game/dota/replays."""
        return dota_path / "game" / "dota" / "replays"

    @staticmethod
    def read_steam_inf(dota_path: Path) -> dict[str, str]:
        """Read game/dota/steam.inf for ClientVersion and VersionDate."""
        inf_file = dota_path / "game" / "dota" / "steam.inf"
        info: dict[str, str] = {}
        if not inf_file.is_file():
            return info

        try:
            for line in inf_file.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = line.strip()
                if "=" in line:
                    key, val = line.split("=", 1)
                    info[key.strip().lower()] = val.strip()
        except Exception:
            pass

        return info

    @staticmethod
    def check_compatibility(
        replay_version_tag: Optional[str],
        replay_patch: Optional[str],
        installed_info: dict[str, str],
    ) -> tuple[bool, Optional[str]]:
        """
        Evaluate playback compatibility between the replay file and current Dota 2 install.
        Returns (is_compatible, warning_message_or_none).
        """
        installed_client_version = installed_info.get("clientversion")
        if not installed_client_version:
            return True, None

        try:
            installed_ver_int = int(installed_client_version)
        except ValueError:
            return True, None

        replay_ver_int: Optional[int] = None
        if replay_version_tag:
            digits = re.search(r"\d+", replay_version_tag)
            if digits:
                try:
                    replay_ver_int = int(digits.group(0))
                except ValueError:
                    pass

        # If both build numbers are available
        if replay_ver_int is not None:
            delta = abs(installed_ver_int - replay_ver_int)
            # Within ~20 build increments is typically minor tweaks / same sub-patch
            if delta <= 20:
                return True, None

            # Different build version: warning
            patch_text = f" ({replay_patch})" if replay_patch else ""
            msg = (
                f"Version mismatch detected!\n"
                f"   - Replay Build:    v{replay_ver_int}{patch_text}\n"
                f"   - Installed Game:  v{installed_ver_int}\n"
                f"   This replay is from a different game update. Playing it in your current client\n"
                f"   might show missing visual effects, incorrect ability values, or fail to load."
            )
            return False, msg

        return True, None
