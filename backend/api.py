from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import time
from typing import Callable, Optional
import requests

from .config import (
    DEFAULT_USER_AGENT,
    OPENDOTA_BASE_URL,
    PARSE_POLL_INTERVAL_SECONDS,
    PARSE_POLL_TIMEOUT_SECONDS,
    REQUEST_TIMEOUT_SECONDS,
)
from .exceptions import (
    MatchNotFoundError,
    NetworkError,
    ParseTimeoutError,
    ProfileNotFoundError,
    RateLimitExceededError,
    ReplayNotAvailableError,
)
from .models import MatchDetails, PlayerMatchSummary, PlayerScore, ReplaySource

DEFAULT_PATCH_MAP: dict[int, str] = {
    56: "7.37",
    57: "7.38",
    58: "7.39",
    59: "7.40",
    60: "7.41",
}


class OpenDotaClient:
    """HTTP client interacting with OpenDota API and Valve replay infrastructure."""

    def __init__(self, api_key: Optional[str] = None):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "application/json",
        })
        self.api_key = api_key
        self._patch_cache: dict[int, str] = dict(DEFAULT_PATCH_MAP)
        self._patch_cache_loaded = False
        self._heroes_cache: dict[int, str] = {}
        self._items_cache: dict[int, str] = {}
        self._constants_loaded = False
        self._match_cache: dict[int, MatchDetails] = {}
        self._cache_file = Path(__file__).parent / ".constants_cache.json"

    def _get_url(self, endpoint: str) -> str:
        return f"{OPENDOTA_BASE_URL.rstrip('/')}/{endpoint.lstrip('/')}"

    def _get_params(self, extra: Optional[dict] = None) -> dict:
        params = dict(extra or {})
        if self.api_key:
            params["api_key"] = self.api_key
        return params

    def load_patch_constants(self) -> dict[int, str]:
        """Fetch patch definitions from OpenDota constants endpoint (cached per session)."""
        if self._patch_cache_loaded:
            return self._patch_cache

        url = self._get_url("constants/patch")
        try:
            resp = self.session.get(url, params=self._get_params(), timeout=10)
            if resp.ok:
                items = resp.json()
                if isinstance(items, list):
                    for item in items:
                        p_id = item.get("id")
                        p_name = item.get("name")
                        if isinstance(p_id, int) and p_name:
                            self._patch_cache[p_id] = str(p_name)
                    self._patch_cache_loaded = True
        except Exception:
            pass

        return self._patch_cache

    def resolve_patch_name(self, patch_id: Optional[int]) -> Optional[str]:
        """Resolve patch ID (e.g. 60) to gameplay patch string (e.g. 7.41)."""
        if patch_id is None:
            return None
        patch_map = self.load_patch_constants()
        return patch_map.get(patch_id)

    def load_game_constants(self) -> tuple[dict[int, str], dict[int, str]]:
        """Load heroes and items dictionary from disk cache or OpenDota."""
        if self._constants_loaded:
            return self._heroes_cache, self._items_cache

        # 1. Try local disk cache
        if self._cache_file.exists():
            try:
                data = json.loads(self._cache_file.read_text(encoding="utf-8"))
                self._heroes_cache = {int(k): v for k, v in data.get("heroes", {}).items()}
                self._items_cache = {int(k): v for k, v in data.get("items", {}).items()}
                self._constants_loaded = True
                return self._heroes_cache, self._items_cache
            except Exception:
                pass

        # 2. Fetch from OpenDota constants endpoint
        try:
            h_resp = self.session.get(self._get_url("constants/heroes"), params=self._get_params(), timeout=10)
            if h_resp.ok:
                h_json = h_resp.json()
                self._heroes_cache = {
                    int(k): v.get("localized_name", str(k))
                    for k, v in h_json.items()
                    if isinstance(v, dict)
                }

            i_resp = self.session.get(self._get_url("constants/items"), params=self._get_params(), timeout=10)
            if i_resp.ok:
                i_json = i_resp.json()
                self._items_cache = {
                    v["id"]: v.get("dname", k)
                    for k, v in i_json.items()
                    if isinstance(v, dict) and "id" in v
                }

            # Save to disk cache
            try:
                self._cache_file.write_text(
                    json.dumps({"heroes": self._heroes_cache, "items": self._items_cache}),
                    encoding="utf-8",
                )
            except Exception:
                pass

            self._constants_loaded = True
        except Exception:
            pass

        return self._heroes_cache, self._items_cache

    def _parse_players(self, raw_players: list) -> list[PlayerScore]:
        """Convert raw OpenDota player dictionaries into PlayerScore dataclasses."""
        if not raw_players or not isinstance(raw_players, list):
            return []

        heroes_map, items_map = self.load_game_constants()
        players: list[PlayerScore] = []

        for p in raw_players:
            if not isinstance(p, dict):
                continue

            slot = p.get("player_slot", 0)
            is_radiant = slot < 128
            name = p.get("personaname") or p.get("name") or "Anonymous"
            hero_id = p.get("hero_id", 0)
            hero_name = heroes_map.get(hero_id, f"Hero {hero_id}")
            level = p.get("level", 1)
            kills = p.get("kills", 0)
            deaths = p.get("deaths", 0)
            assists = p.get("assists", 0)
            lh = p.get("last_hits", 0)
            dn = p.get("denies", 0)
            net_worth = p.get("net_worth") or p.get("total_gold") or 0
            gpm = p.get("gold_per_min", 0)
            xpm = p.get("xp_per_min", 0)

            # Extract main items (slots 0..5)
            item_list: list[str] = []
            for i in range(6):
                item_id = p.get(f"item_{i}")
                if item_id and item_id in items_map:
                    item_list.append(items_map[item_id])

            neutral_id = p.get("item_neutral")
            neutral_item = items_map.get(neutral_id) if neutral_id and neutral_id in items_map else None

            players.append(PlayerScore(
                slot=slot,
                name=name,
                hero_name=hero_name,
                level=level,
                kills=kills,
                deaths=deaths,
                assists=assists,
                last_hits=lh,
                denies=dn,
                net_worth=net_worth,
                gpm=gpm,
                xpm=xpm,
                items=item_list,
                neutral_item=neutral_item,
                is_radiant=is_radiant,
            ))

        return players

    def _build_match_details(self, match_id: int, payload: dict) -> MatchDetails:
        """Construct a MatchDetails dataclass from raw OpenDota match response payload."""
        patch_id = payload.get("patch")
        patch_name = self.resolve_patch_name(patch_id)
        players = self._parse_players(payload.get("players", []))

        return MatchDetails(
            match_id=match_id,
            duration_seconds=int(payload.get("duration") or 0),
            radiant_win=payload.get("radiant_win"),
            radiant_score=payload.get("radiant_score"),
            dire_score=payload.get("dire_score"),
            start_time=payload.get("start_time"),
            game_mode_id=payload.get("game_mode"),
            lobby_type_id=payload.get("lobby_type"),
            cluster=payload.get("cluster"),
            replay_salt=payload.get("replay_salt"),
            direct_replay_url=payload.get("replay_url"),
            patch_id=patch_id,
            patch_name=patch_name,
            players=players,
        )

    def fetch_match(self, match_id: int) -> MatchDetails:
        """Fetch match metadata and scoreboard from OpenDota."""
        if match_id in self._match_cache:
            return self._match_cache[match_id]

        url = self._get_url(f"matches/{match_id}")
        try:
            response = self.session.get(
                url,
                params=self._get_params(),
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except (requests.ConnectionError, requests.Timeout) as exc:
            raise NetworkError(f"Could not reach OpenDota servers: {exc}") from exc

        if response.status_code == 404:
            raise MatchNotFoundError(f"Match ID {match_id} was not found on OpenDota.")
        if response.status_code == 429:
            raise RateLimitExceededError("OpenDota API rate limit reached. Please wait a moment.")
        if not response.ok:
            raise NetworkError(f"OpenDota returned unexpected HTTP status {response.status_code}.")

        payload = response.json()
        if not payload or not isinstance(payload, dict) or payload.get("duration") is None:
            raise MatchNotFoundError(
                f"OpenDota returned empty records for match {match_id}. "
                "The match might be unparsed or the ID may be invalid."
            )

        match = self._build_match_details(match_id, payload)
        self._match_cache[match_id] = match
        return match

    def _enrich_match_scores(self, summaries: list[PlayerMatchSummary]) -> None:
        """Concurrently fetch team scores for match summaries that lack radiant/dire scores."""
        needed = [s for s in summaries if s.radiant_score is None or s.dire_score is None]
        if not needed:
            return

        def fetch_score(summary: PlayerMatchSummary) -> None:
            if summary.match_id in self._match_cache:
                cached = self._match_cache[summary.match_id]
                summary.radiant_score = cached.radiant_score
                summary.dire_score = cached.dire_score
                return

            url = self._get_url(f"matches/{summary.match_id}")
            try:
                resp = self.session.get(url, params=self._get_params(), timeout=REQUEST_TIMEOUT_SECONDS)
                if resp.ok:
                    data = resp.json()
                    if isinstance(data, dict):
                        summary.radiant_score = data.get("radiant_score")
                        summary.dire_score = data.get("dire_score")
                        try:
                            cached_match = self._build_match_details(summary.match_id, data)
                            self._match_cache[summary.match_id] = cached_match
                        except Exception:
                            pass
            except Exception:
                pass

        with ThreadPoolExecutor(max_workers=min(10, len(needed))) as executor:
            list(executor.map(fetch_score, needed))

    def fetch_player_matches(
        self,
        account_id: int,
        limit: int = 10,
        offset: int = 0,
    ) -> list[PlayerMatchSummary]:
        """Fetch recent matches played by a player using their 32-bit account ID."""
        url = self._get_url(f"players/{account_id}/matches")
        params = self._get_params({
            "limit": limit,
            "offset": offset,
        })
        try:
            response = self.session.get(
                url,
                params=params,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except (requests.ConnectionError, requests.Timeout) as exc:
            raise NetworkError(f"Could not reach OpenDota servers: {exc}") from exc

        if response.status_code == 404:
            raise ProfileNotFoundError(f"Player profile ID {account_id} was not found on OpenDota.")
        if response.status_code == 429:
            raise RateLimitExceededError("OpenDota API rate limit reached. Please wait a moment.")
        if not response.ok:
            raise NetworkError(f"OpenDota returned unexpected HTTP status {response.status_code}.")

        payload = response.json()
        if not isinstance(payload, list):
            return []

        summaries: list[PlayerMatchSummary] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            m_id = item.get("match_id")
            if m_id is None:
                continue
            summaries.append(PlayerMatchSummary(
                match_id=int(m_id),
                start_time=item.get("start_time"),
                radiant_win=item.get("radiant_win"),
                radiant_score=item.get("radiant_score"),
                dire_score=item.get("dire_score"),
                player_slot=item.get("player_slot"),
                kills=item.get("kills"),
                deaths=item.get("deaths"),
                assists=item.get("assists"),
                hero_id=item.get("hero_id"),
            ))

        self._enrich_match_scores(summaries)
        return summaries

    def fetch_replay_cluster_fallback(self, match_id: int) -> tuple[Optional[int], Optional[int]]:
        """Query /replays endpoint as a fallback for cluster & replay salt."""
        url = self._get_url("replays")
        try:
            response = self.session.get(
                url,
                params=self._get_params({"match_id": match_id}),
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            if response.ok:
                items = response.json()
                if isinstance(items, list) and items:
                    cluster = items[0].get("cluster")
                    salt = items[0].get("replay_salt")
                    return cluster, salt
        except Exception:
            pass
        return None, None

    def resolve_replay_source(self, match: MatchDetails) -> Optional[ReplaySource]:
        """Determine the direct Valve replay download URL."""
        if match.direct_replay_url:
            return ReplaySource(
                match_id=match.match_id,
                url=match.direct_replay_url,
                cluster=match.cluster,
                replay_salt=match.replay_salt,
            )

        cluster = match.cluster
        salt = match.replay_salt

        if cluster is None or salt is None:
            cluster, salt = self.fetch_replay_cluster_fallback(match.match_id)

        if cluster is not None and salt is not None:
            valve_url = f"http://replay{cluster}.valve.net/570/{match.match_id}_{salt}.dem.bz2"
            return ReplaySource(
                match_id=match.match_id,
                url=valve_url,
                cluster=cluster,
                replay_salt=salt,
            )

        return None

    def trigger_parse_job(self, match_id: int) -> str:
        """Trigger an on-demand match parse job on OpenDota."""
        url = self._get_url(f"request/{match_id}")
        try:
            response = self.session.post(
                url,
                params=self._get_params(),
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            raise NetworkError(f"Failed to submit match parse request: {exc}") from exc

        job_info = data.get("job") if isinstance(data, dict) else None
        job_id = (job_info.get("jobId") if isinstance(job_info, dict) else None) or data.get("jobId")

        if not job_id:
            raise ReplayNotAvailableError("OpenDota did not return a valid parse job identifier.")

        return str(job_id)

    def wait_for_parse(
        self,
        job_id: str,
        timeout: int = PARSE_POLL_TIMEOUT_SECONDS,
        tick_callback: Optional[Callable[[int], None]] = None,
    ) -> bool:
        """Poll parse job until completion or timeout."""
        url = self._get_url(f"request/{job_id}")
        start_time = time.time()

        while (time.time() - start_time) < timeout:
            elapsed = int(time.time() - start_time)
            if tick_callback:
                tick_callback(elapsed)

            try:
                response = self.session.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
                if response.ok:
                    data = response.json()
                    if data is None or not data:
                        return True
            except requests.RequestException:
                pass

            time.sleep(PARSE_POLL_INTERVAL_SECONDS)

        raise ParseTimeoutError("The match parsing request timed out on OpenDota's queue.")

    def check_valve_replay_status(self, url: str) -> tuple[bool, Optional[int]]:
        """
        Verify whether Valve's replay CDN currently hosts the file.
        Returns (is_available, file_size_in_bytes).
        """
        try:
            resp = self.session.head(url, timeout=12, allow_redirects=True)
            if resp.status_code == 200:
                length = resp.headers.get("Content-Length")
                size = int(length) if length and length.isdigit() else None
                return True, size
            return False, None
        except requests.RequestException:
            return True, None
