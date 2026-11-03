"""Recover from access token rejections during Electrolux API reads."""

from __future__ import annotations

import asyncio
from time import monotonic

from aiohttp import ClientResponse, ClientSession
from pyelectroluxgroup.api import ElectroluxHubAPI
from pyelectroluxgroup.auth import Auth
from pyelectroluxgroup.token_manager import TokenManager

_FORCED_REFRESH_INTERVAL = 300


class AuthenticationRejected(Exception):
    """Electrolux rejected a token refresh or a freshly refreshed access token."""


class _RecoveringAuth(Auth):
    def __init__(self, hub: WellbeingHubAPI) -> None:
        auth = hub.auth
        super().__init__(
            auth.session, auth.host, auth.api_key, hub.async_get_access_token
        )
        self._hub = hub

    async def request(self, method: str, path: str, **kwargs) -> ClientResponse:
        response = await super().request(method, path, **kwargs)
        if (
            method.lower() != "get"
            or kwargs.get("skip_auth_headers")
            or response.status not in {401, 403}
        ):
            return response

        authorization = response.request_info.headers.get("Authorization", "")
        if not authorization.startswith("Bearer "):
            return response

        # Release the failed request before acquiring a connection to refresh.
        response.release()
        if not await self._hub.async_refresh_rejected_token(
            authorization.removeprefix("Bearer ")
        ):
            response.raise_for_status()

        response = await super().request(method, path, **kwargs)
        if response.status == 401:
            response.release()
            raise AuthenticationRejected(
                "Electrolux rejected the refreshed access token"
            )
        return response


class WellbeingHubAPI(ElectroluxHubAPI):
    """Share token rotation across polling, live stream setup and commands."""

    def __init__(self, session: ClientSession, token_manager: TokenManager) -> None:
        self._refresh_lock = asyncio.Lock()
        self._next_forced_refresh = float("-inf")
        super().__init__(session, token_manager)
        self.auth = _RecoveringAuth(self)

    async def async_get_access_token(self) -> str:
        """Return the current token, refreshing near expiry when necessary."""
        async with self._refresh_lock:
            if not self.token_manager.is_token_valid():
                await self._async_refresh_access_token()
            return self.token_manager.access_token

    async def async_refresh_rejected_token(self, rejected_token: str) -> bool:
        """Refresh once or reuse a token already rotated by another request."""
        async with self._refresh_lock:
            if self.token_manager.access_token != rejected_token:
                return True

            # A resource-level 403 can persist even with valid credentials.
            now = monotonic()
            if now < self._next_forced_refresh:
                return False
            self._next_forced_refresh = now + _FORCED_REFRESH_INTERVAL
            await self._async_refresh_access_token()
            return True

    async def _async_refresh_access_token(self) -> None:
        response = await self.auth.request(
            "post",
            "token/refresh",
            json={"refreshToken": self.token_manager.refresh_token},
            skip_auth_headers=True,
        )
        try:
            if response.status in {400, 401, 403}:
                raise AuthenticationRejected("Electrolux rejected the refresh token")
            response.raise_for_status()
            tokens = await response.json()
            self.token_manager.update(tokens["accessToken"], tokens["refreshToken"])
        finally:
            response.release()
