from __future__ import annotations

import time
from backend.models import MatchDetails, PlayerMatchSummary, PlayerScore, ReplaySource


def test_player_score_properties():
    player = PlayerScore(
        slot=0,
        name="TestPlayer",
        hero_name="Zeus",
        level=25,
        kills=10,
        deaths=2,
        assists=15,
        last_hits=250,
        denies=12,
        net_worth=21500,
        gpm=550,
        xpm=620,
        items=["Arcane Boots", "Aghanim's Scepter", "Empty", "Blink Dagger"],
        neutral_item="Philosopher's Stone",
        is_radiant=True,
    )

    assert player.kda_str == "10/2/15"
    assert player.lh_dn_str == "250/12"
    assert player.net_worth_str == "21.5k"
    assert player.items_summary == "Arcane Boots, Aghanim's Scepter, Blink Dagger"

    # Edge case: low net worth (< 1000) and no items
    poor_player = PlayerScore(
        slot=1,
        name="Support",
        hero_name="Crystal Maiden",
        level=5,
        kills=0,
        deaths=5,
        assists=2,
        last_hits=10,
        denies=0,
        net_worth=850,
        gpm=150,
        xpm=200,
        items=["Empty", "Empty"],
        is_radiant=True,
    )
    assert poor_player.net_worth_str == "850"
    assert poor_player.items_summary == "No items"


def test_player_match_summary():
    summary = PlayerMatchSummary(
        match_id=9032315904,
        start_time=1700000000,
        radiant_win=True,
        radiant_score=35,
        dire_score=20,
        kills=8,
        deaths=2,
        assists=14,
    )
    assert summary.winner_name == "Radiant"
    assert summary.score_display == "35 - 20"
    assert summary.date_display == "2023-11-14"

    # Dire win and score fallback
    dire_summary = PlayerMatchSummary(
        match_id=9032315905,
        radiant_win=False,
        kills=5,
        deaths=1,
        assists=10,
    )
    assert dire_summary.winner_name == "Dire"
    assert dire_summary.score_display == "5/1/10"
    assert dire_summary.date_display == "Unknown"

    # Empty summary
    empty_summary = PlayerMatchSummary(match_id=123)
    assert empty_summary.winner_name == "Unknown"
    assert empty_summary.score_display == "N/A"
    assert empty_summary.date_display == "Unknown"


def test_match_details_properties():
    now = time.time()
    # Match played 2 hours ago
    match = MatchDetails(
        match_id=1234567890,
        duration_seconds=2245,  # 37:25
        radiant_win=True,
        radiant_score=45,
        dire_score=30,
        start_time=int(now - 7200),
        game_mode_id=22,
        lobby_type_id=7,
        patch_name="7.41",
    )

    assert match.duration_formatted == "37:25"
    assert match.game_mode_name == "Ranked All Pick"
    assert match.lobby_type_name == "Ranked"
    assert match.winner_name == "Radiant"
    assert match.patch_display == "Dota 7.41"
    assert "hour" in match.relative_age_display
    assert match.age_days >= 0.0

    # Dire win & patch fallback
    dire_match = MatchDetails(
        match_id=9876543210,
        duration_seconds=1800,
        radiant_win=False,
        patch_id=56,
    )
    assert dire_match.winner_name == "Dire"
    assert dire_match.patch_display == "Patch #56"

    # Unknown mode & unknown patch
    unknown_match = MatchDetails(
        match_id=1111,
        duration_seconds=600,
        game_mode_id=999,
        lobby_type_id=999,
    )
    assert unknown_match.game_mode_name == "Unknown Mode"
    assert unknown_match.lobby_type_name == "Matchmaking"
    assert unknown_match.patch_display == "Unknown"
    assert unknown_match.winner_name == "Unknown"


def test_match_details_player_filtering():
    p1 = PlayerScore(slot=0, name="R1", hero_name="Axe", level=1, kills=0, deaths=0, assists=0, last_hits=0, denies=0, net_worth=0, gpm=0, xpm=0, is_radiant=True)
    p2 = PlayerScore(slot=128, name="D1", hero_name="Bane", level=1, kills=0, deaths=0, assists=0, last_hits=0, denies=0, net_worth=0, gpm=0, xpm=0, is_radiant=False)

    match = MatchDetails(match_id=123, duration_seconds=100, players=[p1, p2])
    assert len(match.radiant_players) == 1
    assert match.radiant_players[0].name == "R1"
    assert len(match.dire_players) == 1
    assert match.dire_players[0].name == "D1"


def test_replay_source_filenames():
    src_bz2 = ReplaySource(match_id=123, url="http://replay.valve.net/570/123_456.dem.bz2")
    assert src_bz2.archive_filename == "123_456.dem.bz2"
    assert src_bz2.decompressed_filename == "123_456.dem"

    src_zst = ReplaySource(match_id=123, url="http://replay.valve.net/570/123_456.dem.zst")
    assert src_zst.decompressed_filename == "123_456.dem"

    src_gz = ReplaySource(match_id=123, url="http://replay.valve.net/570/123_456.dem.gz")
    assert src_gz.decompressed_filename == "123_456.dem"

    src_dem = ReplaySource(match_id=123, url="http://replay.valve.net/570/123_456.dem")
    assert src_dem.decompressed_filename == "123_456.dem"
