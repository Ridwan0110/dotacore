from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

# Common Dota 2 game mode mappings
GAME_MODES: dict[int, str] = {
    1: "All Pick",
    2: "Captains Mode",
    3: "Random Draft",
    4: "Single Draft",
    5: "All Random",
    12: "Least Played",
    16: "Captains Draft",
    18: "Ability Draft",
    20: "All Random Deathmatch",
    21: "1v1 Mid",
    22: "Ranked All Pick",
    23: "Turbo",
}

LOBBY_TYPES: dict[int, str] = {
    0: "Normal",
    1: "Practice",
    2: "Tournament",
    4: "Co-op Bots",
    7: "Ranked",
    8: "1v1 Mid",
    12: "Battle Cup",
}


@dataclass
class PlayerScore:
    slot: int
    name: str
    hero_name: str
    level: int
    kills: int
    deaths: int
    assists: int
    last_hits: int
    denies: int
    net_worth: int
    gpm: int
    xpm: int
    items: list[str] = field(default_factory=list)
    neutral_item: Optional[str] = None
    is_radiant: bool = True

    @property
    def kda_str(self) -> str:
        return f"{self.kills}/{self.deaths}/{self.assists}"

    @property
    def lh_dn_str(self) -> str:
        return f"{self.last_hits}/{self.denies}"

    @property
    def net_worth_str(self) -> str:
        if self.net_worth >= 1000:
            return f"{self.net_worth / 1000:.1f}k"
        return str(self.net_worth)

    @property
    def items_summary(self) -> str:
        valid_items = [it for it in self.items if it and it.lower() != "empty"]
        if not valid_items:
            return "No items"
        return ", ".join(valid_items)


@dataclass
class PlayerMatchSummary:
    """Summary of a single match in a player's recent match history."""

    match_id: int
    start_time: Optional[int] = None
    radiant_win: Optional[bool] = None
    radiant_score: Optional[int] = None
    dire_score: Optional[int] = None
    player_slot: Optional[int] = None
    kills: Optional[int] = None
    deaths: Optional[int] = None
    assists: Optional[int] = None
    hero_id: Optional[int] = None

    @property
    def winner_name(self) -> str:
        if self.radiant_win is True:
            return "Radiant"
        if self.radiant_win is False:
            return "Dire"
        return "Unknown"

    @property
    def date_display(self) -> str:
        if not self.start_time:
            return "Unknown"
        try:
            dt = datetime.fromtimestamp(self.start_time, tz=timezone.utc)
            return dt.strftime("%Y-%m-%d")
        except Exception:
            return "Unknown"

    @property
    def score_display(self) -> str:
        if self.radiant_score is not None and self.dire_score is not None:
            return f"{self.radiant_score} - {self.dire_score}"
        if self.kills is not None and self.deaths is not None and self.assists is not None:
            return f"{self.kills}/{self.deaths}/{self.assists}"
        return "N/A"


@dataclass
class MatchDetails:
    match_id: int
    duration_seconds: int
    radiant_win: Optional[bool] = None
    radiant_score: Optional[int] = None
    dire_score: Optional[int] = None
    start_time: Optional[int] = None
    game_mode_id: Optional[int] = None
    lobby_type_id: Optional[int] = None
    cluster: Optional[int] = None
    replay_salt: Optional[int] = None
    direct_replay_url: Optional[str] = None
    patch_id: Optional[int] = None
    patch_name: Optional[str] = None
    players: list[PlayerScore] = field(default_factory=list)

    @property
    def duration_formatted(self) -> str:
        minutes, seconds = divmod(self.duration_seconds, 60)
        return f"{minutes:02d}:{seconds:02d}"

    @property
    def game_mode_name(self) -> str:
        if self.game_mode_id is not None and self.game_mode_id in GAME_MODES:
            return GAME_MODES[self.game_mode_id]
        return "Unknown Mode"

    @property
    def lobby_type_name(self) -> str:
        if self.lobby_type_id is not None and self.lobby_type_id in LOBBY_TYPES:
            return LOBBY_TYPES[self.lobby_type_id]
        return "Matchmaking"

    @property
    def age_days(self) -> float:
        if not self.start_time:
            return 0.0
        elapsed = time.time() - self.start_time
        return max(0.0, elapsed / 86400.0)

    @property
    def relative_age_display(self) -> str:
        if not self.start_time:
            return "Unknown date"
        elapsed_sec = int(time.time() - self.start_time)
        if elapsed_sec < 60:
            return "just now"
        if elapsed_sec < 3600:
            mins = elapsed_sec // 60
            return f"{mins} minute{'s' if mins != 1 else ''} ago"
        if elapsed_sec < 86400:
            hours = elapsed_sec // 3600
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        days = elapsed_sec // 86400
        return f"{days} day{'s' if days != 1 else ''} ago"

    @property
    def winner_name(self) -> str:
        if self.radiant_win is True:
            return "Radiant"
        if self.radiant_win is False:
            return "Dire"
        return "Unknown"

    @property
    def patch_display(self) -> str:
        if self.patch_name:
            return f"Dota {self.patch_name}"
        if self.patch_id is not None:
            return f"Patch #{self.patch_id}"
        return "Unknown"

    @property
    def radiant_players(self) -> list[PlayerScore]:
        return [p for p in self.players if p.is_radiant]

    @property
    def dire_players(self) -> list[PlayerScore]:
        return [p for p in self.players if not p.is_radiant]


@dataclass
class ReplaySource:
    match_id: int
    url: str
    cluster: Optional[int] = None
    replay_salt: Optional[int] = None

    @property
    def archive_filename(self) -> str:
        return self.url.rsplit("/", 1)[-1]

    @property
    def decompressed_filename(self) -> str:
        filename = self.archive_filename
        for ext in (".bz2", ".zst", ".gz"):
            if filename.endswith(ext):
                filename = filename[: -len(ext)]
                break
        if not filename.endswith(".dem"):
            filename = f"{filename}.dem"
        return filename
