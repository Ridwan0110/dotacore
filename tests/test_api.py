from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest
import requests

from backend.api import OpenDotaClient
from backend.exceptions import (
    MatchNotFoundError,
    NetworkError,
    ParseTimeoutError,
    ProfileNotFoundError,
    RateLimitExceededError,
    ReplayNotAvailableError,
)
from backend.models import MatchDetails


@pytest.fixture
def client():
    return OpenDotaClient(api_key="test_api_key")


def test_api_params_with_key(client: OpenDotaClient):
    params = client._get_params({"custom": "value"})
    assert params["api_key"] == "test_api_key"
    assert params["custom"] == "value"


def test_fetch_match_success(client: OpenDotaClient):
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "match_id": 9032315904,
        "duration": 2400,
        "radiant_win": True,
        "radiant_score": 35,
        "dire_score": 28,
        "start_time": 1700000000,
        "game_mode": 22,
        "lobby_type": 7,
        "cluster": 152,
        "replay_salt": 1640825826,
        "patch": 58,
        "players": [
            {
                "player_slot": 0,
                "personaname": "Player1",
                "hero_id": 1,
                "level": 25,
                "kills": 10,
                "deaths": 2,
                "assists": 15,
                "last_hits": 250,
                "denies": 10,
                "net_worth": 20000,
                "gold_per_min": 600,
                "xp_per_min": 700,
                "item_0": 1,
                "item_neutral": 0,
            }
        ],
    }

    with patch.object(client.session, "get", return_value=mock_response):
        match = client.fetch_match(9032315904)

    assert match.match_id == 9032315904
    assert match.duration_seconds == 2400
    assert match.radiant_win is True
    assert match.game_mode_name == "Ranked All Pick"
    assert len(match.players) == 1
    assert match.players[0].name == "Player1"
    assert match.players[0].is_radiant is True


def test_fetch_match_404(client: OpenDotaClient):
    mock_response = MagicMock()
    mock_response.ok = False
    mock_response.status_code = 404

    with patch.object(client.session, "get", return_value=mock_response):
        with pytest.raises(MatchNotFoundError):
            client.fetch_match(99999999999)


def test_fetch_match_429(client: OpenDotaClient):
    mock_response = MagicMock()
    mock_response.ok = False
    mock_response.status_code = 429

    with patch.object(client.session, "get", return_value=mock_response):
        with pytest.raises(RateLimitExceededError):
            client.fetch_match(123456)


def test_fetch_match_empty_payload(client: OpenDotaClient):
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.json.return_value = {}

    with patch.object(client.session, "get", return_value=mock_response):
        with pytest.raises(MatchNotFoundError):
            client.fetch_match(123456)


def test_fetch_match_network_error(client: OpenDotaClient):
    with patch.object(client.session, "get", side_effect=requests.ConnectionError("Connection lost")):
        with pytest.raises(NetworkError):
            client.fetch_match(123456)


def test_fetch_player_matches_success(client: OpenDotaClient):
    mock_player_matches_resp = MagicMock()
    mock_player_matches_resp.ok = True
    mock_player_matches_resp.status_code = 200
    mock_player_matches_resp.json.return_value = [
        {
            "match_id": 9032315904,
            "start_time": 1700000000,
            "radiant_win": True,
            "player_slot": 0,
            "kills": 12,
            "deaths": 3,
            "assists": 15,
            "hero_id": 1,
        },
        {
            "match_id": 9032315905,
            "start_time": 1699900000,
            "radiant_win": False,
            "player_slot": 128,
            "kills": 5,
            "deaths": 8,
            "assists": 7,
            "hero_id": 2,
        },
    ]

    mock_match1_resp = MagicMock()
    mock_match1_resp.ok = True
    mock_match1_resp.status_code = 200
    mock_match1_resp.json.return_value = {
        "match_id": 9032315904,
        "radiant_score": 40,
        "dire_score": 25,
        "duration": 2000,
    }

    mock_match2_resp = MagicMock()
    mock_match2_resp.ok = True
    mock_match2_resp.status_code = 200
    mock_match2_resp.json.return_value = {
        "match_id": 9032315905,
        "radiant_score": 18,
        "dire_score": 38,
        "duration": 2200,
    }

    def mock_get(url, params=None, timeout=None):
        if "players/86745124/matches" in url:
            if params:
                assert "project" not in params
            return mock_player_matches_resp
        if "matches/9032315904" in url:
            return mock_match1_resp
        if "matches/9032315905" in url:
            return mock_match2_resp
        return MagicMock(ok=False, status_code=404)

    with patch.object(client.session, "get", side_effect=mock_get):
        matches = client.fetch_player_matches(86745124, limit=10, offset=0)

    assert len(matches) == 2
    assert matches[0].match_id == 9032315904
    assert matches[0].winner_name == "Radiant"
    assert matches[0].date_display == "2023-11-14"
    assert matches[0].score_display == "40 - 25"
    assert matches[1].match_id == 9032315905
    assert matches[1].winner_name == "Dire"
    assert matches[1].date_display == "2023-11-13"
    assert matches[1].score_display == "18 - 38"


def test_fetch_player_matches_fallback_to_kda_when_scores_unavailable(client: OpenDotaClient):
    mock_player_matches_resp = MagicMock()
    mock_player_matches_resp.ok = True
    mock_player_matches_resp.status_code = 200
    mock_player_matches_resp.json.return_value = [
        {
            "match_id": 9032315904,
            "start_time": 1700000000,
            "radiant_win": True,
            "player_slot": 0,
            "kills": 8,
            "deaths": 2,
            "assists": 14,
        }
    ]

    def mock_get(url, params=None, timeout=None):
        if "players" in url:
            return mock_player_matches_resp
        return MagicMock(ok=False, status_code=500)

    with patch.object(client.session, "get", side_effect=mock_get):
        matches = client.fetch_player_matches(86745124, limit=10)

    assert len(matches) == 1
    assert matches[0].match_id == 9032315904
    assert matches[0].date_display == "2023-11-14"
    assert matches[0].score_display == "8/2/14"


def test_fetch_player_matches_404(client: OpenDotaClient):
    mock_response = MagicMock()
    mock_response.ok = False
    mock_response.status_code = 404

    with patch.object(client.session, "get", return_value=mock_response):
        with pytest.raises(ProfileNotFoundError):
            client.fetch_player_matches(999999999)


def test_fetch_player_matches_429(client: OpenDotaClient):
    mock_response = MagicMock()
    mock_response.ok = False
    mock_response.status_code = 429

    with patch.object(client.session, "get", return_value=mock_response):
        with pytest.raises(RateLimitExceededError):
            client.fetch_player_matches(86745124)


def test_fetch_player_matches_network_error(client: OpenDotaClient):
    with patch.object(client.session, "get", side_effect=requests.ConnectionError("Connection lost")):
        with pytest.raises(NetworkError):
            client.fetch_player_matches(86745124)


def test_fetch_player_matches_empty(client: OpenDotaClient):
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.json.return_value = []

    with patch.object(client.session, "get", return_value=mock_response):
        matches = client.fetch_player_matches(86745124)
    assert matches == []


def test_resolve_replay_source_direct(client: OpenDotaClient):
    match = MatchDetails(
        match_id=123,
        duration_seconds=100,
        direct_replay_url="http://valve.cdn/123.dem.bz2",
    )
    source = client.resolve_replay_source(match)
    assert source is not None
    assert source.url == "http://valve.cdn/123.dem.bz2"


def test_resolve_replay_source_cluster_and_salt(client: OpenDotaClient):
    match = MatchDetails(
        match_id=123,
        duration_seconds=100,
        cluster=152,
        replay_salt=999,
    )
    source = client.resolve_replay_source(match)
    assert source is not None
    assert source.url == "http://replay152.valve.net/570/123_999.dem.bz2"


def test_resolve_replay_source_fallback(client: OpenDotaClient):
    match = MatchDetails(
        match_id=123,
        duration_seconds=100,
    )
    with patch.object(client, "fetch_replay_cluster_fallback", return_value=(152, 999)):
        source = client.resolve_replay_source(match)
    assert source is not None
    assert source.url == "http://replay152.valve.net/570/123_999.dem.bz2"


def test_trigger_parse_job(client: OpenDotaClient):
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.json.return_value = {"job": {"jobId": 456789}}

    with patch.object(client.session, "post", return_value=mock_response):
        job_id = client.trigger_parse_job(12345)
    assert job_id == "456789"


def test_wait_for_parse_success(client: OpenDotaClient):
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.json.return_value = None  # Complete / no longer in queue

    with patch.object(client.session, "get", return_value=mock_response):
        success = client.wait_for_parse("456789", timeout=5)
    assert success is True


def test_wait_for_parse_timeout(client: OpenDotaClient):
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.json.return_value = {"jobId": "456789"}  # Still queued

    with patch.object(client.session, "get", return_value=mock_response):
        with pytest.raises(ParseTimeoutError):
            client.wait_for_parse("456789", timeout=0)


def test_check_valve_replay_status(client: OpenDotaClient):
    mock_resp_200 = MagicMock()
    mock_resp_200.status_code = 200
    mock_resp_200.headers = {"Content-Length": "1048576"}

    with patch.object(client.session, "head", return_value=mock_resp_200):
        is_live, size = client.check_valve_replay_status("http://replay.valve.net/test.dem.bz2")
    assert is_live is True
    assert size == 1048576

    mock_resp_404 = MagicMock()
    mock_resp_404.status_code = 404
    with patch.object(client.session, "head", return_value=mock_resp_404):
        is_live, size = client.check_valve_replay_status("http://replay.valve.net/test.dem.bz2")
    assert is_live is False
    assert size is None
