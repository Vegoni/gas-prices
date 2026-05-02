"""
Application configuration.

Loads settings from environment variables (via .env file).
This is the single source of truth for all config values —
no other module should read env vars directly.
"""

import os
from dotenv import load_dotenv

# Load .env file if it exists (won't override real env vars)
load_dotenv()


class Settings:
    """App-wide settings pulled from environment variables."""

    EIA_API_KEY: str = os.getenv("EIA_API_KEY", "")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./gas_prices.db")
    FETCH_INTERVAL_HOURS: int = int(os.getenv("FETCH_INTERVAL_HOURS", "168"))

    # EIA API base URL — unlikely to change, but good to have in one place
    EIA_BASE_URL: str = "https://api.eia.gov/v2"

    def validate(self) -> None:
        """Check that required settings are present. Call at startup."""
        if not self.EIA_API_KEY or self.EIA_API_KEY == "your_api_key_here":
            raise ValueError(
                "EIA_API_KEY is not set. "
                "Get a free key at https://www.eia.gov/opendata/register.php "
                "and add it to your .env file."
            )


# Single instance used throughout the app
settings = Settings()
