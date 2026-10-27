import { test, expect } from '@playwright/test';
test.setTimeout(180000);

test('study studio landing has usable demos, pricing and responsive compositions', async ({ page }) => {
  await page.route('**/*', async route => {
    const url = new URL(route.request().url());
    if (url.origin === new URL(test.info().project.use.baseURL!).origin) return route.continue();
    return route.abort();
  });
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Big lectures.');
  await page.getByRole('tab', { name: 'Ask', exact: true }).click();
  await expect(page.getByRole('tabpanel')).toContainText('How should I break down this slide?');
  await page.getByRole('tab', { name: 'Recall', exact: true }).click();
  await page.getByRole('tabpanel').getByRole('button', { name: 'Reveal flashcard answer' }).click();
  await expect(page.getByRole('tabpanel')).toContainText('Retrieving an answer');
  await page.getByRole('tab', { name: 'Read', exact: true }).click();
  await page.getByRole('button', { name: 'Recalling an answer before checking notes' }).click();
  await expect(page.getByText('That’s the idea.')).toBeVisible();
  await page.getByRole('button', { name: 'Yearly', exact: true }).click();
  await expect(page.locator('#pricing')).toContainText('₦29,990');
  await page.getByRole('button', { name: 'Monthly', exact: true }).click();
  for (const width of [375, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 1000 });
    await page.evaluate(() => window.scrollTo(0, 0));
    await expect(page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'Sign in', exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: `.test-results-uploads/studio-landing-${width}.png`, fullPage: true });
  }
});
