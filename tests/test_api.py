from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest
import requests

from dotacore.api import OpenDotaClient
from dotacore.exceptions import (
    MatchNotFoundError,
    NetworkError,
    ParseTimeoutError,
    RateLimitExceededError,
    ReplayNotAvailableError,
)
from dotacore.models import MatchDetails


@pytest.fixture
def client():
    return OpenDotaClient(api_key="test_key_123")


def test_api_params_with_key(client: OpenDotaClient):
    params = client._get_params({"extra": "val"})
    assert params["api_key"] == "test_key_123"
    assert params["extra"] == "val"


def test_fetch_match_success(client: OpenDotaClient):
    mock_payload = {
        "match_id": 9032315904,
        "duration": 3600,
        "radiant_win": True,
        "radiant_score": 50,
        "dire_score": 40,
        "start_time": 1700000000,
        "game_mode": 22,
        "lobby_type": 7,
        "cluster": 152,
        "replay_salt": 1640825826,
        "replay_url": "http://replay152.valve.net/570/9032315904_1640825826.dem.bz2",
        "patch": 60,
        "players": [
            {
                "player_slot": 0,
                "personaname": "PlayerOne",
                "hero_id": 1,
                "level": 30,
                "kills": 10,
                "deaths": 2,
                "assists": 8,
                "last_hits": 400,
                "denies": 15,
                "net_worth": 32000,
                "gold_per_min": 700,
                "xp_per_min": 900,
                "item_0": 1,
            }
        ],
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.ok = True
    mock_resp.json.return_value = mock_payload

    with patch.object(client.session, "get", return_value=mock_resp):
        match = client.fetch_match(9032315904)
        assert match.match_id == 9032315904
        assert match.duration_seconds == 3600
        assert match.radiant_win is True
        assert len(match.players) == 1
        assert match.players[0].name == "PlayerOne"


def test_fetch_match_404(client: OpenDotaClient):
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.ok = False

    with patch.object(client.session, "get", return_value=mock_resp):
        with pytest.raises(MatchNotFoundError):
            client.fetch_match(99999999999)


def test_fetch_match_429(client: OpenDotaClient):
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.ok = False

    with patch.object(client.session, "get", return_value=mock_resp):
        with pytest.raises(RateLimitExceededError):
            client.fetch_match(12345)


def test_fetch_match_empty_payload(client: OpenDotaClient):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.ok = True
    mock_resp.json.return_value = {}

    with patch.object(client.session, "get", return_value=mock_resp):
        with pytest.raises(MatchNotFoundError):
            client.fetch_match(12345)


def test_fetch_match_network_error(client: OpenDotaClient):
    with patch.object(client.session, "get", side_effect=requests.ConnectionError("DNS failure")):
        with pytest.raises(NetworkError):
            client.fetch_match(12345)


def test_resolve_replay_source_direct(client: OpenDotaClient):
    match = MatchDetails(
        match_id=100,
        duration_seconds=100,
        direct_replay_url="http://direct.valve.net/100.dem.bz2",
    )
    src = client.resolve_replay_source(match)
    assert src is not None
    assert src.url == "http://direct.valve.net/100.dem.bz2"


def test_resolve_replay_source_cluster_and_salt(client: OpenDotaClient):
    match = MatchDetails(
        match_id=100,
        duration_seconds=100,
        cluster=180,
        replay_salt=9999,
    )
    src = client.resolve_replay_source(match)
    assert src is not None
    assert src.url == "http://replay180.valve.net/570/100_9999.dem.bz2"


def test_resolve_replay_source_fallback(client: OpenDotaClient):
    match = MatchDetails(
        match_id=200,
        duration_seconds=100,
        cluster=None,
        replay_salt=None,
    )

    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = [{"cluster": 220, "replay_salt": 5555}]

    with patch.object(client.session, "get", return_value=mock_resp):
        src = client.resolve_replay_source(match)
        assert src is not None
        assert src.cluster == 220
        assert src.replay_salt == 5555


def test_trigger_parse_job(client: OpenDotaClient):
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = {"job": {"jobId": 88888}}

    with patch.object(client.session, "post", return_value=mock_resp):
        job_id = client.trigger_parse_job(123)
        assert job_id == "88888"


def test_wait_for_parse_success(client: OpenDotaClient):
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = None  # None indicates job completed and dequeued

    with patch.object(client.session, "get", return_value=mock_resp):
        assert client.wait_for_parse("88888", timeout=5) is True


def test_wait_for_parse_timeout(client: OpenDotaClient):
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = {"state": "active"}  # Still queued

    with patch.object(client.session, "get", return_value=mock_resp):
        with pytest.raises(ParseTimeoutError):
            client.wait_for_parse("88888", timeout=0.1)


def test_check_valve_replay_status(client: OpenDotaClient):
    mock_200 = MagicMock()
    mock_200.status_code = 200
    mock_200.headers = {"Content-Length": "75000000"}

    with patch.object(client.session, "head", return_value=mock_200):
        live, size = client.check_valve_replay_status("http://replay.valve.net/test.dem.bz2")
        assert live is True
        assert size == 75000000

    mock_404 = MagicMock()
    mock_404.status_code = 404
    with patch.object(client.session, "head", return_value=mock_404):
        live, size = client.check_valve_replay_status("http://replay.valve.net/expired.dem.bz2")
        assert live is False
        assert size is None
