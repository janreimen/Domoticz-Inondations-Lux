"""
Thin HTTP client for the Heichwaasser API (heichwaasser.lu).

An open-data reuse of the official river-level measurements
(Administration de la gestion de l'eau) that also power inondations.lu.

Uses only the standard library (urllib), deliberately avoiding a
`requests` dependency - nothing to pip-install on a Domoticz host.
"""

import json
import urllib.error
import urllib.request

from constants import REQUEST_TIMEOUT_SECONDS, RIVERS_ENDPOINT, USER_AGENT


class HeichwaasserApiError(Exception):
    """Raised for any network, HTTP, or JSON failure talking to the API."""


def fetch_rivers() -> list:
    """GET /rivers and return the parsed JSON payload (a list of rivers,
    each with a nested list of stations).

    Raises HeichwaasserApiError on failure, with the original exception
    preserved as __cause__ for debugging.
    """
    request = urllib.request.Request(RIVERS_ENDPOINT, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            raw = response.read().decode("utf-8")
    except (urllib.error.URLError, OSError) as ex:
        raise HeichwaasserApiError(f"request failed: {ex}") from ex

    try:
        return json.loads(raw)
    except json.JSONDecodeError as ex:
        raise HeichwaasserApiError(f"invalid JSON in response: {ex}") from ex
