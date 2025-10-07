"""Pytest configuration and fixtures."""

import pytest


@pytest.fixture
def sample_weather_data():
    """Sample weather data for testing."""
    return {
        "hourly": {
            "temperature_2m": [15.0, 16.0, 17.0, 18.0, 19.0, 20.0],
            "precipitation": [0.0, 0.5, 1.0, 0.0, 0.0, 0.2],
            "wind_speed_10m": [10.0, 12.0, 11.0, 13.0, 15.0, 14.0]
        }
    }


@pytest.fixture
def sample_forecast_data():
    """Sample forecast data for testing."""
    return {
        "hourly": {
            "temperature_2m": [15.5, 16.2, 17.1, 18.3, 19.5, 20.2],
            "precipitation": [0.0, 0.6, 1.2, 0.1, 0.0, 0.3],
            "wind_speed_10m": [10.5, 12.5, 11.5, 13.5, 15.5, 14.5]
        }
    }


@pytest.fixture
def sample_coordinates():
    """Sample coordinates for testing."""
    return {
        "lat": 40.7128,
        "lon": -74.0060
    }
