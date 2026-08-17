import { test, expect } from '@playwright/test';

test.describe('Page snapshots', () => {
  test('home page header matches aria snapshot', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'AlgoStrategySandbox' })).toBeVisible();
    await expect(page.locator('header')).toMatchAriaSnapshot();
  });

  test('report page header matches aria snapshot', async ({ page }) => {
    await page.goto('/report');
    await expect(
      page.getByRole('heading', { name: 'Lumibot + Alpaca Integration Report' }),
    ).toBeVisible();
    await expect(page.locator('header')).toMatchAriaSnapshot();
  });
});
