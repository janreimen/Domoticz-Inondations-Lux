"""
Minimal, dependency-free .env support for the two data-source URLs.

Deliberately not python-dotenv: this plugin has no third-party
dependencies, and the format needed is trivial - KEY=VALUE lines,
optional surrounding quotes, '#' comments, blank lines ignored.

Precedence (the usual dotenv order): a real process environment
variable wins over the .env file, which wins over the built-in
defaults in constants.py. A missing .env is a normal, supported
setup - not an error.
"""

import os
from typing import Dict, Tuple

from constants import DEFAULT_API_URL, DEFAULT_CSV_URL, ENV_KEY_API_URL, ENV_KEY_CSV_URL


def parse_env_text(text: str) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue  # malformed line: ignore it rather than fail the whole file
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if key:
            result[key] = value
    return result


def load_env_file(path: str) -> Dict[str, str]:
    """Parse the .env file at `path`; {} if it doesn't exist or can't be
    read (config falls back to defaults - a bad .env line is far less
    dangerous than a bad station-unit map, so this is deliberately lenient).
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            return parse_env_text(f.read())
    except OSError:
        return {}


def resolve_source_urls(env_vars: Dict[str, str]) -> Tuple[str, str]:
    """Return (csv_url, api_url) using env var > .env file > default."""
    csv_url = os.environ.get(ENV_KEY_CSV_URL) or env_vars.get(ENV_KEY_CSV_URL) or DEFAULT_CSV_URL
    api_url = os.environ.get(ENV_KEY_API_URL) or env_vars.get(ENV_KEY_API_URL) or DEFAULT_API_URL
    return csv_url, api_url
