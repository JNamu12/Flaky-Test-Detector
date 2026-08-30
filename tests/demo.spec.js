const { test, expect } = require('@playwright/test');

test('sample passing checkout test', async ({ page }) => {
  await page.goto('https://example.com');
  await expect(page).toHaveTitle(/Example Domain/);
});

test('sample API status test', async ({ page }) => {
  await page.goto('https://example.com');
  const h1 = page.locator('h1');
  await expect(h1).toHaveText('Example Domain');
});
