"""An example application."""

import asyncio
import datetime
import getpass
import logging
import pprint
import sys

import aiohttp
import pywxm


async def main() -> None | int:
    refresh_token: str | None = None
    if len(sys.argv) > 1:
        refresh_token = sys.argv[1]

    logging.basicConfig(level=logging.INFO)

    async with aiohttp.ClientSession() as session:
        wxm_client = pywxm.WxmClient(session, refresh_token)

        if not refresh_token:
            username = input("Username: ")
            password = getpass.getpass()

            try:
                refresh_token = await wxm_client.login(username, password)
                print(f"refresh_token={refresh_token}")
            except pywxm.AuthenticationError as e:
                print(e)
                return 1

        wxm_api = pywxm.WxmApi(wxm_client)

        devices = await wxm_api.list_devices()
        pprint.pp(devices)

        rewards = await wxm_api.get_latest_rewards(devices[0].id)
        print("*** Rewards: ")
        pprint.pp(rewards)

        forecast = await wxm_api.get_forecast(
            devices[0].id,
            datetime.date.today(),  # noqa: DTZ011
            datetime.date.today() + datetime.timedelta(days=3),  # noqa: DTZ011
            forecast_type=pywxm.ForecastType.BOTH,
        )
        print("*** Forecast: ")
        pprint.pp(forecast)

        while True:
            current_data = await wxm_api.get_device(devices[0].id)
            current_weather = current_data.current_weather
            print(
                "+++ Weather at ",
                current_weather.timestamp.isoformat(timespec="minutes"),
            )
            print(f"       Temperature: {current_weather.temperature:.1f}°C")
            print(f"       Humidity:    {current_weather.humidity}%")
            print(f"       Wind:        {current_weather.wind_speed} m/s")
            print(f"                    from {current_weather.wind_direction}°")
            await asyncio.sleep(120.0)


exit_code = asyncio.run(main())
if exit_code:
    sys.exit(exit_code)
