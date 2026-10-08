from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Optional, Union

from backend.interfaces import BaseUI
from backend.models import MatchDetails, PlayerMatchSummary
from .styles import Style, paint


class TerminalUI(BaseUI):
    """
    Interactive command-line interface utilities and display widgets.
    Implements backend.interfaces.BaseUI for plug-and-play CLI integration.
    """

    @staticmethod
    def show_banner() -> None:
        banner = f"""
{Style.CYAN}{Style.BOLD}======================================================================
  [+] DOTACORE
      Interactive Match Archive & Scoreboard Client
======================================================================{Style.RESET}"""
        print(banner)

    @staticmethod
    def print_section(title: str) -> None:
        print(f"\n{Style.BOLD}{Style.CYAN}>> {title}{Style.RESET}")

    @staticmethod
    def print_info(message: str) -> None:
        print(f" {Style.BLUE}[i]{Style.RESET} {message}")

    @staticmethod
    def print_success(message: str) -> None:
        print(f" {Style.GREEN}[v]{Style.RESET} {message}")

    @staticmethod
    def print_warning(message: str) -> None:
        print(f" {Style.YELLOW}[!]{Style.RESET} {paint(message, Style.YELLOW)}")

    @staticmethod
    def print_error(message: str) -> None:
        print(f" {Style.RED}[x]{Style.RESET} {paint(message, Style.RED, bold=True)}")

    @staticmethod
    def parse_match_input(user_input: str) -> Optional[int]:
        """
        Extract numeric match ID from raw input or URL (OpenDota, Dotabuff, Stratz).
        Returns integer match_id or None if invalid.
        """
        clean = user_input.strip()
        if not clean:
            return None

        # Check for URL match (e.g. /matches/1234567890)
        url_match = re.search(r"matches/(\d+)", clean)
        if url_match:
            try:
                return int(url_match.group(1))
            except ValueError:
                return None

        # Check for plain integer match ID
        digits = re.search(r"\b(\d{7,12})\b", clean)
        if digits:
            try:
                return int(digits.group(1))
            except ValueError:
                return None

        return None

    @staticmethod
    def parse_profile_input(user_input: str) -> Optional[int]:
        """
        Extract numeric 32-bit account ID from raw input or URL
        (OpenDota player URL, Dotabuff player URL, Stratz player URL, Steam community profile,
        or prefixes like 'p 86745124', 'profile: 86745124', 'player 86745124').
        """
        clean = user_input.strip()
        if not clean:
            return None

        # 1. Check for player URL (e.g. /players/12345678)
        player_url_match = re.search(r"players/(\d+)", clean, re.IGNORECASE)
        if player_url_match:
            try:
                return int(player_url_match.group(1))
            except ValueError:
                return None

        # 2. Check for Steam64 profiles URL (e.g. steamcommunity.com/profiles/76561198086745124)
        steam64_url_match = re.search(r"profiles/(\d{17})", clean, re.IGNORECASE)
        if steam64_url_match:
            try:
                steam64 = int(steam64_url_match.group(1))
                return steam64 - 76561197960265728
            except ValueError:
                return None

        # 3. Check for explicit prefix: p 12345, profile: 12345, player 12345, id: 12345
        prefix_match = re.search(r"^(?:p|profile|player|account|id)\s*[:=]?\s*(\d+)$", clean, re.IGNORECASE)
        if prefix_match:
            try:
                val = int(prefix_match.group(1))
                if len(str(val)) == 17 and str(val).startswith("76561198"):
                    return val - 76561197960265728
                return val
            except ValueError:
                return None

        # 4. Check for 17-digit raw Steam64 ID
        if re.match(r"^76561198\d{9}$", clean):
            try:
                return int(clean) - 76561197960265728
            except ValueError:
                return None

        return None

    @classmethod
    def prompt_profile_id_input(cls) -> Optional[int]:
        """Prompt specifically for a player profile ID or URL."""
        cls.print_section("Profile Search")
        while True:
            raw = cls.prompt_input("Enter Player Profile ID or URL (or 'q' to cancel)")
            clean = raw.strip()
            if clean.lower() in ("q", "quit", "exit", "cancel"):
                return None

            p_id = cls.parse_profile_input(clean)
            if p_id is not None:
                return p_id

            if re.match(r"^\d{1,12}$", clean):
                try:
                    return int(clean)
                except ValueError:
                    pass

            cls.print_error(
                "Please enter a valid numeric Account ID (e.g. 86745124), "
                "Steam ID, or OpenDota/Dotabuff player URL."
            )

    @classmethod
    def prompt_match_input(cls) -> Optional[Union[int, tuple[str, int]]]:
        """
        Prompt user until a valid match ID, profile ID, or exit command is given.
        Returns:
            - int: match ID
            - ('profile', account_id): profile search request
            - None: quit
        """
        while True:
            raw = cls.prompt_input(
                "Enter Match ID/URL, Profile ID (prefix 'p' e.g. 'p 86745124'), or 'q' to quit"
            )
            clean = raw.strip()
            if clean.lower() in ("q", "quit", "exit"):
                return None

            if clean.lower() in ("p", "profile", "player"):
                profile_id = cls.prompt_profile_id_input()
                if profile_id is not None:
                    return ("profile", profile_id)
                continue

            profile_id = cls.parse_profile_input(clean)
            if profile_id is not None:
                return ("profile", profile_id)

            match_id = cls.parse_match_input(clean)
            if match_id is not None:
                return match_id

            cls.print_error(
                "Could not detect a valid Match ID or Profile ID.\n"
                "  - Match: Enter numeric match ID (e.g. 9032315904) or match URL.\n"
                "  - Profile: Enter 'p <id>' (e.g. p 86745124), player URL, or type 'p'."
            )

    @staticmethod
    def prompt_input(prompt_text: str, default: Optional[str] = None) -> str:
        """Prompt user with optional default value."""
        suffix = f" [{paint(default, Style.GRAY)}]: " if default is not None else ": "
        full_prompt = f"{Style.BOLD}{prompt_text}{Style.RESET}{suffix}"
        try:
            val = input(full_prompt).strip()
            return val if val else (default or "")
        except EOFError:
            return default or ""

    @staticmethod
    def prompt_confirm(prompt_text: str, default: bool = True) -> bool:
        """Prompt user for a yes/no response."""
        choice = "Y/n" if default else "y/N"
        full_prompt = f"{Style.BOLD}{prompt_text}{Style.RESET} [{choice}]: "
        try:
            raw = input(full_prompt).strip().lower()
            if not raw:
                return default
            return raw in ("y", "yes", "true", "1")
        except EOFError:
            return default

    @classmethod
    def display_profile_matches(
        cls,
        matches: list[PlayerMatchSummary],
        start_index: int = 1,
    ) -> None:
        """
        Render a clean table of player matches.
        Strict requirement: only show match ID, date, score, and winner (plus selection order).
        """
        if not matches:
            cls.print_info("No matches to display.")
            return

        sep = paint("-" * 62, Style.GRAY)
        print(f"\n{sep}")
        header = f" {'#':<4} {'Match ID':<13} {'Date':<13} {'Score':<13} {'Winner'}"
        print(paint(header, Style.BOLD))
        print(sep)

        for i, m in enumerate(matches, start=start_index):
            winner_color = Style.GREEN if m.radiant_win is True else (Style.RED if m.radiant_win is False else Style.GRAY)
            winner_str = paint(m.winner_name, winner_color, bold=True)
            row = (
                f" {i:<4} "
                f"{paint(str(m.match_id), Style.CYAN):<22} "
                f"{m.date_display:<13} "
                f"{m.score_display:<13} "
                f"{winner_str}"
            )
            print(row)

        print(f"{sep}\n")

    @classmethod
    def prompt_profile_match_selection(
        cls,
        total_loaded: int,
        can_load_more: bool = True,
    ) -> Optional[Union[int, str]]:
        """
        Prompt user to select a match order number, request to load more, or quit.
        Returns:
            - int: The 1-based order index of the selected match.
            - "more": If the user requested to load more matches.
            - None: If the user chose to quit.
        """
        more_hint = ", 'm' to load more" if can_load_more else ""
        prompt_msg = f"Select match order (1-{total_loaded}){more_hint}, or 'q' to quit"

        while True:
            raw = cls.prompt_input(prompt_msg).strip().lower()
            if raw in ("q", "quit", "exit"):
                return None
            if can_load_more and raw in ("m", "more", "load more", "load"):
                return "more"

            try:
                val = int(raw)
                if 1 <= val <= total_loaded:
                    return val
                cls.print_error(f"Please select a number between 1 and {total_loaded}.")
            except ValueError:
                cls.print_error(
                    f"Invalid selection. Enter 1-{total_loaded}{more_hint}, or 'q' to quit."
                )

    @staticmethod
    def display_match_card(match: MatchDetails) -> None:
        """Render a clean card displaying match overview information."""
        radiant_won = match.radiant_win is True
        winner_color = Style.GREEN if radiant_won else Style.RED
        winner_text = paint(f"{match.winner_name} Victory", winner_color, bold=True)

        score_text = ""
        if match.radiant_score is not None and match.dire_score is not None:
            r_score = paint(str(match.radiant_score), Style.GREEN, bold=True)
            d_score = paint(str(match.dire_score), Style.RED, bold=True)
            score_text = f" ({r_score} - {d_score})"

        border = paint("-" * 55, Style.GRAY)
        print(f"\n{border}")
        print(f" {paint('Match ID:', Style.BOLD)}  {paint(str(match.match_id), Style.CYAN, bold=True)}")
        print(f" {paint('Result:', Style.BOLD)}    {winner_text}{score_text}")
        print(f" {paint('Patch:', Style.BOLD)}     {paint(match.patch_display, Style.MAGENTA, bold=True)}")
        print(f" {paint('Mode:', Style.BOLD)}      {match.game_mode_name} ({match.lobby_type_name})")
        print(f" {paint('Duration:', Style.BOLD)}  {match.duration_formatted}")
        print(f" {paint('Played:', Style.BOLD)}    {match.relative_age_display}")
        print(f"{border}\\n")

    @classmethod
    def display_scoreboard(cls, match: MatchDetails) -> None:
        """Render full 10-player detailed scoreboard for Radiant and Dire."""
        if not match.players:
            cls.print_info("No player scoreboard details available for this match.")
            return

        def render_team_table(team_name: str, players: list, is_winner: bool, score: Optional[int]) -> None:
            status_text = "VICTORY" if is_winner else "DEFEAT"
            color = Style.GREEN if is_winner else Style.RED
            score_str = f" - {score} Kills" if score is not None else ""
            title = f"{team_name.upper()} {status_text}{score_str}"

            print()
            print(paint("=" * 110, color, bold=True))
            print(f" {paint(title, color, bold=True)}")
            print(paint("-" * 110, Style.GRAY))

            # Header row
            hdr = (
                f" {'Player':<16} {'Hero':<16} {'Lvl':<4} "
                f"{'K/D/A':<9} {'Net':<6} {'LH/DN':<8} {'GPM/XPM':<9} Items"
            )
            print(paint(hdr, Style.BOLD))
            print(paint("-" * 110, Style.GRAY))

            for p in players:
                p_name = (p.name[:15] + "…") if len(p.name) > 16 else p.name
                h_name = (p.hero_name[:15] + "…") if len(p.hero_name) > 16 else p.hero_name
                gpm_xpm = f"{p.gpm}/{p.xpm}"

                items_text = p.items_summary
                if p.neutral_item:
                    items_text += f" | [{p.neutral_item}]"

                row = (
                    f" {p_name:<16} "
                    f"{paint(h_name, Style.CYAN):<25} "
                    f"{p.level:<4} "
                    f"{paint(p.kda_str, Style.BOLD):<18} "
                    f"{paint(p.net_worth_str, Style.YELLOW):<15} "
                    f"{p.lh_dn_str:<8} "
                    f"{gpm_xpm:<9} "
                    f"{paint(items_text, Style.WHITE)}"
                )
                print(row)

            print(paint("=" * 110, color, bold=True))

        # Render Radiant
        render_team_table(
            team_name="Radiant",
            players=match.radiant_players,
            is_winner=match.radiant_win is True,
            score=match.radiant_score,
        )

        # Render Dire
        render_team_table(
            team_name="Dire",
            players=match.dire_players,
            is_winner=match.radiant_win is False,
            score=match.dire_score,
        )
        print()

    @staticmethod
    def format_bytes(num_bytes: float) -> str:
        """Format bytes into readable MB or GB string."""
        if num_bytes < 1024 * 1024:
            return f"{num_bytes / 1024:.1f} KB"
        if num_bytes < 1024 * 1024 * 1024:
            return f"{num_bytes / (1024 * 1024):.1f} MB"
        return f"{num_bytes / (1024 * 1024 * 1024):.2f} GB"

    @staticmethod
    def format_time(seconds: float) -> str:
        """Format seconds into MM:SS."""
        secs = int(max(0, seconds))
        mins, s = divmod(secs, 60)
        return f"{mins:02d}:{s:02d}"

    @classmethod
    def render_download_progress(
        cls,
        downloaded: int,
        total: Optional[int],
        speed_bps: float,
        eta_seconds: Optional[float],
        bar_width: int = 24,
    ) -> None:
        """Render download progress bar."""
        speed_str = f"{cls.format_bytes(speed_bps)}/s"

        if total and total > 0:
            fraction = min(1.0, downloaded / total)
            filled = int(fraction * bar_width)
            empty = bar_width - filled
            bar = f"{Style.CYAN}{'#' * filled}{Style.GRAY}{'-' * empty}{Style.RESET}"
            pct_str = f"{fraction * 100:5.1f}%"
            size_str = f"{cls.format_bytes(downloaded)} / {cls.format_bytes(total)}"
            eta_str = f"ETA: {cls.format_time(eta_seconds or 0)}"
            line = f"\r [{bar}] {pct_str} ({size_str}) | {speed_str} | {eta_str} "
        else:
            bar = f"{Style.CYAN}{'=' * bar_width}{Style.RESET}"
            line = f"\r [{bar}] {cls.format_bytes(downloaded)} | {speed_str} "

        sys.stdout.write(line)
        sys.stdout.flush()

    @classmethod
    def render_parse_tick(cls, elapsed_sec: int) -> None:
        """Show parse waiting indicator."""
        spinner_chars = ["|", "/", "-", "\\"]
        char = spinner_chars[(elapsed_sec // 2) % len(spinner_chars)]
        sys.stdout.write(f"\r [{Style.CYAN}{char}{Style.RESET}] Waiting for OpenDota parse queue... ({elapsed_sec}s)")
        sys.stdout.flush()
