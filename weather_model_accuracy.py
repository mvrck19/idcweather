#!/usr/bin/env python3
"""
Weather Model Accuracy Checker
Compares different weather forecast models to find the most accurate one for a given location.
"""

import requests
import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from statistics import mean
from typing import Optional, Dict, List, Tuple

import typer
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel
from rich import box

console = Console()
app = typer.Typer(help="Find the most accurate weather model for your location")

# Cache configuration
CACHE_FILE = Path.home() / ".weather_model_cache.json"
CACHE_EXPIRY_DAYS = 7


def load_cache() -> Dict:
    """Load cache from JSON file."""
    if not CACHE_FILE.exists():
        return {}

    try:
        with open(CACHE_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {}


def save_cache(cache_data: Dict) -> None:
    """Save cache to JSON file."""
    try:
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache_data, f, indent=2)
    except Exception as e:
        console.print(f"[yellow]Warning: Could not save cache: {e}[/yellow]")


def get_cache_key(lat: float, lon: float) -> str:
    """Generate cache key from coordinates (rounded to 2 decimals = ~1km precision)."""
    return f"{lat:.2f},{lon:.2f}"


def get_cached_model(lat: float, lon: float, cache: Dict) -> Optional[Dict]:
    """Get cached model result if valid (< 7 days old)."""
    key = get_cache_key(lat, lon)

    if key not in cache:
        return None

    cached = cache[key]
    cached_time = datetime.fromisoformat(cached.get("timestamp", "2000-01-01"))
    age_days = (datetime.now() - cached_time).days

    if age_days >= CACHE_EXPIRY_DAYS:
        return None

    return cached


def cache_model_result(lat: float, lon: float, model_id: str, model_name: str,
                       overall_error: float, location_str: str) -> None:
    """Cache the best model result for a location."""
    cache = load_cache()
    key = get_cache_key(lat, lon)

    cache[key] = {
        "best_model_id": model_id,
        "best_model_name": model_name,
        "overall_error": overall_error,
        "timestamp": datetime.now().isoformat(),
        "location_str": location_str
    }

    save_cache(cache)


def clear_cache() -> None:
    """Clear the cache file."""
    if CACHE_FILE.exists():
        CACHE_FILE.unlink()
        console.print("[green]✓ Cache cleared successfully[/green]")
    else:
        console.print("[yellow]No cache file found[/yellow]")


def show_cache() -> None:
    """Display cached model results."""
    cache = load_cache()

    if not cache:
        console.print("[yellow]Cache is empty[/yellow]")
        return

    table = Table(title="Cached Weather Model Results", box=box.ROUNDED)
    table.add_column("Location", style="cyan", width=35)
    table.add_column("Best Model", style="green", width=20)
    table.add_column("Error", justify="right", width=10)
    table.add_column("Age", justify="right", width=10)
    table.add_column("Status", justify="center", width=10)

    for key, data in cache.items():
        location = data.get("location_str", key)
        model = data.get("best_model_name", "Unknown")
        error = data.get("overall_error", 0)
        timestamp = datetime.fromisoformat(data.get("timestamp", "2000-01-01"))
        age_days = (datetime.now() - timestamp).days

        # Determine status
        if age_days >= CACHE_EXPIRY_DAYS:
            status = "[red]Expired[/red]"
            status_style = "dim"
        else:
            status = "[green]Valid[/green]"
            status_style = ""

        age_str = f"{age_days}d ago" if age_days > 0 else "Today"

        table.add_row(
            location,
            model,
            f"{error:.2f}",
            age_str,
            status,
            style=status_style
        )

    console.print("\n", table, "\n")
    console.print(f"[dim]Cache file: {CACHE_FILE}[/dim]")
    console.print(f"[dim]Cache expiry: {CACHE_EXPIRY_DAYS} days[/dim]")


def fetch_historical_forecast(lat: float, lon: float, date: str, model: str) -> Optional[Dict]:
    """Fetch historical forecast data from Open-Meteo API."""
    url = "https://historical-forecast-api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": date,
        "end_date": date,
        "hourly": "temperature_2m,precipitation,wind_speed_10m",
        "models": model
    }

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception:
        return None


def fetch_actual_weather(lat: float, lon: float, date: str) -> Optional[Dict]:
    """Fetch actual weather data from Open-Meteo Historical Weather API."""
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": date,
        "end_date": date,
        "hourly": "temperature_2m,precipitation,wind_speed_10m"
    }

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception:
        return None


def calculate_mae(forecasted: List, actual: List) -> Optional[float]:
    """Calculate Mean Absolute Error between forecasted and actual values."""
    if not forecasted or not actual:
        return None

    # Filter out None values
    pairs = [(f, a) for f, a in zip(forecasted, actual) if f is not None and a is not None]
    if not pairs:
        return None

    errors = [abs(f - a) for f, a in pairs]
    return mean(errors)


# WMO Weather interpretation codes with emoji indicators
WEATHER_CODES = {
    0: ("☀  ", "Clear sky"),
    1: ("🌤  ", "Mainly clear"),
    2: ("⛅ ", "Partly cloudy"),
    3: ("☁  ", "Overcast"),
    45: ("🌫  ", "Foggy"),
    48: ("🌫  ", "Rime fog"),
    51: ("💧 ", "Light drizzle"),
    53: ("💧 ", "Moderate drizzle"),
    55: ("💧 ", "Dense drizzle"),
    61: ("🌧  ", "Slight rain"),
    63: ("🌧  ", "Moderate rain"),
    65: ("🌧  ", "Heavy rain"),
    71: ("❄  ", "Slight snow"),
    73: ("❄  ", "Moderate snow"),
    75: ("❄  ", "Heavy snow"),
    77: ("🌨  ", "Snow grains"),
    80: ("🌦  ", "Slight showers"),
    81: ("🌦  ", "Moderate showers"),
    82: ("⛈  ", "Violent showers"),
    85: ("🌨  ", "Slight snow showers"),
    86: ("🌨  ", "Heavy snow showers"),
    95: ("⛈  ", "Thunderstorm"),
    96: ("⛈  ", "Thunderstorm with hail"),
    99: ("⛈  ", "Thunderstorm with heavy hail"),
}


def geocode_location(city_name: str, count: int = 5) -> Optional[List[Dict]]:
    """Geocode a city name to coordinates using Open-Meteo Geocoding API."""
    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {
        "name": city_name,
        "count": count,
        "language": "en",
        "format": "json"
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get("results", [])
    except Exception:
        return None


def select_location(locations: List[Dict]) -> Optional[Dict]:
    """Display location options and let user select one."""
    if not locations:
        console.print("[yellow]No locations found. Please try a different search.[/yellow]")
        return None

    # Create selection table
    table = Table(title="Found Locations - Select One", box=box.ROUNDED)
    table.add_column("#", style="cyan", justify="center", width=4)
    table.add_column("City", style="green", width=25)
    table.add_column("Country", style="yellow", width=20)
    table.add_column("Coordinates", style="white", width=25)

    for idx, loc in enumerate(locations, 1):
        city = loc.get("name", "Unknown")
        country = loc.get("country", "Unknown")
        admin1 = loc.get("admin1", "")
        lat = loc.get("latitude", 0)
        lon = loc.get("longitude", 0)

        # Add state/region if available
        location_str = f"{city}, {admin1}" if admin1 else city

        table.add_row(
            str(idx),
            location_str,
            country,
            f"{lat:.4f}, {lon:.4f}"
        )

    console.print("\n", table, "\n")

    # Get user selection
    while True:
        try:
            choice = typer.prompt("Enter number", type=int)
            if 1 <= choice <= len(locations):
                return locations[choice - 1]
            else:
                console.print(f"[red]Please enter a number between 1 and {len(locations)}[/red]")
        except (ValueError, typer.Abort):
            console.print("[yellow]Selection cancelled[/yellow]")
            return None


def fetch_forecast(lat: float, lon: float, model: str, forecast_type: str = "daily",
                   duration: int = 7) -> Optional[Dict]:
    """Fetch weather forecast using specific model from Open-Meteo API.

    Args:
        lat: Latitude
        lon: Longitude
        model: Model ID
        forecast_type: "daily" or "hourly"
        duration: Number of days (for daily) or hours (for hourly)
    """
    url = "https://api.open-meteo.com/v1/forecast"

    if forecast_type == "daily":
        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max",
            "forecast_days": duration,
            "timezone": "auto",
            "models": model
        }
    else:  # hourly
        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": "weather_code,temperature_2m,precipitation,relative_humidity_2m,wind_speed_10m",
            "forecast_hours": duration,
            "timezone": "auto",
            "models": model
        }

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception:
        return None


def display_forecast(forecast_data: Dict, model_name: str, location_str: str,
                     forecast_type: str = "daily", duration: int = 7) -> None:
    """Display weather forecast in a beautiful Rich table."""
    if forecast_type == "daily":
        display_daily_forecast(forecast_data, model_name, location_str, duration)
    else:
        display_hourly_forecast(forecast_data, model_name, location_str, duration)


def display_daily_forecast(forecast_data: Dict, model_name: str, location_str: str, days: int) -> None:
    """Display daily weather forecast."""
    if not forecast_data or "daily" not in forecast_data:
        console.print("[yellow]No forecast data available.[/yellow]")
        return

    daily = forecast_data["daily"]
    dates = daily.get("time", [])
    weather_codes = daily.get("weather_code", [])
    temp_max = daily.get("temperature_2m_max", [])
    temp_min = daily.get("temperature_2m_min", [])
    precipitation = daily.get("precipitation_sum", [])
    wind_speed = daily.get("wind_speed_10m_max", [])

    # Create forecast panel
    console.print()
    forecast_panel = Panel(
        f"[bold cyan]{location_str}[/bold cyan]\n"
        f"Using: [bold green]{model_name}[/bold green]",
        title=f"📍 {days}-Day Weather Forecast",
        border_style="cyan",
        box=box.DOUBLE
    )
    console.print(forecast_panel)

    # Create forecast table
    table = Table(box=box.ROUNDED, show_header=True, header_style="bold magenta")
    table.add_column("Date", style="cyan", width=12)
    table.add_column("Weather", style="white", width=25)
    table.add_column("Temp (°C)", justify="center", width=12)
    table.add_column("Rain (mm)", justify="right", width=11)
    table.add_column("Wind", justify="right", width=15)

    for i in range(len(dates)):
        date = dates[i]
        code = weather_codes[i] if i < len(weather_codes) else 0
        t_max = temp_max[i] if i < len(temp_max) else None
        t_min = temp_min[i] if i < len(temp_min) else None
        precip = precipitation[i] if i < len(precipitation) else 0
        wind = wind_speed[i] if i < len(wind_speed) else 0

        # Get weather indicator and description
        indicator, description = WEATHER_CODES.get(code, ("❓ ", "Unknown"))

        # Color code temperatures
        if t_max is not None and t_min is not None:
            if t_max >= 30:
                temp_color = "red"
            elif t_max >= 20:
                temp_color = "yellow"
            elif t_max >= 10:
                temp_color = "white"
            else:
                temp_color = "cyan"
            temp_str = f"[{temp_color}]{t_min:.0f}° - {t_max:.0f}°[/{temp_color}]"
        else:
            temp_str = "—"

        # Color code precipitation
        if precip > 10:
            precip_color = "blue"
        elif precip > 0:
            precip_color = "cyan"
        else:
            precip_color = "white"
        precip_str = f"[{precip_color}]{precip:.1f}[/{precip_color}]"

        # Color code wind speed
        if wind >= 60:
            wind_color = "red"
        elif wind >= 40:
            wind_color = "orange1"
        elif wind >= 20:
            wind_color = "yellow"
        else:
            wind_color = "green"
        wind_str = f"[{wind_color}]{wind:.0f} km/h[/{wind_color}]"

        table.add_row(
            date,
            f"{indicator} {description}",
            temp_str,
            precip_str,
            wind_str
        )

    console.print("\n", table)


def display_hourly_forecast(forecast_data: Dict, model_name: str, location_str: str, hours: int) -> None:
    """Display hourly weather forecast."""
    if not forecast_data or "hourly" not in forecast_data:
        console.print("[yellow]No forecast data available.[/yellow]")
        return

    hourly = forecast_data["hourly"]
    times = hourly.get("time", [])
    weather_codes = hourly.get("weather_code", [])
    temperatures = hourly.get("temperature_2m", [])
    precipitation = hourly.get("precipitation", [])
    humidity = hourly.get("relative_humidity_2m", [])
    wind_speed = hourly.get("wind_speed_10m", [])

    # Create forecast panel
    console.print()
    forecast_panel = Panel(
        f"[bold cyan]{location_str}[/bold cyan]\n"
        f"Using: [bold green]{model_name}[/bold green]",
        title=f"📍 {hours}-Hour Weather Forecast",
        border_style="cyan",
        box=box.DOUBLE
    )
    console.print(forecast_panel)

    # Create forecast table (show up to requested hours)
    table = Table(box=box.ROUNDED, show_header=True, header_style="bold magenta")
    table.add_column("Date & Time", style="cyan", width=18)
    table.add_column("Weather", style="white", width=25)
    table.add_column("Temp", justify="center", width=8)
    table.add_column("Rain(mm)", justify="right", width=10)
    table.add_column("Humidity", justify="right", width=10)
    table.add_column("Wind", justify="right", width=12)

    # Limit to requested hours
    display_count = min(hours, len(times))

    for i in range(display_count):
        # Parse datetime
        time_str = times[i]
        try:
            dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
            # Format as "Oct 08 10:00"
            formatted_time = dt.strftime("%b %d %H:%M")
        except:
            formatted_time = time_str

        code = weather_codes[i] if i < len(weather_codes) else 0
        temp = temperatures[i] if i < len(temperatures) else None
        precip = precipitation[i] if i < len(precipitation) else 0
        humid = humidity[i] if i < len(humidity) else None
        wind = wind_speed[i] if i < len(wind_speed) else 0

        # Get weather indicator and description
        indicator, description = WEATHER_CODES.get(code, ("❓ ", "Unknown"))

        # Color code temperature
        if temp is not None:
            if temp >= 30:
                temp_color = "red"
            elif temp >= 20:
                temp_color = "yellow"
            elif temp >= 10:
                temp_color = "white"
            else:
                temp_color = "cyan"
            temp_str = f"[{temp_color}]{temp:.0f}°C[/{temp_color}]"
        else:
            temp_str = "—"

        # Color code precipitation
        if precip > 5:
            precip_color = "blue"
        elif precip > 0:
            precip_color = "cyan"
        else:
            precip_color = "white"
        precip_str = f"[{precip_color}]{precip:.1f}[/{precip_color}]"

        # Color code humidity
        if humid is not None:
            if humid >= 80:
                humid_color = "blue"
            elif humid >= 60:
                humid_color = "white"
            else:
                humid_color = "yellow"
            humid_str = f"[{humid_color}]{humid:.0f}%[/{humid_color}]"
        else:
            humid_str = "—"

        # Color code wind speed
        if wind >= 60:
            wind_color = "red"
        elif wind >= 40:
            wind_color = "orange1"
        elif wind >= 20:
            wind_color = "yellow"
        else:
            wind_color = "green"
        wind_str = f"[{wind_color}]{wind:.0f} km/h[/{wind_color}]"

        table.add_row(
            formatted_time,
            f"{indicator} {description}",
            temp_str,
            precip_str,
            humid_str,
            wind_str
        )

    console.print("\n", table)


def analyze_model_accuracy(lat: float, lon: float, days_back: int = 7) -> Tuple[Dict, Dict]:
    """Analyze accuracy of different weather models over the past week."""
    # Models to test (Open-Meteo supported models)
    # Global models work everywhere, regional models have specific coverage areas
    models = [
        # Global Models
        "ecmwf_ifs04",              # ECMWF IFS (Europe)
        "gfs_seamless",             # NOAA GFS (US)
        "icon_seamless",            # DWD ICON (Germany)
        "gem_seamless",             # GEM (Canada)
        "jma_seamless",             # JMA (Japan)
        "meteofrance_seamless",     # Météo-France
        "bom_access_global",        # BOM (Australia)
        "cma_grapes_global",        # CMA GRAPES (China)
        "ukmo_seamless",            # UK Met Office

        # Regional High-Resolution Models
        "icon_eu",                  # ICON Europe (7km, Europe only)
        "icon_d2",                  # ICON D2 (2km, Central Europe only)
        "arpege_seamless",          # ARPEGE Europe (11km, Europe)
        "arome_seamless",           # AROME France (2.5km, France)
        "hrrr_seamless",            # HRRR (3km, US only)
        "nam_seamless",             # NAM (3km, US only)
    ]

    # Display names for models
    model_names = {
        "ecmwf_ifs04": "ECMWF IFS",
        "gfs_seamless": "NOAA GFS",
        "icon_seamless": "DWD ICON Global",
        "gem_seamless": "GEM Canada",
        "jma_seamless": "JMA Japan",
        "meteofrance_seamless": "Météo-France",
        "bom_access_global": "BOM Australia",
        "cma_grapes_global": "CMA GRAPES China",
        "ukmo_seamless": "UK Met Office",
        "icon_eu": "ICON Europe (7km)",
        "icon_d2": "ICON D2 (2km)",
        "arpege_seamless": "ARPEGE Europe",
        "arome_seamless": "AROME France (2.5km)",
        "hrrr_seamless": "HRRR US (3km)",
        "nam_seamless": "NAM US (3km)",
    }

    results = {}

    console.print(f"\n[bold cyan]Analyzing weather models for location ({lat}, {lon})[/bold cyan]")
    console.print(f"Checking accuracy over the past {days_back} days with {len(models)} models\n")

    # Calculate total operations
    total_operations = days_back * (1 + len(models))  # 1 actual weather fetch + N model fetches per day

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console
    ) as progress:
        task = progress.add_task("[cyan]Fetching and comparing data...", total=total_operations)

        # Check each day in the past week
        for day_offset in range(1, days_back + 1):
            date = (datetime.now() - timedelta(days=day_offset)).strftime("%Y-%m-%d")

            # Fetch actual weather
            progress.update(task, description=f"[cyan]Fetching actual weather for {date}...")
            actual_data = fetch_actual_weather(lat, lon, date)
            progress.advance(task)

            if not actual_data:
                # Skip models for this day if we don't have actual data
                progress.advance(task, advance=len(models))
                continue

            actual_temp = actual_data.get("hourly", {}).get("temperature_2m", [])
            actual_precip = actual_data.get("hourly", {}).get("precipitation", [])
            actual_wind = actual_data.get("hourly", {}).get("wind_speed_10m", [])

            # Test each model
            for model in models:
                if model not in results:
                    results[model] = {
                        "temp_errors": [],
                        "precip_errors": [],
                        "wind_errors": []
                    }

                model_display_name = model_names.get(model, model)
                progress.update(task, description=f"[cyan]Testing {model_display_name} for {date}...")

                forecast_data = fetch_historical_forecast(lat, lon, date, model)
                progress.advance(task)

                if not forecast_data:
                    continue

                forecast_temp = forecast_data.get("hourly", {}).get("temperature_2m", [])
                forecast_precip = forecast_data.get("hourly", {}).get("precipitation", [])
                forecast_wind = forecast_data.get("hourly", {}).get("wind_speed_10m", [])

                # Calculate errors
                temp_mae = calculate_mae(forecast_temp, actual_temp)
                precip_mae = calculate_mae(forecast_precip, actual_precip)
                wind_mae = calculate_mae(forecast_wind, actual_wind)

                if temp_mae is not None:
                    results[model]["temp_errors"].append(temp_mae)
                if precip_mae is not None:
                    results[model]["precip_errors"].append(precip_mae)
                if wind_mae is not None:
                    results[model]["wind_errors"].append(wind_mae)

    return results, model_names


def get_error_color(rank: int, total: int) -> str:
    """Get color for error based on ranking."""
    if rank == 1:
        return "green"
    elif rank <= total * 0.3:  # Top 30%
        return "yellow"
    elif rank <= total * 0.6:  # Top 60%
        return "orange1"
    else:
        return "red"


def display_results(results: Dict, model_names: Dict) -> Optional[Tuple[str, float]]:
    """Display model accuracy results and return the best model ID and error score."""
    console.print()

    # Filter out models with no data (e.g., regional models outside their coverage)
    results = {k: v for k, v in results.items() if v["temp_errors"] or v["precip_errors"] or v["wind_errors"]}

    if not results:
        console.print("[yellow]No model data available for this location.[/yellow]")
        return None

    console.print(f"[bold]Tested {len(results)} models with available data for this location.[/bold]\n")

    # Calculate average errors for each model
    model_scores = {}
    for model, errors in results.items():
        avg_temp = mean(errors["temp_errors"]) if errors["temp_errors"] else None
        avg_precip = mean(errors["precip_errors"]) if errors["precip_errors"] else None
        avg_wind = mean(errors["wind_errors"]) if errors["wind_errors"] else None

        # Overall score (lower is better)
        score_components = [s for s in [avg_temp, avg_precip, avg_wind] if s is not None]
        overall_score = mean(score_components) if score_components else None

        model_scores[model] = {
            "overall": overall_score,
            "temp": avg_temp,
            "precip": avg_precip,
            "wind": avg_wind
        }

    # Sort by overall accuracy (lowest error = best)
    sorted_models = sorted(
        model_scores.items(),
        key=lambda x: x[1]["overall"] if x[1]["overall"] is not None else float('inf')
    )
    sorted_models = [(m, s) for m, s in sorted_models if s["overall"] is not None]

    # Create results table
    table = Table(title="Weather Model Accuracy Rankings", box=box.ROUNDED, show_header=True, header_style="bold magenta")
    table.add_column("Rank", style="cyan", justify="center", width=6)
    table.add_column("Model", style="white", width=25)
    table.add_column("Overall Error", justify="right", width=14)
    table.add_column("Temp MAE (°C)", justify="right", width=14)
    table.add_column("Precip MAE (mm)", justify="right", width=16)
    table.add_column("Wind MAE (km/h)", justify="right", width=16)

    total_models = len(sorted_models)
    for rank, (model, scores) in enumerate(sorted_models, 1):
        display_name = model_names.get(model, model.upper())
        color = get_error_color(rank, total_models)

        # Add medal for top 3
        rank_display = str(rank)
        if rank == 1:
            rank_display = "🥇 1"
        elif rank == 2:
            rank_display = "🥈 2"
        elif rank == 3:
            rank_display = "🥉 3"

        table.add_row(
            rank_display,
            display_name,
            f"[{color}]{scores['overall']:.2f}[/{color}]" if scores['overall'] else "—",
            f"[{color}]{scores['temp']:.2f}[/{color}]" if scores['temp'] else "—",
            f"[{color}]{scores['precip']:.2f}[/{color}]" if scores['precip'] else "—",
            f"[{color}]{scores['wind']:.2f}[/{color}]" if scores['wind'] else "—",
        )

    console.print(table)

    # Display best model in a panel
    if sorted_models:
        best_model = sorted_models[0][0]
        best_error = sorted_models[0][1]['overall']
        best_display_name = model_names.get(best_model, best_model.upper())
        best_panel = Panel(
            f"[bold green]{best_display_name}[/bold green]\n"
            f"Overall Error: [green]{best_error:.2f}[/green]",
            title="🏆 Best Model for Your Location",
            border_style="green",
            box=box.DOUBLE
        )
        console.print("\n", best_panel)
        return (best_model, best_error)

    return None


@app.command()
def main(
    city: Optional[str] = typer.Option(None, "--city", "-c", help="City name to search for"),
    latitude: Optional[float] = typer.Option(None, "--lat", "-l", help="Latitude of the location"),
    longitude: Optional[float] = typer.Option(None, "--lon", "-g", help="Longitude of the location"),
    days: int = typer.Option(7, "--days", "-d", help="Number of days to analyze (1-14)", min=1, max=14),
    forecast_type: Optional[str] = typer.Option(None, "--forecast-type", "-ft", help="Forecast type: daily or hourly"),
    forecast_days: Optional[int] = typer.Option(None, "--forecast-days", "-fd", help="Days for daily forecast (3, 7, 14)", min=3, max=14),
    forecast_hours: Optional[int] = typer.Option(None, "--forecast-hours", "-fh", help="Hours for hourly forecast (24, 48, 72, 120)", min=24, max=120),
    no_cache: bool = typer.Option(False, "--no-cache", help="Force re-analysis, ignore cache"),
    show_cache_flag: bool = typer.Option(False, "--show-cache", help="Display cached results and exit"),
    clear_cache_flag: bool = typer.Option(False, "--clear-cache", help="Clear cache and exit"),
):
    """
    Find the most accurate weather forecast model for your location.

    Analyzes historical forecast accuracy from 15 different weather models
    and ranks them based on temperature, precipitation, and wind speed predictions.
    Then shows a forecast using the most accurate model.

    Supports caching to remember the best model for each location.
    """
    # Handle cache management commands first
    if show_cache_flag:
        show_cache()
        return

    if clear_cache_flag:
        clear_cache()
        return
    # Display header
    header = Panel(
        "[bold cyan]Weather Model Accuracy Finder[/bold cyan]\n\n"
        "Compares 15 weather forecast models to find the most accurate one for your location",
        box=box.DOUBLE,
        border_style="cyan"
    )
    console.print(header)

    location_str = None

    # Handle city search if provided
    if city:
        console.print(f"\n[cyan]Searching for: {city}...[/cyan]")
        locations = geocode_location(city)

        if not locations:
            console.print(f"[red]No locations found for '{city}'. Please try again.[/red]")
            raise typer.Exit(code=1)

        selected = select_location(locations)
        if not selected:
            console.print("[yellow]No location selected. Exiting.[/yellow]")
            raise typer.Exit(code=1)

        latitude = selected.get("latitude")
        longitude = selected.get("longitude")
        city_name = selected.get("name", "Unknown")
        country = selected.get("country", "")
        admin1 = selected.get("admin1", "")

        # Build location string
        if admin1:
            location_str = f"{city_name}, {admin1}, {country}"
        else:
            location_str = f"{city_name}, {country}"

        console.print(f"\n[green]Selected: {location_str}[/green]")
        console.print(f"[dim]Coordinates: {latitude:.4f}, {longitude:.4f}[/dim]\n")

    # Get location if not provided - prioritize city search in interactive mode
    if latitude is None or longitude is None:
        # First, try to get city name
        if city is None:
            console.print("\n[yellow]Enter your location:[/yellow]")
            city_input = typer.prompt("City name (or press Enter to use coordinates)", default="", show_default=False)

            if city_input.strip():
                # User provided city name, search for it
                console.print(f"\n[cyan]Searching for: {city_input}...[/cyan]")
                locations = geocode_location(city_input)

                if locations:
                    selected = select_location(locations)
                    if selected:
                        latitude = selected.get("latitude")
                        longitude = selected.get("longitude")
                        city_name = selected.get("name", "Unknown")
                        country = selected.get("country", "")
                        admin1 = selected.get("admin1", "")

                        # Build location string
                        if admin1:
                            location_str = f"{city_name}, {admin1}, {country}"
                        else:
                            location_str = f"{city_name}, {country}"

                        console.print(f"\n[green]Selected: {location_str}[/green]")
                        console.print(f"[dim]Coordinates: {latitude:.4f}, {longitude:.4f}[/dim]\n")
                else:
                    console.print(f"[yellow]No locations found for '{city_input}'.[/yellow]")

        # Fall back to coordinates if still not provided
        if latitude is None or longitude is None:
            console.print("\n[yellow]Enter your location coordinates:[/yellow]")
            console.print("(Find yours at https://www.latlong.net/)\n")

            if latitude is None:
                latitude = typer.prompt("Latitude", type=float)
            if longitude is None:
                longitude = typer.prompt("Longitude", type=float)

    # Validate coordinates
    if not (-90 <= latitude <= 90):
        console.print("[red]Error: Latitude must be between -90 and 90[/red]")
        raise typer.Exit(code=1)
    if not (-180 <= longitude <= 180):
        console.print("[red]Error: Longitude must be between -180 and 180[/red]")
        raise typer.Exit(code=1)

    # Default location string if not set
    if not location_str:
        location_str = f"Lat {latitude:.4f}, Lon {longitude:.4f}"

    # Prompt for forecast preferences if not provided
    if forecast_type is None:
        console.print("\n[yellow]Forecast preferences:[/yellow]")
        forecast_type_input = typer.prompt("Forecast type (daily/hourly)", default="daily", show_default=True)
        forecast_type = forecast_type_input.lower()

    # Validate forecast type
    if forecast_type not in ["daily", "hourly"]:
        console.print("[red]Error: forecast-type must be 'daily' or 'hourly'[/red]")
        raise typer.Exit(code=1)

    # Prompt for duration if not provided
    if forecast_type == "daily" and forecast_days is None:
        forecast_days = typer.prompt("Number of days to forecast", default=7, type=int, show_default=True)
        # Validate range
        if not (3 <= forecast_days <= 14):
            console.print("[red]Error: Days must be between 3 and 14[/red]")
            raise typer.Exit(code=1)
    elif forecast_type == "hourly" and forecast_hours is None:
        forecast_hours = typer.prompt("Number of hours to forecast", default=48, type=int, show_default=True)
        # Validate range
        if not (24 <= forecast_hours <= 120):
            console.print("[red]Error: Hours must be between 24 and 120[/red]")
            raise typer.Exit(code=1)

    # Set defaults if still None
    if forecast_days is None:
        forecast_days = 7
    if forecast_hours is None:
        forecast_hours = 48

    # Determine forecast duration
    forecast_duration = forecast_days if forecast_type == "daily" else forecast_hours

    # Check cache first (unless --no-cache is specified)
    best_model_id = None
    best_model_name = None
    from_cache = False

    if not no_cache:
        cache = load_cache()
        cached_result = get_cached_model(latitude, longitude, cache)

        if cached_result:
            best_model_id = cached_result["best_model_id"]
            best_model_name = cached_result["best_model_name"]
            cache_age = (datetime.now() - datetime.fromisoformat(cached_result["timestamp"])).days
            from_cache = True

            console.print()
            console.print(f"[green]✓ Using cached best model: {best_model_name}[/green]")
            console.print(f"[dim]  Analyzed {cache_age} day{'s' if cache_age != 1 else ''} ago[/dim]")
            console.print(f"[dim]  Use --no-cache to force re-analysis[/dim]\n")

    # Analyze model accuracy if not cached
    if not from_cache:
        try:
            results, model_names = analyze_model_accuracy(latitude, longitude, days_back=days)

            # Display results and get best model
            if results:
                result = display_results(results, model_names)

                if result:
                    best_model_id, best_error = result
                    best_model_name = model_names.get(best_model_id, best_model_id)

                    # Cache the result
                    cache_model_result(latitude, longitude, best_model_id, best_model_name,
                                      best_error, location_str)
                    console.print("[dim]✓ Result cached for future use[/dim]")
            else:
                console.print("\n[yellow]No data available to analyze. Please try again later.[/yellow]")
                return
        except KeyboardInterrupt:
            console.print("\n\n[yellow]Analysis interrupted by user.[/yellow]")
            raise typer.Exit()
        except Exception as e:
            console.print(f"\n[red]An error occurred during analysis: {e}[/red]")
            raise typer.Exit(code=1)

    # Fetch and display forecast with best model
    if best_model_id:
        try:
            console.print(f"\n[cyan]Fetching {forecast_type} forecast with best model...[/cyan]")
            forecast_data = fetch_forecast(latitude, longitude, best_model_id,
                                          forecast_type=forecast_type, duration=forecast_duration)

            if forecast_data:
                display_forecast(forecast_data, best_model_name, location_str,
                               forecast_type=forecast_type, duration=forecast_duration)
            else:
                console.print("[yellow]Could not fetch forecast data.[/yellow]")
        except Exception as e:
            console.print(f"[red]Error fetching forecast: {e}[/red]")


if __name__ == "__main__":
    app()
