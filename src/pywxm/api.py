"""Classes wrapping the WeatherXM API."""

import asyncio
import datetime
import logging
from collections.abc import Awaitable, Callable
from enum import Enum, auto
from typing import Any

import aiohttp
import jwt
from yarl import URL

from .model import DeviceRewards, WeatherForecast, WxmDevice

_BASE_URL = URL("https://api.weatherxm.com/api/v1")

_LOGGER = logging.getLogger(__name__)


class WxmError(Exception):
    """Base exception class for errors from the WeatherXM API."""

    def __init__(self, message: str) -> None:
        """Initialise the WeatherXM error."""
        super().__init__(message)
        self.message = message


class AuthenticationError(WxmError):
    """Raised when an authentication error occurs.

    Authentication errors may occur during initial login, or if a problem occurs
    with token based authentication during other API interactions.
    """


class UnexpectedError(WxmError):
    """Raised when the API returns an unexpected error response.

    In most cases, simply retrying the query after a delay is the most
    appropriate response.
    """


RefreshTokenSubscriber = Callable[[str], Awaitable[Any]]
"""An interface for subscribing to notifications when the Refresh Token is updated.

The subscriber will be passed the updated Refresh Token."""


class WxmClient:
    """The WeatherXM Client.

    The Client should be used in conjunction with the WxmApi to query the WeatherXM API.
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        refresh_token: str | None = None,
    ) -> None:
        """Initialises the WxmClient.

        Args:
            session: An aiohttp ClientSession instance. The session can be
                shared with other APIs.
        """
        self._session = session
        self.refresh_token = refresh_token

        self._access_token: str | None = None
        self._access_token_expiry: datetime.datetime | None = None
        self._token_subscribers: set[RefreshTokenSubscriber] = set()

    async def login(self, username: str, password: str) -> str:
        """Login into the WeatherXM API and generate a new access token.

        Logging in is only required if there is no valid refresh token.

        Returns:
            The new refresh token.
        """
        data = {
            "username": username,
            "password": password,
        }
        async with self._session.post(_BASE_URL / "auth/login", json=data) as resp:
            if resp.ok:
                access_tokens: dict[str, str] = await resp.json()
                await self._update_tokens(access_tokens)
                return access_tokens["refreshToken"]

            if resp.status in (400, 500):
                error = await resp.json()
                raise AuthenticationError(error["message"])
            raise AuthenticationError("Unknown error")

    async def get(self, url: str, **kwargs: Any) -> aiohttp.ClientResponse:  # noqa: ANN401
        """Send a get request to the WeatherXM API."""
        await self._refresh_access_token()

        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self._access_token}"
        return await self._session.get(_BASE_URL / url, headers=headers, **kwargs)

    async def subscribe_refresh_token(self, subscriber: RefreshTokenSubscriber) -> None:
        """Subscribe to receive notifications whenever the refresh token changes.

        Has no effect if the subscriber is already subscribed.
        """
        self._token_subscribers.add(subscriber)

    async def unsubscribe_refresh_token(
        self, subscriber: RefreshTokenSubscriber
    ) -> None:
        """Unsubscribe from receiving refresh token notifications.

        Has no effect if the subscriber is not subscribed.
        """
        self._token_subscribers.discard(subscriber)

    async def _refresh_access_token(self) -> None:
        if (
            self._access_token is not None
            and self._access_token_expiry is not None
            and self._access_token_expiry > datetime.datetime.now(tz=datetime.UTC)
        ):
            return

        if self._access_token:
            _LOGGER.debug("Access token expired, refreshing")

        data = {"refreshToken": self.refresh_token}
        async with self._session.post(_BASE_URL / "auth/refresh", json=data) as resp:
            match resp.status:
                case _ if resp.ok:
                    access_tokens: dict[str, str] = await resp.json()
                    await self._update_tokens(access_tokens)
                case 400:
                    error = await resp.json()
                    raise AuthenticationError(error["message"])
                # 5xx errors from the Cloudflare proxy don't indicate an
                # authentication error. Clients can retry later.
                case _ if resp.status >= 500 and resp.status < 600:  # noqa: PLR2004
                    _LOGGER.info("%d status when refreshing access token", resp.status)
                    _LOGGER.debug(
                        "Unexpected status '%d' during token refresh. Response: %s",
                        resp.status,
                        await resp.text(),
                    )
                    raise UnexpectedError(f"{resp.status} status returned")
                case _:
                    _LOGGER.error(
                        ("Unexpected status '%d' during token refresh. Response: %s"),
                        resp.status,
                        await resp.text(),
                    )
                    raise AuthenticationError(f"Unknown error: {resp.status}")

    async def _update_tokens(self, access_tokens: dict[str, str]) -> None:
        old_refresh_token = self.refresh_token

        self.refresh_token = access_tokens["refreshToken"]
        self._access_token = access_tokens["token"]

        # Decode the token expiry time
        payload = jwt.decode(
            self._access_token, options={"verify_signature": False, "require": ["exp"]}
        )
        self._access_token_expiry = datetime.datetime.fromtimestamp(
            payload["exp"], tz=datetime.UTC
        )
        _LOGGER.debug("Updated access token. New expiry: %s", self._access_token_expiry)

        # Notify subscribers if the refresh token has changed.
        if old_refresh_token and old_refresh_token != self.refresh_token:
            for coro in asyncio.as_completed(
                [s(self.refresh_token) for s in self._token_subscribers]
            ):
                try:
                    _ = await coro
                except Exception:
                    _LOGGER.exception("Exception from subscriber")


class ForecastType(Enum):
    """The type of weather forecast data to retreive."""

    HOURLY = auto()
    DAILY = auto()
    BOTH = auto()


class WxmApi:
    """API for querying specific data from the WeatherXM API."""

    def __init__(self, client: WxmClient) -> None:
        """Initialises the WeatherXM API.

        Args:
            client: An authenticated WxmClient.
        """
        self.client = client

    async def list_devices(self) -> list[WxmDevice]:
        """Get the list of WeatherXM devices associated with the current user."""
        async with await self.client.get("me/devices") as resp:
            await self._raise_if_error(resp)

            if _LOGGER.isEnabledFor(logging.DEBUG):
                _LOGGER.debug("list_devices response: %s", await resp.text())

            devices_response: list[dict[str, Any]] = await resp.json()
            return [WxmDevice.unmarshal(d) for d in devices_response]

    async def get_device(self, device_id: str) -> WxmDevice:
        """Get the current status for a WeatherXM device."""
        async with await self.client.get(f"me/devices/{device_id}") as resp:
            await self._raise_if_error(resp)

            if _LOGGER.isEnabledFor(logging.DEBUG):
                _LOGGER.debug(
                    "get_device(%s) response: %s", device_id, await resp.text()
                )

            json_data = await resp.json()
            return WxmDevice.unmarshal(json_data)

    async def get_forecast(
        self,
        device_id: str,
        from_date: datetime.date,
        to_date: datetime.date,
        forecast_type: ForecastType = ForecastType.BOTH,
    ) -> WeatherForecast:
        """Get forecast weather data for a WeatherXM device.

        Forecast data may not be provided if the requested date range is too far
        in the future.
        """
        params = {
            "fromDate": from_date.isoformat(),
            "toDate": to_date.isoformat(),
        }
        if forecast_type != ForecastType.BOTH:
            # Parameter is named "exclude", but appears to actually be an "include" list
            params["exclude"] = "hourly" if ForecastType.HOURLY else "daily"

        async with await self.client.get(
            f"me/devices/{device_id}/forecast", params=params
        ) as resp:
            await self._raise_if_error(resp)

            if _LOGGER.isEnabledFor(logging.DEBUG):
                _LOGGER.debug(
                    "get_forecast(%s) response: %s", params, await resp.text()
                )

            json_data = await resp.json()
            return WeatherForecast.unmarshal(json_data)

    async def get_latest_rewards(self, device_id: str) -> DeviceRewards:
        """Get the latest rewards data for a WeatherXM device."""
        async with await self.client.get(f"devices/{device_id}/rewards") as resp:
            await self._raise_if_error(resp)

            if _LOGGER.isEnabledFor(logging.DEBUG):
                _LOGGER.debug(
                    "get_latest_rewards(%s) response: %s", device_id, await resp.text()
                )

            json_data = await resp.json()
            return DeviceRewards.unmarshal(json_data)

    async def _raise_if_error(self, resp: aiohttp.ClientResponse) -> None:
        """Raise an appropriate exception if an error response was received.

        Does nothing if the respose was OK.
        """
        if resp.ok:
            return

        error_message = f"Unknown response status: {resp.status}"
        if resp.content_type == "application/json":
            json_data = await resp.json()
            error_message = json_data["message"]

        match resp.status:
            case 400:  # Bad request
                # This error code will be raised if the input parameters were invalid
                # so we raise a ValueError for this.
                raise ValueError(error_message)
            case 401:  # Unauthorized request
                raise AuthenticationError(error_message)
            case 500:  # Unexpected error
                raise UnexpectedError(error_message)
            case 522:  # CloudFlare connection timeout response
                raise UnexpectedError("Connection timed out")
            case _:
                # This shouldn't occur
                raise UnexpectedError(error_message)
