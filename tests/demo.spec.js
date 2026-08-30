const { test, expect } = require('@playwright/test');

test('demo_flaky_checkout_network_retry', async ({ page }, testInfo) => {
  await page.goto('https://example.com');
  if (testInfo.retry === 0) {
    expect(false).toBe(true);
  } else {
    await expect(page).toHaveTitle(/Example Domain/);
  }
});

test('demo_passing_checkout_test', async ({ page }) => {
  await page.goto('https://example.com');
  await expect(page).toHaveTitle(/Example Domain/);
});

test('demo_failing_payment_gateway_bug', async ({ page }) => {
  await page.goto('https://example.com');
  expect('Payment Gateway Timeout').toBe('Payment Success 200');
});
