"""Tests for polling with livestream enabled."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from homeassistant.const import Platform

from custom_components.wellbeing.api import WellbeingApiClient


class FakeAppliance:
    name = "Pure A9"
    type = "PUREA9"
    brand = "Electrolux"
    serial_number = "serial-number"
    device_type = "AIR_PURIFIER"
    initial_data = {"applianceType": type}
    capabilities_data = {"Fanspeed": {"access": "readwrite", "min": 1, "max": 9}}

    def __init__(self, appliance_id="appliance-id"):
        self.id = appliance_id
        self.next_speed = 2
        self.block_update = False
        self.update_started = asyncio.Event()
        self.continue_update = asyncio.Event()
        self.state_data = {
            "status": "enabled",
            "connectionState": "Connected",
            "properties": {"reported": {}},
        }

    @property
    def state(self):
        return self.state_data["properties"]["reported"]

    async def async_update(self):
        if self.block_update:
            self.update_started.set()
            await self.continue_update.wait()
        self.state_data = {
            "status": "enabled",
            "connectionState": "Connected",
            "properties": {
                "reported": {
                    "Workmode": "Manual",
                    "Fanspeed": self.next_speed,
                }
            },
        }


@pytest.mark.asyncio
async def test_polling_does_not_prefetch_livestream_configuration():
    appliance = FakeAppliance()
    hub = SimpleNamespace(
        async_get_appliances=AsyncMock(return_value=[appliance]),
        async_get_livestream_configurations=AsyncMock(),
    )
    client = WellbeingApiClient(hub)

    await client.async_get_appliances()

    hub.async_get_livestream_configurations.assert_not_awaited()


@pytest.mark.asyncio
async def test_polling_replaces_intermediate_livestream_value():
    appliance = FakeAppliance()
    hub = SimpleNamespace(async_get_appliances=AsyncMock(return_value=[appliance]))
    client = WellbeingApiClient(hub)

    appliances = await client.async_get_appliances()
    client.update_appliance_state(appliances, appliance.id, "Fanspeed", 8)
    assert (
        appliances.get_appliance(appliance.id)
        .get_entity(Platform.FAN, "Fanspeed")
        .state
        == 8
    )

    appliance.next_speed = 3
    appliances = await client.async_get_appliances()

    assert (
        appliances.get_appliance(appliance.id)
        .get_entity(Platform.FAN, "Fanspeed")
        .state
        == 3
    )


@pytest.mark.asyncio
async def test_livestream_update_during_poll_is_preserved():
    appliance = FakeAppliance()
    hub = SimpleNamespace(async_get_appliances=AsyncMock(return_value=[appliance]))
    client = WellbeingApiClient(hub)
    appliances = await client.async_get_appliances()

    appliance.next_speed = 3
    appliance.block_update = True
    polling = asyncio.create_task(client.async_get_appliances())
    await appliance.update_started.wait()

    client.update_appliance_state(appliances, appliance.id, "Fanspeed", 8)
    appliance.continue_update.set()
    appliances = await polling

    assert (
        appliances.get_appliance(appliance.id)
        .get_entity(Platform.FAN, "Fanspeed")
        .state
        == 8
    )


@pytest.mark.asyncio
async def test_connection_event_during_poll_is_preserved():
    appliance = FakeAppliance()
    hub = SimpleNamespace(async_get_appliances=AsyncMock(return_value=[appliance]))
    client = WellbeingApiClient(hub)
    appliances = await client.async_get_appliances()

    appliance.block_update = True
    polling = asyncio.create_task(client.async_get_appliances())
    await appliance.update_started.wait()

    client.update_appliance_state(
        appliances, appliance.id, "connectionState", "Disconnected"
    )
    appliance.continue_update.set()
    appliances = await polling

    assert (
        appliances.get_appliance(appliance.id)
        .get_entity(Platform.BINARY_SENSOR, "connectionState")
        .state
        is False
    )


@pytest.mark.asyncio
async def test_event_for_polled_appliance_survives_other_appliance_poll():
    first = FakeAppliance("first-id")
    second = FakeAppliance("second-id")
    hub = SimpleNamespace(async_get_appliances=AsyncMock(return_value=[first, second]))
    client = WellbeingApiClient(hub)
    appliances = await client.async_get_appliances()

    first.next_speed = 3
    second.block_update = True
    polling = asyncio.create_task(client.async_get_appliances())
    await second.update_started.wait()

    client.update_appliance_state(appliances, first.id, "Fanspeed", 8)
    second.continue_update.set()
    appliances = await polling

    assert (
        appliances.get_appliance(first.id).get_entity(Platform.FAN, "Fanspeed").state
        == 8
    )


@pytest.mark.asyncio
async def test_poll_supersedes_event_received_before_appliance_request():
    first = FakeAppliance("first-id")
    second = FakeAppliance("second-id")
    hub = SimpleNamespace(async_get_appliances=AsyncMock(return_value=[first, second]))
    client = WellbeingApiClient(hub)
    appliances = await client.async_get_appliances()

    first.block_update = True
    first.continue_update.clear()
    second.next_speed = 3
    polling = asyncio.create_task(client.async_get_appliances())
    await first.update_started.wait()

    client.update_appliance_state(appliances, second.id, "Fanspeed", 8)
    first.continue_update.set()
    appliances = await polling

    assert (
        appliances.get_appliance(second.id).get_entity(Platform.FAN, "Fanspeed").state
        == 3
    )
