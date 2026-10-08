from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Union

from .models import MatchDetails, PlayerMatchSummary, ReplaySource


class BaseUI(ABC):
    """
    Abstract UI interface.
    Any UI frontend (CLI, Web, GUI, TUI, Bot, etc.) implements this interface
    to plug seamlessly into the DotaCore WorkflowEngine.
    """

    @abstractmethod
    def show_banner(self) -> None:
        """Display introductory application banner or header."""
        pass

    @abstractmethod
    def print_section(self, title: str) -> None:
        """Render a section header."""
        pass

    @abstractmethod
    def print_info(self, message: str) -> None:
        """Display an informational message."""
        pass

    @abstractmethod
    def print_success(self, message: str) -> None:
        """Display a success message."""
        pass

    @abstractmethod
    def print_warning(self, message: str) -> None:
        """Display a warning message."""
        pass

    @abstractmethod
    def print_error(self, message: str) -> None:
        """Display an error message."""
        pass

    @abstractmethod
    def prompt_match_input(self) -> Optional[Union[int, tuple[str, int]]]:
        """Prompt user for match ID/URL or profile search, returning parsed target or None to exit."""
        pass

    @abstractmethod
    def display_match_card(self, match: MatchDetails) -> None:
        """Display overview card for the match."""
        pass

    @abstractmethod
    def prompt_confirm(self, prompt_text: str, default: bool = True) -> bool:
        """Prompt user for a yes/no confirmation."""
        pass

    @abstractmethod
    def prompt_input(self, prompt_text: str, default: Optional[str] = None) -> str:
        """Prompt user for text input with optional default value."""
        pass

    @abstractmethod
    def display_scoreboard(self, match: MatchDetails) -> None:
        """Display detailed player scoreboard."""
        pass

    @abstractmethod
    def render_download_progress(
        self,
        downloaded: int,
        total: Optional[int],
        speed_bps: float,
        eta_seconds: Optional[float],
    ) -> None:
        """Display live download progress."""
        pass

    @abstractmethod
    def render_parse_tick(self, elapsed_sec: int) -> None:
        """Display waiting tick during OpenDota parse queue polling."""
        pass

    @abstractmethod
    def format_bytes(self, num_bytes: float) -> str:
        """Format raw byte counts to human-readable strings (KB/MB/GB)."""
        pass

    def display_profile_matches(
        self,
        matches: list[PlayerMatchSummary],
        start_index: int = 1,
    ) -> None:
        """Display list of player matches showing match ID, date, score, winner."""
        pass

    def prompt_profile_match_selection(
        self,
        total_loaded: int,
        can_load_more: bool = True,
    ) -> Optional[Union[int, str]]:
        """
        Prompt user to select a match by order (1..total_loaded),
        or request to load more ('more' / 'm'), or quit ('q' / None).
        """
        return None
