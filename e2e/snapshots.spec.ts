import { test, expect } from '@playwright/test';

test.describe('Visual snapshots', () => {
  test('home page matches snapshot', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'AlgoStrategySandbox' })).toBeVisible();
    await expect(page).toHaveScreenshot('home-page.png', { fullPage: true });
  });

  test('report page matches snapshot', async ({ page }) => {
    await page.goto('/report');
    await expect(
      page.getByRole('heading', { name: 'Lumibot + Alpaca Integration Report' }),
    ).toBeVisible();
    await expect(page).toHaveScreenshot('report-page.png', { fullPage: true });
  });
});
