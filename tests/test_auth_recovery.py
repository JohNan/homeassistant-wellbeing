"""Test recovery through the API client and Home Assistant coordinator."""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock, call

import jwt
import pytest
from aiohttp import ClientResponse, ClientResponseError, ClientSession, RequestInfo
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed
from multidict import CIMultiDict, CIMultiDictProxy
from pytest_homeassistant_custom_component.common import MockConfigEntry
from yarl import URL

from custom_components.wellbeing import (
    WellbeingDataUpdateCoordinator,
    WellBeingTokenManager,
)
from custom_components.wellbeing.api import WellbeingApiClient
from custom_components.wellbeing.auth import WellbeingHubAPI
from custom_components.wellbeing.const import DOMAIN

API = "https://api.developer.electrolux.one/api/v1"


def access_token(name):
    return jwt.encode(
        {"exp": datetime.now(UTC) + timedelta(hours=1), "jti": name},
        "test-only-key-with-at-least-thirty-two-bytes",
        algorithm="HS256",
    )


@pytest.fixture
def api(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "api_key": "test-key",
            "access_token": access_token("old"),
            "refresh_token": "old-refresh",
        },
    )
    entry.add_to_hass(hass)
    session = Mock(spec=ClientSession, request=AsyncMock())
    hub = WellbeingHubAPI(session, WellBeingTokenManager(hass, entry))
    coordinator = WellbeingDataUpdateCoordinator(
        hass, WellbeingApiClient(hub), timedelta(seconds=60), entry
    )
    return entry, session.request, hub, coordinator


def mock_responses(request, *responses):
    replies = iter(responses)

    async def respond(method, url, *, headers, json):
        status, payload = next(replies)
        info = RequestInfo(URL(url), method, CIMultiDictProxy(CIMultiDict(headers)))
        response = Mock(spec=ClientResponse, status=status, request_info=info)
        response.json = AsyncMock(return_value=payload)
        if status >= 400:
            response.raise_for_status.side_effect = ClientResponseError(
                info, (), status=status
            )
        await asyncio.sleep(0)
        return response

    request.side_effect = respond


@pytest.mark.parametrize("status", [401, 403])
async def test_poll_recovers_rejected_access_token(api, status):
    entry, request, _, coordinator = api
    old_token = entry.data["access_token"]
    new_token = access_token("new")
    mock_responses(
        request,
        (
            200,
            [
                {
                    "applianceId": "purifier",
                    "applianceName": "Pure A9",
                    "applianceType": "PUREA9",
                }
            ],
        ),
        (
            200,
            {
                "applianceInfo": {
                    "deviceType": "AIR_PURIFIER",
                    "brand": "Electrolux",
                    "serialNumber": "serial",
                },
                "capabilities": {},
            },
        ),
        (status, {}),
        (200, {"accessToken": new_token, "refreshToken": "new-refresh"}),
        (
            200,
            {
                "status": "enabled",
                "connectionState": "Connected",
                "properties": {"reported": {"Workmode": "Manual", "Fanspeed": 3}},
            },
        ),
    )

    data = await coordinator._async_update_data()

    assert data["appliances"].get_appliance("purifier") is not None
    assert entry.data["access_token"] == new_token
    assert entry.data["refresh_token"] == "new-refresh"
    assert request.await_args_list[-3:] == [
        call(
            "get",
            f"{API}/appliances/purifier/state",
            headers={"authorization": f"Bearer {old_token}", "x-api-key": "test-key"},
            json=None,
        ),
        call(
            "post",
            f"{API}/token/refresh",
            headers={},
            json={"refreshToken": "old-refresh"},
        ),
        call(
            "get",
            f"{API}/appliances/purifier/state",
            headers={"authorization": f"Bearer {new_token}", "x-api-key": "test-key"},
            json=None,
        ),
    ]


async def test_persistent_forbidden_keeps_polling(api):
    _, request, _, coordinator = api
    mock_responses(
        request,
        (403, {}),
        (200, {"accessToken": access_token("new"), "refreshToken": "new-refresh"}),
        (403, {}),
        (403, {}),
        (200, []),
    )

    for _ in range(2):
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()
    assert (await coordinator._async_update_data())["appliances"].appliances == {}
    assert [args.args[0] for args in request.await_args_list] == [
        "get",
        "post",
        "get",
        "get",
        "get",
    ]


@pytest.mark.parametrize("status", [400, 401, 403, 503])
async def test_refresh_failure_classification(api, status):
    entry, request, _, coordinator = api
    mock_responses(request, (403, {}), (status, {}))

    error = UpdateFailed if status == 503 else ConfigEntryAuthFailed
    with pytest.raises(error):
        await coordinator._async_update_data()

    assert entry.data["refresh_token"] == "old-refresh"
    assert request.await_count == 2


async def test_unauthorized_after_refresh_requires_reauth(api):
    _, request, _, coordinator = api
    mock_responses(
        request,
        (401, {}),
        (200, {"accessToken": access_token("new"), "refreshToken": "new-refresh"}),
        (401, {}),
    )

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()
    assert request.await_count == 3


async def test_concurrent_rejections_share_token_refresh(api):
    _, request, hub, _ = api
    mock_responses(
        request,
        (403, {}),
        (403, {}),
        (200, {"accessToken": access_token("new"), "refreshToken": "new-refresh"}),
        (200, []),
        (200, []),
    )

    assert await asyncio.gather(
        hub.async_get_appliances(), hub.async_get_appliances()
    ) == [[], []]
    assert sum(args.args[0] == "post" for args in request.await_args_list) == 1


async def test_command_is_not_replayed_after_rejection(api):
    _, request, hub, _ = api
    mock_responses(request, (403, {}))

    response = await hub.auth.request(
        "put", "appliances/purifier/command", json={"Workmode": "Quiet"}
    )

    assert response.status == 403
    assert request.await_count == 1
