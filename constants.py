"""
Shared constants for the Domoticz-Inondations-Lux plugin.

Kept in one place, separate from any Domoticz import, so both the plugin code and the offline test suite can use the same values. 
"""

# Built-in fallbacks for the two data-source URLs. The real values are
# normally read from the plugin's .env file (see env_config.py and
# .env.sample); these only apply if that file or a key in it is missing.
DEFAULT_CSV_URL = "https://inondations.public.lu/dam-assets/ctie/datas/Water-Levels-LocalTime.csv"
DEFAULT_API_URL = "https://heichwaasser.lu/api/v1/rivers"

ENV_FILENAME = ".env"
ENV_KEY_CSV_URL = "INONDATIONS_CSV_URL"
ENV_KEY_API_URL = "HEICHWAASSER_API_URL"

# Selectable via the plugin's "Data source" hardware parameter (Mode3).
DATA_SOURCE_CSV = "csv"
DATA_SOURCE_API = "api"
DEFAULT_DATA_SOURCE = DATA_SOURCE_CSV

PLUGIN_VERSION = "0.1.1"

# The CSV carries several days of 15-minute history for every station (only the newest reading is used), 
# so it is much larger than the API response and gets a somewhat generous timeout. CSV mode only: 
# how devices are named. "river" builds "<River> - <Station>" from station_rivers.json where the river 
# is known (the CSV has no river column); "feed" uses the name exactly as published. Identity is always
# the feed name either way, so this never creates duplicate devices.
RIVERS_FILENAME = "station_rivers.json"
NAMING_RIVER = "river"
NAMING_FEED = "feed"
DEFAULT_NAMING = NAMING_RIVER

REQUEST_TIMEOUT_SECONDS = 20
USER_AGENT = "Domoticz-Inondations-Lux/{}".format(PLUGIN_VERSION)

DEFAULT_UPDATE_INTERVAL_MINUTES = 15  # both sources refresh roughly every 15 min
HEARTBEAT_SECONDS = 20  # Domoticz's own callback interval; polling is throttled on top of it

# Neither source gives a usable stable id (the CSV has none at all, and
# the API's ids aren't comparable to CSV names), so for BOTH sources a
# station name -> Unit mapping is persisted to disk (see registry.py).
# That keeps devices stable across restarts even if row order changes.
UNIT_MAP_FILENAME = "station_units.json"

# Reserved Domoticz Unit for the plugin-wide "last successful update"
# status sensor. MAX_UNIT is capped one below this so the registry never
# allocates it to a station.
LAST_UPDATE_UNIT = 255
LAST_UPDATE_DEVICE_ID = "last_update"

MIN_UNIT = 1
MAX_UNIT = 254
