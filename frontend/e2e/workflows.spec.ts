import { expect, test } from '@playwright/test';
import { PASSWORD, signUp, uniqueEmail } from './helpers';

test('anonymous portfolio analysis, validation, and stress test', async ({ page }) => {
  await page.goto('/portfolio');
  const analyze = page.getByRole('button', { name: 'Analyze portfolio' });
  // Invalid weights block submission client-side.
  await page.getByLabel('Weight for SPY').fill('70');
  await expect(page.getByText(/Weights sum to 120\.00%/)).toBeVisible();
  await expect(analyze).toBeDisabled();
  await page.getByLabel('Weight for SPY').fill('50');
  await expect(analyze).toBeEnabled();
  await analyze.click();
  await expect(page.getByText('Holdings breakdown')).toBeVisible();
  const risk = page.locator('section', { hasText: 'Capital vs risk allocation' });
  await expect(risk.getByText('SPY', { exact: true })).toBeVisible();
  await expect(page.locator('table[aria-label="Correlation of daily returns"]')).toBeVisible();
  await page.getByRole('button', { name: 'Run stress test' }).click();
  await expect(page.getByText('COVID-19 crash', { exact: true })).toBeVisible();
  await expect(page.getByText(/Buy-and-hold replay/)).toBeVisible();
});

test('anonymous research is deterministic, cited, and inspectable', async ({ page }) => {
  await page.goto('/research?symbol=NVDA');
  await page.getByLabel(/Question/).fill('How volatile has NVDA been?');
  await page.getByRole('button', { name: 'Generate report' }).click();
  await expect(page.getByText('Deterministic agents')).toBeVisible();
  await expect(page.getByText(/claims verified/)).toBeVisible();
  // The answer comes first and cites computed volatility.
  await expect(page.getByText('Answer', { exact: true })).toBeVisible();
  const chip = page.locator('main button', { hasText: /^M\d+$/ }).first();
  const id = (await chip.textContent())!.trim();
  await chip.click();
  await expect(page.locator(`#evidence-${id}`)).toHaveClass(/border-accent/);
  await expect(page.getByText(/This report uses ARGUS synthetic fixture data/)).toBeVisible();
  await expect(page.getByText('Synthesized by')).toHaveCount(0);
});

test('signed-in workflow persists across reloads: watchlist, portfolio, documents, research, logout/login', async ({ page }) => {
  test.setTimeout(180_000);
  const email = uniqueEmail();
  await signUp(page, email);

  // Watchlist from the asset page; survives a reload.
  await page.goto('/asset?symbol=AAPL');
  await page.getByRole('button', { name: 'Watch' }).click();
  await expect(page.getByRole('button', { name: 'Watching' })).toBeVisible();
  await page.goto('/');
  await page.reload();
  await expect(page.locator('section', { hasText: 'Watchlist' }).getByRole('link', { name: /^AAPL/ })).toBeVisible();

  // Save a portfolio; it is listed after a reload.
  await page.goto('/portfolio');
  await page.getByLabel('Name').fill('E2E 50/30/20');
  await page.getByRole('button', { name: 'Save' }).click();
  await expect(page.getByText('Saved "E2E 50/30/20".')).toBeVisible();
  await page.reload();
  await expect(page.locator('section', { hasText: 'Saved portfolios' }).getByText('E2E 50/30/20')).toBeVisible();

  // Upload a document, search it (and get an explicit insufficient-evidence state).
  await page.goto('/documents');
  await page.getByLabel(/^File/).setInputFiles({
    name: 'nvda-10k-excerpt.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from(
      'Risk Factors. We depend on a small number of foundry partners in Taiwan; export controls on advanced chips ' +
        'could materially reduce data center revenue. Gross margin was 74.6 percent in fiscal 2026.',
    ),
  });
  await page.locator('#doc-symbol').fill('NVDA');
  await page.getByRole('button', { name: /Upload and index/ }).click();
  await expect(page.getByText(/Indexed ".*": 1 page\(s\)/)).toBeVisible();
  await expect(page.locator('section', { hasText: 'Library (1)' }).getByText('ready')).toBeVisible();
  const search = page.locator('section', { hasText: 'Search your documents' });
  await search.getByLabel('Search query').fill('foundry Taiwan export controls');
  await search.getByRole('button', { name: 'Search' }).click();
  await expect(search.getByText(/relevance/)).toBeVisible();
  await search.getByLabel('Search query').fill('cryptocurrency mining hashrate');
  await search.getByRole('button', { name: 'Search' }).click();
  await expect(search.getByText(/insufficient evidence/)).toBeVisible();

  // Research cites the document and is saved to history.
  await page.goto('/research?symbol=NVDA');
  await page.getByLabel(/Question/).fill('What supply chain risks does the company describe?');
  await page.getByRole('button', { name: 'Generate report' }).click();
  await expect(page).toHaveURL(/research\/?\?id=/);
  const docChip = page.locator('main button', { hasText: /^D\d+$/ }).first();
  await expect(docChip).toBeVisible();
  await docChip.click();
  const docId = (await docChip.textContent())!.trim();
  await expect(page.locator(`#evidence-${docId}`)).toContainText('third-party');
  // A claim resting only on the user's document is labelled "Reported", not "Fact".
  const docClaim = page.locator('main li').filter({ has: page.getByRole('button', { name: docId, exact: true }) }).first();
  await expect(docClaim.getByText('Reported', { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.locator('section', { hasText: 'History' }).getByText('NVDA').first()).toBeVisible();
  await expect(page.locator('main button', { hasText: /^D\d+$/ }).first()).toBeVisible();

  // Delete the document.
  await page.goto('/documents');
  page.once('dialog', (dialog) => dialog.accept());
  await page.getByRole('button', { name: /^Delete / }).click();
  await expect(page.getByText('Library (0)')).toBeVisible();

  // Sign out: workspace data is no longer accessible; sign in again: it is back.
  await page.getByRole('button', { name: email }).click();
  await page.getByRole('menuitem', { name: 'Sign out' }).click();
  await expect(page.getByRole('link', { name: 'Sign in' }).first()).toBeVisible();
  expect((await page.request.get('/api/portfolios')).status()).toBe(401);
  await page.goto('/login');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password').fill(PASSWORD);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.locator('section', { hasText: 'Watchlist' }).getByRole('link', { name: /^AAPL/ })).toBeVisible();
});

test('wrong password and duplicate signup show actionable errors', async ({ page }) => {
  const email = uniqueEmail('dup');
  await signUp(page, email);
  await page.context().clearCookies();
  await page.goto('/login');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password').fill('not-the-password');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.locator('form p[role="alert"]')).toHaveText('Incorrect email or password.');
  await page.getByRole('radio', { name: 'Create account' }).click();
  await page.getByLabel('Password').fill(PASSWORD);
  await page.getByRole('button', { name: 'Create account' }).click();
  await expect(page.locator('form p[role="alert"]')).toContainText('already exists');
});
