class DotaCoreError(Exception):
    """Base exception for all DotaCore operations."""


class MatchNotFoundError(DotaCoreError):
    """Raised when the specified match ID cannot be found on OpenDota."""


class ReplayExpiredError(DotaCoreError):
    """Raised when Valve has already purged the replay from their servers."""


class ReplayNotAvailableError(DotaCoreError):
    """Raised when replay metadata or download links are missing."""


class RateLimitExceededError(DotaCoreError):
    """Raised when OpenDota's API rate limits are reached."""


class NetworkError(DotaCoreError):
    """Raised when a network failure occurs during communication."""


class DownloadError(DotaCoreError):
    """Raised when an error occurs during replay download or decompression."""


class ParseTimeoutError(DotaCoreError):
    """Raised when waiting for OpenDota to parse a match exceeds the deadline."""
