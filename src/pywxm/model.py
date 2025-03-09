"""Classes to capture the WeatherXM Data Model."""

import datetime
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class DeviceRelation(StrEnum):
    """Whether the WeatherXM device is owned by the account or just followed."""

    OWNED = "owned"
    FOLLOWED = "followed"


class BatteryState(StrEnum):
    """The battery state of a WeatherXM device."""

    OK = "ok"
    LOW = "low"


@dataclass(frozen=True, kw_only=True)
class Location:
    """Represents a location on the Earth.

    Latitude and Longitude values are represented in decimal degrees.
    """

    latitude: float
    longitude: float

    @classmethod
    def unmarshal(cls, data: dict[str, float]) -> "Location":  # noqa: D102
        return Location(latitude=data["lat"], longitude=data["lon"])


@dataclass(kw_only=True)
class HourlyWeatherData:
    """Detailed weather data.

    Data is valid at the specified timestamp.
    """

    timestamp: datetime.datetime
    temperature: float
    """Temperature in degrees Celsius."""
    apparent_temperature: float
    """Apparent temperature in degrees Celsius."""
    dew_point: float
    """Dew point in degrees Celsius."""
    humidity: int
    """Humidity in %"""
    precipitation_rate: float
    """Current precipitation rate in mm/h."""
    precipitation_accumulated: float
    """Accumlated precipitation for the day in mm."""
    wind_speed: float
    """Wind speed in m/s."""
    wind_gust: float
    """Wind gust speed in m/s."""
    wind_direction: int
    """Originating wind direction in degrees."""
    absolute_pressure: float
    """Absolute Air Pressure in hPa."""
    uv_index: int
    solar_irradiance: float
    """Solar Irradiance in W/m2."""
    icon: str
    """String identifier for the current weather state.

    Possible icon values are not documented.
    """

    @classmethod
    def unmarshal(cls, data: dict[str, Any]) -> "HourlyWeatherData":  # noqa: D102
        return HourlyWeatherData(
            timestamp=datetime.datetime.fromisoformat(data["timestamp"]),
            temperature=data["temperature"],
            apparent_temperature=data["feels_like"],
            dew_point=data["dew_point"],
            humidity=data["humidity"],
            precipitation_rate=data["precipitation"],
            precipitation_accumulated=data["precipitation_accumulated"],
            wind_speed=data["wind_speed"],
            wind_gust=data["wind_gust"],
            wind_direction=data["wind_direction"],
            absolute_pressure=data["pressure"],
            uv_index=data["uv_index"],
            solar_irradiance=data["solar_irradiance"],
            icon=data["icon"],
        )


@dataclass(kw_only=True)
class WxmDevice:
    """Represents a WeatherXM Device."""

    id: str
    """Unique identifier for the device."""
    name: str
    """Public name for the device."""
    friendly_name: str | None
    """Optional friendly name for the device."""

    relation: DeviceRelation
    """Whether the device is owned by the account, or just followed."""

    weather_station_model: str
    """The model of the weather station."""
    firmware_version: str
    """Current firmware version of the weather station."""

    address: str
    """Address where the weather station is installed."""
    timezone: str
    """Timezone where the weather station is installed."""
    location: Location
    """Location of the weather station."""

    battery_state: BatteryState
    """Current battery state of the weather station."""

    current_weather: HourlyWeatherData
    """Latest weather data reported by the station."""

    @classmethod
    def unmarshal(cls, data: dict[str, Any]) -> "WxmDevice":  # noqa: D102
        attributes = data["attributes"]
        bundle = data["bundle"]
        return WxmDevice(
            id=data["id"],
            name=data["name"],
            friendly_name=attributes.get("friendlyName", None),
            relation=DeviceRelation(data["relation"]),
            weather_station_model=bundle["ws_model"],
            firmware_version=attributes["firmware"]["current"],
            address=data["address"],
            timezone=data["timezone"],
            location=Location.unmarshal(data["location"]),
            battery_state=BatteryState(data["bat_state"]),
            current_weather=HourlyWeatherData.unmarshal(data["current_weather"]),
        )


@dataclass(kw_only=True)
class HourlyForecast:
    """Weather forecast data for an hourly forecast."""

    timestamp: datetime.datetime
    temperature: float
    feels_like_temperature: float
    humidity: int
    pressure: float
    precipitation: float
    precipitation_probability: int
    wind_speed: float
    wind_direction: int
    uv_index: int
    icon: str

    @classmethod
    def unmarshal(cls, data: dict[str, Any]) -> "HourlyForecast":  # noqa: D102
        return HourlyForecast(
            timestamp=datetime.datetime.fromisoformat(data["timestamp"]),
            temperature=data["temperature"],
            feels_like_temperature=data["feels_like"],
            humidity=data["humidity"],
            pressure=data["pressure"],
            precipitation=data["precipitation"],
            precipitation_probability=data["precipitation_probability"],
            wind_speed=data["wind_speed"],
            wind_direction=data["wind_direction"],
            uv_index=data["uv_index"],
            icon=data["icon"],
        )


@dataclass(kw_only=True)
class DailyForecast:
    """Weather forecast data for a daily forecast."""

    forecast_date: datetime.date
    temperature_min: float
    temperature_max: float
    humidity: int
    pressure: float
    precipitation_probability: int
    precipitation_intensity: float
    precipitation_type: str
    wind_speed: float
    wind_direction: int
    uv_index: int
    icon: str

    @classmethod
    def unmarshal(cls, data: dict[str, Any]) -> "DailyForecast":  # noqa: D102
        return DailyForecast(
            forecast_date=datetime.datetime.fromisoformat(data["timestamp"]).date(),
            temperature_min=data["temperature_min"],
            temperature_max=data["temperature_max"],
            humidity=data["humidity"],
            pressure=data["pressure"],
            precipitation_probability=data["precipitation_probability"],
            precipitation_intensity=data["precipitation_intensity"],
            precipitation_type=data["precipitation_type"],
            wind_speed=data["wind_speed"],
            wind_direction=data["wind_direction"],
            uv_index=data["uv_index"],
            icon=data["icon"],
        )


@dataclass(kw_only=True)
class ForecastForDate:
    """Forecast data for a specific date.

    Depending on the request used, the forecast may contain hourly forecasts,
    daily forecasts, or both.
    """

    forecast_date: datetime.date
    timezone: str
    hourly_forecasts: list[HourlyForecast] | None
    daily_forecast: DailyForecast | None

    @classmethod
    def unmarshal(cls, data: dict[str, Any]) -> "ForecastForDate":  # noqa: D102
        hourly_data: list[dict[str, Any]] = data.get("hourly", [])
        hourly_forecasts = [HourlyForecast.unmarshal(d) for d in hourly_data]

        daily_data = data.get("daily")
        daily_forecast = None
        if daily_data:
            daily_forecast = DailyForecast.unmarshal(daily_data)

        return ForecastForDate(
            forecast_date=datetime.date.fromisoformat(data["date"]),
            timezone=data["tz"],
            hourly_forecasts=hourly_forecasts,
            daily_forecast=daily_forecast,
        )


@dataclass
class WeatherForecast:
    """Encapsulates a WeatherXM weather forecast."""

    forecast: list[ForecastForDate]

    @classmethod
    def unmarshal(cls, data: list[dict[str, Any]]) -> "WeatherForecast":  # noqa: D102
        return WeatherForecast(
            forecast=[ForecastForDate.unmarshal(d) for d in data],
        )


@dataclass
class TokenSummary:
    """Token summary for a reward event."""

    timestamp: datetime.datetime
    base_reward: float
    total_business_boost_reward: float | None
    total_reward: float
    """Sum of base reward plus any boosts."""
    base_reward_score: int
    """Percentage of maximum base reward awarded to the station."""

    @classmethod
    def unmarshal(cls, data: dict[str, Any]) -> "TokenSummary":  # noqa: D102
        return TokenSummary(
            timestamp=datetime.datetime.fromisoformat(data["timestamp"]),
            base_reward=data["base_reward"],
            total_business_boost_reward=data.get("total_business_boost_reward"),
            total_reward=data["total_reward"],
            base_reward_score=data["base_reward_score"],
        )


@dataclass
class DeviceRewards:
    """Reward information for a device."""

    total_rewards: float
    latest_reward: TokenSummary

    @classmethod
    def unmarshal(cls, data: dict[str, Any]) -> "DeviceRewards":  # noqa: D102
        return DeviceRewards(
            total_rewards=data["total_rewards"],
            latest_reward=TokenSummary.unmarshal(data["latest"]),
        )
