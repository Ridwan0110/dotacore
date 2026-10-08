from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from backend.models import MatchDetails, PlayerMatchSummary, PlayerScore, ReplaySource
from frontend.cli.app import CLIApp, DotaCoreApp


@pytest.fixture
def app():
    return CLIApp()


def test_app_quit_immediately(app: CLIApp):
    with patch("frontend.cli.ui.TerminalUI.prompt_input", return_value="q"):
        # Should exit gracefully without raising or attempting API calls
        app._run_single_match()


def test_app_expired_match_flow(app: CLIApp, capsys):
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
         patch("frontend.cli.ui.TerminalUI.prompt_input", return_value="1234567"), \
         patch("frontend.cli.ui.TerminalUI.prompt_confirm", side_effect=[True]):  # view scoreboard = True

        app._run_single_match()

    captured = capsys.readouterr().out
    assert "1234567" in captured
    assert "AncientPlayer" in captured
    assert "Valve purges replay files" in captured


def test_app_successful_download_and_copy(app: CLIApp, tmp_path: Path):
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
         patch("backend.game_finder.DotaGameFinder.find_installation", return_value=mock_dota_dir), \
         patch("backend.game_finder.DotaGameFinder.read_steam_inf", return_value={"clientversion": "6944"}), \
         patch("frontend.cli.ui.TerminalUI.prompt_input", side_effect=["9032315904", str(tmp_path)]), \
         patch("frontend.cli.ui.TerminalUI.prompt_confirm", side_effect=[
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


def test_app_profile_search_and_select_match(app: CLIApp, capsys):
    mock_summaries = [
        PlayerMatchSummary(
            match_id=9000000001 + i,
            start_time=1700000000 - i * 3600,
            radiant_win=(i % 2 == 0),
            radiant_score=30 + i,
            dire_score=20 + i,
        )
        for i in range(10)
    ]
    mock_match_details = MatchDetails(
        match_id=9000000002,
        duration_seconds=1800,
        start_time=1000000,
        radiant_win=False,
        radiant_score=31,
        dire_score=21,
    )

    with patch.object(app.service, "fetch_player_matches", return_value=mock_summaries), \
         patch.object(app.api, "fetch_match", return_value=mock_match_details), \
         patch("frontend.cli.ui.TerminalUI.prompt_input", side_effect=["p 86745124", "2"]), \
         patch("frontend.cli.ui.TerminalUI.prompt_confirm", return_value=False):

        app._run_single_match()

    captured = capsys.readouterr().out
    assert "Profile Search" in captured
    assert "Match ID" in captured
    assert "9000000001" in captured
    assert "9000000002" in captured
    assert "Loading match 9000000002 for more information..." in captured
    assert "Dire Victory" in captured


def test_app_profile_search_load_more_matches(app: CLIApp, capsys):
    batch1 = [
        PlayerMatchSummary(
            match_id=9000000001 + i,
            start_time=1700000000,
            radiant_win=True,
            radiant_score=35,
            dire_score=25,
        )
        for i in range(10)
    ]
    batch2 = [
        PlayerMatchSummary(
            match_id=9000000011 + i,
            start_time=1690000000,
            radiant_win=False,
            radiant_score=20,
            dire_score=40,
        )
        for i in range(5)
    ]
    mock_match_details = MatchDetails(
        match_id=9000000012,
        duration_seconds=2000,
        start_time=1000000,
        radiant_win=False,
    )

    with patch.object(app.service, "fetch_player_matches", side_effect=[batch1, batch2]), \
         patch.object(app.api, "fetch_match", return_value=mock_match_details), \
         patch("frontend.cli.ui.TerminalUI.prompt_input", side_effect=["p 86745124", "m", "12"]), \
         patch("frontend.cli.ui.TerminalUI.prompt_confirm", return_value=False):

        app._run_single_match()

    captured = capsys.readouterr().out
    assert "9000000001" in captured
    assert "9000000012" in captured
    assert "Loading match 9000000012 for more information..." in captured
