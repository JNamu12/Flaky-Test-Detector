const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests',
  reporter: [
    ['junit', { outputFile: 'results/junit.xml' }],
    ['list']
  ],
  use: {
    headless: true,
  },
});
