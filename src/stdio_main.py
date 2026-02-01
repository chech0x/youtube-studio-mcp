"""FastMCP stdio entrypoint for YouTube-MCP."""

from __future__ import annotations

from config.settings import settings
from main import mcp


def main() -> None:  # pragma: no cover
    mcp.run(
        transport="stdio",
        log_level=settings.LOG_LEVEL.lower(),
        show_banner=False,
    )


if __name__ == "__main__":  # pragma: no cover
    main()
