from __future__ import annotations

import io
from unittest.mock import patch
import pytest
from backend.models import MatchDetails, PlayerMatchSummary, PlayerScore
from frontend.cli import Style, TerminalUI, paint


@pytest.mark.parametrize(
    "raw_input, expected_id",
    [
        ("9032315904", 9032315904),
        ("  9032315904  ", 9032315904),
        ("https://www.opendota.com/matches/9032315904", 9032315904),
        ("https://www.dotabuff.com/matches/9032315904", 9032315904),
        ("https://stratz.com/matches/9032315904?query=1", 9032315904),
        ("match id is 9032315904 here", 9032315904),
        ("", None),
        ("   ", None),
        ("invalid_input", None),
        ("12345", None),  # Under 7 digits
        ("https://google.com", None),
    ],
)
def test_parse_match_input(raw_input: str, expected_id: int | None):
    assert TerminalUI.parse_match_input(raw_input) == expected_id


@pytest.mark.parametrize(
    "raw_input, expected_id",
    [
        ("https://www.opendota.com/players/86745124", 86745124),
        ("https://www.dotabuff.com/players/86745124", 86745124),
        ("https://stratz.com/players/86745124?tab=matches", 86745124),
        ("p 86745124", 86745124),
        ("P: 86745124", 86745124),
        ("profile 86745124", 86745124),
        ("player 86745124", 86745124),
        ("https://steamcommunity.com/profiles/76561198046779852", 86514124),
        ("76561198046779852", 86514124),
        ("", None),
        ("   ", None),
        ("invalid", None),
        ("https://google.com", None),
    ],
)
def test_parse_profile_input(raw_input: str, expected_id: int | None):
    assert TerminalUI.parse_profile_input(raw_input) == expected_id


def test_format_bytes():
    assert TerminalUI.format_bytes(500) == "0.5 KB"
    assert TerminalUI.format_bytes(1024 * 500) == "500.0 KB"
    assert TerminalUI.format_bytes(1024 * 1024 * 72.5) == "72.5 MB"
    assert TerminalUI.format_bytes(1024 * 1024 * 1024 * 2.5) == "2.50 GB"


def test_format_time():
    assert TerminalUI.format_time(0) == "00:00"
    assert TerminalUI.format_time(45) == "00:45"
    assert TerminalUI.format_time(90) == "01:30"
    assert TerminalUI.format_time(3665) == "61:05"


def test_paint():
    colored = paint("Hello", Style.GREEN, bold=True)
    assert Style.GREEN in colored
    assert Style.BOLD in colored
    assert Style.RESET in colored

    plain = paint("Plain")
    assert plain == "Plain"


def test_display_match_card(capsys):
    match = MatchDetails(
        match_id=9032315904,
        duration_seconds=3600,
        radiant_win=True,
        radiant_score=35,
        dire_score=20,
        patch_name="7.41",
    )
    TerminalUI.display_match_card(match)
    captured = capsys.readouterr().out
    assert "9032315904" in captured
    assert "Radiant Victory" in captured
    assert "35" in captured and "20" in captured
    assert "Dota 7.41" in captured


def test_display_scoreboard(capsys):
    p_rad = PlayerScore(
        slot=0,
        name="RadHero",
        hero_name="Pudge",
        level=25,
        kills=15,
        deaths=5,
        assists=20,
        last_hits=150,
        denies=10,
        net_worth=18000,
        gpm=500,
        xpm=600,
        items=["Blink Dagger", "Heart of Tarrasque"],
        neutral_item="Apex",
        is_radiant=True,
    )
    p_dire = PlayerScore(
        slot=128,
        name="DirePlayerWithAVeryLongNameExceeding16Chars",
        hero_name="Invoker",
        level=24,
        kills=10,
        deaths=12,
        assists=8,
        last_hits=220,
        denies=15,
        net_worth=16000,
        gpm=480,
        xpm=550,
        items=["Hand of Midas", "Aghanim's Scepter"],
        is_radiant=False,
    )

    match = MatchDetails(
        match_id=9032315904,
        duration_seconds=3600,
        radiant_win=True,
        radiant_score=45,
        dire_score=30,
        players=[p_rad, p_dire],
    )

    TerminalUI.display_scoreboard(match)
    captured = capsys.readouterr().out
    assert "RADIANT VICTORY" in captured
    assert "DIRE DEFEAT" in captured
    assert "RadHero" in captured
    assert "Pudge" in captured
    assert "Apex" in captured
    assert "DirePlayerWithA…" in captured or "DirePlayerWithA" in captured


def test_display_scoreboard_empty(capsys):
    match = MatchDetails(match_id=123, duration_seconds=100, players=[])
    TerminalUI.display_scoreboard(match)
    captured = capsys.readouterr().out
    assert "No player scoreboard details available" in captured


def test_display_profile_matches(capsys):
    matches = [
        PlayerMatchSummary(
            match_id=9032315904,
            start_time=1700000000,
            radiant_win=True,
            radiant_score=42,
            dire_score=28,
        ),
        PlayerMatchSummary(
            match_id=9032315905,
            start_time=1699900000,
            radiant_win=False,
            radiant_score=15,
            dire_score=39,
        ),
    ]

    TerminalUI.display_profile_matches(matches, start_index=1)
    captured = capsys.readouterr().out

    assert "Match ID" in captured
    assert "Date" in captured
    assert "Score" in captured
    assert "Winner" in captured
    assert "9032315904" in captured
    assert "42 - 28" in captured
    assert "Radiant" in captured
    assert "9032315905" in captured
    assert "15 - 39" in captured
    assert "Dire" in captured


def test_prompt_profile_match_selection():
    # Selecting valid order number
    with patch("frontend.cli.ui.TerminalUI.prompt_input", return_value="3"):
        res = TerminalUI.prompt_profile_match_selection(total_loaded=10, can_load_more=True)
        assert res == 3

    # Requesting to load more
    with patch("frontend.cli.ui.TerminalUI.prompt_input", return_value="m"):
        res = TerminalUI.prompt_profile_match_selection(total_loaded=10, can_load_more=True)
        assert res == "more"

    # Quitting
    with patch("frontend.cli.ui.TerminalUI.prompt_input", return_value="q"):
        res = TerminalUI.prompt_profile_match_selection(total_loaded=10, can_load_more=True)
        assert res is None

    # Invalid input then valid
    with patch("frontend.cli.ui.TerminalUI.prompt_input", side_effect=["99", "1"]):
        res = TerminalUI.prompt_profile_match_selection(total_loaded=10, can_load_more=True)
        assert res == 1


def test_prompt_match_input_routing():
    # Numeric match ID input
    with patch("frontend.cli.ui.TerminalUI.prompt_input", return_value="9032315904"):
        res = TerminalUI.prompt_match_input()
        assert res == 9032315904

    # Profile prefix input
    with patch("frontend.cli.ui.TerminalUI.prompt_input", return_value="p 86745124"):
        res = TerminalUI.prompt_match_input()
        assert res == ("profile", 86745124)

    # Profile URL input
    with patch("frontend.cli.ui.TerminalUI.prompt_input", return_value="https://www.opendota.com/players/86745124"):
        res = TerminalUI.prompt_match_input()
        assert res == ("profile", 86745124)

    # Quit input
    with patch("frontend.cli.ui.TerminalUI.prompt_input", return_value="q"):
        res = TerminalUI.prompt_match_input()
        assert res is None


def test_render_download_progress(capsys):
    TerminalUI.render_download_progress(
        downloaded=50000000,
        total=100000000,
        speed_bps=5000000,
        eta_seconds=10,
    )
    captured = capsys.readouterr().out
    assert "50.0%" in captured
    assert "ETA: 00:10" in captured

    # Indeterminate progress (total is None)
    TerminalUI.render_download_progress(
        downloaded=25000000,
        total=None,
        speed_bps=2000000,
        eta_seconds=None,
    )
    captured = capsys.readouterr().out
    assert "23.8 MB" in captured
