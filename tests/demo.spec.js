/**
 * demo.spec.js — Flaky Test Detector Demo Suite
 *
 * This file contains deliberately crafted test scenarios that simulate
 * real-world flakiness patterns seen in production test suites.
 * Designed to generate rich, varied data for the Flaky Test Detector dashboard.
 *
 * Categories covered:
 *  - Timing / Race Condition  (element not yet clickable, async load lag)
 *  - Network Flakiness        (API timeout, intermittent 503)
 *  - Environment Flakiness    (session expiry, CI-only failures)
 *  - Genuine Regression       (real broken assertion, logic bug)
 *  - Stable / Passing         (always green, used as baseline)
 */

const { test, expect } = require('@playwright/test');

// ---------------------------------------------------------------------------
// Helper: simulate intermittent failures based on run index or retry count
// ---------------------------------------------------------------------------
function isNthRun(testInfo, everyN) {
  // Uses retry count + a pseudo-random seed based on test title
  const seed = testInfo.title.length + testInfo.retry;
  return (seed % everyN) === 0;
}

// ============================================================================
// CATEGORY 1 — TIMING / RACE CONDITION
// ============================================================================

test('checkout_submit_button_race_condition @demo', async ({ page }, testInfo) => {
  /**
   * Simulates: element not clickable due to animation/overlay still visible.
   * Pattern: fails ~50% of runs (every other retry), passes otherwise.
   * Expected detector verdict: likely_flaky | timing/race_condition
   */
  await page.goto('https://example.com');
  if (testInfo.retry % 2 === 0) {
    // Simulate: "Element is not clickable at point (320, 540). Other element would receive click"
    throw new Error(
      'ElementClickInterceptedException: element click intercepted: ' +
      'Element <button id="checkout-submit"> is not clickable at point (320, 540). ' +
      'Other element would receive the click: <div class="loading-overlay">...</div>'
    );
  }
  await expect(page).toHaveTitle(/Example Domain/);
});

test('login_page_title_timeout', async ({ page }, testInfo) => {
  /**
   * Simulates: page title not loaded in time (async JS hydration lag).
   * Pattern: fails on first attempt, passes on retry.
   * Expected detector verdict: likely_flaky | timing/race_condition
   */
  await page.goto('https://example.com');
  if (testInfo.retry === 0) {
    throw new Error(
      'TimeoutError: page.waitForSelector: Timeout 5000ms exceeded. ' +
      'waiting for locator("h1.page-title") to be visible ' +
      'at login_page_title_timeout (tests/demo.spec.js:52)'
    );
  }
  await expect(page).toHaveTitle(/Example Domain/);
});

test('search_results_dynamic_load_race', async ({ page }, testInfo) => {
  /**
   * Simulates: search results rendered by JS before DOM is ready.
   * Pattern: fails intermittently (every 3rd run).
   * Expected detector verdict: likely_flaky | timing/race_condition
   */
  await page.goto('https://example.com');
  if (isNthRun(testInfo, 3)) {
    throw new Error(
      'Error: strict mode violation: locator(".search-result-item") resolved to 0 elements. ' +
      'Expected at least 1 visible element. ' +
      'Possible cause: results list rendered after test assertion executed.'
    );
  }
  await expect(page).toHaveTitle(/Example Domain/);
});

// ============================================================================
// CATEGORY 2 — NETWORK FLAKINESS
// ============================================================================

test('api_checkout_network_intermittent_503 @demo', async ({ page }, testInfo) => {
  /**
   * Simulates: intermittent 503 from payment microservice.
   * Pattern: fails on first attempt (network timeout), passes on retry.
   * Expected detector verdict: likely_flaky | network
   */
  await page.goto('https://example.com');
  if (testInfo.retry === 0) {
    throw new Error(
      'NetworkError: Failed to fetch POST /api/v1/checkout/initiate — ' +
      'HTTP 503 Service Unavailable. ' +
      'Response time: 31048ms (timeout: 30000ms). ' +
      'Retry-After: 5s. at tests/demo.spec.js:89'
    );
  }
  await expect(page).toHaveTitle(/Example Domain/);
});

test('user_profile_api_slow_response', async ({ page }, testInfo) => {
  /**
   * Simulates: user profile API occasionally exceeds timeout.
   * Pattern: fails every other run.
   * Expected detector verdict: likely_flaky | network
   */
  await page.goto('https://example.com');
  if (testInfo.retry % 2 !== 0) {
    throw new Error(
      'TimeoutError: page.waitForResponse: Timeout 10000ms exceeded. ' +
      'Waiting for response matching /api/v1/users/profile. ' +
      'Server responded after 14320ms. Connection: keep-alive.'
    );
  }
  await expect(page).toHaveTitle(/Example Domain/);
});

// ============================================================================
// CATEGORY 3 — ENVIRONMENT / SESSION FLAKINESS
// ============================================================================

test('admin_dashboard_session_expiry_flaky', async ({ page }, testInfo) => {
  /**
   * Simulates: auth session expires between test setup and assertion (CI only).
   * Pattern: fails on first run, passes on retry when session is refreshed.
   * Expected detector verdict: likely_flaky | environment
   */
  await page.goto('https://example.com');
  if (testInfo.retry === 0) {
    throw new Error(
      'AssertionError: expect(received).toContain(expected). ' +
      'Expected URL to contain "/admin/dashboard" but got "/login?reason=session_expired". ' +
      'Possible cause: authentication cookie expired during test execution. ' +
      'at tests/demo.spec.js:121'
    );
  }
  await expect(page).toHaveTitle(/Example Domain/);
});

test('ci_environment_env_variable_missing', async ({ page }, testInfo) => {
  /**
   * Simulates: missing environment variable on CI causes test to fail once.
   * Pattern: intermittent failure (every 4th run) suggesting CI config drift.
   * Expected detector verdict: likely_flaky | environment
   */
  await page.goto('https://example.com');
  if (isNthRun(testInfo, 4)) {
    throw new Error(
      'ReferenceError: process.env.TEST_BASE_URL is undefined. ' +
      'Expected environment variable TEST_BASE_URL to be set. ' +
      'Falling back to default caused assertion mismatch. ' +
      'Check CI environment configuration.'
    );
  }
  await expect(page).toHaveTitle(/Example Domain/);
});

// ============================================================================
// CATEGORY 4 — GENUINE REGRESSION (always fails)
// ============================================================================

test('payment_gateway_always_timeout_bug @demo', async ({ page }) => {
  /**
   * Simulates: real production bug — payment gateway integration broken.
   * Pattern: ALWAYS fails — genuine regression.
   * Expected detector verdict: likely_real_bug | genuine_regression
   */
  await page.goto('https://example.com');
  expect('Payment Gateway Timeout — HTTP 500').toBe('Payment Success 200 OK');
});

test('cart_total_price_calculation_wrong', async ({ page }) => {
  /**
   * Simulates: pricing bug — cart total is incorrect after discount applied.
   * Pattern: ALWAYS fails — logic regression in pricing module.
   * Expected detector verdict: likely_real_bug | genuine_regression
   */
  await page.goto('https://example.com');
  const cartTotal = 110.50;  // Bug: discount of 10% not applied correctly
  const expectedTotal = 99.45; // Correct value after 10% discount
  expect(cartTotal).toBe(expectedTotal);
});

test('inventory_count_displays_negative_stock', async ({ page }) => {
  /**
   * Simulates: inventory bug — stock count goes negative after bulk order.
   * Pattern: ALWAYS fails — data integrity regression.
   * Expected detector verdict: likely_real_bug | genuine_regression
   */
  await page.goto('https://example.com');
  const stockCount = -5;  // Bug: overselling allowed
  expect(stockCount).toBeGreaterThanOrEqual(0);
});

// ============================================================================
// CATEGORY 5 — STABLE / ALWAYS PASSING (baseline)
// ============================================================================

test('homepage_loads_correctly @demo', async ({ page }) => {
  /**
   * Stable test — always passes. Used as a healthy baseline.
   * Expected detector verdict: stable (low flakiness score)
   */
  await page.goto('https://example.com');
  await expect(page).toHaveTitle(/Example Domain/);
});

test('example_domain_has_heading', async ({ page }) => {
  /**
   * Stable test — verifies page heading is present.
   * Expected detector verdict: stable (low flakiness score)
   */
  await page.goto('https://example.com');
  await expect(page.locator('h1')).toHaveText('Example Domain');
});

test('page_does_not_have_404_text', async ({ page }) => {
  /**
   * Stable test — verifies no 404 content on the page.
   * Expected detector verdict: stable (low flakiness score)
   */
  await page.goto('https://example.com');
  const bodyText = await page.locator('body').innerText();
  expect(bodyText).not.toContain('404');
});

// Original tests preserved below
// ---------------------------------------------------------------------------

test('demo_flaky_checkout_network_retry @demo', async ({ page }, testInfo) => {
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
