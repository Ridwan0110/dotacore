"""Backend package for DotaCore."""

from __future__ import annotations

from .api import OpenDotaClient
from .config import (
    DEFAULT_REPLAY_DIR,
    DEFAULT_USER_AGENT,
    OPENDOTA_BASE_URL,
    PARSE_POLL_INTERVAL_SECONDS,
    PARSE_POLL_TIMEOUT_SECONDS,
    REQUEST_TIMEOUT_SECONDS,
    VALVE_EXPIRY_THRESHOLD_DAYS,
)
from .downloader import Downloader
from .exceptions import (
    DotaCoreError,
    DownloadError,
    MatchNotFoundError,
    NetworkError,
    ParseTimeoutError,
    ProfileNotFoundError,
    RateLimitExceededError,
    ReplayExpiredError,
    ReplayNotAvailableError,
)
from .game_finder import DotaGameFinder
from .interfaces import BaseUI
from .models import MatchDetails, PlayerMatchSummary, PlayerScore, ReplaySource
from .service import DotaCoreService
from .workflow import WorkflowEngine

__all__ = [
    "BaseUI",
    "DEFAULT_REPLAY_DIR",
    "DEFAULT_USER_AGENT",
    "DotaCoreError",
    "DotaCoreService",
    "DotaGameFinder",
    "DownloadError",
    "Downloader",
    "MatchDetails",
    "MatchNotFoundError",
    "NetworkError",
    "OPENDOTA_BASE_URL",
    "OpenDotaClient",
    "PARSE_POLL_INTERVAL_SECONDS",
    "PARSE_POLL_TIMEOUT_SECONDS",
    "ParseTimeoutError",
    "PlayerMatchSummary",
    "PlayerScore",
    "ProfileNotFoundError",
    "REQUEST_TIMEOUT_SECONDS",
    "RateLimitExceededError",
    "ReplayExpiredError",
    "ReplayNotAvailableError",
    "ReplaySource",
    "VALVE_EXPIRY_THRESHOLD_DAYS",
    "WorkflowEngine",
]
