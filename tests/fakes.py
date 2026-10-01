"""Fake Open-Meteo, shaped like the real API: answers with the requested date range and models.

Multi-model responses suffix each variable with the model ID (temperature_2m_gfs_seamless).
"""

import json
from datetime import date, timedelta
from urllib.parse import parse_qs, urlparse

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
HISTORICAL_URL = "https://historical-forecast-api.open-meteo.com/v1/forecast"

# Constant "actual" weather, so each model's error is exactly its offset
ACTUAL = {"temperature_2m": 10.0, "precipitation": 0.2, "wind_speed_10m": 5.0}


def _query(request):
    return {k: v[0] for k, v in parse_qs(urlparse(request.url).query).items()}


def _hours(q):
    start, end = date.fromisoformat(q["start_date"]), date.fromisoformat(q["end_date"])
    return [f"{start + timedelta(days=d)}T{h:02d}:00" for d in range((end - start).days + 1) for h in range(24)]


def archive(request):
    times = _hours(_query(request))
    hourly = {"time": times, **{var: [value] * len(times) for var, value in ACTUAL.items()}}
    return 200, {}, json.dumps({"hourly": hourly})


def historical(offsets, default=3.0):
    """Callback where each requested model is off by offsets.get(model, default); None = no coverage there."""
    def callback(request):
        q = _query(request)
        times = _hours(q)
        hourly = {"time": times}
        for model in q["models"].split(","):
            off = offsets.get(model, default)
            for var, value in ACTUAL.items():
                hourly[f"{var}_{model}"] = [None if off is None else value + off] * len(times)
        return 200, {}, json.dumps({"hourly": hourly})
    return callback
