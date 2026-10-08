## Version: v0.1.0

Initial release of DotaCore, an interactive command-line utility to query Dota 2 match metadata, inspect 10-player scoreboards, and download and decompress Source 2 match replays directly from Valve CDN servers.

## Added
- Interactive terminal interface for match lookup and scoreboard visualization (feature)
- Match ID and URL parser supporting direct IDs, OpenDota, Dotabuff, and Stratz links (feature)
- OpenDota API client for querying match metadata, player statistics, and requesting parse jobs (feature)
- Pre-flight availability check verifying replay hosting on Valve edge CDN servers (feature)
- Streaming replay downloader with real-time transfer progress, speed, and ETA metrics (feature)
- Magic byte format detector and decompression pipeline supporting Zstandard, BZip2, and GZip (feature)
- Source 2 demo binary header parser extracting server build tag, engine build number, and network protocol (feature)
- Cross-platform Steam and Dota 2 installation finder for Windows, macOS, and Linux (feature)
- Client compatibility checker comparing demo build versions against local steam.inf (feature)
- Replay installation workflow copying decompressed demos directly into game/dota/replays (feature)
- Strongly typed data models for match details, player scoreboards, and replay sources (improvement)
- Structured domain exception hierarchy for API, network, and download error handling (improvement)
- Initial project configuration, dependencies, documentation, and MIT licensing (misc)
