from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Optional

# Reconfigure stdout/stderr to UTF-8 on Windows to prevent charmap / cp1252 encoding errors
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Enable VT100 / ANSI escape sequences on Windows console
if os.name == "nt":
    try:
        os.system("")
    except Exception:
        pass


class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    GRAY = "\033[90m"


def paint(text: str, color: str = "", bold: bool = False) -> str:
    """Colorize text with optional bold styling."""
    prefix = f"{Style.BOLD if bold else ''}{color}"
    return f"{prefix}{text}{Style.RESET}" if prefix else text


class TerminalUI:
    """Interactive command-line interface utilities and display widgets."""

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

    @staticmethod
    def display_match_card(match) -> None:
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
        print(f"{border}\n")

    @classmethod
    def display_scoreboard(cls, match) -> None:
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
