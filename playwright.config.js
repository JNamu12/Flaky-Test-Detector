const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests',
  retries: 2,          // Allow up to 2 retries — needed for flaky test simulation
  timeout: 30000,      // 30s per test
  reporter: [
    ['junit', { outputFile: 'results/junit.xml' }],
    ['list']
  ],
  use: {
    headless: true,
  },
});
