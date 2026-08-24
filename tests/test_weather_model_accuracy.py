"""Tests for weather model accuracy checker."""

import pytest
import responses
from datetime import datetime, timedelta
from weather_model_accuracy import (
    calculate_mae,
    fetch_historical_forecast,
    fetch_actual_weather,
    analyze_model_accuracy,
    get_error_color,
    geocode_location,
    fetch_forecast,
)


class TestCalculateMAE:
    """Tests for calculate_mae function."""

    def test_calculate_mae_basic(self):
        """Test basic MAE calculation."""
        forecasted = [10.0, 20.0, 30.0]
        actual = [11.0, 19.0, 31.0]
        mae = calculate_mae(forecasted, actual)
        assert mae == 1.0

    def test_calculate_mae_with_none_values(self):
        """Test MAE calculation with None values."""
        forecasted = [10.0, None, 30.0]
        actual = [11.0, 19.0, None]
        mae = calculate_mae(forecasted, actual)
        assert mae == 1.0  # Only the first pair (10.0, 11.0) is valid

    def test_calculate_mae_empty_lists(self):
        """Test MAE calculation with empty lists."""
        assert calculate_mae([], []) is None
        assert calculate_mae([10.0], []) is None

    def test_calculate_mae_all_none(self):
        """Test MAE calculation with all None values."""
        forecasted = [None, None, None]
        actual = [None, None, None]
        assert calculate_mae(forecasted, actual) is None

    def test_calculate_mae_perfect_forecast(self):
        """Test MAE calculation with perfect forecast."""
        forecasted = [10.0, 20.0, 30.0]
        actual = [10.0, 20.0, 30.0]
        assert calculate_mae(forecasted, actual) == 0.0


class TestFetchFunctions:
    """Tests for fetch functions."""

    @responses.activate
    def test_fetch_historical_forecast_success(self, sample_forecast_data):
        """Test successful historical forecast fetch."""
        responses.get(
            "https://historical-forecast-api.open-meteo.com/v1/forecast",
            json=sample_forecast_data,
            status=200
        )

        result = fetch_historical_forecast(40.7128, -74.0060, "2025-01-01", "gfs_seamless")
        assert result is not None
        assert "hourly" in result
        assert "temperature_2m" in result["hourly"]

    @responses.activate
    def test_fetch_historical_forecast_failure(self):
        """Test failed historical forecast fetch."""
        responses.get(
            "https://historical-forecast-api.open-meteo.com/v1/forecast",
            json={"error": "Not found"},
            status=404
        )

        result = fetch_historical_forecast(40.7128, -74.0060, "2025-01-01", "gfs_seamless")
        assert result is None

    @responses.activate
    def test_fetch_actual_weather_success(self, sample_weather_data):
        """Test successful actual weather fetch."""
        responses.get(
            "https://archive-api.open-meteo.com/v1/archive",
            json=sample_weather_data,
            status=200
        )

        result = fetch_actual_weather(40.7128, -74.0060, "2025-01-01")
        assert result is not None
        assert "hourly" in result
        assert "temperature_2m" in result["hourly"]

    @responses.activate
    def test_fetch_actual_weather_failure(self):
        """Test failed actual weather fetch."""
        responses.get(
            "https://archive-api.open-meteo.com/v1/archive",
            json={"error": "Not found"},
            status=404
        )

        result = fetch_actual_weather(40.7128, -74.0060, "2025-01-01")
        assert result is None

    @responses.activate
    def test_fetch_historical_forecast_rate_limited(self, capsys):
        """Test rate-limited (429) historical forecast fetch is surfaced distinctly."""
        responses.get(
            "https://historical-forecast-api.open-meteo.com/v1/forecast",
            json={"error": "Rate limited"},
            status=429
        )

        result = fetch_historical_forecast(40.7128, -74.0060, "2025-01-01", "gfs_seamless")
        assert result is None
        captured = capsys.readouterr()
        assert "429" in captured.out

    @responses.activate
    def test_fetch_with_timeout(self):
        """Test fetch with timeout."""
        # Note: responses library doesn't easily simulate timeouts,
        # but we can verify the timeout parameter is passed
        responses.get(
            "https://archive-api.open-meteo.com/v1/archive",
            json={"hourly": {}},
            status=200
        )

        result = fetch_actual_weather(40.7128, -74.0060, "2025-01-01")
        assert result is not None


class TestAnalyzeModelAccuracy:
    """Tests for analyze_model_accuracy function."""

    @responses.activate
    def test_analyze_model_accuracy_basic(self, sample_weather_data, sample_forecast_data):
        """Test basic model accuracy analysis."""
        # Mock actual weather data
        responses.get(
            "https://archive-api.open-meteo.com/v1/archive",
            json=sample_weather_data,
            status=200
        )

        # Mock forecast data for all models
        responses.get(
            "https://historical-forecast-api.open-meteo.com/v1/forecast",
            json=sample_forecast_data,
            status=200
        )

        # Run analysis with just 1 day
        results, model_names = analyze_model_accuracy(40.7128, -74.0060, days_back=1)

        assert isinstance(results, dict)
        assert isinstance(model_names, dict)
        assert len(model_names) > 0

    @responses.activate
    def test_analyze_model_accuracy_no_data(self):
        """Test analysis when no data is available."""
        # Mock failed requests
        responses.get(
            "https://archive-api.open-meteo.com/v1/archive",
            json={"error": "Not found"},
            status=404
        )

        results, model_names = analyze_model_accuracy(40.7128, -74.0060, days_back=1)

        # Results should be empty or have empty error lists
        assert isinstance(results, dict)
        assert isinstance(model_names, dict)

    @responses.activate
    def test_analyze_model_accuracy_multiple_days(self, sample_weather_data, sample_forecast_data):
        """Test that errors accumulate correctly across multiple days via the shared executor."""
        responses.get(
            "https://archive-api.open-meteo.com/v1/archive",
            json=sample_weather_data,
            status=200
        )
        responses.get(
            "https://historical-forecast-api.open-meteo.com/v1/forecast",
            json=sample_forecast_data,
            status=200
        )

        results, model_names = analyze_model_accuracy(40.7128, -74.0060, days_back=3)

        assert isinstance(results, dict)
        assert len(results) > 0
        for model, errors in results.items():
            assert len(errors["temp_errors"]) == 3
            assert len(errors["precip_errors"]) == 3
            assert len(errors["wind_errors"]) == 3


class TestGetErrorColor:
    """Tests for get_error_color function."""

    def test_get_error_color_best(self):
        """Test color for best model."""
        assert get_error_color(1, 10) == "green"

    def test_get_error_color_top_30(self):
        """Test color for top 30% models."""
        assert get_error_color(2, 10) == "yellow"
        assert get_error_color(3, 10) == "yellow"

    def test_get_error_color_top_60(self):
        """Test color for top 60% models."""
        assert get_error_color(5, 10) == "orange1"

    def test_get_error_color_worst(self):
        """Test color for worst models."""
        assert get_error_color(9, 10) == "red"
        assert get_error_color(10, 10) == "red"


class TestIntegration:
    """Integration tests."""

    @responses.activate
    def test_full_workflow(self, sample_weather_data, sample_forecast_data):
        """Test full workflow from fetch to results."""
        # Mock actual weather
        responses.get(
            "https://archive-api.open-meteo.com/v1/archive",
            json=sample_weather_data,
            status=200
        )

        # Mock forecast data
        responses.get(
            "https://historical-forecast-api.open-meteo.com/v1/forecast",
            json=sample_forecast_data,
            status=200
        )

        # Fetch data
        actual = fetch_actual_weather(40.7128, -74.0060, "2025-01-01")
        forecast = fetch_historical_forecast(40.7128, -74.0060, "2025-01-01", "gfs_seamless")

        assert actual is not None
        assert forecast is not None

        # Calculate MAE
        actual_temp = actual["hourly"]["temperature_2m"]
        forecast_temp = forecast["hourly"]["temperature_2m"]
        mae = calculate_mae(forecast_temp, actual_temp)

        assert mae is not None
        assert mae > 0  # There should be some error between forecast and actual


class TestEdgeCases:
    """Tests for edge cases."""

    def test_calculate_mae_different_lengths(self):
        """Test MAE with different length arrays."""
        forecasted = [10.0, 20.0, 30.0, 40.0]
        actual = [11.0, 19.0]
        # zip will only use the shorter length
        mae = calculate_mae(forecasted, actual)
        assert mae == 1.0

    def test_calculate_mae_large_errors(self):
        """Test MAE with large errors."""
        forecasted = [0.0, 100.0, 200.0]
        actual = [50.0, 150.0, 250.0]
        mae = calculate_mae(forecasted, actual)
        assert mae == 50.0

    def test_calculate_mae_negative_values(self):
        """Test MAE with negative values."""
        forecasted = [-10.0, -5.0, 0.0]
        actual = [-11.0, -4.0, 1.0]
        mae = calculate_mae(forecasted, actual)
        assert mae == 1.0


class TestGeocoding:
    """Tests for geocoding functions."""

    @responses.activate
    def test_geocode_location_success(self):
        """Test successful geocoding."""
        mock_response = {
            "results": [
                {
                    "name": "London",
                    "latitude": 51.5074,
                    "longitude": -0.1278,
                    "country": "United Kingdom",
                    "admin1": "England"
                },
                {
                    "name": "London",
                    "latitude": 42.9834,
                    "longitude": -81.2497,
                    "country": "Canada",
                    "admin1": "Ontario"
                }
            ]
        }

        responses.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            json=mock_response,
            status=200
        )

        result = geocode_location("London")
        assert result is not None
        assert len(result) == 2
        assert result[0]["name"] == "London"
        assert result[0]["country"] == "United Kingdom"

    @responses.activate
    def test_geocode_location_no_results(self):
        """Test geocoding with no results."""
        mock_response = {"results": []}

        responses.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            json=mock_response,
            status=200
        )

        result = geocode_location("NonexistentCity12345")
        assert result is not None
        assert len(result) == 0

    @responses.activate
    def test_geocode_location_failure(self):
        """Test failed geocoding request."""
        responses.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            json={"error": "Server error"},
            status=500
        )

        result = geocode_location("London")
        assert result is None

    @responses.activate
    def test_geocode_location_rate_limited(self, capsys):
        """Test rate-limited (429) geocoding request is surfaced distinctly."""
        responses.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            json={"error": "Rate limited"},
            status=429
        )

        result = geocode_location("London")
        assert result is None
        captured = capsys.readouterr()
        assert "429" in captured.out


class TestForecast:
    """Tests for forecast functions."""

    @responses.activate
    def test_fetch_forecast_success(self):
        """Test successful forecast fetch."""
        mock_forecast = {
            "daily": {
                "time": ["2025-10-08", "2025-10-09"],
                "weather_code": [0, 61],
                "temperature_2m_max": [15.0, 18.0],
                "temperature_2m_min": [8.0, 10.0],
                "precipitation_sum": [0.0, 5.2],
                "wind_speed_10m_max": [12.0, 18.0]
            }
        }

        responses.get(
            "https://api.open-meteo.com/v1/forecast",
            json=mock_forecast,
            status=200
        )

        result = fetch_forecast(40.7128, -74.0060, "gfs_seamless", forecast_type="daily", duration=7)
        assert result is not None
        assert "daily" in result
        assert len(result["daily"]["time"]) == 2

    @responses.activate
    def test_fetch_forecast_failure(self):
        """Test failed forecast fetch."""
        responses.get(
            "https://api.open-meteo.com/v1/forecast",
            json={"error": "Not found"},
            status=404
        )

        result = fetch_forecast(40.7128, -74.0060, "gfs_seamless")
        assert result is None


class TestDisplayResults:
    """Tests for display_results function."""

    def test_display_results_returns_best_model(self):
        """Test that display_results returns the best model ID and error."""
        from weather_model_accuracy import display_results

        # Mock results with different error levels
        mock_results = {
            "model_a": {
                "temp_errors": [1.0, 1.2, 0.8],
                "precip_errors": [0.5, 0.6],
                "wind_errors": [2.0, 2.5]
            },
            "model_b": {
                "temp_errors": [2.0, 2.2, 1.8],
                "precip_errors": [1.5, 1.6],
                "wind_errors": [3.0, 3.5]
            }
        }

        mock_model_names = {
            "model_a": "Model A",
            "model_b": "Model B"
        }

        result = display_results(mock_results, mock_model_names)
        # model_a has lower errors, so it should be the best
        assert result is not None
        best_model, best_error = result
        assert best_model == "model_a"
        assert isinstance(best_error, float)
        assert best_error > 0

    def test_display_results_no_data(self):
        """Test display_results with no data."""
        from weather_model_accuracy import display_results

        mock_results = {
            "model_a": {
                "temp_errors": [],
                "precip_errors": [],
                "wind_errors": []
            }
        }

        mock_model_names = {"model_a": "Model A"}

        result = display_results(mock_results, mock_model_names)
        assert result is None
