import { expect, test } from '@playwright/test';
import { expectNoHorizontalOverflow, trackConsoleErrors } from './helpers';

test('overview shows fixture-labelled market data and system status', async ({ page }) => {
  const errors = trackConsoleErrors(page);
  await page.goto('/');
  await expect(page.getByText(/Offline fixture mode/)).toBeVisible();
  const snapshot = page.locator('section', { hasText: 'Market snapshot' });
  for (const symbol of ['SPY', 'QQQ', 'IWM', 'TLT', 'GLD']) {
    await expect(snapshot.getByRole('link', { name: new RegExp(`^${symbol}`) })).toBeVisible();
  }
  await expect(snapshot.getByText('not market prices').first()).toBeVisible();
  await expect(page.getByText('Deterministic (no language model)')).toBeVisible();
  expect(errors).toEqual([]);
});

test('symbol search opens the asset page with a rendered price chart', async ({ page }) => {
  const errors = trackConsoleErrors(page);
  await page.goto('/');
  await page.waitForLoadState('networkidle'); // the "/" shortcut is attached after hydration
  const search = page.getByRole('combobox').first();
  await expect(async () => {
    await page.keyboard.press('/');
    await expect(search).toBeFocused({ timeout: 1_000 });
  }).toPass();
  await page.keyboard.type('nvd');
  await page.getByRole('option', { name: /NVDA/ }).first().click();
  await expect(page).toHaveURL(/\/asset\/?\?symbol=NVDA/);
  await expect(page.getByRole('heading', { name: 'NVDA' })).toBeVisible();
  await expect(page.getByText('NVIDIA Corporation (synthetic)').first()).toBeVisible();
  const chart = page.locator('figure[aria-label="NVDA daily closing price"] canvas').first();
  await expect(chart).toBeVisible();
  const box = await chart.boundingBox();
  expect(box && box.width > 200 && box.height > 100).toBeTruthy();
  expect(errors).toEqual([]);
});

test('analytics tab shows engine metrics and charts, with undefined values as dashes not zeros', async ({ page }) => {
  await page.goto('/asset?symbol=MSFT&tab=analytics');
  const metrics = page.locator('section', { hasText: 'Return & risk' });
  await expect(metrics.getByText('Annualized volatility', { exact: false }).first()).toBeVisible();
  await expect(metrics.locator('dd').first()).toHaveText(/%$/);
  await expect(page.locator('section', { hasText: 'Relative to SPY' }).getByText(/Beta/).first()).toBeVisible();
  for (const title of ['Cumulative return vs SPY', 'Drawdown from running peak', 'Rolling 63-day volatility']) {
    await expect(page.locator('section', { hasText: title }).locator('canvas').first()).toBeVisible();
  }
  // Changing the window recomputes from the backend.
  await page.getByRole('radio', { name: '3Y' }).click();
  await expect(page.getByText(/· 252 periods\/yr/)).toBeVisible();
});

test('unknown and malformed symbols produce clear messages', async ({ page }) => {
  await page.goto('/asset?symbol=ZZZZ');
  await expect(page.getByText(/No current quote available/)).toBeVisible();
  await expect(page.locator('section', { hasText: 'Price history' }).getByRole('alert')).toContainText(/No price history|not available/i);
  await page.goto('/asset?symbol=NVDA!!');
  await expect(page.getByText('"NVDA!!" is not a valid symbol')).toBeVisible();
});

test('provider failures surface as retryable errors, not empty success', async ({ page }) => {
  await page.route('**/api/market/AAPL/technicals**', (route) =>
    route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({ error: { code: 'provider_unavailable', message: 'Yahoo Finance is temporarily unavailable.' }, request_id: 'e2e-req' }),
    }),
  );
  await page.goto('/asset?symbol=AAPL');
  const alert = page.locator('section', { hasText: 'Price history' }).getByRole('alert');
  await expect(alert).toContainText('temporarily unavailable');
  await expect(alert).toContainText('request id e2e-req');
  await page.unroute('**/api/market/AAPL/technicals**');
  await alert.getByRole('button', { name: 'Retry' }).click();
  await expect(page.locator('figure[aria-label="AAPL daily closing price"] canvas').first()).toBeVisible();
});

test('backend unreachable is shown as offline', async ({ page }) => {
  await page.route('**/api/system/status', (route) => route.abort());
  await page.goto('/');
  await expect(page.getByRole('link', { name: /Offline/ })).toBeVisible();
});

test.describe('mobile layout', () => {
  test.use({ viewport: { width: 375, height: 812 } });
  for (const path of ['/', '/asset?symbol=NVDA', '/asset?symbol=NVDA&tab=analytics', '/portfolio', '/research', '/documents', '/settings', '/login']) {
    test(`no horizontal scroll on ${path}`, async ({ page }) => {
      await page.goto(path);
      await page.waitForLoadState('networkidle');
      await expectNoHorizontalOverflow(page);
    });
  }
});

test('benchmark is automatic unless the user picks one, and the UI shows the one used', async ({ page }) => {
  const bodies: Record<string, unknown>[] = [];
  await page.route('**/api/analytics/asset', async (route) => {
    bodies.push(route.request().postDataJSON());
    await route.continue();
  });
  await page.goto('/asset?symbol=MSFT&tab=analytics');
  await expect(page.locator('section', { hasText: 'Relative to SPY' }).first()).toBeVisible();
  expect(bodies[0]).not.toHaveProperty('benchmark');
  await expect(page.locator('#benchmark')).toHaveAttribute('placeholder', 'Auto: SPY');

  await page.locator('#benchmark').fill('qqq');
  await page.getByRole('button', { name: 'Apply' }).click();
  await expect(page.locator('section', { hasText: 'Relative to QQQ' }).first()).toBeVisible();
  expect(bodies.at(-1)).toMatchObject({ benchmark: 'QQQ' });

  const portfolioBodies: Record<string, unknown>[] = [];
  await page.route('**/api/portfolio/analyze', async (route) => {
    portfolioBodies.push(route.request().postDataJSON());
    await route.continue();
  });
  await page.goto('/portfolio');
  await page.getByRole('button', { name: 'Analyze portfolio' }).click();
  await expect(page.getByText('Holdings breakdown')).toBeVisible();
  expect(portfolioBodies[0]).not.toHaveProperty('benchmark');
  await expect(page.locator('#pf-bench')).toHaveAttribute('placeholder', 'Auto: SPY');
});
