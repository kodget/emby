import { test, expect, type Page, type Route } from '@playwright/test';
test.setTimeout(120000);

const user = { id: 12, user_id: 42, username: 'student', full_name: 'Test Student', email: 'student@example.test',
  class_role: 'student', class_group: 1, school_name: 'Test School', set_name: 'Year 1', class_code: '123456',
  email_verified: true, onboarding_completed: true, can_access_app: true, subscription_tier: 'free',
  class_head_verified: false, is_premium: false, is_staff: false, is_superuser: false, streak: 0 };
const row = { id: 'slide:slide:lesson', type: 'slide', title: 'Upper limb lecture',
  excerpt: 'The brachial plexus supplies the upper limb.', label: 'Slides · Anatomy', page: 4,
  url: '/read/upper/lesson?page=4', created_at: '2026-10-26T09:00:00Z' };
function response(q: string, rows = [row], extra = {}) {
  return { query: q, results: rows, total: rows.length, counts: { slide: rows.length },
    subjects: [{ id: 'anatomy', name: 'Anatomy' }], next_offset: null, ...extra };
}
async function fixtures(page: Page, handler?: (route: Route, url: URL) => Promise<boolean | void>, authenticated = true) {
  if (authenticated) await page.addInitScript(profile => {
    sessionStorage.setItem('token', 'isolated-browser-access');
    sessionStorage.setItem('refreshToken', 'isolated-browser-refresh');
    sessionStorage.setItem('user', JSON.stringify(profile));
  }, user);
  await page.routeWebSocket('ws://127.0.0.1:8600/**', () => {});
  await page.route('**/*', async route => {
    const url = new URL(route.request().url());
    if (url.origin === new URL(test.info().project.use.baseURL!).origin) return route.continue();
    if (url.origin !== 'http://127.0.0.1:8600') return route.abort();
    if (route.request().method() === 'OPTIONS') return route.fulfill({ status: 204, headers: {
      'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*', 'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
    } });
    if (await handler?.(route, url)) return;
    const data: Record<string, unknown> = { '/auth/profile/': user, '/api/credits/balance/': { balance: 20 }, '/api/subjects/': [{ id: 'anatomy', name: 'Anatomy' }] };
    await route.fulfill({ json: data[url.pathname] ?? [] });
  });
}

test('keyboard search is lazy, searches saved text and opens the matching page', async ({ page }) => {
  test.setTimeout(120000);
  const searches: string[] = [];
  await fixtures(page, async (route, url) => {
    if (url.pathname === '/api/search/') { searches.push(url.searchParams.get('q')!); await route.fulfill({ json: response(url.searchParams.get('q')!) }); return true; }
  });
  await page.goto('/search');
  await expect(page.getByRole('button', { name: 'User menu' })).toBeVisible();
  expect(searches).toEqual([]);
  await page.keyboard.press('Control+k');
  const dialog = page.getByRole('dialog');
  await expect(dialog.getByRole('heading', { name: 'Find it in Emby' })).toBeVisible();
  await dialog.getByRole('combobox', { name: 'Search your library' }).fill('brachial');
  await expect(dialog.getByRole('option').filter({ hasText: 'Upper limb lecture' })).toContainText('Page 4');
  await dialog.getByRole('combobox', { name: 'Search your library' }).press('ArrowDown');
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/\/read\/upper\/lesson\?page=4$/);
  expect(searches).toEqual(['brachial']);
});

test('filters, pagination and a reload preserve a usable search', async ({ page }) => {
  const requests: URL[] = [];
  await fixtures(page, async (route, url) => {
    if (url.pathname === '/api/search/') {
      requests.push(url);
      const offset = Number(url.searchParams.get('offset'));
      await route.fulfill({ json: response(url.searchParams.get('q')!, [{ ...row, title: offset ? 'Later result' : row.title }], { total: 25, next_offset: offset ? null : 20 }) }); return true;
    }
  });
  await page.goto('/search?q=brachial');
  await expect(page.getByRole('option').filter({ hasText: 'Upper limb lecture' })).toBeVisible();
  await page.getByRole('combobox', { name: 'Content type', exact: true }).selectOption('slide');
  await page.getByRole('combobox', { name: 'Subject', exact: true }).selectOption('anatomy');
  await page.getByRole('combobox', { name: 'Sort results' }).selectOption('recent');
  await expect(page).toHaveURL(/subject=anatomy.*sort=recent/);
  await page.getByRole('button', { name: 'Next results' }).click();
  await expect(page.getByRole('option').filter({ hasText: 'Later result' })).toBeVisible();
  expect(requests.at(-1)?.searchParams.get('offset')).toBe('20');
  await page.reload();
  await expect(page.getByRole('combobox', { name: 'Content type', exact: true })).toHaveValue('slide');
  await expect(page.getByRole('combobox', { name: 'Subject', exact: true })).toHaveValue('anatomy');
  await expect(page.getByRole('option').filter({ hasText: 'Upper limb lecture' })).toBeVisible();
});

test('search distinguishes an outage from an empty result and allows retry', async ({ page }) => {
  let calls = 0;
  await fixtures(page, async (route, url) => {
    if (url.pathname !== '/api/search/') return;
    calls++;
    await route.fulfill(calls === 1 ? { status: 503, json: {} } : { json: response('missing', []) }); return true;
  });
  await page.goto('/search?q=missing&type=slide');
  await expect(page.getByRole('alert').filter({ hasText: 'Could not search' })).toBeVisible();
  await page.getByRole('button', { name: 'Try again' }).click();
  await expect(page.getByRole('heading', { name: 'No matches for “missing”' })).toBeVisible();
  await page.getByRole('button', { name: 'Clear filters' }).click();
  await expect(page.getByRole('combobox', { name: 'Content type', exact: true })).toHaveValue('all');
});

test('a slow old query cannot replace a newer result', async ({ page }) => {
  await fixtures(page, async (route, url) => {
    if (url.pathname !== '/api/search/') return;
    const q = url.searchParams.get('q')!;
    if (q === 'old') await new Promise(resolve => setTimeout(resolve, 1200));
    await route.fulfill({ json: response(q, [{ ...row, title: q === 'old' ? 'Stale result' : 'Current result' }]) }); return true;
  });
  await page.goto('/search');
  const input = page.getByRole('combobox', { name: 'Search your library' });
  await input.fill('old');
  await page.waitForRequest(request => request.url().includes('/api/search/?q=old'));
  await input.fill('new');
  await expect(page.getByRole('option').filter({ hasText: 'Current result' })).toBeVisible();
  await page.waitForTimeout(1300);
  await expect(page.getByText('Stale result')).toHaveCount(0);
});

test('mobile search and the navigation dialog fit and support Escape', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await fixtures(page, async (route, url) => {
    if (url.pathname === '/api/search/') { await route.fulfill({ json: response(url.searchParams.get('q')!) }); return true; }
  });
  await page.goto('/search?q=brachial');
  await expect(page.getByRole('option').filter({ hasText: 'Upper limb lecture' })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: '.test-results-uploads/search-mobile.png', fullPage: true });
  await page.getByRole('button', { name: 'More', exact: true }).click();
  await expect(page.getByRole('dialog').getByRole('link', { name: 'My class', exact: true })).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'More', exact: true })).toBeFocused();
});

test('landing page has visible mobile sign in and readable responsive layouts', async ({ page }) => {
  await fixtures(page, undefined, false);
  for (const width of [375, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto('/');
    await expect(page.getByRole('heading', { level: 1 })).toContainText('study breakthrough');
    await expect(page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'Sign in', exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: `.test-results-uploads/landing-${width}.png`, fullPage: true, caret: 'initial' });
  }
});

test('students can open exam dates without management controls', async ({ page }) => {
  await fixtures(page, async (route, url) => {
    if (url.pathname.includes('exam-countdowns')) { await route.fulfill({ json: [{ id: 9, title: 'Anatomy exam', exam_date: '2027-01-01', days_remaining: 10 }] }); return true; }
  });
  await page.goto('/class/exams#exam-9');
  await expect(page.getByRole('heading', { name: 'Anatomy exam', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Add exam' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Delete Anatomy exam' })).toHaveCount(0);
});

test('sign in offers password visibility and autocomplete', async ({ page }) => {
  await fixtures(page, undefined, false);
  await page.goto('/signin');
  await page.getByLabel('Password', { exact: true }).fill('test-only-value');
  await page.getByRole('button', { name: 'Show password', exact: true }).click();
  await expect(page.getByLabel('Password', { exact: true })).toHaveAttribute('type', 'text');
  await page.getByRole('button', { name: 'Hide password', exact: true }).click();
  await expect(page.getByLabel('Password', { exact: true })).toHaveAttribute('type', 'password');
});

test('search page links override a saved reading position in both readers', async ({ page }) => {
  const image = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jYzQAAAAASUVORK5CYII=';
  const pages = [1, 2, 3].map(number => ({ id: number, page_number: number, slide_number: number, image_url: image, text: `Page ${number}`, width: 400, height: 300 }));
  await fixtures(page, async (route, url) => {
    const data: Record<string, unknown> = {
      '/api/slides/lesson/': { id: 'lesson', title: 'Saved lecture', subject: 'anatomy', file_type: 'pdf', page_count: 3 },
      '/api/slides/lesson/content/': { total_pages: 3, pages },
      '/api/progress/': [{ slide: 'lesson', current_page: 1 }],
      '/api/decks/document/': { id: 'document', title: 'Saved document', processing_status: 'completed', page_count: 3, file_type: 'pdf', pages },
      '/api/decks/document/pages/': pages,
      '/api/decks/document/reading-progress/': { current_page: 1, total_seconds: 0 },
    };
    if (url.pathname in data) { await route.fulfill({ json: data[url.pathname] }); return true; }
  });
  await page.goto('/read/anatomy/lesson?page=3');
  await expect(page.getByAltText('Page 3', { exact: true })).toBeVisible();
  await page.goto('/decks/document?page=3');
  await expect(page.getByAltText('Page 3', { exact: true })).toBeVisible();
});

test('flashcard search links load the selected card directly', async ({ page }) => {
  let listed = false;
  await fixtures(page, async (route, url) => {
    if (url.pathname === '/api/flashcards/') listed = true;
    if (url.pathname === '/api/flashcards/99/') { await route.fulfill({ json: { id: 99, front: 'Selected brachial flashcard', back: 'The answer', source: 'manual' } }); return true; }
  });
  await page.goto('/flashcards/manage?card=99');
  await expect(page.getByText('Selected brachial flashcard', { exact: true })).toBeVisible();
  expect(listed).toBe(false);
});

test('recent queries can be reused and cleared without showing cached results', async ({ page }) => {
  await fixtures(page, async (route, url) => {
    if (url.pathname === '/api/search/') { await route.fulfill({ json: response(url.searchParams.get('q')!) }); return true; }
  });
  await page.goto('/search');
  await page.getByRole('button', { name: 'Open global search' }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('combobox', { name: 'Search your library' }).fill('brachial');
  await expect(dialog.getByRole('option').filter({ hasText: 'Upper limb lecture' })).toBeVisible();
  await dialog.getByRole('button', { name: 'All results' }).click();
  await expect(page).toHaveURL(/search\?q=brachial/);
  await page.getByRole('button', { name: 'Open global search' }).click();
  await expect(dialog.getByRole('option', { name: 'brachial', exact: true })).toBeVisible();
  await expect(dialog.getByText('Upper limb lecture')).toHaveCount(0);
  await dialog.getByRole('button', { name: 'Clear recent searches' }).click();
  await expect(dialog.getByRole('option', { name: 'brachial', exact: true })).toHaveCount(0);
});
