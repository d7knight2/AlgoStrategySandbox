import { test, expect } from '@playwright/test';

test.describe('Home Page', () => {
  test('should load and display the main heading', async ({ page }) => {
    await page.goto('/');
    
    // Check page title
    await expect(page).toHaveTitle(/AlgoStrategySandbox/);
    
    // Check main heading
    const mainHeading = page.getByRole('heading', { name: 'AlgoStrategySandbox' });
    await expect(mainHeading).toBeVisible();
  });

  test('should display subtitle and hero text', async ({ page }) => {
    await page.goto('/');
    
    // Check subtitle
    await expect(page.getByText('QuantConnect Integration Starter Site')).toBeVisible();
    
    // Check hero title
    await expect(page.getByRole('heading', { name: 'Build and Manage Stock Portfolios' })).toBeVisible();
  });

  test('should display all feature cards', async ({ page }) => {
    await page.goto('/');
    
    // Check all feature cards are visible
    await expect(page.getByRole('heading', { name: '📊 Portfolio Management' })).toBeVisible();
    await expect(page.getByRole('heading', { name: '📈 Paper Trading' })).toBeVisible();
    await expect(page.getByRole('heading', { name: '💰 Live Trading' })).toBeVisible();
    await expect(page.getByRole('heading', { name: '🔍 Stock Search' })).toBeVisible();
  });

  test('should have a link to portfolios page', async ({ page }) => {
    await page.goto('/');
    
    const portfoliosLink = page.getByRole('link', { name: 'Go to Portfolios' });
    await expect(portfoliosLink).toBeVisible();
    await expect(portfoliosLink).toHaveAttribute('href', '/portfolios');
  });

  test('should display getting started section', async ({ page }) => {
    await page.goto('/');
    
    await expect(page.getByRole('heading', { name: 'Getting Started' })).toBeVisible();
    
    // Check list items
    await expect(page.getByText('Sign up for a')).toBeVisible();
    await expect(page.getByText('Get your API credentials')).toBeVisible();
    await expect(page.getByText('Configure your')).toBeVisible();
    await expect(page.getByText('Start creating and managing')).toBeVisible();
  });

  test('should display footer', async ({ page }) => {
    await page.goto('/');
    
    await expect(page.getByText('Built with Next.js and QuantConnect API')).toBeVisible();
  });

  test('should have a link to QuantConnect', async ({ page }) => {
    await page.goto('/');
    
    const qcLink = page.getByRole('link', { name: 'QuantConnect account' });
    await expect(qcLink).toBeVisible();
    await expect(qcLink).toHaveAttribute('href', 'https://www.quantconnect.com/');
    await expect(qcLink).toHaveAttribute('target', '_blank');
  });
});
