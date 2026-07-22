"""Tests for the platforms of the Wellbeing integration."""

from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.wellbeing.api import Appliance, Appliances
from custom_components.wellbeing.const import DOMAIN
from custom_components.wellbeing.switch import WellbeingSwitch


class DummyMap:
    """Dummy map object to bypass Mock name property issues."""

    def __init__(self, name, map_id, zones=None):
        self.name = name
        self.id = map_id
        self.zones = zones or []


class DummyZone:
    """Dummy zone object for dummy map."""

    def __init__(self, name, zone_id, power_mode=2):
        self.name = name
        self.id = zone_id
        self.power_mode = power_mode


class DummyMemoryMap:
    """Dummy memory map object for Gordias vacuum."""

    def __init__(self, map_id, name, rooms):
        self.id = map_id
        self.data = {"name": name, "rooms": rooms}


@pytest.mark.asyncio
async def test_platforms(hass):
    """Test all platforms (vacuum, climate, fan, sensor, binary_sensor, camera, switch) setup and operations."""

    # Define a mock PUREi9 vacuum
    vacuum_app = Appliance("Vacuum Cleaner", "pnc_vac1", "PUREi9")
    vacuum_app.brand = "Electrolux"
    vacuum_app.serialNumber = "sn_vac1"
    vacuum_app.device = "ROBOTIC_VACUUM_CLEANER"
    vacuum_data = {
        "batteryStatus": 90,
        "robotStatus": 9,
        "powerMode": 3,
        "ecoMode": "off",
        "vacuumMode": "eco",
        "FrmVer_NIU": "v1.0",
        "status": "Running",
        "connectionState": "Connected",
        "mapData": {
            "sessionId": "session_1",
            "timestamp": 123456789,
            "crumbs": [
                {"xy": [0.0, 0.0], "t": 0},
                {"xy": [0.2, 0.2], "t": 0},
            ],
        },
    }
    vacuum_app.setup(vacuum_data, {})

    # Define a mock Gordias vacuum (VacuumHygienic700)
    gordias_app = Appliance("Robot Gordias", "pnc_vac2", "Gordias")
    gordias_app.brand = "Electrolux"
    gordias_app.serialNumber = "sn_vac2"
    gordias_app.device = "ROBOTIC_VACUUM_CLEANER"
    gordias_data = {
        "batteryStatus": 80,
        "robotStatus": 9,
        "vacuumMode": "standard",
        "FrmVer_NIU": "v1.1",
        "status": "Running",
        "connectionState": "Connected",
    }
    gordias_app.setup(gordias_data, {})

    # Define a mock Muju fan/purifier
    purifier_app = Appliance("Air Purifier", "pnc_pur1", "Muju")
    purifier_app.brand = "AEG"
    purifier_app.serialNumber = "sn_pur1"
    purifier_app.device = "AIR_PURIFIER"
    purifier_data = {
        "Workmode": "Manual",
        "LouverSwing": "off",
        "FrmVer_NIU": "v2.0",
        "connectionState": "Connected",
        "status": "unknown",
        "FilterLife": 90,
        "SafetyLock": True,
        "UILight": False,
        "Fanspeed": 2,
    }
    purifier_app.setup(purifier_data, {"UILight": {}, "SafetyLock": {}})

    # Define a mock Climate (AC)
    climate_app = Appliance("Climate AC", "pnc_ac1", "COMFORT600")
    climate_app.brand = "Electrolux"
    climate_app.serialNumber = "sn_ac1"
    climate_app.device = "PORTABLE_AIR_CONDITIONER"
    climate_data = {
        "mode": "cool",
        "targetTemperatureC": 22.0,
        "sleepMode": False,
        "compressorState": True,
        "FrmVer_NIU": "v3.0",
        "connectionState": "Connected",
        "status": "unknown",
        "applianceState": True,
        "ambientTemperatureC": 22.0,
        "fanSpeedSetting": "low",
        "verticalSwing": False,
    }
    climate_app.setup(climate_data, {})

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "api_key": "test_api_key",
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token",
        },
        options={
            "stream": False,
        },
        entry_id="test_entry_id",
    )
    entry.add_to_hass(hass)

    # Mock the API client and update coordinator requests
    with (
        patch("custom_components.wellbeing.ElectroluxHubAPI") as mock_hub_class,
        patch(
            "custom_components.wellbeing.WellbeingApiClient.async_get_appliances"
        ) as mock_get_appliances,
    ):
        mock_hub = AsyncMock()
        mock_hub_class.return_value = mock_hub

        # Setup mock Appliances dictionary
        mock_get_appliances.return_value = Appliances(
            {
                "pnc_vac1": vacuum_app,
                "pnc_vac2": gordias_app,
                "pnc_pur1": purifier_app,
                "pnc_ac1": climate_app,
            }
        )

        # Load entry
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][entry.entry_id]

        # Retrieve the API Client from the coordinator
        client = coordinator.api

        # Mock raw ApiAppliance objects in client._api_appliances
        mock_api_vac = AsyncMock()
        mock_api_vac.type = "PUREi9"
        mock_api_vac.brand = "Electrolux"
        mock_api_vac.serial_number = "sn_vac1"
        mock_api_vac.device_type = "ROBOTIC_VACUUM_CLEANER"

        # Setup dummy interactive map for PUREi9 clean_zones
        dummy_zone = DummyZone("Kitchen", "zone_123", 2)
        dummy_map = DummyMap("Downstairs", "map_123", [dummy_zone])
        mock_api_vac.async_get_interactive_maps = AsyncMock(return_value=[dummy_map])

        # Setup dummy memory map for Gordias clean_room
        dummy_mem_map = DummyMemoryMap(
            "mem_map_123", "Downstairs", [{"id": 1, "name": "Kitchen"}]
        )

        mock_api_gordias = AsyncMock()
        mock_api_gordias.type = "Gordias"
        mock_api_gordias.brand = "Electrolux"
        mock_api_gordias.serial_number = "sn_vac2"
        mock_api_gordias.device_type = "ROBOTIC_VACUUM_CLEANER"
        mock_api_gordias.async_get_memory_maps = AsyncMock(return_value=[dummy_mem_map])

        mock_api_pur = AsyncMock()
        mock_api_pur.type = "Muju"
        mock_api_pur.brand = "AEG"
        mock_api_pur.serial_number = "sn_pur1"
        mock_api_pur.device_type = "AIR_PURIFIER"

        mock_api_ac = AsyncMock()
        mock_api_ac.type = "COMFORT600"
        mock_api_ac.brand = "Electrolux"
        mock_api_ac.serial_number = "sn_ac1"
        mock_api_ac.device_type = "PORTABLE_AIR_CONDITIONER"

        client._api_appliances = {
            "pnc_vac1": mock_api_vac,
            "pnc_vac2": mock_api_gordias,
            "pnc_pur1": mock_api_pur,
            "pnc_ac1": mock_api_ac,
        }

        # Verify entity setups in HASS state
        vacuum_entity_id = "vacuum.wellbeing_vacuum_cleaner_robotstatus"
        gordias_entity_id = "vacuum.wellbeing_robot_gordias_robotstatus"
        purifier_fan_entity_id = "fan.wellbeing_air_purifier_fanspeed"
        climate_entity_id = "climate.wellbeing_climate_ac_mode"
        camera_entity_id = "camera.wellbeing_vacuum_cleaner_mapdata"
        sensor_entity_id = "sensor.wellbeing_air_purifier_filterlife"
        binary_entity_id = "binary_sensor.wellbeing_air_purifier_safetylock"

        assert hass.states.get(vacuum_entity_id) is not None
        assert hass.states.get(gordias_entity_id) is not None
        assert hass.states.get(purifier_fan_entity_id) is not None
        assert hass.states.get(climate_entity_id) is not None
        assert hass.states.get(camera_entity_id) is not None
        assert hass.states.get(sensor_entity_id) is not None
        assert hass.states.get(binary_entity_id) is not None

        # 1. Test Vacuum Operations
        # Start
        await hass.services.async_call(
            "vacuum", "start", {"entity_id": vacuum_entity_id}, blocking=True
        )
        mock_api_vac.send_command.assert_any_call({"CleaningCommand": "play"})

        # Stop
        await hass.services.async_call(
            "vacuum", "stop", {"entity_id": vacuum_entity_id}, blocking=True
        )
        mock_api_vac.send_command.assert_any_call({"CleaningCommand": "stop"})

        # Pause
        await hass.services.async_call(
            "vacuum", "pause", {"entity_id": vacuum_entity_id}, blocking=True
        )
        mock_api_vac.send_command.assert_any_call({"CleaningCommand": "pause"})

        # Return to base
        await hass.services.async_call(
            "vacuum", "return_to_base", {"entity_id": vacuum_entity_id}, blocking=True
        )
        mock_api_vac.send_command.assert_any_call({"CleaningCommand": "home"})

        # Set fan speed
        await hass.services.async_call(
            "vacuum",
            "set_fan_speed",
            {"entity_id": vacuum_entity_id, "fan_speed": "eco"},
            blocking=True,
        )
        mock_api_vac.send_command.assert_any_call({"ecoMode": True})

        # Clean segments / clean zones (PUREi9)
        await hass.services.async_call(
            "vacuum",
            "send_command",
            {
                "entity_id": vacuum_entity_id,
                "command": "clean_zones",
                "params": {"map": "Downstairs", "zones": [{"zone": "Kitchen"}]},
            },
            blocking=True,
        )
        mock_api_vac.send_command.assert_any_call(
            {
                "CustomPlay": {
                    "persistentMapId": "map_123",
                    "zones": [{"zoneId": "zone_123", "powerMode": 2}],
                }
            }
        )

        # Clean rooms (Gordias/Hygienic700)
        await hass.services.async_call(
            "vacuum",
            "send_command",
            {
                "entity_id": gordias_entity_id,
                "command": "clean_room",
                "params": {
                    "map_name": "Downstairs",
                    "room_info": [
                        {
                            "room_name": "Kitchen",
                            "sweep_mode": 1,
                            "vacuum_mode": "standard",
                            "water_pump_rate": "low",
                            "repetitions": 1,
                        }
                    ],
                },
            },
            blocking=True,
        )
        mock_api_gordias.send_command.assert_any_call(
            {
                "mapCommand": "selectRoomsClean",
                "mapId": "mem_map_123",
                "type": 1,
                "roomInfo": [
                    {
                        "roomId": 1,
                        "sweepMode": 1,
                        "vacuumMode": "standard",
                        "waterPumpRate": "low",
                        "numberOfCleaningRepetitions": 1,
                    }
                ],
            }
        )

        # 2. Test Climate Operations
        # Set Temperature
        await hass.services.async_call(
            "climate",
            "set_temperature",
            {"entity_id": climate_entity_id, "temperature": 24.0},
            blocking=True,
        )
        mock_api_ac.send_command.assert_any_call({"targetTemperatureC": 24.0})

        # Set Mode
        await hass.services.async_call(
            "climate",
            "set_hvac_mode",
            {"entity_id": climate_entity_id, "hvac_mode": "cool"},
            blocking=True,
        )

        # Set climate fan mode
        await hass.services.async_call(
            "climate",
            "set_fan_mode",
            {"entity_id": climate_entity_id, "fan_mode": "low"},
            blocking=True,
        )
        mock_api_ac.send_command.assert_any_call({"fanSpeedSetting": "LOW"})

        # Set climate swing mode
        await hass.services.async_call(
            "climate",
            "set_swing_mode",
            {"entity_id": climate_entity_id, "swing_mode": "on"},
            blocking=True,
        )
        mock_api_ac.send_command.assert_any_call({"verticalSwing": "ON"})

        # Turn Climate off and on
        await hass.services.async_call(
            "climate", "turn_off", {"entity_id": climate_entity_id}, blocking=True
        )
        mock_api_ac.send_command.assert_any_call({"executeCommand": "OFF"})

        await hass.services.async_call(
            "climate", "turn_on", {"entity_id": climate_entity_id}, blocking=True
        )
        mock_api_ac.send_command.assert_any_call({"executeCommand": "ON"})

        # 3. Test Fan Operations
        # Preset Mode
        await hass.services.async_call(
            "fan",
            "set_preset_mode",
            {"entity_id": purifier_fan_entity_id, "preset_mode": "Manual"},
            blocking=True,
        )

        # Fan speed percentage
        await hass.services.async_call(
            "fan",
            "set_percentage",
            {"entity_id": purifier_fan_entity_id, "percentage": 50},
            blocking=True,
        )
        mock_api_pur.send_command.assert_any_call({"Fanspeed": 2})

        await hass.services.async_call(
            "fan",
            "turn_on",
            {"entity_id": purifier_fan_entity_id, "percentage": 100},
            blocking=True,
        )
        mock_api_pur.send_command.assert_any_call({"Fanspeed": 3})

        # Turn Off
        await hass.services.async_call(
            "fan", "turn_off", {"entity_id": purifier_fan_entity_id}, blocking=True
        )
        mock_api_pur.send_command.assert_any_call({"Workmode": "PowerOff"})

        # Turn On
        await hass.services.async_call(
            "fan", "turn_on", {"entity_id": purifier_fan_entity_id}, blocking=True
        )

        # 4. Test Camera Operations
        camera_state = hass.states.get(camera_entity_id)
        assert camera_state is not None
        assert "calibration_points" in camera_state.attributes

        # 5. Test Switch Operations (via WellbeingSwitch unit test to bypass unique_id conflict)
        sw = WellbeingSwitch(coordinator, entry, "pnc_pur1", "UILight")
        assert sw.is_on is False

        with patch.object(client, "set_feature_state", AsyncMock()) as mock_set_feature:
            await sw.async_turn_on()
            mock_set_feature.assert_called_with("pnc_pur1", "UILight", True)

            await sw.async_turn_off()
            mock_set_feature.assert_called_with("pnc_pur1", "UILight", False)

        # Clean unload
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
