"""Tests for the HTTP API. Only Open-Meteo is mocked; the analysis and ranking run for real."""

import pytest
import responses
from fastapi.testclient import TestClient

import weather_api
from tests import fakes
from tests.fakes import ARCHIVE_URL

# How far each model's forecast is off; every other model is off by 3
OFFSETS = {"gfs_seamless": 0.1, "icon_seamless": 1.0}

client = TestClient(weather_api.app)


@pytest.fixture(autouse=True)
def empty_cache():
    weather_api.clear_cache()


@pytest.fixture
def open_meteo():
    with responses.RequestsMock() as mock:
        mock.add_callback(responses.GET, fakes.ARCHIVE_URL, callback=fakes.archive)
        mock.add_callback(responses.GET, fakes.HISTORICAL_URL, callback=fakes.historical(OFFSETS))
        yield mock


def test_ranks_models_most_accurate_first(open_meteo):
    res = client.get("/best-model", params={"lat": 40.64, "lon": 22.94, "days": 1})

    assert res.status_code == 200
    body = res.json()
    assert body["best"]["id"] == "gfs_seamless"
    assert body["best"]["name"] == "NOAA GFS"
    assert [m["id"] for m in body["ranking"][:2]] == ["gfs_seamless", "icon_seamless"]
    assert body["best"] == body["ranking"][0]
    assert body["best"]["overall"] == pytest.approx(0.1)
    assert set(body["best"]) == {"id", "name", "overall", "temp", "precip", "wind"}
    assert body["cached"] is False


def test_nearby_repeat_request_is_served_from_cache(open_meteo):
    client.get("/best-model", params={"lat": 40.64, "lon": 22.94, "days": 1})
    calls_after_first = len(open_meteo.calls)

    res = client.get("/best-model", params={"lat": 40.6412, "lon": 22.9431, "days": 1})  # same ~1 km cell

    assert res.status_code == 200
    assert res.json()["cached"] is True
    assert len(open_meteo.calls) == calls_after_first


@pytest.mark.parametrize("params", [{"lat": 91, "lon": 0}, {"lat": 0, "lon": -181}, {"lat": "abc", "lon": 0}, {"lat": 0}])
def test_rejects_invalid_coordinates(params):
    with responses.RequestsMock():  # fails the test if any upstream call is made
        res = client.get("/best-model", params=params)
    assert res.status_code == 422


def test_upstream_outage_returns_503_and_is_not_cached():
    with responses.RequestsMock(assert_all_requests_are_fired=False) as mock:
        mock.get(ARCHIVE_URL, status=500)
        first = client.get("/best-model", params={"lat": 40.64, "lon": 22.94, "days": 1})
        calls_after_first = len(mock.calls)
        client.get("/best-model", params={"lat": 40.64, "lon": 22.94, "days": 1})
        assert len(mock.calls) > calls_after_first  # retried, not served a cached failure

    assert first.status_code == 503
    assert "try again" in first.json()["detail"].lower()


def test_other_sites_can_call_it(open_meteo):
    res = client.get("/best-model", params={"lat": 40.64, "lon": 22.94, "days": 1},
                     headers={"Origin": "https://weather.example.com"})
    assert res.headers["access-control-allow-origin"] == "*"
