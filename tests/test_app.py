from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from dotacore.app import DotaCoreApp
from dotacore.models import MatchDetails, PlayerScore, ReplaySource


@pytest.fixture
def app():
    return DotaCoreApp()


def test_app_quit_immediately(app: DotaCoreApp):
    with patch("dotacore.ui.TerminalUI.prompt_input", return_value="q"):
        # Should exit gracefully without raising or attempting API calls
        app._run_single_match()


def test_app_expired_match_flow(app: DotaCoreApp, capsys):
    # Match from 100 days ago (older than 14 days threshold)
    mock_match = MatchDetails(
        match_id=1234567,
        duration_seconds=2000,
        start_time=1000000,  # ancient
        radiant_win=True,
        radiant_score=20,
        dire_score=15,
        patch_name="7.30",
        players=[
            PlayerScore(
                slot=0,
                name="AncientPlayer",
                hero_name="Tiny",
                level=20,
                kills=5,
                deaths=2,
                assists=10,
                last_hits=150,
                denies=5,
                net_worth=15000,
                gpm=450,
                xpm=500,
                is_radiant=True,
            )
        ],
    )

    with patch.object(app.api, "fetch_match", return_value=mock_match), \
         patch("dotacore.ui.TerminalUI.prompt_input", return_value="1234567"), \
         patch("dotacore.ui.TerminalUI.prompt_confirm", side_effect=[True]):  # view scoreboard = True

        app._run_single_match()

    captured = capsys.readouterr().out
    assert "1234567" in captured
    assert "AncientPlayer" in captured
    assert "Valve purges replay files" in captured


def test_app_successful_download_and_copy(app: DotaCoreApp, tmp_path: Path):
    mock_match = MatchDetails(
        match_id=9032315904,
        duration_seconds=3600,
        start_time=int(Path().stat().st_mtime),  # recent
        radiant_win=True,
        radiant_score=40,
        dire_score=35,
        patch_name="7.41",
    )
    mock_source = ReplaySource(
        match_id=9032315904,
        url="http://replay152.valve.net/570/9032315904_1640825826.dem.bz2",
    )

    app.output_directory = tmp_path

    fake_dem = tmp_path / "9032315904_1640825826.dem"
    fake_dem.write_bytes(b"PBDEMS2\x00")

    mock_dota_dir = tmp_path / "dota_install"
    (mock_dota_dir / "game" / "dota" / "replays").mkdir(parents=True)

    with patch.object(app.api, "fetch_match", return_value=mock_match), \
         patch.object(app.api, "resolve_replay_source", return_value=mock_source), \
         patch.object(app.api, "check_valve_replay_status", return_value=(True, 50000000)), \
         patch.object(app.downloader, "download", return_value=fake_dem), \
         patch.object(app.downloader, "detect_format", return_value="zstd"), \
         patch.object(app.downloader, "decompress", return_value=fake_dem), \
         patch.object(app.downloader, "inspect_demo_header", return_value={"server_version": "v6944", "engine_build": 10836}), \
         patch("dotacore.game_finder.DotaGameFinder.find_installation", return_value=mock_dota_dir), \
         patch("dotacore.game_finder.DotaGameFinder.read_steam_inf", return_value={"clientversion": "6944"}), \
         patch("dotacore.ui.TerminalUI.prompt_input", side_effect=["9032315904", str(tmp_path)]), \
         patch("dotacore.ui.TerminalUI.prompt_confirm", side_effect=[
             False,  # View scoreboard
             True,   # Download replay
             True,   # Decompress to .dem
             False,  # Keep archive
             True,   # Copy to Dota 2 folder
         ]):

        app._run_single_match()

    # Verify copied file in mock dota replays folder
    copied = mock_dota_dir / "game" / "dota" / "replays" / fake_dem.name
    assert copied.is_file()
