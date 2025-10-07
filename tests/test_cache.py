"""Tests for caching functionality."""

import pytest
import json
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from weather_model_accuracy import (
    load_cache,
    save_cache,
    get_cache_key,
    get_cached_model,
    cache_model_result,
    CACHE_FILE,
    CACHE_EXPIRY_DAYS,
)


@pytest.fixture
def temp_cache_file(monkeypatch):
    """Create a temporary cache file for testing."""
    temp_file = Path(tempfile.gettempdir()) / "test_weather_cache.json"

    # Monkeypatch the CACHE_FILE constant
    monkeypatch.setattr("weather_model_accuracy.CACHE_FILE", temp_file)

    yield temp_file

    # Cleanup
    if temp_file.exists():
        temp_file.unlink()


class TestCacheBasics:
    """Tests for basic cache operations."""

    def test_get_cache_key(self):
        """Test cache key generation."""
        key = get_cache_key(40.7128, -74.0060)
        assert key == "40.71,-74.01"

        # Test rounding
        key2 = get_cache_key(40.71283, -74.00601)
        assert key2 == "40.71,-74.01"  # Should round to same key

    def test_load_cache_empty(self, temp_cache_file, monkeypatch):
        """Test loading empty cache."""
        monkeypatch.setattr("weather_model_accuracy.CACHE_FILE", temp_cache_file)
        cache = load_cache()
        assert cache == {}

    def test_save_and_load_cache(self, temp_cache_file, monkeypatch):
        """Test saving and loading cache."""
        monkeypatch.setattr("weather_model_accuracy.CACHE_FILE", temp_cache_file)

        test_cache = {
            "40.71,-74.01": {
                "best_model_id": "ecmwf_ifs04",
                "best_model_name": "ECMWF IFS",
                "overall_error": 1.5,
                "timestamp": datetime.now().isoformat(),
                "location_str": "New York, NY, United States"
            }
        }

        save_cache(test_cache)
        loaded_cache = load_cache()

        assert "40.71,-74.01" in loaded_cache
        assert loaded_cache["40.71,-74.01"]["best_model_id"] == "ecmwf_ifs04"

    def test_save_cache_invalid_path(self, monkeypatch, capsys):
        """Test save_cache with invalid path."""
        invalid_path = Path("/invalid/path/cache.json")
        monkeypatch.setattr("weather_model_accuracy.CACHE_FILE", invalid_path)

        save_cache({"test": "data"})
        # Should print warning but not crash


class TestCacheRetrieval:
    """Tests for cache retrieval."""

    def test_get_cached_model_valid(self, temp_cache_file, monkeypatch):
        """Test retrieving valid cached model."""
        monkeypatch.setattr("weather_model_accuracy.CACHE_FILE", temp_cache_file)

        # Create cache with recent timestamp
        cache = {
            "40.71,-74.01": {
                "best_model_id": "gfs_seamless",
                "best_model_name": "NOAA GFS",
                "overall_error": 2.0,
                "timestamp": datetime.now().isoformat(),
                "location_str": "Test Location"
            }
        }

        result = get_cached_model(40.7128, -74.0060, cache)
        assert result is not None
        assert result["best_model_id"] == "gfs_seamless"

    def test_get_cached_model_expired(self, temp_cache_file, monkeypatch):
        """Test retrieving expired cached model."""
        monkeypatch.setattr("weather_model_accuracy.CACHE_FILE", temp_cache_file)

        # Create cache with old timestamp (more than CACHE_EXPIRY_DAYS old)
        old_date = datetime.now() - timedelta(days=CACHE_EXPIRY_DAYS + 1)
        cache = {
            "40.71,-74.01": {
                "best_model_id": "gfs_seamless",
                "best_model_name": "NOAA GFS",
                "overall_error": 2.0,
                "timestamp": old_date.isoformat(),
                "location_str": "Test Location"
            }
        }

        result = get_cached_model(40.7128, -74.0060, cache)
        assert result is None  # Should be expired

    def test_get_cached_model_not_found(self):
        """Test retrieving model for location not in cache."""
        cache = {}
        result = get_cached_model(40.7128, -74.0060, cache)
        assert result is None


class TestCacheModelResult:
    """Tests for caching model results."""

    def test_cache_model_result(self, temp_cache_file, monkeypatch):
        """Test caching a model result."""
        monkeypatch.setattr("weather_model_accuracy.CACHE_FILE", temp_cache_file)

        cache_model_result(
            lat=51.5074,
            lon=-0.1278,
            model_id="ecmwf_ifs04",
            model_name="ECMWF IFS",
            overall_error=1.23,
            location_str="London, England, United Kingdom"
        )

        # Load and verify
        cache = load_cache()
        key = get_cache_key(51.5074, -0.1278)
        assert key in cache
        assert cache[key]["best_model_id"] == "ecmwf_ifs04"
        assert cache[key]["overall_error"] == 1.23

    def test_cache_model_result_overwrites(self, temp_cache_file, monkeypatch):
        """Test that caching overwrites old results."""
        monkeypatch.setattr("weather_model_accuracy.CACHE_FILE", temp_cache_file)

        # Cache first result
        cache_model_result(51.5, -0.1, "model_a", "Model A", 2.0, "Location A")

        # Cache second result for same location
        cache_model_result(51.5, -0.1, "model_b", "Model B", 1.5, "Location A")

        # Should have the second result
        cache = load_cache()
        key = get_cache_key(51.5, -0.1)
        assert cache[key]["best_model_id"] == "model_b"
        assert cache[key]["overall_error"] == 1.5


class TestCacheIntegration:
    """Integration tests for cache workflow."""

    def test_full_cache_workflow(self, temp_cache_file, monkeypatch):
        """Test complete cache save/load/retrieve workflow."""
        monkeypatch.setattr("weather_model_accuracy.CACHE_FILE", temp_cache_file)

        # 1. Cache a result
        cache_model_result(40.7, -74.0, "test_model", "Test Model", 1.0, "Test City")

        # 2. Load cache
        cache = load_cache()

        # 3. Retrieve cached result
        result = get_cached_model(40.7, -74.0, cache)

        assert result is not None
        assert result["best_model_id"] == "test_model"
        assert result["best_model_name"] == "Test Model"

    def test_cache_multiple_locations(self, temp_cache_file, monkeypatch):
        """Test caching multiple locations."""
        monkeypatch.setattr("weather_model_accuracy.CACHE_FILE", temp_cache_file)

        # Cache multiple locations
        locations = [
            (40.7, -74.0, "model_ny", "NY Model", "New York"),
            (51.5, -0.1, "model_london", "London Model", "London"),
            (35.7, 139.7, "model_tokyo", "Tokyo Model", "Tokyo"),
        ]

        for lat, lon, model_id, model_name, loc_str in locations:
            cache_model_result(lat, lon, model_id, model_name, 1.0, loc_str)

        # Verify all are cached
        cache = load_cache()
        assert len(cache) == 3

        # Verify each can be retrieved
        result_ny = get_cached_model(40.7, -74.0, cache)
        assert result_ny["best_model_id"] == "model_ny"

        result_london = get_cached_model(51.5, -0.1, cache)
        assert result_london["best_model_id"] == "model_london"
