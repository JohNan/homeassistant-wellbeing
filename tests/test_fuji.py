"""Tests for the Fuji air purifier with heater and humidifier."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.const import Platform
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.wellbeing.api import Appliance, Appliances, Model, WorkMode
from custom_components.wellbeing.const import DOMAIN

# Reported state as seen on a Taiwanese Fuji (trimmed to the relevant keys).
FUJI_STATE = {
    "AQIColor": "green",
    "AQILevel": "very_good",
    "AQILight": "ambient",
    "ErrCommSensorUIBrd": "not active",
    "ErrGasNotResp": "not active",
    "ErrPmNotResp": "not active",
    "Fanspeed": 1,
    "FilterLife_1": 75,
    "FilterLife_2": 68,
    "FilterType_1": 57,
    "FilterType_2": 195,
    "Heating": False,
    "Humidification": False,
    "HumidityTarget": 40,
    "Ionizer": True,
    "LouverSwing": "off",
    "Monitoring": False,
    "PMLeadingMode": "PM2.5",
    "QuietFan": "off",
    "SafetyLock": False,
    "SignalStrength": "EXCELLENT",
    "TemperatureTarget": 22,
    "UVWaterState": "on",
    "VmNo_NIU": "VM222_A_04.43.06_FUJI",
    "WaterTrayLevelLow": True,
    "Workmode": "Auto",
    "applianceState": "running",
    "PM2_5": 1,
    "ECO2": 639,
    "TVOC": 412,
    "Temp": 25.3,
    "PM1": 0,
    "Humidity": 60,
    "PM10": 8,
    "status": "enabled",
    "connectionState": "Connected",
}

# Capabilities as returned by GET /appliances/{id}/info for an EP91-67UGA.
# Note: Workmode values are lower case while the state reports "Auto",
# power is switched with executeCommand, and Humidification is reported in
# the state but is not a capability on this variant.
FUJI_CAPABILITIES = {
    "executeCommand": {
        "access": "write",
        "type": "string",
        "values": {"on": {}, "off": {}},
    },
    "applianceState": {
        "access": "read",
        "type": "string",
        "values": {"off": {}, "running": {}, "monitoring": {}, "alert": {}},
    },
    "Workmode": {
        "access": "readwrite",
        "type": "string",
        "values": {"manual": {}, "auto": {}},
    },
    "Fanspeed": {
        "access": "readwrite",
        "type": "number",
        "min": 0,
        "max": 9,
        "step": 1,
    },
    "Ionizer": {"access": "readwrite", "type": "boolean"},
    "SafetyLock": {"access": "readwrite", "type": "boolean"},
    "AQILight": {
        "access": "readwrite",
        "type": "string",
        "values": {"on": {}, "off": {}, "ambient": {}},
    },
    "QuietFan": {
        "access": "readwrite",
        "type": "string",
        "values": {"on": {}, "off": {}, "whenDark": {}},
    },
    "PMLeadingMode": {
        "access": "readwrite",
        "type": "string",
        "values": {"PM2.5": {}, "PM10": {}},
    },
    "LouverSwing": {
        "access": "readwrite",
        "type": "string",
        "values": {"off": {}, "swing": {}, "frontBack": {}, "front": {}},
    },
    "UVWaterState": {
        "access": "readwrite",
        "type": "string",
        "values": {"on": {}, "off": {}},
    },
    "Heating": {"access": "readwrite", "type": "boolean"},
    "TemperatureTarget": {
        "access": "readwrite",
        "type": "Number",
        "default": 22,
        "min": 22,
        "max": 26,
        "step": 2,
    },
    "Temp": {
        "access": "read",
        "type": "number",
        "min": -40.0,
        "max": 100.0,
        "step": 0.1,
    },
    "ErrPmNotResp": {
        "access": "read",
        "type": "string",
        "values": {"not active": {}, "active": {}, "was active": {}},
    },
}

HUMIDIFIER_CAPABILITIES = {
    **FUJI_CAPABILITIES,
    "Humidification": {"access": "readwrite", "type": "boolean"},
    "HumidityTarget": {
        "access": "readwrite",
        "type": "number",
        "min": 30,
        "max": 70,
        "step": 5,
    },
}


def _fuji_appliance(
    name="Fuji Purifier", state=None, capabilities=None, pnc_id="pnc_fuji"
):
    appliance = Appliance(name, pnc_id, "Fuji")
    appliance.brand = "Electrolux"
    appliance.serialNumber = "sn_fuji"
    appliance.device = "MULTI_AIR_PURIFIER"
    appliance.setup(dict(state or FUJI_STATE), capabilities or FUJI_CAPABILITIES)
    return appliance


def test_fuji_appliance_setup():
    """The Fuji model is recognised and exposes heater/humidifier entities."""
    appliance = _fuji_appliance()
    assert appliance.model == Model.FUJI
    assert appliance.mode == WorkMode.AUTO
    assert appliance.firmware == "VM222_A_04.43.06_FUJI"
    # min 0 means "stopped"; Home Assistant models that as off.
    assert appliance.speed_range == (1, 9)
    # Capability values are lower case; Heat and Quiet are virtual presets for
    # the Heating / QuietFan properties; power is executeCommand, not a preset.
    assert appliance.preset_modes == [
        WorkMode.MANUAL,
        WorkMode.AUTO,
        WorkMode.HEAT,
        WorkMode.QUITE,
    ]
    assert appliance.work_mode_raw == WorkMode.AUTO
    assert not appliance.is_manual_fan_control
    assert appliance.supports_execute_command
    assert appliance.work_mode_command_value(WorkMode.AUTO) == "auto"
    assert appliance.work_mode_command_value(WorkMode.OFF) == "PowerOff"

    assert appliance.get_entity(Platform.CLIMATE, "Heating") is not None
    assert appliance.get_entity(Platform.HUMIDIFIER, "Humidification") is not None
    assert appliance.capability_values("LouverSwing", []) == [
        "off",
        "swing",
        "frontBack",
        "front",
    ]
    assert appliance.get_entity(Platform.SENSOR, "AQILevel").state == "very_good"
    assert appliance.get_entity(Platform.SENSOR, "TemperatureTarget").state == 22
    assert appliance.get_entity(Platform.BINARY_SENSOR, "Heating").state is False
    assert appliance.get_entity(Platform.BINARY_SENSOR, "UVWaterState").state is True
    assert appliance.get_entity(Platform.BINARY_SENSOR, "QuietFan").state is False
    assert (
        appliance.get_entity(Platform.BINARY_SENSOR, "WaterTrayLevelLow").state is True
    )

    error = appliance.get_entity(Platform.BINARY_SENSOR, "ErrorActive")
    assert error.state is False
    assert error.active_errors == []

    assert appliance.get_entity_or_none(Platform.SENSOR, "nonexistent") is None


def test_fuji_error_flags_aggregate():
    """Any active error flag turns the aggregated problem sensor on."""
    appliance = _fuji_appliance(state={**FUJI_STATE, "ErrPmNotResp": "active"})
    error = appliance.get_entity(Platform.BINARY_SENSOR, "ErrorActive")
    assert error.state is True
    assert error.active_errors == ["ErrPmNotResp"]


def test_capability_helpers():
    """Ranges and values come from the capabilities, with fallbacks."""
    appliance = _fuji_appliance()
    assert appliance.capability_range("TemperatureTarget", 10, 40, 1) == (22, 26, 2)
    assert appliance.capability_range("Missing", 10, 40, 2) == (10, 40, 2)
    assert appliance.capability_values("PMLeadingMode", ["x"]) == ["PM2.5", "PM10"]
    assert appliance.capability_values("Missing", ["x"]) == ["x"]
    assert appliance.has_capability("UVWaterState")
    assert not appliance.has_capability("Humidification")
    assert not appliance.has_capability("executeCommand")


def test_virtual_presets_from_feature_properties():
    """Heating / QuietFan map to the Heat / Quiet presets."""
    heating = _fuji_appliance(
        state={**FUJI_STATE, "Heating": True, "Workmode": "Manual"}
    )
    assert heating.mode == WorkMode.HEAT
    assert heating.work_mode_raw == WorkMode.MANUAL
    assert heating.is_manual_fan_control
    quiet = _fuji_appliance(state={**FUJI_STATE, "QuietFan": "on"})
    assert quiet.mode == WorkMode.QUITE


def test_optimistic_values_survive_stale_cloud_state():
    """Values set from HA are kept until the cloud confirms them or they expire."""
    appliance = _fuji_appliance()
    appliance.set_mode(WorkMode.HEAT)
    appliance.set_optimistic("LouverSwing", "swing")
    assert appliance.get_entity(Platform.SELECT, "LouverSwing").state == "swing"

    # A stale cloud update (e.g. a live stream event for another property)
    # must not revert them.
    appliance.setup(dict(FUJI_STATE), FUJI_CAPABILITIES)
    assert appliance.mode == WorkMode.HEAT
    assert appliance.get_entity(Platform.SELECT, "LouverSwing").state == "swing"
    assert appliance.get_entity(Platform.SENSOR, "LouverSwing").state == "swing"

    # Once the cloud confirms, the optimistic entries are dropped.
    appliance.setup(
        {**FUJI_STATE, "Heating": True, "LouverSwing": "swing"}, FUJI_CAPABILITIES
    )
    assert appliance.mode == WorkMode.HEAT
    assert appliance._optimistic == {}
    assert appliance._optimistic_mode is None

    # Expired entries give way to whatever the cloud reports.
    appliance.set_mode(WorkMode.QUITE)
    appliance._optimistic_mode = (WorkMode.QUITE, 0)
    appliance.setup(dict(FUJI_STATE), FUJI_CAPABILITIES)
    assert appliance.mode == WorkMode.AUTO


def test_powered_off_appliance_reports_off_mode():
    """applianceState off maps to the OFF work mode (Workmode keeps its value)."""
    appliance = _fuji_appliance(
        state={**FUJI_STATE, "applianceState": "off", "Fanspeed": 0}
    )
    assert appliance.mode == WorkMode.OFF


def test_display_name_falls_back_to_model_for_non_latin_names():
    """Chinese appliance names use the model name for device and entity ids."""
    appliance = _fuji_appliance(name="空氣清淨機")
    assert appliance.display_name == "Fuji"
    appliance.model_name = "EP91-67UGA"
    assert appliance.display_name == "EP91-67UGA"
    latin = _fuji_appliance(name="Living room purifier")
    latin.model_name = "EP91-67UGA"
    assert latin.display_name == "Living room purifier"


def test_unknown_workmode_does_not_break_setup():
    """A work mode the integration does not know falls back to UNDEFINED."""
    appliance = Appliance("Purifier", "pnc_x", "Fuji")
    appliance.device = "AIR_PURIFIER"
    appliance.setup({"Workmode": "Sleep"}, {})
    assert appliance.mode == WorkMode.UNDEFINED


@pytest.mark.asyncio
async def test_fuji_platforms(hass):
    """Climate, humidifier, select and switch entities send the right commands."""
    appliance = _fuji_appliance()
    humid_appliance = _fuji_appliance(
        name="Fuji Humid",
        state={**FUJI_STATE, "Humidification": True},
        capabilities=HUMIDIFIER_CAPABILITIES,
        pnc_id="pnc_humid",
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "api_key": "test_api_key",
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token",
        },
        options={"stream": False},
        entry_id="test_entry_fuji",
    )
    entry.add_to_hass(hass)

    with (
        patch("custom_components.wellbeing.WellbeingHubAPI") as mock_hub_class,
        patch(
            "custom_components.wellbeing.WellbeingApiClient.async_get_appliances"
        ) as mock_get_appliances,
    ):
        mock_hub_class.return_value = AsyncMock()
        mock_get_appliances.return_value = Appliances(
            {"pnc_fuji": appliance, "pnc_humid": humid_appliance}
        )

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][entry.entry_id]
        mock_api = AsyncMock()
        mock_api.type = "Fuji"
        mock_api.brand = "Electrolux"
        mock_api.serial_number = "sn_fuji"
        mock_api.device_type = "AIR_PURIFIER"
        mock_api.state = dict(FUJI_STATE)
        mock_api.capabilities_data = dict(FUJI_CAPABILITIES)
        mock_humid_api = AsyncMock()
        mock_humid_api.type = "Fuji"
        mock_humid_api.brand = "Electrolux"
        mock_humid_api.serial_number = "sn_humid"
        mock_humid_api.device_type = "MULTI_AIR_PURIFIER"
        mock_humid_api.state = {**FUJI_STATE, "Humidification": True}
        mock_humid_api.capabilities_data = dict(HUMIDIFIER_CAPABILITIES)
        coordinator.api._api_appliances = {
            "pnc_fuji": mock_api,
            "pnc_humid": mock_humid_api,
        }

        climate_id = "climate.wellbeing_fuji_purifier_heating"
        humidifier_id = "humidifier.wellbeing_fuji_humid_humidification"
        louver_id = "select.wellbeing_fuji_purifier_louverswing"
        uv_switch_id = "switch.wellbeing_fuji_purifier_uvwaterstate"
        quiet_switch_id = "switch.wellbeing_fuji_purifier_quietfan"
        ionizer_switch_id = "switch.wellbeing_fuji_purifier_ionizer"
        error_id = "binary_sensor.wellbeing_fuji_purifier_erroractive"
        fan_id = "fan.wellbeing_fuji_purifier_fanspeed"

        climate = hass.states.get(climate_id)
        assert climate is not None
        assert climate.state == "fan_only"
        assert climate.attributes["current_temperature"] == 25.3
        assert climate.attributes["temperature"] == 22
        assert climate.attributes["min_temp"] == 22
        assert climate.attributes["max_temp"] == 26
        assert climate.attributes["target_temp_step"] == 2

        # No humidifier on the variant without the capability...
        assert (
            hass.states.get("humidifier.wellbeing_fuji_purifier_humidification") is None
        )
        # ...but one on the variant that has it.
        humidifier = hass.states.get(humidifier_id)
        assert humidifier is not None
        assert humidifier.state == "on"
        assert humidifier.attributes["humidity"] == 40
        assert humidifier.attributes["current_humidity"] == 60

        louver = hass.states.get(louver_id)
        assert louver.state == "off"
        assert louver.attributes["options"] == ["off", "swing", "frontBack", "front"]
        assert hass.states.get("select.wellbeing_fuji_purifier_aqilight").state == (
            "ambient"
        )
        assert hass.states.get(uv_switch_id).state == "on"
        assert hass.states.get(quiet_switch_id).state == "off"
        assert hass.states.get(error_id).state == "off"
        fan = hass.states.get(fan_id)
        assert fan is not None
        assert fan.attributes["preset_modes"] == ["Manual", "Auto", "Heat", "Quiet"]

        # Heater
        await hass.services.async_call(
            "climate",
            "set_hvac_mode",
            {"entity_id": climate_id, "hvac_mode": "heat"},
            blocking=True,
        )
        mock_api.send_command.assert_any_call({"Heating": True})

        await hass.services.async_call(
            "climate",
            "set_temperature",
            {"entity_id": climate_id, "temperature": 24},
            blocking=True,
        )
        mock_api.send_command.assert_any_call({"TemperatureTarget": 24})

        # Power is switched with executeCommand on this model.
        await hass.services.async_call(
            "climate",
            "set_hvac_mode",
            {"entity_id": climate_id, "hvac_mode": "off"},
            blocking=True,
        )
        mock_api.send_command.assert_any_call({"executeCommand": "off"})

        # Fan presets are sent with the casing the capabilities expect.
        await hass.services.async_call(
            "fan",
            "set_preset_mode",
            {"entity_id": fan_id, "preset_mode": "Manual"},
            blocking=True,
        )
        mock_api.send_command.assert_any_call({"Workmode": "manual"})

        # Virtual presets: Heat turns the heater on, Quiet needs Auto first.
        await hass.services.async_call(
            "fan",
            "set_preset_mode",
            {"entity_id": fan_id, "preset_mode": "Heat"},
            blocking=True,
        )
        mock_api.send_command.assert_any_call({"Heating": True})
        # The Heating entities follow the preset immediately.
        assert (
            hass.states.get("binary_sensor.wellbeing_fuji_purifier_heating").state
            == "on"
        )
        assert hass.states.get(climate_id).state == "heat"
        mock_api.state = {**FUJI_STATE, "Heating": True, "Workmode": "Manual"}
        mock_api.send_command.reset_mock()
        await hass.services.async_call(
            "fan",
            "set_preset_mode",
            {"entity_id": fan_id, "preset_mode": "Quiet"},
            blocking=True,
        )
        assert mock_api.send_command.call_args_list[0].args[0] == {"Workmode": "auto"}
        mock_api.send_command.assert_any_call({"QuietFan": "on"})
        mock_api.state = {**FUJI_STATE, "QuietFan": "on"}
        mock_api.send_command.reset_mock()
        await hass.services.async_call(
            "fan",
            "set_preset_mode",
            {"entity_id": fan_id, "preset_mode": "Auto"},
            blocking=True,
        )
        assert [c.args[0] for c in mock_api.send_command.call_args_list] == [
            {"QuietFan": "off"},
            {"Heating": False},
            {"Workmode": "auto"},
        ]
        # Leaving Heat clears heating even if the cached state is stale.
        mock_api.state = {**FUJI_STATE, "Workmode": "Manual"}
        mock_api.send_command.reset_mock()
        await hass.services.async_call(
            "fan",
            "set_preset_mode",
            {"entity_id": fan_id, "preset_mode": "Manual"},
            blocking=True,
        )
        assert [c.args[0] for c in mock_api.send_command.call_args_list] == [
            {"Heating": False},
            {"Workmode": "manual"},
        ]

        # Humidifier (variant with the capability)
        await hass.services.async_call(
            "humidifier", "turn_off", {"entity_id": humidifier_id}, blocking=True
        )
        mock_humid_api.send_command.assert_any_call({"Humidification": False})

        await hass.services.async_call(
            "humidifier",
            "set_humidity",
            {"entity_id": humidifier_id, "humidity": 50},
            blocking=True,
        )
        mock_humid_api.send_command.assert_any_call({"HumidityTarget": 50})

        # Select
        await hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": louver_id, "option": "swing"},
            blocking=True,
        )
        mock_api.send_command.assert_any_call({"LouverSwing": "swing"})

        # Switches: string on/off properties vs boolean properties
        await hass.services.async_call(
            "switch", "turn_off", {"entity_id": uv_switch_id}, blocking=True
        )
        mock_api.send_command.assert_any_call({"UVWaterState": "off"})

        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": quiet_switch_id}, blocking=True
        )
        mock_api.send_command.assert_any_call({"QuietFan": "on"})

        await hass.services.async_call(
            "switch", "turn_off", {"entity_id": ionizer_switch_id}, blocking=True
        )
        mock_api.send_command.assert_any_call({"Ionizer": False})
