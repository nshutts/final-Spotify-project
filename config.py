"""Load API keys from a local .env file into environment variables.

Keys are read lazily: importing this module never fails, so offline
calculator replay and saved-output checks work without credentials.
A missing key only raises an error when a live API call asks for it.
"""

import os

from dotenv import load_dotenv

# Reads .env from the project root if present; does nothing otherwise.
# Existing environment variables take precedence over .env values.
load_dotenv()

ANTHROPIC = "ANTHROPIC_API_KEY"
TYPESAFE = "TYPESAFE_API_KEY"  # key used for Jev


def get_key(name: str) -> str:
    """Return the key for `name`, or raise a clear error without revealing values."""
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(
            f"{name} is not set. Copy .env.example to .env and fill it in "
            "to make live API calls. Offline replay does not need it."
        )
    return value


def has_key(name: str) -> bool:
    """True if `name` is set, so callers can choose offline mode instead."""
    return bool(os.getenv(name, "").strip())
