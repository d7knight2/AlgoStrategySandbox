import { test, expect } from '@playwright/test';

test.describe('Visual snapshots', () => {
  test('home page header matches snapshot', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'AlgoStrategySandbox' })).toBeVisible();
    await expect(page.locator('header')).toHaveScreenshot('home-header.png');
  });

  test('report page header matches snapshot', async ({ page }) => {
    await page.goto('/report');
    await expect(
      page.getByRole('heading', { name: 'Lumibot + Alpaca Integration Report' }),
    ).toBeVisible();
    await expect(page.locator('header')).toHaveScreenshot('report-header.png');
  });
});
