from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import Optional

from .api import OpenDotaClient
from .config import DEFAULT_REPLAY_DIR, VALVE_EXPIRY_THRESHOLD_DAYS
from .downloader import Downloader
from .exceptions import (
    DotaCoreError,
    MatchNotFoundError,
    NetworkError,
    ParseTimeoutError,
    RateLimitExceededError,
    ReplayExpiredError,
)
from .game_finder import DotaGameFinder
from .models import MatchDetails, ReplaySource
from .ui import Style, TerminalUI, paint


class DotaCoreApp:
    """Main application controller for single match lookup, scoreboard, and replay download."""

    def __init__(self, api_key: Optional[str] = None):
        self.api = OpenDotaClient(api_key=api_key)
        self.downloader = Downloader()
        self.output_directory = DEFAULT_REPLAY_DIR
        self.auto_decompress = True
        self.keep_archive = False

    def start(self) -> None:
        """Entry point for single-match execution."""
        TerminalUI.show_banner()
        try:
            self._run_single_match()
        except KeyboardInterrupt:
            print(f"\n\n{paint('Operation canceled by user. Goodbye!', Style.YELLOW)}")

        print(f"\n{paint('Done! Thanks for using DotaCore.', Style.CYAN)}\n")

    def _run_single_match(self) -> None:
        """Execute lookup, scoreboard display, and optional download for one match."""
        TerminalUI.print_section("Match Selection")

        match_id = self._prompt_for_match_id()
        if match_id is None:
            return

        TerminalUI.print_info(f"Looking up match {paint(str(match_id), Style.CYAN)} on OpenDota...")

        try:
            match = self.api.fetch_match(match_id)
        except MatchNotFoundError as exc:
            TerminalUI.print_error(str(exc))
            return
        except RateLimitExceededError as exc:
            TerminalUI.print_warning(str(exc))
            return
        except NetworkError as exc:
            TerminalUI.print_error(f"Network error: {exc}")
            return

        # 1. Display Overview Card
        TerminalUI.display_match_card(match)

        # 2. Offer Scoreboard View
        want_scoreboard = TerminalUI.prompt_confirm("View detailed player scoreboard?", default=True)
        if want_scoreboard:
            TerminalUI.display_scoreboard(match)

        # 3. Check Replay Availability & Offer Download
        if match.age_days > VALVE_EXPIRY_THRESHOLD_DAYS:
            TerminalUI.print_warning(
                f"Note: This match occurred {match.relative_age_display} "
                f"({match.age_days:.0f} days ago). Valve purges replay files after "
                "approximately 1-2 weeks, so the 3D demo file is no longer downloadable."
            )
            return

        # Resolve replay source
        replay_source = self._obtain_replay_source(match)
        if not replay_source:
            return

        # Check Valve server availability
        is_live, file_size = self.api.check_valve_replay_status(replay_source.url)
        if not is_live:
            TerminalUI.print_warning(
                f"Replay is no longer hosted on Valve's cluster ({replay_source.url}). "
                "Valve has purged the file from their servers."
            )
            return

        want_download = TerminalUI.prompt_confirm("Download match replay (.dem)?", default=True)
        if not want_download:
            TerminalUI.print_info("Replay download skipped.")
            return

        # Output options & download
        self._prompt_output_settings()
        self._execute_download(replay_source, match)

    def _prompt_for_match_id(self) -> Optional[int]:
        """Prompt user until a valid match ID or exit command is given."""
        while True:
            raw = TerminalUI.prompt_input("Enter Match ID or Match URL (or 'q' to quit)")
            if raw.lower() in ("q", "quit", "exit"):
                return None

            match_id = TerminalUI.parse_match_input(raw)
            if match_id is not None:
                return match_id

            TerminalUI.print_error(
                "Could not detect a valid match ID. "
                "Please enter a numeric ID (e.g. 8123456789) or a Dotabuff/OpenDota URL."
            )

    def _obtain_replay_source(self, match: MatchDetails) -> Optional[ReplaySource]:
        """Resolve replay source, requesting OpenDota parse if needed."""
        replay_source = self.api.resolve_replay_source(match)

        if replay_source is not None:
            return replay_source

        TerminalUI.print_warning("Replay server cluster info is not yet registered for this match.")

        if match.age_days > VALVE_EXPIRY_THRESHOLD_DAYS:
            TerminalUI.print_error(
                "Because this match is older than Valve's retention window, "
                "requesting a parse cannot recover the purged replay file."
            )
            return None

        want_parse = TerminalUI.prompt_confirm(
            "Would you like to request OpenDota to parse this match to retrieve the replay?",
            default=True,
        )

        if not want_parse:
            TerminalUI.print_info("Parse request skipped.")
            return None

        try:
            job_id = self.api.trigger_parse_job(match.match_id)
            TerminalUI.print_info(f"Parse job #{job_id} enqueued.")
            self.api.wait_for_parse(job_id, tick_callback=TerminalUI.render_parse_tick)
            print()  # newline after tick
            TerminalUI.print_success("Match parsing finished! Refreshing match details...")

            refreshed_match = self.api.fetch_match(match.match_id)
            replay_source = self.api.resolve_replay_source(refreshed_match)

            if not replay_source:
                TerminalUI.print_error(
                    "OpenDota finished parsing, but Valve replay coordinates remain unavailable."
                )
                return None

            return replay_source

        except ParseTimeoutError:
            print()
            TerminalUI.print_warning("Parse request took longer than expected. Please try again in a few moments.")
            return None
        except DotaCoreError as exc:
            print()
            TerminalUI.print_error(f"Failed to parse match: {exc}")
            return None

    def _prompt_output_settings(self) -> None:
        """Prompt user for target destination and decompression preferences."""
        TerminalUI.print_section("Download Configuration")

        custom_dir_str = TerminalUI.prompt_input(
            "Save directory",
            default=str(self.output_directory),
        )
        self.output_directory = Path(custom_dir_str).expanduser().resolve()

        self.auto_decompress = TerminalUI.prompt_confirm(
            "Decompress to playable .dem format after download?",
            default=self.auto_decompress,
        )

        if self.auto_decompress:
            self.keep_archive = TerminalUI.prompt_confirm(
                "Keep compressed archive alongside .dem?",
                default=self.keep_archive,
            )

    def _execute_download(self, source: ReplaySource, match: MatchDetails) -> None:
        """Perform download, decompression, and game folder integration."""
        TerminalUI.print_section("Downloading Replay")
        TerminalUI.print_info(f"Source: {paint(source.url, Style.GRAY)}")

        target_archive = self.output_directory / source.archive_filename
        final_file: Optional[Path] = None

        try:
            self.downloader.download(
                url=source.url,
                dest_path=target_archive,
                progress_cb=TerminalUI.render_download_progress,
            )
            print()  # newline after progress bar
            TerminalUI.print_success(f"Archive saved: {paint(str(target_archive), Style.CYAN)}")
            final_file = target_archive

            if self.auto_decompress:
                fmt = self.downloader.detect_format(target_archive)
                fmt_label = fmt.upper() if fmt != "unknown" else "archive"
                TerminalUI.print_info(f"Decompressing {paint(fmt_label, Style.CYAN)} archive into Dota 2 demo (.dem)...")
                decompressed_file = self.downloader.decompress(
                    archive_file=target_archive,
                    delete_archive=not self.keep_archive,
                )
                final_file = decompressed_file
                file_size_str = TerminalUI.format_bytes(decompressed_file.stat().st_size)
                TerminalUI.print_success(
                    f"Ready to watch: {paint(str(decompressed_file), Style.GREEN, bold=True)} ({file_size_str})"
                )

                # Inspect and display internal Valve demo header metadata
                build_info = self.downloader.inspect_demo_header(decompressed_file)
                tags = []
                if build_info.get("server_version"):
                    tags.append(f"Valve Build: {build_info['server_version']}")
                if build_info.get("engine_build"):
                    tags.append(f"Engine Build #{build_info['engine_build']}")
                if build_info.get("network_protocol"):
                    tags.append(f"Protocol: {build_info['network_protocol']}")
                if tags:
                    TerminalUI.print_info(f"Replay Binary Info: {paint(' | '.join(tags), Style.CYAN)}")

                if not self.keep_archive:
                    TerminalUI.print_info("Compressed archive file was cleaned up.")

            # Search Dota 2 installation and offer to copy to game folder
            if final_file and final_file.is_file():
                self._offer_copy_to_dota(final_file, match)

        except ReplayExpiredError as exc:
            print()
            TerminalUI.print_error(str(exc))
        except DotaCoreError as exc:
            print()
            TerminalUI.print_error(f"Download failed: {exc}")

    def _offer_copy_to_dota(self, replay_file: Path, match: MatchDetails) -> None:
        """Find Dota 2 installation, check patch compatibility, and prompt to copy."""
        dota_dir = DotaGameFinder.find_installation()
        if not dota_dir:
            return

        replays_dir = DotaGameFinder.get_replays_directory(dota_dir)
        TerminalUI.print_section("Dota 2 Game Integration")
        TerminalUI.print_info(f"Found Dota 2 installation: {paint(str(dota_dir), Style.CYAN)}")

        want_copy = TerminalUI.prompt_confirm(
            "Copy replay file to Dota 2 replays folder?",
            default=True,
        )
        if not want_copy:
            return

        # Check compatibility between replay and installed client
        installed_info = DotaGameFinder.read_steam_inf(dota_dir)
        replay_build_tag: Optional[str] = None
        if replay_file.name.endswith(".dem"):
            demo_meta = self.downloader.inspect_demo_header(replay_file)
            replay_build_tag = demo_meta.get("server_version")

        is_compatible, warning_msg = DotaGameFinder.check_compatibility(
            replay_version_tag=replay_build_tag,
            replay_patch=match.patch_display,
            installed_info=installed_info,
        )

        if not is_compatible and warning_msg:
            TerminalUI.print_warning(warning_msg)

        # Copy the file to game/dota/replays
        try:
            replays_dir.mkdir(parents=True, exist_ok=True)
            dest_file = replays_dir / replay_file.name
            shutil.copy2(replay_file, dest_file)
            TerminalUI.print_success(f"Copied to: {paint(str(dest_file), Style.GREEN, bold=True)}")
            demo_name = replay_file.stem if replay_file.name.endswith(".dem") else replay_file.name
            TerminalUI.print_info(
                f"Watch in-game via Watch -> Downloaded or console command: {paint(f'playdemo replays/{demo_name}', Style.CYAN)}"
            )
        except Exception as exc:
            TerminalUI.print_error(f"Could not copy replay to Dota 2 folder: {exc}")
