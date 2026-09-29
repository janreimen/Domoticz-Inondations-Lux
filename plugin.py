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
            stations get a device (e.g. "Alzette, S&ucirc;re"). Leave empty for all stations.</li>
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
        <param field="Mode1" label="Update interval (minutes)" width="75px" required="true" default="15"/>
        <param field="Mode2" label="Station name filter (comma-separated, empty = all)" width="300px" required="false" default=""/>
        <param field="Mode6" label="Debug" width="150px">
            <options>
                <option label="None" value="0" default="true"/>
                <option label="Python Only" value="2"/>
                <option label="Basic Debugging" value="62"/>
                <option label="Basic+Messages" value="126"/>
                <option label="Queue" value="128"/>
                <option label="Connection" value="16"/>
                <option label="All" value="-1"/>
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

    # --- Domoticz callbacks ---

    def onStart(self):
        Domoticz.Log(f"Starting Luxembourg River Levels (inondations.lu) {PLUGIN_VERSION}")

        if Parameters["Mode6"] != "0":
            Domoticz.Debugging(int(Parameters["Mode6"]))
            Domoticz.Debug("Debug logging enabled")

        try:
            self.update_interval_minutes = max(1, int(Parameters["Mode1"]))
        except (KeyError, ValueError):
            self.update_interval_minutes = DEFAULT_UPDATE_INTERVAL_MINUTES

        self.name_filter = parse_name_filter(Parameters.get("Mode2", ""))

        selected = (Parameters.get("Mode3", "") or DEFAULT_DATA_SOURCE).strip().lower()
        if selected not in (DATA_SOURCE_CSV, DATA_SOURCE_API):
            Domoticz.Error(f"Unknown data source '{selected}', falling back to '{DEFAULT_DATA_SOURCE}'")
            selected = DEFAULT_DATA_SOURCE
        self.data_source = selected

        naming = (Parameters.get("Mode4", "") or DEFAULT_NAMING).strip().lower()
        if naming not in (NAMING_RIVER, NAMING_FEED):
            Domoticz.Error(f"Unknown device naming '{naming}', falling back to '{DEFAULT_NAMING}'")
            naming = DEFAULT_NAMING
        self.device_naming = naming

        if self.use_river_names():
            rivers_path = os.path.join(Parameters["HomeFolder"], RIVERS_FILENAME)
            try:
                self.river_index = load_river_index(rivers_path)
            except RiverTableError as ex:
                # Names only: safe to carry on, stations just keep their feed name.
                Domoticz.Error(f"{ex} - device names will fall back to the feed's own names")

        env_vars = load_env_file(os.path.join(Parameters["HomeFolder"], ENV_FILENAME))
        self.csv_url, self.api_url = resolve_source_urls(env_vars)
        Domoticz.Log(
            f"Data source: {self.data_source} "
            f"({self.csv_url if self.data_source == DATA_SOURCE_CSV else self.api_url})"
        )

        # Domoticz.Heartbeat sets the base callback interval; polling itself
        # is throttled against update_interval_minutes on top of it.
        Domoticz.Heartbeat(HEARTBEAT_SECONDS)

        unit_map_path = os.path.join(Parameters["HomeFolder"], UNIT_MAP_FILENAME)
        try:
            self.registry = StationUnitRegistry(unit_map_path)
        except RegistryError as ex:
            Domoticz.Error(f"Could not load station unit map ({unit_map_path}): {ex}")
            self.registry = None

        self.device_manager = DeviceManager(Devices)
        self.device_manager.ensure_status_device()

        self.next_poll = datetime.now()
        self.poll_and_update()

    def onStop(self):
        Domoticz.Debug("onStop called")

    def onConnect(self, Connection, Status, Description):
        pass

    def onMessage(self, Connection, Data):
        pass

    def onCommand(self, Unit, Command, Level, Hue):
        pass

    def onNotification(self, Name, Subject, Text, Status, Priority, Sound, ImageFile):
        pass

    def onDisconnect(self, Connection):
        pass

    def onHeartbeat(self):
        if datetime.now() >= self.next_poll:
            self.poll_and_update()
            self.next_poll = datetime.now() + timedelta(minutes=self.update_interval_minutes)

    # --- internals ---

    def use_river_names(self):
        return self.data_source == DATA_SOURCE_CSV and self.device_naming == NAMING_RIVER

    def fetch_stations(self):
        """Fetch + parse from whichever source is selected. Both branches
        return the same Station model, so everything downstream is
        source-agnostic."""
        if self.data_source == DATA_SOURCE_API:
            return parse_api(fetch_api(self.api_url))
        return parse_csv(fetch_csv(self.csv_url))

    def poll_and_update(self):
        if self.registry is None:
            Domoticz.Error("Station unit map failed to load at startup - skipping poll. Fix or remove the file and restart Domoticz.")
            return

        try:
            stations = self.fetch_stations()
        except SourceFetchError as ex:
            Domoticz.Error(f"Fetch from '{self.data_source}' source failed: {ex}")
            return

        if self.use_river_names():
            unresolved = apply_rivers(stations, self.river_index)
            new = sorted(n for n in unresolved if n not in self._reported_unmapped)
            if new:
                self._reported_unmapped.update(new)
                Domoticz.Log(
                    f"No river known for {len(new)} station(s), keeping the feed name "
                    f"(add them to {RIVERS_FILENAME} if you want a river prefix): " + ", ".join(new)
                )

        stations = filter_stations(stations, self.name_filter)

        updated = 0
        for station in stations:
            unit = self.registry.unit_for(station.name)
            if self.device_manager.upsert_station(station, unit):
                updated += 1

        if updated == 0:
            Domoticz.Error("No stations matched (check the station name filter parameter) - no devices updated")
            return

        self.device_manager.mark_update_succeeded(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        Domoticz.Debug(f"Updated {updated} station(s) via '{self.data_source}'")


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
    _plugin.onConnect(Connection, Status, Description)


def onMessage(Connection, Data):
    global _plugin
    _plugin.onMessage(Connection, Data)


def onCommand(Unit, Command, Level, Hue):
    global _plugin
    _plugin.onCommand(Unit, Command, Level, Hue)


def onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile):
    global _plugin
    _plugin.onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile)


def onDisconnect(Connection):
    global _plugin
    _plugin.onDisconnect(Connection)


def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()


