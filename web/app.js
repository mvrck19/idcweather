// Error reporting loads in the background so it never delays the forecast. Errors from
// before it arrives wait in `unsent`; if an ad blocker stops it, they're simply dropped.
const isLocal = ['localhost', '127.0.0.1'].includes(location.hostname);
let sentryReady = false;
const unsent = [];
const report = (err, step) => (sentryReady
  ? Sentry.captureException(err, { tags: { step } })
  : unsent.push([err, step]));

document.head.append(Object.assign(document.createElement('script'), {
  src: 'https://browser.sentry-cdn.com/11.1.0/bundle.tracing.min.js',
  integrity: 'sha384-2wFCZVEMgV3bEAFuxyGPq6RUOy0fqw5cagFjTgPf51ZCn2eMSidU68Yc3ZHS5d29',
  crossOrigin: 'anonymous',
  onload() {
    Sentry.init({
      dsn: 'https://dbb08a295a5c0eaedaf0122102d72c08@o4512168525037568.ingest.de.sentry.io/4512179761840208',
      environment: isLocal ? 'development' : 'production',
      integrations: [Sentry.browserTracingIntegration()],
      tracesSampleRate: isLocal ? 1.0 : 0.2,
    });
    sentryReady = true;
    unsent.splice(0).forEach(([err, step]) => report(err, step));
  },
}));

// The model-ranking API (weather_api.py). ponytail: placeholder until it's deployed (step 5)
const API_URL = isLocal ? 'http://127.0.0.1:8000' : 'https://weather-api.example.com';

// WMO weather codes, same mapping as the CLI
const CODES = {
  0: ['☀️', 'Clear sky'], 1: ['🌤️', 'Mainly clear'], 2: ['⛅', 'Partly cloudy'], 3: ['☁️', 'Overcast'],
  45: ['🌫️', 'Foggy'], 48: ['🌫️', 'Rime fog'],
  51: ['💧', 'Light drizzle'], 53: ['💧', 'Moderate drizzle'], 55: ['💧', 'Dense drizzle'],
  61: ['🌧️', 'Slight rain'], 63: ['🌧️', 'Moderate rain'], 65: ['🌧️', 'Heavy rain'],
  71: ['❄️', 'Slight snow'], 73: ['❄️', 'Moderate snow'], 75: ['❄️', 'Heavy snow'], 77: ['🌨️', 'Snow grains'],
  80: ['🌦️', 'Slight showers'], 81: ['🌦️', 'Moderate showers'], 82: ['⛈️', 'Violent showers'],
  85: ['🌨️', 'Slight snow showers'], 86: ['🌨️', 'Heavy snow showers'],
  95: ['⛈️', 'Thunderstorm'], 96: ['⛈️', 'Thunderstorm with hail'], 99: ['⛈️', 'Thunderstorm with heavy hail'],
};

const $ = id => document.getElementById(id);
const q = $('q'), results = $('results');
const setStatus = text => { $('status').textContent = text; };

async function getJSON(url, params) {
  const res = await fetch(`${url}?${new URLSearchParams(params)}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

function describe(code, isDay = 1) {
  const [icon, text] = CODES[code] || ['❓', 'Unknown'];
  return [!isDay && code <= 1 ? '🌙' : icon, text];
}

const deg = v => (v == null ? '—' : `${Math.round(v)}°`);

// --- Search -------------------------------------------------------------

let searchTimer, searchSeq = 0;

q.addEventListener('input', () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(search, 250);
});
q.addEventListener('keydown', e => {
  if (e.key === 'Escape') results.hidden = true;
});
$('search').addEventListener('submit', e => {
  e.preventDefault();
  clearTimeout(searchTimer);
  search(true);  // Enter picks the top match
});

async function search(pickFirst = false) {
  const name = q.value.trim();
  const seq = ++searchSeq;
  if (name.length < 2) { results.hidden = true; return; }

  try {
    const data = await getJSON('https://geocoding-api.open-meteo.com/v1/search',
      { name, count: 5, language: 'en', format: 'json' });
    if (seq !== searchSeq) return;  // a newer search already started
    const places = data.results || [];
    if (pickFirst && places.length) return choose(places[0]);

    results.replaceChildren(...places.map(p => {
      const li = document.createElement('li');
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.append(p.name, ' ');
      const region = document.createElement('small');
      region.textContent = [p.admin1, p.country].filter(Boolean).join(', ');
      btn.append(region);
      btn.onclick = () => choose(p);
      li.append(btn);
      return li;
    }));
    if (!places.length) {
      const li = document.createElement('li');
      li.textContent = `No places match “${name}”. Check the spelling or try a nearby city.`;
      results.append(li);
    }
    results.hidden = false;
  } catch (err) {
    console.error(err);
    report(err, 'search');
    setStatus("Couldn't reach the place search. Check your connection and try again.");
  }
}

function choose(p) {
  const name = [...new Set([p.name, p.admin1, p.country])].filter(Boolean).join(', ');
  // ~1 km precision: plenty for weather, and keeps exact positions out of shared links and error reports
  const lat = +p.latitude.toFixed(2), lon = +p.longitude.toFixed(2);
  results.hidden = true;
  q.value = '';
  history.pushState(null, '', `?${new URLSearchParams({ lat, lon, name })}`);
  show(lat, lon, name);
}

$('locate').addEventListener('click', () => {
  if (!navigator.geolocation) {
    return setStatus("This browser can't share your location. Search for a city instead.");
  }
  setStatus('Finding your location…');
  navigator.geolocation.getCurrentPosition(
    pos => choose({ latitude: pos.coords.latitude, longitude: pos.coords.longitude, name: 'Your location' }),
    () => setStatus('Location access is blocked. Allow it in your browser settings, or search for a city.'),
    { timeout: 10000, maximumAge: 600000 },
  );
});

// --- Forecast -----------------------------------------------------------

const DAILY = ['weather_code', 'temperature_2m_max', 'temperature_2m_min', 'precipitation_sum', 'wind_speed_10m_max'];

// Without `models`, Open-Meteo blends its models (best_match)
function getForecast(lat, lon, models) {
  return getJSON('https://api.open-meteo.com/v1/forecast', {
    latitude: lat,
    longitude: lon,
    current: 'temperature_2m,weather_code,wind_speed_10m,is_day',
    daily: DAILY.join(','),
    timezone: 'auto',
    forecast_days: 7,
    ...(models && { models }),
  });
}

let showSeq = 0;  // bumped per place, so answers for a previous place are dropped

// Show the blended forecast straight away, then upgrade to the most accurate model
async function show(lat, lon, name) {
  const seq = ++showSeq;
  setStatus('Loading forecast…');
  $('compare').hidden = true;
  $('source').textContent = 'Blended forecast. Checking which model has been most accurate here…';
  try {
    const f = await getForecast(lat, lon);
    if (seq !== showSeq) return;
    render(f, name);
    setStatus('');
  } catch (err) {
    console.error(err);  // the status line below covers fetch and render failures alike
    report(err, 'forecast');
    if (seq === showSeq) setStatus("Couldn't load the forecast. Check your connection and try again.");
    return;
  }
  upgrade(lat, lon, name, seq);
}

// If this fails, the blended forecast simply stays
async function upgrade(lat, lon, name, seq) {
  try {
    const rank = await getJSON(`${API_URL}/best-model`, { lat, lon });
    if (seq !== showSeq) return;
    const { best } = rank;
    const [f, covered] = merge(await getForecast(lat, lon, `${best.id},best_match`), best.id);
    if (seq !== showSeq) return;
    if (covered) render(f, name);
    showComparison(rank, covered);
  } catch (err) {
    console.error(err);
    report(err, 'best-model');
    if (seq === showSeq) $('source').textContent = "Blended forecast. The model comparison isn't available right now.";
  }
}

// The best model and the blend arrive side by side, keys suffixed with the model ID.
// Short-range models stop after a few days, so later days come from the blend.
function merge(f, model) {
  const daily = { time: f.daily.time };
  for (const key of DAILY) {
    const own = f.daily[`${key}_${model}`] || [], blend = f.daily[`${key}_best_match`] || [];
    daily[key] = f.daily.time.map((_, i) => own[i] ?? blend[i] ?? null);
  }
  const covered = (f.daily[`temperature_2m_max_${model}`] || []).filter(v => v != null).length;
  return [{ current: f.current, daily }, covered];
}

function showComparison({ best, ranking, days }, covered) {
  const plural = n => (n === 1 ? '' : 's');
  let text = `Forecast from ${best.name}, the most accurate of ${ranking.length} models here over the past ${days} day${plural(days)}.`;
  if (best.temp != null) text += ` Its temperatures were off by ${best.temp.toFixed(1)}° on average.`;
  if (!covered) text = `${best.name} has been the most accurate here, but it has no forecast for the coming days, so this is the blended forecast.`;
  else if (covered < 7) text += ` ${best.name} only forecasts ${covered} day${plural(covered)} ahead, so later days use the blended forecast.`;
  $('source').textContent = text;

  const cell = (tag, text) => Object.assign(document.createElement(tag), { textContent: text });
  const fixed = (v, unit, digits = 1) => (v == null ? '—' : `${v.toFixed(digits)}${unit}`);
  $('ranking').replaceChildren(...ranking.map(m => {
    const row = document.createElement('tr');
    // Hourly rain errors are hundredths of a mm, so they need the extra digit
    row.append(cell('th', m.name), cell('td', fixed(m.temp, '°')), cell('td', fixed(m.precip, ' mm', 2)), cell('td', fixed(m.wind, ' km/h')));
    row.firstChild.scope = 'row';
    return row;
  }));
  $('model-count').textContent = ranking.length;
  $('compare').hidden = false;
}

function render(f, name) {
  const [city, ...region] = name.split(', ');
  document.title = `${city} weather`;
  $('place').textContent = city;
  $('region').textContent = region.join(', ');

  const c = f.current;
  const [, nowText] = describe(c.weather_code, c.is_day);
  $('now').textContent = `${deg(c.temperature_2m)} and ${nowText.toLowerCase()}. Wind ${Math.round(c.wind_speed_10m)} km/h.`;

  // One shared scale for the week, so bars compare across days
  const d = f.daily;
  const lows = d.temperature_2m_min.filter(v => v != null);
  const highs = d.temperature_2m_max.filter(v => v != null);
  const weekLo = Math.min(...lows), span = (Math.max(...highs) - weekLo) || 1;
  const pct = v => ((v - weekLo) / span) * 100;

  $('days').innerHTML = d.time.map((date, i) => {
    const lo = d.temperature_2m_min[i], hi = d.temperature_2m_max[i];
    const rain = d.precipitation_sum[i], wind = d.wind_speed_10m_max[i];
    const [icon, text] = describe(d.weather_code[i]);
    const [y, m, day] = date.split('-').map(Number);
    const label = i === 0 ? 'Today' : new Date(y, m - 1, day).toLocaleDateString(undefined, { weekday: 'short' });
    const bar = lo == null || hi == null ? '' : `<i style="left:${pct(lo)}%;width:${pct(hi) - pct(lo)}%"></i>`;
    return `<li>
      <span class="day">${label}</span>
      <span class="icon" aria-hidden="true">${icon}</span>
      <span class="lo"><span class="sr">low </span>${deg(lo)}</span>
      <span class="bar" aria-hidden="true">${bar}</span>
      <span class="hi"><span class="sr">high </span>${deg(hi)}</span>
      <span class="meta">
        <span class="desc">${text}</span>
        <span class="rain">${rain > 0 ? `${rain.toFixed(1)} mm` : ''}</span>
        <span class="wind">${wind == null ? '' : `${Math.round(wind)} km/h`}</span>
      </span>
    </li>`;
  }).join('');

  $('intro').hidden = true;
  $('forecast').hidden = false;
}

// --- Shareable URLs: ?lat=..&lon=..&name=.. -----------------------------

function loadFromURL() {
  const p = new URLSearchParams(location.search);
  const lat = parseFloat(p.get('lat')), lon = parseFloat(p.get('lon'));
  if (Number.isFinite(lat) && Number.isFinite(lon)) {
    $('intro').hidden = true;
    show(lat, lon, p.get('name') || `${lat}, ${lon}`);
  } else {
    $('intro').hidden = false;
    $('forecast').hidden = true;
    q.focus();
  }
}

window.addEventListener('popstate', loadFromURL);
loadFromURL();
