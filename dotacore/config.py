from pathlib import Path

OPENDOTA_BASE_URL = "https://api.opendota.com/api"
DEFAULT_USER_AGENT = "DotaCore/2.0 (Interactive CLI)"
REQUEST_TIMEOUT_SECONDS = 25
PARSE_POLL_INTERVAL_SECONDS = 3
PARSE_POLL_TIMEOUT_SECONDS = 180

# Replays are typically cleared by Valve within 14 days
VALVE_EXPIRY_THRESHOLD_DAYS = 14

# Default output directory for replays
DEFAULT_REPLAY_DIR = Path.cwd() / "replays"
