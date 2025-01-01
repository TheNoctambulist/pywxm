"""An SDK for querying WeatherXM data."""

from .api import (
    AuthenticationError,
    ForecastType,
    UnexpectedError,
    WxmApi,
    WxmClient,
    WxmError,
)
from .model import (
    BatteryState,
    DailyForecast,
    DeviceRelation,
    ForecastForDate,
    HourlyForecast,
    HourlyWeatherData,
    Location,
    WeatherForecast,
    WxmDevice,
)

# Explicitly export the public API to satisfy mypy strict type checking.
# fmt:off
__all__ = [
    # API
    "WxmError",
    "AuthenticationError",
    "UnexpectedError",
    "WxmApi",
    "WxmClient",
    "ForecastType",
    # Model
    "BatteryState",
    "DailyForecast",
    "DeviceRelation",
    "ForecastForDate",
    "HourlyForecast",
    "HourlyWeatherData",
    "Location",
    "WeatherForecast",
    "WxmDevice",
]
# fmt:on
