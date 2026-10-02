const { test, expect } = require('@playwright/test');

const LONDON = { name: 'London', admin1: 'England', country: 'United Kingdom', latitude: 51.50853, longitude: -0.12574 };

const FORECAST = {
  current: { temperature_2m: 14.2, weather_code: 3, wind_speed_10m: 11.5, is_day: 1 },
  daily: {
    time: ['2026-10-01', '2026-10-02', '2026-10-03', '2026-10-04', '2026-10-05', '2026-10-06', '2026-10-07'],
    weather_code: [3, 61, 2, 0, 1, 80, 3],
    temperature_2m_max: [16.1, 14.8, 15.3, 17.9, 18.2, 15.0, 14.4],
    temperature_2m_min: [9.2, 10.1, 8.4, 7.9, 9.5, 10.3, 8.8],
    precipitation_sum: [0, 4.2, 0, 0, 0, 1.1, 0],
    wind_speed_10m_max: [18.4, 25.0, 12.1, 9.8, 11.0, 22.3, 15.6],
  },
};

const PARIS = { name: 'Paris', admin1: 'Île-de-France', country: 'France', latitude: 48.85341, longitude: 2.3488 };

// What the ranking API (weather_api.py) answers
const RANKING = [
  { id: 'ecmwf_ifs025', name: 'ECMWF IFS', overall: 0.4, temp: 0.31, precip: 0.12, wind: 0.77 },
  { id: 'icon_seamless', name: 'DWD ICON Global', overall: 0.72, temp: 0.58, precip: 0.2, wind: 1.38 },
  { id: 'gfs_seamless', name: 'NOAA GFS', overall: 1.07, temp: 0.79, precip: 0.3, wind: 2.12 },
];
const ranked = (ranking = RANKING) => ({ lat: 51.51, lon: -0.13, days: 7, best: ranking[0], ranking, cached: false });

const BEST_HIGH = 30;  // the best model's highs, so tests can tell its days from the blend's

// Plain requests get the blended forecast. ?models=<best>,best_match gets both side by side,
// keys suffixed with the model ID (as Open-Meteo does), the best model covering only `covered` days.
function forecastFor(url, covered = 7) {
  const models = url.searchParams.get('models');
  if (!models) return FORECAST;
  const best = models.split(',')[0];
  const daily = { time: FORECAST.daily.time };
  for (const [key, values] of Object.entries(FORECAST.daily)) {
    if (key === 'time') continue;
    daily[`${key}_best_match`] = values;
    daily[`${key}_${best}`] = values.map((v, i) => (i >= covered ? null : key === 'temperature_2m_max' ? BEST_HIGH : v));
  }
  return { current: FORECAST.current, daily };
}

const isGeocoding = url => url.hostname === 'geocoding-api.open-meteo.com';
const isForecast = url => url.hostname === 'api.open-meteo.com';
const isRankingApi = url => url.port === '8000' && url.pathname === '/best-model';
const isSentryIngest = url => url.hostname.endsWith('.sentry.io');
const isSentryScript = url => url.hostname === 'browser.sentry-cdn.com';

test.beforeEach(async ({ page }) => {
  // Never send test events to the real Sentry project
  await page.route(isSentryIngest, r => r.fulfill({ status: 200, body: '{}' }));
  // Ranking API unreachable unless a test says otherwise (later routes take precedence)
  await page.route(isRankingApi, r => r.abort());
});

async function expectLondonForecast(page) {
  await expect(page.locator('#place')).toHaveText('London');
  await expect(page.locator('#days li')).toHaveCount(7);
  await expect(page.locator('#forecast')).toBeVisible();
  await expect(page.locator('#intro')).toBeHidden();
  await expect(page.locator('#status')).toBeEmpty();
}

test.describe('with mocked Open-Meteo', () => {
  test.beforeEach(async ({ page }) => {
    await page.route(isGeocoding, r => r.fulfill({ json: { results: [LONDON] } }));
    await page.route(isForecast, r => r.fulfill({ json: forecastFor(new URL(r.request().url())) }));
  });

  test('picking a city from the results shows its forecast', async ({ page }) => {
    await page.goto('/');
    await page.locator('#q').fill('london');
    await page.locator('#results button', { hasText: 'London' }).click();

    await expectLondonForecast(page);
    await expect(page.locator('#region')).toHaveText('England, United Kingdom');
    await expect(page.locator('#now')).toHaveText('14° and overcast. Wind 12 km/h.');
    await expect(page).toHaveURL(/lat=51\.51&lon=-0\.13&/);  // rounded to ~1 km
  });

  test('Enter picks the top match', async ({ page }) => {
    await page.goto('/');
    await page.locator('#q').fill('london');
    await page.locator('#q').press('Enter');
    await expectLondonForecast(page);
  });

  test('a shared link opens straight to the forecast', async ({ page }) => {
    await page.goto('/?lat=51.5085&lon=-0.1257&name=London%2C+England%2C+United+Kingdom');
    await expectLondonForecast(page);
  });

  test('missing values in the forecast still render', async ({ page }) => {
    const gappy = structuredClone(FORECAST);
    gappy.daily.temperature_2m_min[2] = null;
    gappy.daily.precipitation_sum[1] = null;
    gappy.daily.wind_speed_10m_max[3] = null;
    gappy.daily.weather_code[4] = null;
    await page.route(isForecast, r => r.fulfill({ json: gappy }));

    await page.goto('/?lat=51.5085&lon=-0.1257&name=London');
    await expect(page.locator('#days li')).toHaveCount(7);
    await expect(page.locator('#days li').nth(2).locator('.lo')).toContainText('—');
    await expect(page.locator('#status')).toBeEmpty();
  });

  test('no matches tells you what to try', async ({ page }) => {
    await page.route(isGeocoding, r => r.fulfill({ json: {} }));  // Open-Meteo omits `results` when empty
    await page.goto('/');
    await page.locator('#q').fill('xqzv');
    await expect(page.locator('#results')).toContainText('No places match “xqzv”');
  });

  test('forecast service down shows a retry message', async ({ page }) => {
    await page.route(isForecast, r => r.abort());
    await page.goto('/?lat=51.5085&lon=-0.1257&name=London');
    await expect(page.locator('#status')).toHaveText("Couldn't load the forecast. Check your connection and try again.");
  });

  test('a failed forecast is reported to Sentry', async ({ page }) => {
    await page.route(isForecast, r => r.abort());
    const sent = page.waitForRequest(req =>
      isSentryIngest(new URL(req.url())) && (req.postData() || '').includes('"step":"forecast"'));
    await page.goto('/?lat=51.51&lon=-0.13&name=London');
    await sent;
  });

  test('the site still works when Sentry is blocked', async ({ page }) => {
    await page.route(isSentryScript, r => r.abort());  // what an ad blocker does
    await page.goto('/?lat=51.51&lon=-0.13&name=London%2C+England%2C+United+Kingdom');
    await expectLondonForecast(page);
  });

  test('a slow Sentry CDN does not delay the forecast', async ({ page }) => {
    await page.route(isSentryScript, async r => {
      await new Promise(done => setTimeout(done, 5000));
      await r.continue();
    });
    await page.goto('/?lat=51.51&lon=-0.13&name=London', { waitUntil: 'commit' });  // don't wait for page load
    await expect(page.locator('#days li')).toHaveCount(7, { timeout: 2000 });
  });

  test('a failure is still reported once Sentry has loaded', async ({ page }) => {
    await page.route(isForecast, r => r.abort());
    const sent = page.waitForRequest(req =>
      isSentryIngest(new URL(req.url())) && (req.postData() || '').includes('"step":"forecast"'));
    await page.goto('/?lat=51.51&lon=-0.13&name=London');
    await sent;
  });

  test('makes no requests to Google (visitor IPs stay private)', async ({ page }) => {
    const hosts = new Set();
    page.on('request', req => hosts.add(new URL(req.url()).hostname));
    await page.goto('/?lat=51.51&lon=-0.13&name=London');
    await expectLondonForecast(page);
    expect([...hosts].filter(h => /google|gstatic/.test(h))).toEqual([]);
  });

  test('sets no cookies or browser storage', async ({ page, context }) => {
    await page.goto('/');
    await page.locator('#q').fill('london');
    await page.locator('#results button', { hasText: 'London' }).click();
    await expectLondonForecast(page);

    expect(await context.cookies()).toEqual([]);
    expect(await page.evaluate(() => [localStorage.length, sessionStorage.length])).toEqual([0, 0]);
  });
});

test.describe('switching to the most accurate model', () => {
  async function open(page, { ranking = RANKING, covered = 7, apiDelay = 0 } = {}) {
    await page.route(isForecast, r => r.fulfill({ json: forecastFor(new URL(r.request().url()), covered) }));
    await page.route(isRankingApi, async r => {
      await new Promise(done => setTimeout(done, apiDelay));
      await r.fulfill({ json: ranked(ranking) });
    });
    await page.goto('/?lat=51.51&lon=-0.13&name=London');
  }

  test('swaps in the most accurate model and says which', async ({ page }) => {
    await open(page);
    await expect(page.locator('#days .hi')).toHaveText(Array(7).fill(new RegExp(`${BEST_HIGH}°`)));
    await expect(page.locator('#source')).toContainText('ECMWF IFS, the most accurate of 3 models here over the past 7 days');
    await expect(page.locator('#source')).toContainText('off by 0.3° on average');
  });

  test('lists every model in the comparison', async ({ page }) => {
    await open(page);
    await page.getByText('Compare all 3 models').click();
    await expect(page.locator('#ranking tr')).toHaveCount(3);
    await expect(page.locator('#ranking tr').first()).toContainText('ECMWF IFS');
    await expect(page.locator('#ranking tr').first()).toContainText('0.3°');
  });

  test('a short-range best model fills the later days from the blend', async ({ page }) => {
    const iconD2First = [{ ...RANKING[0], id: 'icon_d2', name: 'ICON D2 (2km)' }, ...RANKING.slice(1)];
    await open(page, { ranking: iconD2First, covered: 2 });
    await expect(page.locator('#days .hi')).toHaveText([/30°/, /30°/, /15°/, /18°/, /18°/, /15°/, /14°/]);
    await expect(page.locator('#source')).toContainText('ICON D2 (2km) only forecasts 2 days ahead, so later days use the blended forecast');
  });

  test('the forecast shows before the model comparison is ready', async ({ page }) => {
    await open(page, { apiDelay: 3000 });
    await expectLondonForecast(page);
    await expect(page.locator('#days .hi').first()).toContainText('16°');  // blended
    await expect(page.locator('#source')).toContainText('Checking which model');
    await expect(page.locator('#days .hi').first()).toContainText(`${BEST_HIGH}°`, { timeout: 6000 });
  });

  test('if the ranking API is down, the blended forecast stays', async ({ page }) => {
    await page.route(isForecast, r => r.fulfill({ json: forecastFor(new URL(r.request().url())) }));
    await page.goto('/?lat=51.51&lon=-0.13&name=London');  // API route aborts by default
    await expectLondonForecast(page);
    await expect(page.locator('#source')).toContainText("model comparison isn't available right now");
    await expect(page.locator('#days .hi').first()).toContainText('16°');
    await expect(page.locator('#compare')).toBeHidden();
  });

  test('a late ranking for the previous city is ignored', async ({ page }) => {
    await page.route(isGeocoding, r => {
      const london = new URL(r.request().url()).searchParams.get('name') === 'london';
      return r.fulfill({ json: { results: [london ? LONDON : PARIS] } });
    });
    await page.route(isForecast, r => r.fulfill({ json: forecastFor(new URL(r.request().url())) }));
    await page.route(isRankingApi, async r => {
      const isLondon = new URL(r.request().url()).searchParams.get('lat') === '51.51';
      if (isLondon) await new Promise(done => setTimeout(done, 1500));  // London's answer arrives late
      await r.fulfill({ json: ranked(isLondon ? RANKING : [RANKING[1], RANKING[0], RANKING[2]]) });
    });

    await page.goto('/');
    await page.locator('#q').fill('london');
    await page.locator('#results button', { hasText: 'London' }).click();
    await page.locator('#q').fill('paris');
    await page.locator('#results button', { hasText: 'Paris' }).click();
    await expect(page.locator('#source')).toContainText('DWD ICON Global, the most accurate');

    await page.waitForTimeout(2000);  // London's late answer has now arrived
    await expect(page.locator('#place')).toHaveText('Paris');
    await expect(page.locator('#source')).toContainText('DWD ICON Global, the most accurate');
  });
});

// Real API: catches Open-Meteo changing its response shape. Skip offline with --grep-invert @live
test('live: London forecast loads from the real API @live', async ({ page }) => {
  await page.goto('/');
  await page.locator('#q').fill('london');
  await page.locator('#results button', { hasText: 'England' }).click();
  await expect(page.locator('#days li')).toHaveCount(7, { timeout: 15000 });
  await expectLondonForecast(page);
});
