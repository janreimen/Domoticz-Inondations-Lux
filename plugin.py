#!/usr/bin/env python3

"""
<plugin key="InondationsLux" name="Luxembourg River Levels (inondations.lu)" author="Jan Reimen" version="0.1.1" externallink="https://github.com/janreimen/Domoticz-Inondations-Lux">

    <description>
        <h2>Domoticz-Inondations-Lux</h2>
        <p>Creates one Custom sensor per river-gauging station in Luxembourg, showing
        the current water level, refreshed roughly every 15 minutes.</p>

        <h3>Data source</h3>
        <ul style="list-style-type:square">
            <li><b>Official CSV</b> (default, recommended): the Water-Levels-LocalTime.csv feed
            published directly by the Administration de la gestion de l'eau / CTIE - the same
            data <a href="https://www.inondations.lu">www.inondations.lu</a> shows. The unit
            (cm or m) is read per station.</li>

            <li><b>heichwaasser.lu API</b> (alternative): an open-data JSON reuse of the same
            measurements. Use it if the CSV is unreachable from your network. Known to label
            the Esch-Sure reservoir (metres) as cm - see README.md.</li>
        </ul>

        <p>Both URLs live in a <code>.env</code> file in the plugin folder (see
        <code>.env.sample</code>); built-in defaults apply if it is missing.</p>

        <h3>Configuration</h3>
        <ul style="list-style-type:square">
            <li>Update interval: how often the plugin polls the source, in minutes.</li>

            <li>Device names (CSV only): the CSV has no river column, so "River - Station" names
            come from the bundled <code>station_rivers.json</code> where the river is known;
            other stations keep the feed's own name.</li>

            <li>Station name filter: optional comma-separated substrings to limit which
            stations get a device (e.g. "Alzette, Sûre"). Leave empty for all stations.</li>

            <li>Debug: cumulative bitmask controlling the categories of diagnostic logging.
            "All" enables all debug categories including full plugin operational logging.</li>
        </ul>
    </description>

    <params>
        <param field="Mode3" label="Data source" width="220px">
            <options>
                <option label="Official CSV (recommended)" value="csv" default="true"/>
                <option label="heichwaasser.lu API" value="api"/>
            </options>
        </param>

        <param field="Mode4" label="Device names (CSV source)" width="260px">
            <options>
                <option label="River - Station (where known)" value="river" default="true"/>
                <option label="Name as published in the feed" value="feed"/>
            </options>
        </param>

        <param field="Mode1" label="Update interval (minutes)" width="75px"
               required="true" default="15"/>

        <param field="Mode2" label="Station name filter (comma-separated, empty = all)"
               width="300px" required="false" default=""/>

        <param field="Mode6" label="Debug" width="300px">
            <options>
                <option label="None" value="0" default="true"/>

                <option label="Basic" value="1"/>
                <option label="Python" value="2"/>
                <option label="Connection" value="4"/>
                <option label="Messages" value="8"/>
                <option label="Queue" value="16"/>
                <option label="Operational" value="32"/>

                <option label="Basic + Python" value="3"/>
                <option label="Python + Connection" value="6"/>
                <option label="Python + Messages" value="10"/>
                <option label="Python + Queue" value="18"/>
                <option label="Connection + Messages" value="12"/>
                <option label="Messages + Queue" value="24"/>

                <option label="Python + Connection + Messages" value="14"/>
                <option label="Python + Connection + Queue" value="22"/>
                <option label="Python + Messages + Queue" value="26"/>
                <option label="Connection + Messages + Queue" value="28"/>

                <option label="Python + Connection + Messages + Queue" value="30"/>

                <option label="All" value="63"/>
            </options>
        </param>
    </params>

</plugin>
"""

import os
from datetime import datetime, timedelta

import Domoticz

from api_client import fetch_api

from constants import (
    DATA_SOURCE_API,
    DATA_SOURCE_CSV,
    DEFAULT_API_URL,
    DEFAULT_CSV_URL,
    DEFAULT_DATA_SOURCE,
    DEFAULT_NAMING,
    DEFAULT_UPDATE_INTERVAL_MINUTES,
    ENV_FILENAME,
    HEARTBEAT_SECONDS,
    NAMING_FEED,
    NAMING_RIVER,
    PLUGIN_VERSION,
    RIVERS_FILENAME,
    UNIT_MAP_FILENAME,
)

from csv_client import fetch_csv
from devices import DeviceManager
from env_config import load_env_file, resolve_source_urls
from errors import SourceFetchError
from registry import RegistryError, StationUnitRegistry
from rivers import RiverIndex, RiverTableError, load_river_index
from stations import apply_rivers, filter_stations, parse_api, parse_csv
from utils import parse_name_filter


# ============================================================================
# Debug bitmask
# ============================================================================
#
# Mode6 is a cumulative bitmask.
#
# Bit 0 = Basic
# Bit 1 = Python
# Bit 2 = Connection
# Bit 3 = Messages
# Bit 4 = Queue
# Bit 5 = Plugin operational logging
#
# Examples:
#
#   Python                         = 2
#   Python + Connection            = 6
#   Python + Messages              = 10
#   Python + Connection + Messages = 14
#   Python + Queue                 = 18
#   All                            = 63
#
# The plugin uses the selected mask for its own diagnostic logging.
# Domoticz.Debugging() is also configured with the selected mask.
#

DEBUG_BASIC = 1
DEBUG_PYTHON = 2
DEBUG_CONNECTION = 4
DEBUG_MESSAGES = 8
DEBUG_QUEUE = 16
DEBUG_OPERATIONAL = 32

DEBUG_ALL = (
    DEBUG_BASIC
    | DEBUG_PYTHON
    | DEBUG_CONNECTION
    | DEBUG_MESSAGES
    | DEBUG_QUEUE
    | DEBUG_OPERATIONAL
)


class InondationsPlugin:
    """Holds all plugin state; plugin.py's module-level functions below
    are just the Domoticz callback contract delegating into this class.
    """

    def __init__(self):
        self.update_interval_minutes = DEFAULT_UPDATE_INTERVAL_MINUTES
        self.name_filter = None

        self.data_source = DEFAULT_DATA_SOURCE
        self.device_naming = DEFAULT_NAMING

        self.river_index = RiverIndex({})
        self._reported_unmapped = set()

        self.csv_url = DEFAULT_CSV_URL
        self.api_url = DEFAULT_API_URL

        self.next_poll = datetime.now()

        self.device_manager = None
        self.registry = None

        # Debug mask selected through Mode6.
        self.debug_mask = 0

    # ========================================================================
    # Logging helpers
    # ========================================================================

    def debug_enabled(self, flag):
        """Return True when a particular debug category is enabled."""

        return bool(self.debug_mask & flag)

    def debug(self, message, flag=DEBUG_BASIC):
        """Emit a Domoticz debug message when the selected mask enables it."""

        if self.debug_enabled(flag):
            Domoticz.Debug(message)

    def operational(self, message):
        """Emit detailed plugin operational logging.

        Operational logging is deliberately a separate bit so that
        'All' provides a complete execution trace without requiring
        every normal debug message to be enabled.
        """

        if self.debug_enabled(DEBUG_OPERATIONAL):
            Domoticz.Debug(f"[Operational] {message}")

    # ========================================================================
    # Domoticz callbacks
    # ========================================================================

    def onStart(self):
        Domoticz.Log(
            f"Starting Luxembourg River Levels (inondations.lu) "
            f"{PLUGIN_VERSION}"
        )

        # --------------------------------------------------------------------
        # Debug configuration
        # --------------------------------------------------------------------

        try:
            self.debug_mask = int(Parameters.get("Mode6", "0"))
        except (ValueError, TypeError):
            self.debug_mask = 0

        # Only accept the masks defined by this plugin.
        if self.debug_mask < 0:
            self.debug_mask = DEBUG_ALL

        self.debug(
            f"Debug mask enabled: {self.debug_mask} "
            f"(0b{self.debug_mask:06b})",
            DEBUG_BASIC,
        )

        if self.debug_mask:
            Domoticz.Debugging(self.debug_mask)

        self.operational(
            f"Debug configuration: mask={self.debug_mask}, "
            f"binary=0b{self.debug_mask:06b}"
        )

        # --------------------------------------------------------------------
        # Update interval
        # --------------------------------------------------------------------

        try:
            self.update_interval_minutes = max(
                1,
                int(Parameters["Mode1"]),
            )
        except (KeyError, ValueError):
            self.update_interval_minutes = (
                DEFAULT_UPDATE_INTERVAL_MINUTES
            )

        self.operational(
            f"Update interval: "
            f"{self.update_interval_minutes} minute(s)"
        )

        # --------------------------------------------------------------------
        # Station filter
        # --------------------------------------------------------------------

        self.name_filter = parse_name_filter(
            Parameters.get("Mode2", "")
        )

        self.operational(
            f"Station filter: {self.name_filter!r}"
        )

        # --------------------------------------------------------------------
        # Data source
        # --------------------------------------------------------------------

        selected = (
            Parameters.get("Mode3", "")
            or DEFAULT_DATA_SOURCE
        ).strip().lower()

        if selected not in (
            DATA_SOURCE_CSV,
            DATA_SOURCE_API,
        ):
            Domoticz.Error(
                f"Unknown data source '{selected}', "
                f"falling back to '{DEFAULT_DATA_SOURCE}'"
            )
            selected = DEFAULT_DATA_SOURCE

        self.data_source = selected

        # --------------------------------------------------------------------
        # Device naming
        # --------------------------------------------------------------------

        naming = (
            Parameters.get("Mode4", "")
            or DEFAULT_NAMING
        ).strip().lower()

        if naming not in (
            NAMING_RIVER,
            NAMING_FEED,
        ):
            Domoticz.Error(
                f"Unknown device naming '{naming}', "
                f"falling back to '{DEFAULT_NAMING}'"
            )
            naming = DEFAULT_NAMING

        self.device_naming = naming

        # --------------------------------------------------------------------
        # River index
        # --------------------------------------------------------------------

        if self.use_river_names():
            rivers_path = os.path.join(
                Parameters["HomeFolder"],
                RIVERS_FILENAME,
            )

            self.operational(
                f"Loading river index from '{rivers_path}'"
            )

            try:
                self.river_index = load_river_index(
                    rivers_path
                )

                self.operational(
                    "River index loaded successfully"
                )

            except RiverTableError as ex:
                # Names only: safe to carry on, stations just keep
                # their feed name.
                Domoticz.Error(
                    f"{ex} - device names will fall back "
                    f"to the feed's own names"
                )

        # --------------------------------------------------------------------
        # Environment / source URLs
        # --------------------------------------------------------------------

        env_path = os.path.join(
            Parameters["HomeFolder"],
            ENV_FILENAME,
        )

        self.operational(
            f"Loading environment configuration from '{env_path}'"
        )

        env_vars = load_env_file(env_path)

        self.csv_url, self.api_url = resolve_source_urls(
            env_vars
        )

        Domoticz.Log(
            f"Data source: {self.data_source} "
            f"({self.csv_url if self.data_source == DATA_SOURCE_CSV else self.api_url})"
        )

        self.operational(
            f"CSV URL: {self.csv_url}"
        )

        self.operational(
            f"API URL: {self.api_url}"
        )

        # --------------------------------------------------------------------
        # Heartbeat
        # --------------------------------------------------------------------

        Domoticz.Heartbeat(HEARTBEAT_SECONDS)

        self.operational(
            f"Heartbeat configured: {HEARTBEAT_SECONDS} second(s)"
        )

        # --------------------------------------------------------------------
        # Station unit registry
        # --------------------------------------------------------------------

        unit_map_path = os.path.join(
            Parameters["HomeFolder"],
            UNIT_MAP_FILENAME,
        )

        self.operational(
            f"Loading station unit map from '{unit_map_path}'"
        )

        try:
            self.registry = StationUnitRegistry(
                unit_map_path
            )

            self.operational(
                "Station unit map loaded successfully"
            )

        except RegistryError as ex:
            Domoticz.Error(
                f"Could not load station unit map "
                f"({unit_map_path}): {ex}"
            )

            self.registry = None

        # --------------------------------------------------------------------
        # Device manager
        # --------------------------------------------------------------------

        self.device_manager = DeviceManager(Devices)

        self.operational(
            "Device manager initialized"
        )

        self.device_manager.ensure_status_device()

        self.operational(
            "Status device verified"
        )

        # --------------------------------------------------------------------
        # Initial poll
        # --------------------------------------------------------------------

        self.next_poll = datetime.now()

        self.operational(
            f"Initial poll scheduled immediately: "
            f"{self.next_poll:%Y-%m-%d %H:%M:%S}"
        )

        self.poll_and_update()

    def onStop(self):
        self.debug(
            "onStop called",
            DEBUG_BASIC,
        )

        self.operational(
            "Plugin stopping"
        )

    def onConnect(self, Connection, Status, Description):
        self.debug(
            f"onConnect: Status={Status}, "
            f"Description={Description}",
            DEBUG_CONNECTION,
        )

    def onMessage(self, Connection, Data):
        self.debug(
            f"onMessage: Data={Data}",
            DEBUG_MESSAGES,
        )

    def onCommand(self, Unit, Command, Level, Hue):
        self.debug(
            f"onCommand: Unit={Unit}, "
            f"Command={Command}, "
            f"Level={Level}, "
            f"Hue={Hue}",
            DEBUG_MESSAGES,
        )

    def onNotification(
        self,
        Name,
        Subject,
        Text,
        Status,
        Priority,
        Sound,
        ImageFile,
    ):
        self.debug(
            f"onNotification: Name={Name}, "
            f"Subject={Subject}, "
            f"Status={Status}",
            DEBUG_MESSAGES,
        )

    def onDisconnect(self, Connection):
        self.debug(
            f"onDisconnect: Connection={Connection}",
            DEBUG_CONNECTION,
        )

    def onHeartbeat(self):
        now = datetime.now()

        self.operational(
            f"Heartbeat received: "
            f"now={now:%Y-%m-%d %H:%M:%S}, "
            f"next_poll={self.next_poll:%Y-%m-%d %H:%M:%S}"
        )

        if now < self.next_poll:
            self.operational(
                "Heartbeat received but poll interval "
                "has not expired"
            )
            return

        self.operational(
            "Heartbeat triggered poll"
        )

        self.poll_and_update()

        self.next_poll = datetime.now() + timedelta(
            minutes=self.update_interval_minutes
        )

        self.operational(
            f"Poll finished; next poll scheduled for "
            f"{self.next_poll:%Y-%m-%d %H:%M:%S}"
        )

    # ========================================================================
    # Internals
    # ========================================================================

    def use_river_names(self):
        return (
            self.data_source == DATA_SOURCE_CSV
            and self.device_naming == NAMING_RIVER
        )

    def fetch_stations(self):
        """Fetch + parse from whichever source is selected.

        Both branches return the same Station model, so everything
        downstream is source-agnostic.
        """

        self.operational(
            f"Fetching stations using source '{self.data_source}'"
        )

        if self.data_source == DATA_SOURCE_API:
            self.debug(
                f"Fetching API source: {self.api_url}",
                DEBUG_CONNECTION,
            )

            stations = parse_api(
                fetch_api(self.api_url)
            )

        else:
            self.debug(
                f"Fetching CSV source: {self.csv_url}",
                DEBUG_CONNECTION,
            )

            stations = parse_csv(
                fetch_csv(self.csv_url)
            )

        self.operational(
            f"Fetched and parsed {len(stations)} station(s)"
        )

        return stations

    def poll_and_update(self):
        """Fetch current station data and update Domoticz devices."""

        self.operational(
            "poll_and_update() started"
        )

        if self.registry is None:
            Domoticz.Error(
                "Station unit map failed to load at startup - "
                "skipping poll. Fix or remove the file and "
                "restart Domoticz."
            )

            self.operational(
                "Poll aborted because station unit registry "
                "is unavailable"
            )

            return

        # --------------------------------------------------------------------
        # Fetch
        # --------------------------------------------------------------------

        try:
            stations = self.fetch_stations()

        except SourceFetchError as ex:
            Domoticz.Error(
                f"Fetch from '{self.data_source}' "
                f"source failed: {ex}"
            )

            self.operational(
                f"Poll aborted because source fetch failed: {ex}"
            )

            return

        # --------------------------------------------------------------------
        # River names
        # --------------------------------------------------------------------

        if self.use_river_names():
            self.operational(
                "Applying river names to stations"
            )

            unresolved = apply_rivers(
                stations,
                self.river_index,
            )

            new = sorted(
                n
                for n in unresolved
                if n not in self._reported_unmapped
            )

            if new:
                self._reported_unmapped.update(new)

                Domoticz.Log(
                    f"No river known for {len(new)} station(s), "
                    f"keeping the feed name "
                    f"(add them to {RIVERS_FILENAME} "
                    f"if you want a river prefix): "
                    + ", ".join(new)
                )

                self.operational(
                    f"Unresolved river mappings: {len(new)}"
                )

            else:
                self.operational(
                    "All stations have a known river mapping"
                )

        # --------------------------------------------------------------------
        # Filter
        # --------------------------------------------------------------------

        before_filter = len(stations)

        stations = filter_stations(
            stations,
            self.name_filter,
        )

        self.operational(
            f"Station filtering: "
            f"{before_filter} -> {len(stations)} station(s)"
        )

        # --------------------------------------------------------------------
        # Device updates
        # --------------------------------------------------------------------

        updated = 0

        for station in stations:
            unit = self.registry.unit_for(
                station.name
            )

            self.debug(
                f"Station '{station.name}' "
                f"mapped to unit {unit}",
                DEBUG_MESSAGES,
            )

            self.operational(
                f"Updating station '{station.name}' "
                f"(unit {unit})"
            )

            if self.device_manager.upsert_station(
                station,
                unit,
            ):
                updated += 1

        # --------------------------------------------------------------------
        # No updates
        # --------------------------------------------------------------------

        if updated == 0:
            Domoticz.Error(
                "No stations matched "
                "(check the station name filter parameter) "
                "- no devices updated"
            )

            self.operational(
                "Poll completed without updating any station"
            )

            return

        # --------------------------------------------------------------------
        # Success
        # --------------------------------------------------------------------

        timestamp = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        self.device_manager.mark_update_succeeded(
            timestamp
        )

        Domoticz.Log(
            f"Updated {updated} station(s) "
            f"via '{self.data_source}'"
        )

        self.operational(
            f"Poll completed successfully: "
            f"{updated} station(s) updated"
        )


# ============================================================================
# Domoticz plugin callback contract
# ============================================================================

global _plugin

_plugin = InondationsPlugin()


def onStart():
    global _plugin
    _plugin.onStart()


def onStop():
    global _plugin
    _plugin.onStop()


def onConnect(Connection, Status, Description):
    global _plugin
    _plugin.onConnect(
        Connection,
        Status,
        Description,
    )


def onMessage(Connection, Data):
    global _plugin
    _plugin.onMessage(
        Connection,
        Data,
    )


def onCommand(Unit, Command, Level, Hue):
    global _plugin
    _plugin.onCommand(
        Unit,
        Command,
        Level,
        Hue,
    )


def onNotification(
    Name,
    Subject,
    Text,
    Status,
    Priority,
    Sound,
    ImageFile,
):
    global _plugin
    _plugin.onNotification(
        Name,
        Subject,
        Text,
        Status,
        Priority,
        Sound,
        ImageFile,
    )


def onDisconnect(Connection):
    global _plugin
    _plugin.onDisconnect(
        Connection,
    )


def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()
