"""
Shared exception types for the plugin's data-source clients.
"""


class SourceFetchError(Exception):
    """Raised for any network, HTTP, decoding, or JSON failure while
    fetching a data source (CSV or API), so plugin.py needs just one
    except clause regardless of which source is active.
    """
