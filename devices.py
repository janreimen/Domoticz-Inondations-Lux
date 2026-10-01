"""
Owns all Domoticz device creation/update logic, kept separate from plugin.py so the Domoticz-callback plumbing there stays thin and the CSV/registry logic elsewhere stays Domoticz-free.
"""

import Domoticz

from constants import LAST_UPDATE_DEVICE_ID, LAST_UPDATE_UNIT, MAX_UNIT, MIN_UNIT


class DeviceManager:
    def __init__(self, devices):
        # `devices` is Domoticz's injected Devices collection for this
        # plugin instance, passed in rather than imported globally so
        # this class can be exercised with a plain dict in tests.py.
        self.devices = devices

    def ensure_status_device(self) -> None:
        if LAST_UPDATE_UNIT not in self.devices:
            Domoticz.Device(
                Name="Last successful update",
                Unit=LAST_UPDATE_UNIT,
                TypeName="Text",
                DeviceID=LAST_UPDATE_DEVICE_ID,
            ).Create()

    def mark_update_succeeded(self, timestamp_str: str) -> None:
        self.devices[LAST_UPDATE_UNIT].Update(nValue=0, sValue=timestamp_str)

    def upsert_station(self, station, unit: int) -> bool:
        """Create the device if it doesn't exist yet and update its value.

        The device is updated on every successful poll, even when the measured
        value has not changed. This keeps Domoticz's LastUpdate timestamp aligned
        with the source polling cycle.
        """
        if not (MIN_UNIT <= unit <= MAX_UNIT):
            Domoticz.Error(
                f"Unit {unit} for station '{station.name}' is outside "
                f"the {MIN_UNIT}-{MAX_UNIT} range, skipped"
            )
            return False

        if station.current_value is None:
            Domoticz.Debug(
                f"No usable current value for station '{station.name}', skipped"
            )
            return False

        if unit not in self.devices:
            Domoticz.Device(
                Name=station.display_name,
                Unit=unit,
                TypeName="Custom",
                Options={"Custom": f"1;{station.unit_label}"},
                DeviceID=f"station_{unit}",
            ).Create()

            Domoticz.Log(
                f"Created device '{station.display_name}' for feed station "
                f"'{station.name}' (Unit {unit}, {station.unit_label})"
            )

        s_value = str(station.current_value)

        # Always update the Domoticz device, even when the value is unchanged.
        # This keeps LastUpdate aligned with the successful source poll.
        self.devices[unit].Update(
            nValue=0,
            sValue=s_value,
        )

        return True    

