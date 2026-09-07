"""Tests for api.py."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp import ClientResponseError
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import Platform

from custom_components.wellbeing.api import (
    Appliance,
    ApplianceBinary,
    ApplianceCamera,
    ApplianceCleaningSessionSensor,
    ApplianceClimate,
    ApplianceConsumableSensor,
    ApplianceFan,
    Appliances,
    ApplianceSensor,
    ApplianceVacuum,
    LouverSwingMode,
    Model,
    WellbeingApiClient,
    WorkMode,
)


def test_enums():
    """Test model enums parsing."""
    assert Model.PUREi9.value == "PUREi9"
    assert WorkMode.OFF.value == "PowerOff"
    assert LouverSwingMode.OFF.value == "off"


def test_appliance_entities():
    """Test basic ApplianceEntity subclasses."""
    sensor = ApplianceSensor(
        "Sensor Name",
        "sensor_attr",
        "unit",
        SensorDeviceClass.TEMPERATURE,
        "diagnostic",
        SensorStateClass.MEASUREMENT,
    )
    assert sensor.entity_type == Platform.SENSOR
    assert sensor.state is None
    sensor.setup({"sensor_attr": 25.5})
    assert sensor.state == 25.5
    sensor.clear_state()
    assert sensor.state is None

    fan = ApplianceFan("Fan Name", "fan_attr")
    assert fan.entity_type == Platform.FAN

    vacuum = ApplianceVacuum("Vacuum Name", "vacuum_attr")
    assert vacuum.entity_type == Platform.VACUUM

    binary = ApplianceBinary(
        "Binary Name", "binary_attr", BinarySensorDeviceClass.CONNECTIVITY
    )
    assert binary.entity_type == Platform.BINARY_SENSOR

    climate = ApplianceClimate("Climate Name", "climate_attr")
    assert climate.entity_type == Platform.CLIMATE

    camera = ApplianceCamera("Camera Name", "camera_attr")
    assert camera.entity_type == Platform.CAMERA
    camera.setup({"camera_attr": b"image_data"})
    assert camera.state == b"image_data"

    consumable = ApplianceConsumableSensor("Consumable", "filter_life", 1000)
    assert consumable.entity_type == Platform.SENSOR
    consumable.setup({"filter_life": 500})
    assert consumable.state == 50.0  # 500 / 1000 * 100

    session_sensor = ApplianceCleaningSessionSensor(
        "Session", "clean_time", "sessionKey"
    )
    assert session_sensor.entity_type == Platform.SENSOR
    session_sensor.setup({"cleaningSession": {"sessionKey": 60}})
    assert session_sensor.state == 60


def test_appliance_setup_purei9():
    """Test Appliance parsing for PUREi9 model."""
    appliance = Appliance("Vacuum", "pnc_1", "PUREi9")
    appliance.device = "ROBOTIC_VACUUM_CLEANER"

    data = {
        "FrmVer_NIU": "v1.2",
        "Workmode": "Manual",
        "batteryStatus": 85,
        "powerMode": 3,
        "ecoMode": "off",
        "vacuumMode": "eco",
    }
    appliance.setup(data, {})
    assert appliance.firmware == "v1.2"
    assert appliance.mode == WorkMode.MANUAL
    assert appliance.power_mode == 3
    assert appliance.eco_mode == "off"
    assert appliance.vacuum_mode == "eco"
    assert len(appliance.entities) > 0

    # Test get_entity helper
    entity = appliance.get_entity(Platform.SENSOR, "batteryStatus")
    assert entity is not None
    assert entity.state == 85

    # Test non-existent entity helper raises StopIteration
    with pytest.raises(StopIteration):
        appliance.get_entity(Platform.SENSOR, "nonexistent")

    # Test preset modes
    assert appliance.preset_modes == [WorkMode.AUTO, WorkMode.MANUAL, WorkMode.OFF]
    assert appliance.work_mode_from_preset_mode("Manual") == WorkMode.MANUAL

    # Test battery range
    assert appliance.battery_range == (2, 6)

    # Test vacuum fan speed list and speed setting
    assert "smart" in appliance.vacuum_fan_speed_list
    assert appliance.vacuum_fan_speed == "power"  # mapped from powerMode=3
    appliance.vacuum_set_fan_speed("smart")
    assert appliance.power_mode == 2  # smart maps to 2


def test_appliance_setup_alternative_firmware():
    """Test other firmware field options in Appliance setup."""
    appliance1 = Appliance("App1", "pnc_1", "WELLA5")
    appliance1.device = "AIR_PURIFIER"
    appliance1.setup({"VmNo_NIU": "v1.0"}, {})
    assert appliance1.firmware == "v1.0"

    appliance2 = Appliance("App2", "pnc_2", "WELLA7")
    appliance2.device = "AIR_PURIFIER"
    appliance2.setup({"applianceUiSwVersion": "v2.0"}, {})
    assert appliance2.firmware == "v2.0"

    appliance3 = Appliance("App3", "pnc_3", "PUREA9")
    appliance3.device = "AIR_PURIFIER"
    appliance3.setup({"firmwareVersion": "v3.0"}, {})
    assert appliance3.firmware == "v3.0"


def test_appliance_setup_muju():
    """Test Appliance preset modes and speeds for Muju model."""
    appliance = Appliance("AirPurifier", "pnc_muju", "Muju")
    appliance.device = "AIR_PURIFIER"
    appliance.setup({"Workmode": "Manual", "LouverSwing": "off"}, {})
    assert appliance.preset_modes == [
        WorkMode.SMART,
        WorkMode.QUITE,
        WorkMode.MANUAL,
        WorkMode.OFF,
    ]
    assert appliance.work_mode_from_preset_mode("PowerOff") == WorkMode.OFF

    # speed range
    assert appliance.speed_range == (1, 3)


def test_appliances_collection():
    """Test Appliances collection wrapper."""
    app1 = Appliance("A", "1", "PUREi9")
    apps = Appliances({"1": app1})
    assert apps.get_appliance("1") == app1
    assert apps.get_appliance("2") is None


@pytest.mark.asyncio
async def test_api_client_ensure_loaded():
    """Test WellbeingApiClient ensures remote state is loaded."""
    mock_hub = AsyncMock()
    mock_appliance = MagicMock()
    mock_appliance.id = "pnc_1"
    mock_hub.async_get_appliances.return_value = [mock_appliance]

    client = WellbeingApiClient(mock_hub)
    await client._ensure_loaded()

    assert "pnc_1" in client._api_appliances
    mock_hub.async_get_appliances.assert_called_once()


@pytest.mark.asyncio
async def test_api_client_livestream():
    """Test livestream state updates."""
    mock_hub = AsyncMock()
    mock_appliance = MagicMock()
    mock_appliance.id = "pnc_1"
    mock_appliance.state_data = {}
    mock_hub.async_get_appliances.return_value = [mock_appliance]
    client = WellbeingApiClient(mock_hub)
    await client._ensure_loaded()
    mock_hub.async_get_livestream_configurations.assert_not_awaited()

    # Test update_appliance_state
    ha_appliances = MagicMock()
    ha_appliance = MagicMock()
    ha_appliances.get_appliance.return_value = ha_appliance

    # Status property update
    client.update_appliance_state(ha_appliances, "pnc_1", "status", "Running")
    assert mock_appliance.state_data["status"] == "Running"

    # Other property update
    client.update_appliance_state(ha_appliances, "pnc_1", "battery", 90)
    assert mock_appliance.state_data["properties"]["reported"]["battery"] == 90
    ha_appliance.setup.assert_called()


@pytest.mark.asyncio
async def test_api_client_update_error():
    """Test handling of client update errors."""
    mock_hub = AsyncMock()
    # Simulate a ClientResponseError during load
    mock_hub.async_get_appliances.side_effect = ClientResponseError(
        request_info=MagicMock(), history=(), status=401, message="Unauthorized"
    )

    client = WellbeingApiClient(mock_hub)
    with pytest.raises(ClientResponseError):
        await client._ensure_loaded()
