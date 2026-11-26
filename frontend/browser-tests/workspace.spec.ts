import { test, expect, type Page } from '@playwright/test';
// These tests use a running real backend. No successful research/draft is mocked.
// Use a disposable local database and a worker for the live-failure case.
async function signIn(page: Page) {
    await page.goto('/');
    await page.getByLabel('Workspace access code').fill(process.env.SIGNALFLOW_TEST_ACCESS_CODE || 'signalflow-local');
    await page.getByRole('button', { name: 'Open workspace' }).click();
    await expect(page.getByRole('heading', { name: 'Research overview.' })).toBeVisible();
}
async function submit(page: Page) {
    await page.goto('/research/new');
    await page.getByLabel('Prospect name', { exact: true }).fill('Satya Nadella');
    await page.getByLabel('Job title / designation').fill('CEO');
    await page.getByLabel('Company', { exact: true }).fill('Microsoft');
    await page.getByLabel('Company website').fill('https://microsoft.com');
    await page.getByLabel('Product or service').fill('Cloud cost analytics');
    await page.getByLabel('Value proposition').fill('Help finance teams understand cloud spending.');
    await page.getByRole('button', { name: 'Start research', exact: true }).click();
    await expect(page).toHaveURL(/\/runs\/.+/);
}
test('login rejects an invalid code and retains authentication after reload', async ({ page, context }) => {
    // Do not retain auth traces: login request bodies contain the access code.
    await context.tracing.stop();
    await page.goto('/');
    const invalidResponse = page.waitForResponse(response => response.url().endsWith('/api/v1/session') && response.request().method() === 'POST');
    await page.getByLabel('Workspace access code').fill('invalid-test-code-' + Date.now());
    await page.getByRole('button', { name: 'Open workspace' }).click();
    expect((await invalidResponse).status()).toBe(401);
    await expect(page.getByRole('alert')).toContainText('Invalid access code');
    expect((await context.cookies()).some(cookie => cookie.name === 'signalflow_session')).toBe(false);
    await page.getByLabel('Workspace access code').fill(process.env.SIGNALFLOW_TEST_ACCESS_CODE || 'signalflow-local');
    await page.getByRole('button', { name: 'Open workspace' }).click();
    await expect(page.getByRole('heading', { name: 'Research overview.' })).toBeVisible();
    const cookie = (await context.cookies()).find(cookie => cookie.name === 'signalflow_session');
    // Check attributes individually: never put the secret cookie value in assertions.
    expect(cookie?.httpOnly).toBe(true);
    expect(cookie?.sameSite).toBe('Strict');
    expect(cookie?.path).toBe('/');
    expect(cookie?.secure).toBe(new URL(page.url()).protocol === 'https:');
    const response = await page.request.get('/api/v1/runs?limit=1');
    expect(response.status()).toBe(200);
    await page.reload();
    await expect(page.getByRole('heading', { name: 'Research overview.' })).toBeVisible();
    await page.goto('/runs');
    await expect(page.getByRole('heading', { name: 'Research history.' })).toBeVisible();
});
test('empty dashboard, navigation and mobile layout', async ({ page }) => {
    await signIn(page);
    await expect(page.getByText('Your first signal starts here')).toBeVisible();
    await page.screenshot({ path: 'test-results/empty-dashboard.png', fullPage: true });
    await page.getByRole('link', { name: 'New research', exact: true }).first().click();
    await expect(page.getByLabel('Prospect name', { exact: true })).toBeVisible();
    await page.setViewportSize({ width: 390, height: 844 });
    await expect(page.getByLabel('Open navigation')).toBeVisible();
    await page.getByLabel('Open navigation').click();
    await page.getByRole('link', { name: 'Research history', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Research history.' })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
    await page.screenshot({ path: 'test-results/mobile-history.png', fullPage: true });
});
test('real failed research retains zero sources/drafts and can reopen', async ({ page }) => {
    test.skip(process.env.SIGNALFLOW_TEST_EXPECT_FAILURE !== '1', 'Requires a backend/provider configured to produce a real failure.');
    test.setTimeout(240000);
    await signIn(page);
    await submit(page);
    const url = page.url();
    await expect(page.getByText('Research couldn’t be completed')).toBeVisible({ timeout: 200000 });
    await expect(page.getByText(/Backend reason:/)).toBeVisible();
    await page.getByRole('tab', { name: /Evidence/ }).click();
    await expect(page.getByText('No evidence retained')).toBeVisible();
    await page.getByRole('tab', { name: /Outreach draft/ }).click();
    await expect(page.getByText('No draft generated')).toBeVisible();
    await page.getByRole('tab', { name: /Execution log/ }).click();
    await expect(page.getByText('Provider requests & retries')).toBeVisible();
    await page.screenshot({ path: 'test-results/real-failed-run.png', fullPage: true });
    await page.goto('/runs');
    await page.getByRole('link', { name: 'Satya Nadella', exact: false }).first().click();
    expect(page.url()).toBe(url);
});
test('API unavailable does not invent empty metrics', async ({ page }) => {
    await signIn(page);
    await page.route('**/api/v1/**', route => route.abort('failed'));
    await page.reload();
    await expect(page.getByRole('alert')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Try again' })).toBeVisible();
    await expect(page.getByText('Your first signal starts here')).not.toBeVisible();
});
test('SSE interruption is separate from research status', async ({ page }) => {
    test.skip(process.env.SIGNALFLOW_TEST_WORKER_PAUSED !== '1', 'Requires a paused worker to observe a persisted queued run during transport loss.');
    await signIn(page);
    await page.route('**/api/v1/runs/*/events?*', route => route.abort('failed'));
    await submit(page);
    await expect(page.getByText(/Live connection interrupted/).first()).toBeVisible();
    await page.getByRole('tab', { name: /Execution log/ }).click();
    await expect(page.getByText('Browser connection log')).toBeVisible();
    await page.screenshot({ path: 'test-results/sse-interrupted.png', fullPage: true });
});
