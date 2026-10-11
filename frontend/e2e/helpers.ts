import { expect, type Page } from '@playwright/test';

/** Console errors other than the expected 401 from /api/auth/me for anonymous visitors. */
export function trackConsoleErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on('console', (message) => {
    if (message.type() !== 'error') return;
    const text = message.text();
    if (/status of 401/.test(text)) return;
    errors.push(text);
  });
  page.on('pageerror', (error) => errors.push(`pageerror: ${error.message}`));
  page.on('response', (response) => {
    if (response.status() === 404 && !response.url().includes('/api/')) errors.push(`404 ${response.url()}`);
  });
  return errors;
}

export async function expectNoHorizontalOverflow(page: Page): Promise<void> {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow, 'page should not scroll horizontally').toBeLessThanOrEqual(1);
}

export function uniqueEmail(prefix = 'e2e'): string {
  return `${prefix}-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.test`;
}

export const PASSWORD = 'e2e-password-not-secret';

export async function signUp(page: Page, email: string): Promise<void> {
  await page.goto('/login');
  await page.getByRole('radio', { name: 'Create account' }).click();
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password').fill(PASSWORD);
  await page.getByRole('button', { name: 'Create account' }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole('button', { name: email })).toBeVisible();
}
