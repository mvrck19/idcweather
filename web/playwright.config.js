const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: 'tests',
  use: {
    baseURL: 'http://localhost:8765',
    channel: 'chrome',  // ponytail: installed Chrome, no browser download; use `npx playwright install` for Firefox/WebKit
  },
  webServer: {
    command: 'python -m http.server 8765',
    url: 'http://localhost:8765',
    reuseExistingServer: true,
  },
});
