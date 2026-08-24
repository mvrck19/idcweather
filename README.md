# Weather Model Accuracy Finder

A Python tool that helps you find the most accurate weather forecast model for your specific location by analyzing historical performance, then gives you a 7-day forecast using the best model.

## ✨ Features

- 🔍 **City Search** - Just type a city name, no coordinates needed
- 📊 **15 Weather Models** - Compares global models (ECMWF, GFS, ICON, etc.) + regional high-res models
- 🎯 **Accuracy Analysis** - Tests which model performed best for YOUR location over the past week
- 🌤️ **Smart Forecast** - Daily (3-14 days) OR hourly (24-120 hours) forecasts
- 💾 **Intelligent Caching** - Remembers the best model for each location (7-day cache)
- 🎨 **Beautiful CLI** - Rich terminal UI with colors, progress bars, and emoji weather icons
- ⚡ **Comprehensive Testing** - 38 tests with 100% pass rate

## Concept

Different weather models perform differently across regions. This tool:
1. Takes your location (city name or coordinates)
2. Fetches the past week's forecasts from 15 models
3. Compares them against actual weather data
4. Ranks models by accuracy for YOUR area
5. Shows you a 7-day forecast using the best model

## Installation

No API key or account needed — it uses [Open-Meteo](https://open-meteo.com/)'s free, unauthenticated APIs.

### Install directly (recommended)

Use [pipx](https://pypa.github.io/pipx/) — it installs the tool in its own isolated environment and automatically makes sure the command ends up on your `PATH`, on Windows, macOS, and Linux alike:

```bash
pipx install git+https://github.com/mvrck19/idcweather
```

Don't have `pipx`? `python -m pip install --user pipx && pipx ensurepath`, then re-run the command above (open a new terminal afterward so the PATH change takes effect).

```bash
weather-model-accuracy --city "London"
```

### Alternative: plain pip

```bash
pip install git+https://github.com/mvrck19/idcweather
```

With plain `pip`, the `weather-model-accuracy` command may not be on your `PATH` afterward — this is general `pip`/Windows behavior (a user-site install's Scripts folder isn't on `PATH` by default), not specific to this tool. If the command isn't found after installing this way, use `pipx` above instead, or add your Python user Scripts/bin directory to `PATH` manually.

### Run from source (for development)

```bash
git clone https://github.com/mvrck19/idcweather
cd idcweather
pip install -r requirements.txt
python weather_model_accuracy.py --city "London"
```

## Usage

The examples below use `python weather_model_accuracy.py`, matching a from-source setup. If you installed via `pip install git+...`, use `weather-model-accuracy` instead — both forms take identical arguments.

### 🆕 Search by City Name (Easiest!)

```bash
# Search for a city - tool will show options to select from
python weather_model_accuracy.py --city "London"
python weather_model_accuracy.py -c "New York"
```

The tool will:
1. Find all matching locations
2. Show you a table to pick from (e.g., London UK vs London Canada)
3. Auto-fill coordinates from your selection

### Specify Coordinates Directly

```bash
# Use exact coordinates
python weather_model_accuracy.py --lat 40.7128 --lon -74.0060

# Customize analysis period (1-14 days)
python weather_model_accuracy.py --lat 40.7128 --lon -74.0060 --days 14

# Short flags
python weather_model_accuracy.py -l 40.7128 -g -74.0060 -d 7
```

### Interactive Mode

```bash
# Run without arguments to be prompted
python weather_model_accuracy.py
```

You'll be prompted to enter coordinates manually. Find yours at [latlong.net](https://www.latlong.net/).

### Get Help

```bash
python weather_model_accuracy.py --help
```

### 🆕 Forecast Type & Duration

Choose between **daily** or **hourly** forecasts:

```bash
# Daily forecast (default: 7 days, range: 3-14)
python weather_model_accuracy.py -c "Tokyo" --forecast-type daily --forecast-days 3

# Hourly forecast (default: 48 hours, range: 24-120)
python weather_model_accuracy.py -c "Paris" --forecast-type hourly --forecast-hours 72

# Short flags
python weather_model_accuracy.py -c "Berlin" -ft hourly -fh 48
```

### 💾 Caching (Faster Repeated Runs)

The tool **automatically caches** the best model for each location for 7 days:

```bash
# First run: Analyzes all 15 models (takes time)
python weather_model_accuracy.py -c "London"

# Second run (within 7 days): Uses cached result (instant!)
python weather_model_accuracy.py -c "London"
# → ✓ Using cached best model: ECMWF IFS (analyzed 2 days ago)

# Force re-analysis (ignore cache)
python weather_model_accuracy.py -c "London" --no-cache

# View all cached results
python weather_model_accuracy.py --show-cache

# Clear the cache
python weather_model_accuracy.py --clear-cache
```

**Cache benefits:**
- ⚡ Instant results for repeated locations
- 🌍 Remembers best model per city
- 📅 Auto-expires after 7 days
- 💽 Stored in `~/.weather_model_cache.json`

## Output

### Model Accuracy Analysis

The tool features a beautiful, colorized CLI output with:
- **Progress bar** showing real-time data fetching status (15 models tested)
- **Ranked table** with medal indicators (🥇🥈🥉) for top 3 models
- **Color-coded accuracy** (green = best, yellow = good, orange = moderate, red = poor)
- **Detailed metrics** for each model:
  - Temperature accuracy (Mean Absolute Error in °C)
  - Precipitation accuracy (MAE in mm)
  - Wind speed accuracy (MAE in km/h)
- **Best model highlight** in a bordered panel

The results are ranked by overall accuracy (lower error = better).

### 🆕 Forecast Display (Using Best Model)

After finding the most accurate model, shows a forecast using that model.

#### Daily Forecast (3-14 days)

- **Weather conditions** with emoji indicators (☀️ ☁️ 🌧️ ⛈️ ❄️)
- **Daily temperature range** (min/max, color-coded by temperature)
- **Precipitation amounts** (rainfall in mm)
- **Wind speed** (max daily wind speed)

Example:
```
📍 7-Day Weather Forecast
London, England, United Kingdom
Using: ECMWF IFS

┌────────────┬──────────────────┬─────────────┬────────────┬──────────────┐
│ Date       │ Weather          │ Temp (°C)   │ Rain (mm)  │ Wind (km/h)  │
├────────────┼──────────────────┼─────────────┼────────────┼──────────────┤
│ 2025-10-08 │ ⛅ Partly cloudy │ 8° - 15°    │ 0.0        │ 12           │
│ 2025-10-09 │ 🌧️ Moderate rain│ 10° - 13°   │ 5.2        │ 18           │
│ ...        │ ...              │ ...         │ ...        │ ...          │
└────────────┴──────────────────┴─────────────┴────────────┴──────────────┘
```

#### Hourly Forecast (24-120 hours)

- **Hourly weather conditions** with timestamps
- **Temperature** (color-coded)
- **Precipitation** per hour
- **Relative humidity** (%)
- **Wind speed**

Example:
```
📍 48-Hour Weather Forecast
Tokyo, Japan
Using: JMA Japan

┌──────────────────┬──────────────────┬─────────┬───────────┬───────────┬──────┐
│ Date & Time      │ Weather          │ Temp    │ Rain(mm)  │ Humidity  │ Wind │
├──────────────────┼──────────────────┼─────────┼───────────┼───────────┼──────┤
│ Oct 08 14:00     │ ☀️ Clear sky     │ 22°C    │ 0.0       │ 55%       │ 8    │
│ Oct 08 15:00     │ 🌤️ Mainly clear  │ 23°C    │ 0.0       │ 52%       │ 9    │
│ ...              │ ...              │ ...     │ ...       │ ...       │ ...  │
└──────────────────┴──────────────────┴─────────┴───────────┴───────────┴──────┘
```

## Models Tested

### Global Models (work worldwide)
- **ECMWF IFS** - European Centre for Medium-Range Weather Forecasts
- **NOAA GFS** - Global Forecast System (US)
- **DWD ICON** - German Weather Service
- **GEM** - Canadian Meteorological Centre
- **JMA** - Japan Meteorological Agency
- **Météo-France** - French National Weather Service
- **BOM** - Australian Bureau of Meteorology
- **CMA GRAPES** - China Meteorological Administration
- **UK Met Office** - United Kingdom

### Regional High-Resolution Models
- **HRRR** (3km) - US only
- **NAM** (3km) - US only
- **ICON Europe** (7km) - Europe
- **ICON D2** (2km) - Central Europe
- **ARPEGE** (11km) - Europe
- **AROME** (2.5km) - France

*Note: Regional models are only tested if your location is within their coverage area.*

## Data Source

Uses [Open-Meteo](https://open-meteo.com/) APIs:
- Historical Forecast API for past predictions
- Archive API for actual weather data

## Testing

### Run Tests

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run all tests
pytest

# Run with coverage report
pytest --cov=weather_model_accuracy --cov-report=term-missing

# Run specific test file
pytest tests/test_weather_model_accuracy.py

# Run with verbose output
pytest -v
```

### Test Coverage

The test suite includes **38 tests** covering:
- Unit tests for MAE calculations
- Mocked API requests (using `responses` library)
- Integration tests for the full workflow
- Edge case testing (empty data, large errors, negative values)
- Error handling tests
- **Geocoding tests** (city search, no results, failures)
- **Forecast fetch tests** (success and error cases, daily/hourly)
- **Display results tests** (best model selection)
- **Caching tests** (save/load, expiry, retrieval, multiple locations)

## Dependencies

### Production
- `requests` - HTTP library for API calls
- `rich` - Beautiful terminal output
- `typer` - Modern CLI framework

### Development
- `pytest` - Testing framework
- `responses` - HTTP request mocking
- `pytest-cov` - Coverage reporting

## CLI Reference

### Location Options
```
--city, -c TEXT            City name to search for
--lat, -l FLOAT            Latitude of the location
--lon, -g FLOAT            Longitude of the location
```

### Analysis Options
```
--days, -d INTEGER         Number of days to analyze (1-14) [default: 7]
```

### Forecast Options
```
--forecast-type, -ft       Forecast type: daily or hourly [default: daily]
--forecast-days, -fd       Days for daily forecast (3-14) [default: 7]
--forecast-hours, -fh      Hours for hourly forecast (24-120) [default: 48]
```

### Cache Options
```
--no-cache                 Force re-analysis, ignore cache
--show-cache               Display cached results and exit
--clear-cache              Clear cache and exit
```

### Complete Examples
```bash
# Quick 3-day forecast for a city (uses cache if available)
python weather_model_accuracy.py -c "Seattle" -fd 3

# Hourly 72-hour forecast, force new analysis
python weather_model_accuracy.py -c "Mumbai" -ft hourly -fh 72 --no-cache

# Analyze 14 days of history, show 14-day forecast
python weather_model_accuracy.py --city "Sydney" --days 14 --forecast-days 14

# Check what's in the cache
python weather_model_accuracy.py --show-cache
```

## Limitations

- Requires 7+ days of historical data (recent models only)
- Free API has rate limits
- Accuracy depends on data availability for your region
- Regional models only provide data within their coverage area (e.g., HRRR works only in US)
- More models = longer analysis time (15 models tested)
- Cache is location-based (rounded to ~1km precision)
