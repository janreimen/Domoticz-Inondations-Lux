#!/usr/bin/env python3
"""
Offline test suite for Domoticz-InondationsLu.

Run directly with `python3 tests.py` - no real Domoticz install, and no
network access, needed. A minimal Domoticz stub is installed into
sys.modules before anything that imports Domoticz (devices.py,
plugin.py) is loaded, and the CSV HTTP call is monkeypatched to read
the bundled fixture in fixtures/water_levels_sample.csv instead.
"""

import json
import os
import shutil
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

FIXTURE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "water_levels_sample.csv")

API_FIXTURE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "rivers_api_sample.json")

with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
    FIXTURE_CSV = f.read()

with open(API_FIXTURE_PATH, "r", encoding="utf-8") as f:
    FIXTURE_API = json.load(f)


def _install_domoticz_stub_once():
    """Install a single Domoticz stub module, shared for the whole test
    process.

    devices.py and plugin.py are only ever imported once per process
    (Python caches modules), so their `import Domoticz` binds to
    whichever module object was in sys.modules at that first import.
    Swapping in a brand-new stub module per test would leave their
    Domoticz reference stale. Instead, Device.Create() always writes
    into whatever dict `_devices_box["devices"]` currently points at,
    so each test can swap in its own fresh dict via _fresh_devices()
    below without ever needing to reinstall the stub itself.
    """
    existing = sys.modules.get("Domoticz")
    if existing is not None and getattr(existing, "_is_test_stub", False):
        return existing._devices_box

    box = {"devices": {}}
    stub = types.ModuleType("Domoticz")
    stub._is_test_stub = True
    stub._devices_box = box
    stub.Debugging = lambda x: None
    stub.Debug = lambda x: None
    stub.Log = lambda x: None
    stub.Error = lambda x: None
    stub.Heartbeat = lambda x: None

    class DeviceStub:
        def __init__(self, Name=None, Unit=None, TypeName=None, Options=None, DeviceID=None):
            self.Name = Name
            self.Unit = Unit
            self.TypeName = TypeName
            self.Options = Options
            self.DeviceID = DeviceID
            self.sValue = ""
            self.nValue = 0

        def Create(self):
            box["devices"][self.Unit] = self
            return self

        def Update(self, nValue, sValue):
            self.nValue = nValue
            self.sValue = sValue

    stub.Device = DeviceStub
    sys.modules["Domoticz"] = stub
    return box


def _fresh_devices():
    """A brand-new, empty devices dict, wired up as the active target
    for Domoticz.Device(...).Create() calls in the current test."""
    box = _install_domoticz_stub_once()
    box["devices"] = {}
    return box["devices"]


class TestUtils(unittest.TestCase):
    def test_safe_float(self):
        from utils import safe_float

        self.assertEqual(safe_float("38.5"), 38.5)
        self.assertEqual(safe_float("314.826", ndigits=2), 314.83)
        self.assertIsNone(safe_float(None))
        self.assertIsNone(safe_float(""))
        self.assertIsNone(safe_float("   "))
        self.assertIsNone(safe_float("n/a"))

    def test_last_non_empty(self):
        from utils import last_non_empty

        self.assertEqual(last_non_empty(["1", "2", "3"]), "3")
        self.assertEqual(last_non_empty(["1", "2", "", "", ""]), "2")
        self.assertIsNone(last_non_empty(["", "", ""]))
        self.assertIsNone(last_non_empty([]))

    def test_parse_name_filter(self):
        from utils import parse_name_filter

        self.assertIsNone(parse_name_filter(""))
        self.assertIsNone(parse_name_filter("   "))
        self.assertEqual(parse_name_filter("Alzette, S\u00fbre"), {"alzette", "s\u00fbre"})

    def test_name_matches_filter(self):
        from utils import name_matches_filter

        self.assertTrue(name_matches_filter("Ettelbr\u00fcck / Alzette", {"alzette"}))
        self.assertTrue(name_matches_filter("Ettelbr\u00fcck / Alzette", None))
        self.assertFalse(name_matches_filter("Perl", {"alzette"}))


class TestStationsParsing(unittest.TestCase):
    def test_parses_bundled_fixture(self):
        from stations import parse_csv

        stations = parse_csv(FIXTURE_CSV)
        self.assertEqual(len(stations), 8)
        names = [s.name for s in stations]
        self.assertIn("Ettelbr\u00fcck / Alzette", names)
        self.assertIn("Welscheid-Village", names)
        self.assertIn("Gem\u00fcnd_Our", names)

    def test_unit_label_read_per_station(self):
        from stations import parse_csv

        stations = {s.name: s for s in parse_csv(FIXTURE_CSV)}
        self.assertEqual(stations["Esch-Sure"].unit_label, "m")
        self.assertEqual(stations["Heiderscheidergrund"].unit_label, "cm")

    def test_current_value_is_last_non_empty(self):
        from stations import parse_csv

        stations = {s.name: s for s in parse_csv(FIXTURE_CSV)}
        # Ubersyren's row has two real readings followed by trailing blanks -
        # the true current value is the last real one, not blank.
        self.assertEqual(stations["Ubersyren"].current_value, 19.3)
        self.assertEqual(stations["Esch-Sure"].current_value, 314.16)

    def test_bom_is_stripped(self):
        from stations import parse_csv

        stations = parse_csv("\ufeff" + FIXTURE_CSV)
        self.assertEqual(len(stations), 8)

    def test_malformed_and_blank_rows_are_skipped_not_fatal(self):
        from stations import parse_csv

        csv_text = (
            '"Name","Number","Unit","t1","t2"\n'
            '"Good Station","","cm","1.0","2.0"\n'
            '"","","cm","3.0","4.0"\n'  # blank name, skipped
            '"Too Short"\n'  # malformed, skipped
            '"Another Good","","cm","5.0","6.0"\n'
        )
        stations = parse_csv(csv_text)
        names = [s.name for s in stations]
        self.assertEqual(names, ["Good Station", "Another Good"])

    def test_all_blank_tail_gives_none(self):
        from stations import parse_csv

        csv_text = '"Name","Number","Unit","t1","t2"\n' '"Silent Station","","cm","",""\n'
        stations = parse_csv(csv_text)
        self.assertEqual(len(stations), 1)
        self.assertIsNone(stations[0].current_value)

    def test_filter_stations(self):
        from stations import filter_stations, parse_csv

        stations = parse_csv(FIXTURE_CSV)
        filtered = filter_stations(stations, {"alzette", "welscheid"})
        names = sorted(s.name for s in filtered)
        self.assertEqual(names, ["Ettelbr\u00fcck / Alzette", "Welscheid-Village"])


class TestStationUnitRegistry(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.map_path = os.path.join(self.tmp_dir, "station_units.json")

    def test_allocates_and_persists(self):
        from registry import StationUnitRegistry

        reg = StationUnitRegistry(self.map_path)
        unit_a = reg.unit_for("Perl")
        unit_b = reg.unit_for("Diekirch")
        self.assertNotEqual(unit_a, unit_b)
        self.assertTrue(os.path.exists(self.map_path))

        # A fresh registry instance reading the same file must return the
        # SAME units for the same names - this is the whole point.
        reg2 = StationUnitRegistry(self.map_path)
        self.assertEqual(reg2.unit_for("Perl"), unit_a)
        self.assertEqual(reg2.unit_for("Diekirch"), unit_b)

    def test_same_name_stable_within_one_instance(self):
        from registry import StationUnitRegistry

        reg = StationUnitRegistry(self.map_path)
        first = reg.unit_for("Perl")
        second = reg.unit_for("Perl")
        self.assertEqual(first, second)

    def test_never_allocates_reserved_status_unit(self):
        from constants import LAST_UPDATE_UNIT
        from registry import StationUnitRegistry

        reg = StationUnitRegistry(self.map_path)
        units = {reg.unit_for(f"Station {i}") for i in range(20)}
        self.assertNotIn(LAST_UPDATE_UNIT, units)

    def test_corrupt_file_raises_registry_error(self):
        from registry import RegistryError, StationUnitRegistry

        with open(self.map_path, "w", encoding="utf-8") as f:
            f.write("{not valid json")

        with self.assertRaises(RegistryError):
            StationUnitRegistry(self.map_path)

    def test_missing_file_starts_empty(self):
        from registry import StationUnitRegistry

        reg = StationUnitRegistry(self.map_path)  # file doesn't exist yet
        unit = reg.unit_for("Perl")
        self.assertIsInstance(unit, int)


RIVERS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "station_rivers.json")

# Station names exactly as captured from the live CSV during development
# (a partial capture: the response was cut off mid-file, so this is not the
# complete station list).
LIVE_CSV_NAMES_SEEN = [
    "Heiderscheidergrund", "M\u00fcllerthal", "Bissen", "Walferdange", "Steinsel", "SN_Wasserbillig",
    "Ubersyren", "Schoenfels", "Esch-Sure", "Perl", "Ettelbr\u00fcck / Alzette", "Clervaux", "Bollendorf",
    "Eischen", "Welscheid", "SN_Remich", "Dasbourg", "Wiltz", "Pfaffenthal", "SN_Stadtbredimus", "Hunnebuer",
    "SN_Grevenmacher", "Reichlange", "Livange", "Welscheid-Village", "Mertert", "Kautenbach", "P\u00e9tange",
    "Diekirch", "Gem\u00fcnd_Our", "Niederfeulen", "Rosport",
]


class TestRiverIndex(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from rivers import load_river_index

        cls.index = load_river_index(RIVERS_PATH)

    def test_normalize(self):
        from rivers import normalize

        self.assertEqual(normalize("S\u00fbre"), "sure")
        self.assertEqual(normalize("Mondorf-les-Bains"), normalize("mondorf les bains"))

    def test_real_feed_decorations(self):
        r = self.index.resolve
        self.assertEqual(r("Ettelbr\u00fcck / Alzette"), ("Alzette", "Ettelbr\u00fcck"))  # " / River" hint
        self.assertEqual(r("Gem\u00fcnd_Our"), ("Our", "Gem\u00fcnd"))  # "_River" hint
        self.assertEqual(r("SN_Wasserbillig"), ("Moselle", "Wasserbillig"))  # "SN_" prefix
        self.assertEqual(r("Perl"), ("Moselle", "Perl"))
        self.assertEqual(r("Esch-Sure"), ("S\u00fbre", "Esch-Sure"))
        self.assertEqual(r("P\u00e9tange"), ("Chiers", "P\u00e9tange"))

    def test_spelling_variants_map_to_the_api_label(self):
        self.assertEqual(self.index.resolve("Ubersyren"), ("Syre", "Uebersyren"))
        self.assertEqual(self.index.resolve("Welscheid-Village"), ("Wark", "Welscheid (Village)"))
        self.assertEqual(self.index.resolve("Welscheid"), ("Wark", "Welscheid"))

    def test_ambiguous_locality_needs_the_feeds_own_hint(self):
        # Ettelbr\u00fcck has a gauge on the Alzette and on the Wark.
        self.assertIsNone(self.index.resolve("Ettelbr\u00fcck"))
        self.assertEqual(self.index.resolve("Ettelbr\u00fcck / Wark"), ("Wark", "Ettelbr\u00fcck"))
        self.assertIsNone(self.index.resolve("Ettelbr\u00fcck / Moselle"))  # hint contradicts the table

    def test_unknown_station_is_none_not_a_guess(self):
        self.assertIsNone(self.index.resolve("Nowhere"))
        self.assertIsNone(self.index.resolve(""))

    def test_every_live_csv_name_seen_resolves(self):
        unresolved = [n for n in LIVE_CSV_NAMES_SEEN if self.index.resolve(n) is None]
        self.assertEqual(unresolved, [])

    def test_matches_api_mode_device_names(self):
        """A CSV station and its API twin get the same display name, so the
        two modes look alike in Domoticz."""
        from stations import parse_api

        api_names = {s.name for s in parse_api(FIXTURE_API)}
        csv_side = ["Ettelbr\u00fcck / Alzette", "Hesperange", "Welscheid", "Welscheid-Village", "Esch-Sure"]
        derived = set()
        for feed_name in csv_side:
            river, label = self.index.resolve(feed_name)
            derived.add(f"{river} - {label}")
        self.assertEqual(derived, api_names)

    def test_table_is_well_formed(self):
        with open(RIVERS_PATH, "r", encoding="utf-8") as f:
            table = json.load(f)
        self.assertGreaterEqual(len(table), 15)
        for river, entries in table.items():
            labels = [e if isinstance(e, str) else e["name"] for e in entries]
            self.assertEqual(len(labels), len(set(labels)), f"duplicate station under {river}")

    def test_malformed_table_raises(self):
        from rivers import RiverIndex, RiverTableError

        with self.assertRaises(RiverTableError):
            RiverIndex({"Alzette": "not a list"})
        with self.assertRaises(RiverTableError):
            RiverIndex({"Alzette": [42]})


class TestApplyRivers(unittest.TestCase):
    def test_sets_display_name_but_keeps_identity(self):
        from rivers import load_river_index
        from stations import apply_rivers, parse_csv

        stations = parse_csv(FIXTURE_CSV)
        unresolved = apply_rivers(stations, load_river_index(RIVERS_PATH))
        self.assertEqual(unresolved, [])  # every fixture station is known

        by_name = {s.name: s for s in stations}
        self.assertEqual(by_name["Ubersyren"].display_name, "Syre - Uebersyren")
        self.assertEqual(by_name["Ubersyren"].name, "Ubersyren")  # identity untouched

    def test_unresolved_names_are_returned_and_keep_their_feed_name(self):
        from rivers import RiverIndex
        from stations import Station, apply_rivers

        st = Station(name="Mystery", unit_label="cm", current_value=1.0)
        self.assertEqual(apply_rivers([st], RiverIndex({})), ["Mystery"])
        self.assertEqual(st.display_name, "Mystery")


class TestDeviceManager(unittest.TestCase):
    def setUp(self):
        self.devices = _fresh_devices()
        from devices import DeviceManager  # safe to import repeatedly; cached after first time

        self.DeviceManager = DeviceManager

    def test_ensure_status_device_creates_once(self):
        from constants import LAST_UPDATE_UNIT

        dm = self.DeviceManager(self.devices)
        dm.ensure_status_device()
        dm.ensure_status_device()  # idempotent
        self.assertEqual(len(self.devices), 1)
        self.assertIn(LAST_UPDATE_UNIT, self.devices)

    def test_upsert_station_creates_and_updates_with_unit_label(self):
        from stations import Station

        dm = self.DeviceManager(self.devices)
        station = Station(name="Esch-Sure", unit_label="m", current_value=314.16)

        self.assertTrue(dm.upsert_station(station, unit=10))
        self.assertEqual(self.devices[10].sValue, "314.16")
        self.assertEqual(self.devices[10].Options, {"Custom": "1;m"})

        station.current_value = 314.2
        dm.upsert_station(station, unit=10)
        self.assertEqual(self.devices[10].sValue, "314.2")

    def test_upsert_station_rejects_out_of_range_unit(self):
        from stations import Station

        dm = self.DeviceManager(self.devices)
        station = Station(name="Test", unit_label="cm", current_value=1.0)
        self.assertFalse(dm.upsert_station(station, unit=999))
        self.assertEqual(len(self.devices), 0)

    def test_upsert_station_skips_missing_value(self):
        from stations import Station

        dm = self.DeviceManager(self.devices)
        station = Station(name="Test", unit_label="cm", current_value=None)
        self.assertFalse(dm.upsert_station(station, unit=10))
        self.assertEqual(len(self.devices), 0)


class TestApiParsing(unittest.TestCase):
    def test_parses_api_fixture(self):
        from stations import parse_api

        stations = parse_api(FIXTURE_API)
        self.assertEqual(len(stations), 5)
        names = sorted(s.name for s in stations)
        self.assertIn("Alzette - Ettelbr\u00fcck", names)
        self.assertIn("Wark - Welscheid", names)
        # supplement disambiguates the two Welscheid gauges
        self.assertIn("Wark - Welscheid (Village)", names)

    def test_values_and_units(self):
        from stations import parse_api

        stations = {s.name: s for s in parse_api(FIXTURE_API)}
        self.assertEqual(stations["Alzette - Hesperange"].current_value, 38.5)
        self.assertEqual(stations["Alzette - Hesperange"].unit_label, "cm")

    def test_known_limitation_esch_sure_unit_is_mislabelled_cm(self):
        """Documents (and pins) a real upstream data bug: the API calls
        Esch-Sure's metre-scale reservoir reading 'cm', where the
        official CSV says 'm'. If heichwaasser.lu ever fixes this, this
        test failing is the cue to update README 'Known limitations'."""
        from stations import parse_api

        stations = {s.name: s for s in parse_api(FIXTURE_API)}
        self.assertEqual(stations["S\u00fbre - Esch-Sure"].unit_label, "cm")

    def test_garbage_payload_is_not_fatal(self):
        from stations import parse_api

        self.assertEqual(parse_api({"not": "a list"}), [])
        self.assertEqual(parse_api([None, "x", {"name": "R", "stations": [None, 5]}]), [])
        self.assertEqual(parse_api([{"name": "R", "stations": [{"id": 1, "city": "C"}]}])[0].current_value, None)


class TestEnvConfig(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)

    def test_parse_env_text(self):
        from env_config import parse_env_text

        parsed = parse_env_text(
            "# comment\n"
            "\n"
            "A=plain\n"
            "B = spaced value \n"
            "C=\"double quoted\"\n"
            "D='single quoted'\n"
            "URL=https://example.org/x?a=b&c=d\n"
            "no equals sign here\n"
            "=novalue-key\n"
        )
        self.assertEqual(parsed["A"], "plain")
        self.assertEqual(parsed["B"], "spaced value")
        self.assertEqual(parsed["C"], "double quoted")
        self.assertEqual(parsed["D"], "single quoted")
        self.assertEqual(parsed["URL"], "https://example.org/x?a=b&c=d")  # '=' inside a value survives
        self.assertNotIn("", parsed)
        self.assertEqual(len(parsed), 5)

    def test_missing_file_gives_empty_dict(self):
        from env_config import load_env_file

        self.assertEqual(load_env_file(os.path.join(self.tmp_dir, "nope.env")), {})

    def test_defaults_when_nothing_configured(self):
        from constants import DEFAULT_API_URL, DEFAULT_CSV_URL
        from env_config import resolve_source_urls

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("INONDATIONS_CSV_URL", None)
            os.environ.pop("HEICHWAASSER_API_URL", None)
            self.assertEqual(resolve_source_urls({}), (DEFAULT_CSV_URL, DEFAULT_API_URL))

    def test_env_file_beats_default_and_real_env_beats_file(self):
        from env_config import resolve_source_urls

        env_file = {"INONDATIONS_CSV_URL": "https://file.example/csv", "HEICHWAASSER_API_URL": "https://file.example/api"}
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("INONDATIONS_CSV_URL", None)
            os.environ.pop("HEICHWAASSER_API_URL", None)
            self.assertEqual(resolve_source_urls(env_file), ("https://file.example/csv", "https://file.example/api"))

        with patch.dict(os.environ, {"INONDATIONS_CSV_URL": "https://real-env.example/csv"}):
            csv_url, api_url = resolve_source_urls(env_file)
            self.assertEqual(csv_url, "https://real-env.example/csv")
            self.assertEqual(api_url, "https://file.example/api")

    def test_shipped_env_files_match_defaults(self):
        """.env.sample and the shipped .env must carry exactly the built-in
        default URLs, so 'copy the sample' and 'no .env at all' agree."""
        from constants import DEFAULT_API_URL, DEFAULT_CSV_URL
        from env_config import load_env_file

        here = os.path.dirname(os.path.abspath(__file__))
        for filename in (".env.sample", ".env"):
            path = os.path.join(here, filename)
            if not os.path.exists(path):
                continue  # .env is gitignored, so may legitimately be absent in a fresh clone
            parsed = load_env_file(path)
            self.assertEqual(parsed.get("INONDATIONS_CSV_URL"), DEFAULT_CSV_URL, filename)
            self.assertEqual(parsed.get("HEICHWAASSER_API_URL"), DEFAULT_API_URL, filename)


class TestPluginIntegration(unittest.TestCase):
    """Exercises InondationsPlugin.onStart end-to-end against the bundled
    fixtures, the same way onHeartbeat would drive it in Domoticz.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        shutil.copy(RIVERS_PATH, self.tmp_dir)  # the plugin reads it from its HomeFolder
        # Keep real environment variables from leaking into URL resolution.
        env_patch = patch.dict(os.environ, {}, clear=False)
        env_patch.start()
        self.addCleanup(env_patch.stop)
        os.environ.pop("INONDATIONS_CSV_URL", None)
        os.environ.pop("HEICHWAASSER_API_URL", None)

    def _run(self, mode2="", mode3="csv", devices=None, env_text=None, mode4=None):
        devices = _fresh_devices() if devices is None else devices
        if env_text is not None:
            with open(os.path.join(self.tmp_dir, ".env"), "w", encoding="utf-8") as f:
                f.write(env_text)

        # plugin.py is reloaded fresh each time so its module-level
        # _plugin singleton doesn't carry state between test cases; the
        # Domoticz stub itself stays the single persistent instance from
        # _fresh_devices(), so plugin.py's `import Domoticz` stays valid.
        sys.modules.pop("plugin", None)
        import plugin as plugin_module

        plugin_module.Devices = devices
        plugin_module.Parameters = {
            "Mode1": "15",
            "Mode2": mode2,
            "Mode3": mode3,
            "Mode6": "0",
            "HomeFolder": self.tmp_dir,
        }
        if mode4 is not None:
            plugin_module.Parameters["Mode4"] = mode4

        with patch("plugin.fetch_csv", return_value=FIXTURE_CSV) as csv_mock, patch(
            "plugin.fetch_api", return_value=FIXTURE_API
        ) as api_mock:
            plugin_module.onStart()

        self.csv_mock, self.api_mock = csv_mock, api_mock
        return devices, plugin_module

    def test_csv_source_is_default(self):
        devices, _ = self._run(mode3="")
        self.assertEqual(len(devices), 9)  # 8 stations + 1 status sensor
        self.assertIn(255, devices)
        self.assertNotEqual(devices[255].sValue, "")
        self.csv_mock.assert_called_once()
        self.api_mock.assert_not_called()

    def test_api_source(self):
        devices, _ = self._run(mode3="api")
        self.assertEqual(len(devices), 6)  # 5 stations + 1 status sensor
        names = {d.Name for u, d in devices.items() if u != 255}
        self.assertIn("Wark - Welscheid (Village)", names)
        self.api_mock.assert_called_once()
        self.csv_mock.assert_not_called()

    def test_unknown_source_falls_back_to_csv(self):
        devices, _ = self._run(mode3="bogus")
        self.assertEqual(len(devices), 9)
        self.csv_mock.assert_called_once()
        self.api_mock.assert_not_called()

    def test_urls_come_from_env_file(self):
        self._run(mode3="csv", env_text="INONDATIONS_CSV_URL=https://mirror.example/levels.csv\n")
        self.csv_mock.assert_called_once_with("https://mirror.example/levels.csv")

        self._run(mode3="api", env_text="HEICHWAASSER_API_URL=https://mirror.example/rivers\n")
        self.api_mock.assert_called_once_with("https://mirror.example/rivers")

    def test_defaults_used_without_env_file(self):
        from constants import DEFAULT_CSV_URL

        self._run(mode3="csv")
        self.csv_mock.assert_called_once_with(DEFAULT_CSV_URL)

    def test_name_filter_applies_to_both_sources(self):
        devices, _ = self._run(mode2="Alzette, Welscheid", mode3="csv")
        self.assertEqual(len([u for u in devices if u != 255]), 2)

        devices, _ = self._run(mode2="Alzette", mode3="api")
        self.assertEqual(len([u for u in devices if u != 255]), 2)

    def test_fetch_failure_updates_nothing(self):
        from errors import SourceFetchError

        devices = _fresh_devices()
        sys.modules.pop("plugin", None)
        import plugin as plugin_module

        plugin_module.Devices = devices
        plugin_module.Parameters = {"Mode1": "15", "Mode2": "", "Mode3": "csv", "Mode6": "0", "HomeFolder": self.tmp_dir}
        with patch("plugin.fetch_csv", side_effect=SourceFetchError("boom")):
            plugin_module.onStart()

        # only the status sensor exists, and it was never marked successful
        self.assertEqual(list(devices.keys()), [255])
        self.assertEqual(devices[255].sValue, "")

    def test_csv_devices_get_river_names_by_default(self):
        devices, _ = self._run()
        names = {d.Name for u, d in devices.items() if u != 255}
        self.assertEqual(
            names,
            {
                "S\u00fbre - Heiderscheidergrund", "S\u00fbre - Esch-Sure", "Moselle - Wasserbillig", "Syre - Uebersyren",
                "Alzette - Ettelbr\u00fcck", "Our - Gem\u00fcnd", "Wark - Welscheid (Village)", "Moselle - Perl",
            },
        )

    def test_feed_names_when_river_naming_is_off(self):
        devices, _ = self._run(mode4="feed")
        names = {d.Name for u, d in devices.items() if u != 255}
        self.assertIn("Perl", names)
        self.assertIn("Ettelbr\u00fcck / Alzette", names)
        self.assertIn("SN_Wasserbillig", names)

    def test_missing_river_table_falls_back_to_feed_names(self):
        os.remove(os.path.join(self.tmp_dir, "station_rivers.json"))
        devices, _ = self._run()
        self.assertEqual(len(devices), 9)  # nothing lost, just unprefixed
        self.assertIn("Perl", {d.Name for d in devices.values()})

    def test_identity_is_the_feed_name_so_naming_changes_never_duplicate(self):
        devices, _ = self._run(mode4="river")
        with open(os.path.join(self.tmp_dir, "station_units.json"), encoding="utf-8") as f:
            keys = set(json.load(f))
        self.assertIn("Perl", keys)
        self.assertIn("Ettelbr\u00fcck / Alzette", keys)
        self.assertNotIn("Moselle - Perl", keys)

        # Restart with the other naming mode: same devices, none added.
        devices2, _ = self._run(mode4="feed", devices=devices)
        self.assertEqual(len(devices2), 9)

    def test_filter_can_match_a_river_name(self):
        devices, _ = self._run(mode2="Moselle")
        names = sorted(d.Name for u, d in devices.items() if u != 255)
        self.assertEqual(names, ["Moselle - Perl", "Moselle - Wasserbillig"])  # SN_Wasserbillig + Perl

    def test_api_mode_ignores_river_naming(self):
        devices, _ = self._run(mode3="api", mode4="river")
        self.assertIn("Wark - Welscheid (Village)", {d.Name for d in devices.values()})

    def test_unit_assignment_survives_restart(self):
        """The core promise of the persisted registry: the same station
        gets the same Domoticz Unit across a full plugin restart, even
        though Devices (Domoticz's own state) also carries over."""
        devices, _ = self._run()
        perl_unit = next(u for u, d in devices.items() if d.Name == "Moselle - Perl")

        # Simulate a Domoticz restart: same Devices dict persists (as it
        # would on disk in real Domoticz), but the plugin module and its
        # in-memory registry are reloaded from scratch.
        devices2, _ = self._run(devices=devices)
        perl_unit_after_restart = next(u for u, d in devices2.items() if d.Name == "Moselle - Perl")
        self.assertEqual(perl_unit, perl_unit_after_restart)


class TestVersionConsistency(unittest.TestCase):
    """The version is written by hand in several places (Domoticz needs a
    literal in plugin.py's XML header). Fail loudly if they drift apart."""

    def _read(self, name):
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), name), "r", encoding="utf-8") as f:
            return f.read()

    def test_version_matches_everywhere(self):
        import re

        from constants import PLUGIN_VERSION

        xml_version = re.search(r'<plugin [^>]*version="([^"]+)"', self._read("plugin.py")).group(1)
        self.assertEqual(xml_version, PLUGIN_VERSION, "plugin.py XML header")

        self.assertIn(f"**Version {PLUGIN_VERSION}**", self._read("README.md"), "README.md")

        changelog_top = re.search(r"^## \[([^\]]+)\]", self._read("CHANGELOG.md"), re.M).group(1)
        self.assertEqual(changelog_top, PLUGIN_VERSION, "newest CHANGELOG.md entry")

        self.assertIn(f"**{PLUGIN_VERSION} ", self._read("ROADMAP.md"), "ROADMAP.md 'currently at'")


if __name__ == "__main__":
    unittest.main(verbosity=2)
