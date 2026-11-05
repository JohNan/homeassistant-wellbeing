"""Tests for Wellbeing climate temperatures."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.const import Platform
from homeassistant.util.unit_system import METRIC_SYSTEM, US_CUSTOMARY_SYSTEM
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.wellbeing.api import Appliance, Appliances
from custom_components.wellbeing.const import DOMAIN


@pytest.mark.parametrize(
    ("unit_system", "current", "target", "minimum", "maximum", "setpoint"),
    [
        (METRIC_SYSTEM, 22.0, 24.0, 16.0, 32.0, 25.0),
        (US_CUSTOMARY_SYSTEM, 72.0, 75.0, 61.0, 90.0, 77.0),
    ],
)
async def test_climate_temperatures(
    hass, unit_system, current, target, minimum, maximum, setpoint
):
    """Keep displayed temperatures and device commands in their respective units."""
    hass.config.units = unit_system
    appliance = Appliance("Climate AC", "pnc_ac1", "COMFORT600")
    appliance.brand = "Electrolux"
    appliance.setup(
        {
            "mode": "cool",
            "applianceState": True,
            "ambientTemperatureC": 22.0,
            "targetTemperatureC": 24.0,
            "fanSpeedSetting": "low",
            "verticalSwing": False,
        },
        {},
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"api_key": "test", "access_token": "test", "refresh_token": "test"},
        options={"stream": False},
    )
    entry.add_to_hass(hass)

    with (
        patch("custom_components.wellbeing.WellbeingHubAPI"),
        patch(
            "custom_components.wellbeing.WellbeingApiClient.async_get_appliances",
            return_value=Appliances({"pnc_ac1": appliance}),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "climate.wellbeing_climate_ac_mode"
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.attributes["current_temperature"] == pytest.approx(current)
        assert state.attributes["temperature"] == pytest.approx(target)
        assert state.attributes["min_temp"] == pytest.approx(minimum)
        assert state.attributes["max_temp"] == pytest.approx(maximum)

        coordinator = hass.data[DOMAIN][entry.entry_id]
        with (
            patch.object(
                coordinator.api, "ac_set_temperature", new_callable=AsyncMock
            ) as set_temperature,
            patch.object(coordinator, "async_request_refresh"),
        ):
            await hass.services.async_call(
                "climate",
                "set_temperature",
                {"entity_id": entity_id, "temperature": setpoint},
                blocking=True,
            )
            set_temperature.assert_awaited_once_with("pnc_ac1", 25.0)

        appliance.get_entity(Platform.SENSOR, "ambientTemperatureC").clear_state()
        appliance.get_entity(Platform.SENSOR, "targetTemperatureC").clear_state()
        coordinator.async_update_listeners()
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state.attributes["current_temperature"] is None
        assert state.attributes["temperature"] is None
