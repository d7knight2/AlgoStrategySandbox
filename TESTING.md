# Branch Protection and Testing Documentation

## Overview

This document describes the testing infrastructure and branch protection rules configured for the AlgoStrategySandbox repository to ensure code quality and stability.

## Test Infrastructure

### Unit Tests (Jest)

Unit tests are configured using Jest and React Testing Library to test individual components and functions.

**Running unit tests:**
```bash
# Run all unit tests
npm test

# Run tests in watch mode
npm run test:watch

# Generate coverage report
npm run test:coverage
```

**Test files location:**
- Unit tests are located in `src/__tests__/`
- Test files follow the pattern `*.test.ts` or `*.test.tsx`

**Configuration files:**
- `jest.config.js` - Jest configuration
- `jest.setup.js` - Jest setup file for testing library

### UI Tests (Playwright)

UI tests are configured using Playwright to test the application's user interface and user interactions.

**Running UI tests:**
```bash
# Run all Playwright tests
npm run test:ui

# Run tests in headed mode (see browser)
npm run test:ui:headed

# View test report
npm run test:ui:report
```

**Test files location:**
- UI tests are located in `e2e/`
- Test files follow the pattern `*.spec.ts`

**Configuration file:**
- `playwright.config.ts` - Playwright configuration

## GitHub Actions Workflows

### Unit Tests Workflow

**File:** `.github/workflows/unit-tests.yml`

This workflow runs automatically on:
- Pull requests to any branch
- Pushes to the `main` branch

**Steps:**
1. Checkout code
2. Setup Node.js environment
3. Install dependencies
4. Run unit tests
5. Generate and upload coverage report

### UI Tests Workflow

**File:** `.github/workflows/ui-tests.yml`

This workflow runs automatically on:
- Pull requests to any branch
- Pushes to the `main` branch

**Steps:**
1. Checkout code
2. Setup Node.js environment
3. Install dependencies
4. Install Playwright browsers
5. Build and start the application
6. Run Playwright tests
7. Upload test report

## Branch Protection Rules

To enforce these quality checks and prevent merging untested code, configure the following branch protection rules for the `main` branch:

### Required Steps

1. Navigate to your repository on GitHub
2. Go to **Settings** → **Branches**
3. Click **Add branch protection rule**
4. Configure the following settings:

#### Branch Name Pattern
```
main
```

#### Protection Settings

**Require a pull request before merging**
- ✅ Enable this option
- Optionally: Require approvals (recommended: at least 1)

**Require status checks to pass before merging**
- ✅ Enable this option
- ✅ Require branches to be up to date before merging
- Add the following required status checks:
  - `Run Unit Tests`
  - `Run UI Tests`

**Do not allow bypassing the above settings**
- ✅ Enable this option (recommended for strict enforcement)

### Visual Guide

```
Settings → Branches → Add branch protection rule

┌─────────────────────────────────────────────────────────┐
│ Branch name pattern: main                               │
├─────────────────────────────────────────────────────────┤
│ ☑ Require a pull request before merging                │
│   ☐ Require approvals: 1                               │
│                                                          │
│ ☑ Require status checks to pass before merging         │
│   ☑ Require branches to be up to date                  │
│   Search for status checks:                             │
│   ☑ Run Unit Tests                                      │
│   ☑ Run UI Tests                                        │
│                                                          │
│ ☑ Do not allow bypassing the above settings            │
└─────────────────────────────────────────────────────────┘
```

## Benefits

With this configuration in place:

1. **Quality Assurance**: All code must pass unit and UI tests before merging
2. **Stability**: Prevents broken code from reaching the main branch
3. **Confidence**: Developers can merge with confidence knowing tests have passed
4. **Automation**: Tests run automatically on every PR and push
5. **Visibility**: Test results are visible directly in the PR interface

## Adding New Tests

### Adding a Unit Test

1. Create a new test file in `src/__tests__/` directory
2. Import the component or function to test
3. Write test cases using Jest and React Testing Library
4. Run `npm test` to verify

Example:
```typescript
import { render, screen } from '@testing-library/react';
import MyComponent from '@/components/MyComponent';

describe('MyComponent', () => {
  it('should render correctly', () => {
    render(<MyComponent />);
    expect(screen.getByText('Hello World')).toBeInTheDocument();
  });
});
```

### Adding a UI Test

1. Create a new test file in `e2e/` directory
2. Import Playwright test utilities
3. Write test scenarios using Playwright API
4. Run `npm run test:ui` to verify

Example:
```typescript
import { test, expect } from '@playwright/test';

test('should navigate to portfolio page', async ({ page }) => {
  await page.goto('/');
  await page.click('text=Go to Portfolios');
  await expect(page).toHaveURL('/portfolios');
});
```

## Troubleshooting

### Tests fail locally but pass in CI

- Ensure you have the latest dependencies: `npm install`
- Clear test cache: `npx jest --clearCache`
- Check Node.js version matches CI (18.x)

### Playwright tests fail

- Install browser dependencies: `npx playwright install --with-deps`
- Check if the development server is running
- Increase timeout if tests are timing out

### Workflow approval required

- First-time workflow runs may require approval
- Repository admins can approve workflows in the Actions tab
- After first approval, subsequent runs will be automatic

## Contact

For questions or issues related to the testing infrastructure, please open an issue on GitHub.
