"""HTTP API: which weather model has been most accurate at a location.

Run locally:  uvicorn weather_api:app --reload
Docs:         http://localhost:8000/docs
"""

import time
from typing import Dict, Tuple

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from weather_model_accuracy import MODELS, analyze_model_accuracy, rank_models

app = FastAPI(
    title="Weather model accuracy API",
    description="Ranks 15 weather models by how well they forecast the past days at a location.",
)

# Public, read-only, no cookies or auth, so any site may call it
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"])

# Rankings come from the past week's data, so one a day old is still good.
# ponytail: per-instance memory; move to Firestore/Redis once more than one instance runs
CACHE_SECONDS = 24 * 3600
_cache: Dict[str, Tuple[float, dict]] = {}


def clear_cache() -> None:
    _cache.clear()


@app.get("/best-model")
def best_model(
    lat: float = Query(ge=-90, le=90, description="Latitude"),
    lon: float = Query(ge=-180, le=180, description="Longitude"),
    days: int = Query(7, ge=1, le=14, description="Past days to score the models on"),
):
    # ~1 km cells: weather doesn't change within one, and nearby requests share a cache entry
    lat, lon = round(lat, 2), round(lon, 2)
    key = f"{lat},{lon},{days}"

    hit = _cache.get(key)
    if hit and time.time() - hit[0] < CACHE_SECONDS:
        return {**hit[1], "cached": True}

    results, _ = analyze_model_accuracy(lat, lon, days_back=days, quiet=True)
    ranking = [{"id": model, "name": MODELS.get(model, model), **scores}
               for model, scores in rank_models(results)]
    if not ranking:
        raise HTTPException(503, "Forecast history is unavailable for this location right now. Try again in a few minutes.")

    body = {"lat": lat, "lon": lon, "days": days, "best": ranking[0], "ranking": ranking}
    _cache[key] = (time.time(), body)
    return {**body, "cached": False}
