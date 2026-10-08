from __future__ import annotations

from pathlib import Path
from typing import Optional

from .config import DEFAULT_REPLAY_DIR, VALVE_EXPIRY_THRESHOLD_DAYS
from .exceptions import (
    DotaCoreError,
    MatchNotFoundError,
    NetworkError,
    ParseTimeoutError,
    RateLimitExceededError,
    ReplayExpiredError,
)
from .interfaces import BaseUI
from .models import MatchDetails, ReplaySource
from .service import DotaCoreService


class WorkflowEngine:
    """
    Coordinates the match replay workflow using an injected BaseUI implementation
    and DotaCoreService backend.
    """

    def __init__(
        self,
        ui: BaseUI,
        service: Optional[DotaCoreService] = None,
        api_key: Optional[str] = None,
    ):
        self.ui = ui
        self.service = service or DotaCoreService(api_key=api_key)
        self.output_directory: Path = self.service.default_output_dir
        self.auto_decompress: bool = True
        self.keep_archive: bool = False

    def run(self) -> None:
        """Start the interactive single-match session."""
        self.ui.show_banner()
        try:
            self._run_single_match()
        except KeyboardInterrupt:
            self.ui.print_warning("Operation canceled by user. Goodbye!")

        self.ui.print_info("Done! Thanks for using DotaCore.")

    def _run_single_match(self) -> None:
        """Execute lookup, scoreboard display, and optional download for one match."""
        self.ui.print_section("Match Selection")

        match_id = self.ui.prompt_match_input()
        if match_id is None:
            return

        self.ui.print_info(f"Looking up match {match_id} on OpenDota...")

        try:
            match = self.service.fetch_match(match_id)
        except MatchNotFoundError as exc:
            self.ui.print_error(str(exc))
            return
        except RateLimitExceededError as exc:
            self.ui.print_warning(str(exc))
            return
        except NetworkError as exc:
            self.ui.print_error(f"Network error: {exc}")
            return

        # 1. Display Overview Card
        self.ui.display_match_card(match)

        # 2. Offer Scoreboard View
        want_scoreboard = self.ui.prompt_confirm("View detailed player scoreboard?", default=True)
        if want_scoreboard:
            self.ui.display_scoreboard(match)

        # 3. Check Replay Availability & Offer Download
        if match.age_days > VALVE_EXPIRY_THRESHOLD_DAYS:
            self.ui.print_warning(
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
        is_live, file_size = self.service.check_valve_replay_status(replay_source.url)
        if not is_live:
            self.ui.print_warning(
                f"Replay is no longer hosted on Valve's cluster ({replay_source.url}). "
                "Valve has purged the file from their servers."
            )
            return

        want_download = self.ui.prompt_confirm("Download match replay (.dem)?", default=True)
        if not want_download:
            self.ui.print_info("Replay download skipped.")
            return

        # Output options & download
        self._prompt_output_settings()
        self._execute_download(replay_source, match)

    def _obtain_replay_source(self, match: MatchDetails) -> Optional[ReplaySource]:
        """Resolve replay source, requesting OpenDota parse if needed."""
        replay_source = self.service.resolve_replay_source(match)

        if replay_source is not None:
            return replay_source

        self.ui.print_warning("Replay server cluster info is not yet registered for this match.")

        if match.age_days > VALVE_EXPIRY_THRESHOLD_DAYS:
            self.ui.print_error(
                "Because this match is older than Valve's retention window, "
                "requesting a parse cannot recover the purged replay file."
            )
            return None

        want_parse = self.ui.prompt_confirm(
            "Would you like to request OpenDota to parse this match to retrieve the replay?",
            default=True,
        )

        if not want_parse:
            self.ui.print_info("Parse request skipped.")
            return None

        try:
            job_id = self.service.trigger_parse_job(match.match_id)
            self.ui.print_info(f"Parse job #{job_id} enqueued.")
            self.service.wait_for_parse(job_id, tick_callback=self.ui.render_parse_tick)
            self.ui.print_success("Match parsing finished! Refreshing match details...")

            refreshed_match = self.service.fetch_match(match.match_id)
            replay_source = self.service.resolve_replay_source(refreshed_match)

            if not replay_source:
                self.ui.print_error(
                    "OpenDota finished parsing, but Valve replay coordinates remain unavailable."
                )
                return None

            return replay_source

        except ParseTimeoutError:
            self.ui.print_warning("Parse request took longer than expected. Please try again in a few moments.")
            return None
        except DotaCoreError as exc:
            self.ui.print_error(f"Failed to parse match: {exc}")
            return None

    def _prompt_output_settings(self) -> None:
        """Prompt user for target destination and decompression preferences."""
        self.ui.print_section("Download Configuration")

        custom_dir_str = self.ui.prompt_input(
            "Save directory",
            default=str(self.output_directory),
        )
        self.output_directory = Path(custom_dir_str).expanduser().resolve()

        self.auto_decompress = self.ui.prompt_confirm(
            "Decompress to playable .dem format after download?",
            default=self.auto_decompress,
        )

        if self.auto_decompress:
            self.keep_archive = self.ui.prompt_confirm(
                "Keep compressed archive alongside .dem?",
                default=self.keep_archive,
            )

    def _execute_download(self, source: ReplaySource, match: MatchDetails) -> None:
        """Perform download, decompression, and game folder integration."""
        self.ui.print_section("Downloading Replay")
        self.ui.print_info(f"Source: {source.url}")

        target_archive = self.output_directory / source.archive_filename
        final_file: Optional[Path] = None

        try:
            self.service.download_replay(
                url=source.url,
                dest_path=target_archive,
                progress_cb=self.ui.render_download_progress,
            )
            self.ui.print_success(f"Archive saved: {target_archive}")
            final_file = target_archive

            if self.auto_decompress:
                fmt = self.service.detect_format(target_archive)
                fmt_label = fmt.upper() if fmt != "unknown" else "archive"
                self.ui.print_info(f"Decompressing {fmt_label} archive into Dota 2 demo (.dem)...")
                decompressed_file = self.service.decompress_replay(
                    archive_file=target_archive,
                    delete_archive=not self.keep_archive,
                )
                final_file = decompressed_file
                file_size_str = self.ui.format_bytes(decompressed_file.stat().st_size)
                self.ui.print_success(
                    f"Ready to watch: {decompressed_file} ({file_size_str})"
                )

                # Inspect and display internal Valve demo header metadata
                build_info = self.service.inspect_demo_header(decompressed_file)
                tags = []
                if build_info.get("server_version"):
                    tags.append(f"Valve Build: {build_info['server_version']}")
                if build_info.get("engine_build"):
                    tags.append(f"Engine Build #{build_info['engine_build']}")
                if build_info.get("network_protocol"):
                    tags.append(f"Protocol: {build_info['network_protocol']}")
                if tags:
                    self.ui.print_info(f"Replay Binary Info: {' | '.join(tags)}")

                if not self.keep_archive:
                    self.ui.print_info("Compressed archive file was cleaned up.")

            # Search Dota 2 installation and offer to copy to game folder
            if final_file and final_file.is_file():
                self._offer_copy_to_dota(final_file, match)

        except ReplayExpiredError as exc:
            self.ui.print_error(str(exc))
        except DotaCoreError as exc:
            self.ui.print_error(f"Download failed: {exc}")

    def _offer_copy_to_dota(self, replay_file: Path, match: MatchDetails) -> None:
        """Find Dota 2 installation, check patch compatibility, and prompt to copy."""
        dota_dir = self.service.find_game_installation()
        if not dota_dir:
            return

        replays_dir = self.service.get_game_replays_directory(dota_dir)
        self.ui.print_section("Dota 2 Game Integration")
        self.ui.print_info(f"Found Dota 2 installation: {dota_dir}")

        want_copy = self.ui.prompt_confirm(
            "Copy replay file to Dota 2 replays folder?",
            default=True,
        )
        if not want_copy:
            return

        # Check compatibility between replay and installed client
        installed_info = self.service.read_steam_inf(dota_dir)
        replay_build_tag: Optional[str] = None
        if replay_file.name.endswith(".dem"):
            demo_meta = self.service.inspect_demo_header(replay_file)
            replay_build_tag = demo_meta.get("server_version")

        is_compatible, warning_msg = self.service.check_game_compatibility(
            replay_version_tag=replay_build_tag,
            replay_patch=match.patch_display,
            installed_info=installed_info,
        )

        if not is_compatible and warning_msg:
            self.ui.print_warning(warning_msg)

        # Copy the file to game/dota/replays
        try:
            dest_file = self.service.copy_replay_to_game(replay_file, dota_dir)
            self.ui.print_success(f"Copied to: {dest_file}")
            demo_name = replay_file.stem if replay_file.name.endswith(".dem") else replay_file.name
            self.ui.print_info(
                f"Watch in-game via Watch -> Downloaded or console command: playdemo replays/{demo_name}"
            )
        except Exception as exc:
            self.ui.print_error(f"Could not copy replay to Dota 2 folder: {exc}")
