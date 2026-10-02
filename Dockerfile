# The model-ranking API (weather_api.py), as run on Azure Container Apps
FROM python:3.14-slim

# Links the image on GitHub Container Registry to this repo
LABEL org.opencontainers.image.source=https://github.com/mvrck19/idcweather

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY pyproject.toml weather_model_accuracy.py weather_api.py ./
# ponytail: unpinned (>=) versions; add a lock file if a dependency update ever breaks a build
RUN pip install ".[api]"

USER nobody
EXPOSE 8000
CMD ["uvicorn", "weather_api:app", "--host", "0.0.0.0", "--port", "8000"]
