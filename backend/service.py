from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional

from .api import OpenDotaClient
from .config import DEFAULT_REPLAY_DIR
from .downloader import Downloader
from .game_finder import DotaGameFinder
from .models import MatchDetails, PlayerMatchSummary, ReplaySource


class DotaCoreService:
    """
    Headless backend service providing full access to match lookup,
    OpenDota API parsing, streaming downloads, decompression, and Dota 2 integration.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api = OpenDotaClient(api_key=api_key)
        self.downloader = Downloader()
        self.default_output_dir = DEFAULT_REPLAY_DIR

    def fetch_match(self, match_id: int) -> MatchDetails:
        """Fetch match metadata and scoreboard from OpenDota."""
        return self.api.fetch_match(match_id)

    def fetch_player_matches(
        self,
        account_id: int,
        limit: int = 10,
        offset: int = 0,
    ) -> list[PlayerMatchSummary]:
        """Fetch recent matches played by a player using their account ID."""
        return self.api.fetch_player_matches(account_id, limit=limit, offset=offset)

    def resolve_replay_source(self, match: MatchDetails) -> Optional[ReplaySource]:
        """Determine direct Valve replay download coordinates and URL."""
        return self.api.resolve_replay_source(match)

    def check_valve_replay_status(self, url: str) -> tuple[bool, Optional[int]]:
        """Verify whether Valve replay CDN currently hosts the file."""
        return self.api.check_valve_replay_status(url)

    def trigger_parse_job(self, match_id: int) -> str:
        """Enqueue an on-demand match parse job with OpenDota."""
        return self.api.trigger_parse_job(match_id)

    def wait_for_parse(
        self,
        job_id: str,
        timeout: int = 180,
        tick_callback: Optional[Callable[[int], None]] = None,
    ) -> bool:
        """Poll parse job until completion or timeout."""
        return self.api.wait_for_parse(job_id, timeout=timeout, tick_callback=tick_callback)

    def download_replay(
        self,
        url: str,
        dest_path: Path,
        progress_cb: Optional[Callable[[int, Optional[int], float, Optional[float]], None]] = None,
    ) -> Path:
        """Download replay archive over HTTP with progress reporting."""
        return self.downloader.download(url=url, dest_path=dest_path, progress_cb=progress_cb)

    def decompress_replay(
        self,
        archive_file: Path,
        output_file: Optional[Path] = None,
        delete_archive: bool = False,
        progress_cb: Optional[Callable[[int, int], None]] = None,
    ) -> Path:
        """Decompress replay archive into playable Source 2 .dem file."""
        return self.downloader.decompress(
            archive_file=archive_file,
            output_file=output_file,
            delete_archive=delete_archive,
            progress_cb=progress_cb,
        )

    def detect_format(self, archive_file: Path) -> str:
        """Detect archive compression format by inspecting magic bytes."""
        return self.downloader.detect_format(archive_file)

    def inspect_demo_header(self, dem_path: Path) -> dict[str, Any]:
        """Inspect Source 2 demo binary headers for engine and server build tags."""
        return self.downloader.inspect_demo_header(dem_path)

    def find_game_installation(self) -> Optional[Path]:
        """Discover local Dota 2 installation path."""
        return DotaGameFinder.find_installation()

    def get_game_replays_directory(self, dota_path: Path) -> Path:
        """Get target game replays directory."""
        return DotaGameFinder.get_replays_directory(dota_path)

    def read_steam_inf(self, dota_path: Path) -> dict[str, str]:
        """Read client version information from steam.inf."""
        return DotaGameFinder.read_steam_inf(dota_path)

    def check_game_compatibility(
        self,
        replay_version_tag: Optional[str],
        replay_patch: Optional[str],
        installed_info: dict[str, str],
    ) -> tuple[bool, Optional[str]]:
        """Evaluate compatibility between replay file and installed client."""
        return DotaGameFinder.check_compatibility(
            replay_version_tag=replay_version_tag,
            replay_patch=replay_patch,
            installed_info=installed_info,
        )

    def copy_replay_to_game(self, replay_file: Path, dota_path: Optional[Path] = None) -> Path:
        """Copy replay file to Dota 2's replays directory."""
        return DotaGameFinder.copy_replay(replay_file, dota_path)
