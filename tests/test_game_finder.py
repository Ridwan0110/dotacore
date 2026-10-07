from __future__ import annotations

import tempfile
from pathlib import Path
from dotacore.game_finder import DotaGameFinder


def test_read_steam_inf():
    with tempfile.TemporaryDirectory() as tmp_dir:
        dota_path = Path(tmp_dir)
        dota_dir = dota_path / "game" / "dota"
        dota_dir.mkdir(parents=True)
        inf_file = dota_dir / "steam.inf"
        inf_file.write_text(
            "ClientVersion=6951\n"
            "ServerVersion=6951\n"
            "ProductName=dota2_workshop\n"
            "VersionDate=Oct 06 2026\n"
        )

        data = DotaGameFinder.read_steam_inf(dota_path)
        assert data.get("clientversion") == "6951"
        assert data.get("serverversion") == "6951"
        assert data.get("versiondate") == "Oct 06 2026"


def test_get_replays_directory():
    base = Path("/opt/steam/dota2")
    replays = DotaGameFinder.get_replays_directory(base)
    assert replays == base / "game" / "dota" / "replays"


def test_check_compatibility_close_versions():
    installed = {"clientversion": "6951"}
    # Within delta 20
    compatible, warning = DotaGameFinder.check_compatibility(
        replay_version_tag="v6944",
        replay_patch="Dota 7.41",
        installed_info=installed,
    )
    assert compatible is True
    assert warning is None


def test_check_compatibility_mismatched_versions():
    installed = {"clientversion": "6951"}
    # Far delta (v5500 vs 6951)
    compatible, warning = DotaGameFinder.check_compatibility(
        replay_version_tag="v5500",
        replay_patch="Dota 6.88",
        installed_info=installed,
    )
    assert compatible is False
    assert warning is not None
    assert "Version mismatch detected" in warning
    assert "v5500" in warning
    assert "v6951" in warning


def test_check_compatibility_missing_info():
    # If clientversion is missing or invalid
    comp, warn = DotaGameFinder.check_compatibility("v6944", "7.41", {})
    assert comp is True
    assert warn is None

    # If replay build tag is None
    comp2, warn2 = DotaGameFinder.check_compatibility(None, "7.41", {"clientversion": "6951"})
    assert comp2 is True
    assert warn2 is None
