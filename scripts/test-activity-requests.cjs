const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const { webcrypto } = require('node:crypto');
const ts = require('typescript');
const axios = require('axios');

const compiled = ts.transpileModule(fs.readFileSync(path.join(__dirname, '../lib/api.ts'), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true },
}).outputText;

function client({ expired = false } = {}) {
  const requests = [];
  const storage = new Map([['token', 'old'], ['refreshToken', 'refresh'], ['user', 'student']]);
  let refreshed = 0;
  const events = [];
  const adapter = async config => {
    requests.push({ data: config.data ? JSON.parse(config.data) : null, url: config.url });
    if (expired && requests.length === 1) {
      throw new axios.AxiosError('Expired', 'ERR_BAD_REQUEST', config, {}, { status: 401, config });
    }
    return { status: 200, data: {}, headers: {}, config };
  };
  const dependencies = {
    create: options => axios.create({ ...options, adapter }),
    isAxiosError: axios.isAxiosError,
    post: async url => {
      assert.equal(url, 'http://127.0.0.1:8000/auth/token/refresh/');
      refreshed++;
      return { data: { access: 'new-access' } };
    },
  };
  const context = { exports: {}, process: { env: {} }, crypto: webcrypto,
    Event,
    window: { location: { href: '/read/test' }, dispatchEvent: event => events.push(event.type) },
    sessionStorage: { getItem: key => storage.get(key) ?? null,
      setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key) },
    require: name => { assert.equal(name, 'axios'); return dependencies; },
  };
  vm.runInNewContext(compiled, context);
  return { api: context.exports.progressApi, deck: context.exports.deckApi, practice: context.exports.practiceApi, schedule: context.exports.scheduleApi, requests, events, refreshCount: () => refreshed };
}

test('reading time keeps the same request identifier through a real Axios 401 replay', async () => {
  const fixture = client({ expired: true });
  await fixture.api.updateProgress({ slide_id: 'lecture', current_page: 2, total_pages: 3, time_spent_minutes: 1 });
  assert.equal(fixture.refreshCount(), 1);
  assert.equal(fixture.requests.length, 2);
  assert.deepEqual(fixture.requests[0], fixture.requests[1]);
  assert.match(fixture.requests[0].data.request_id, /^[a-f0-9-]{36}$/);
});

test('manual logs retain a supplied retry identifier while distinct logs get different identifiers', async () => {
  const fixture = client();
  const request_id = webcrypto.randomUUID();
  await fixture.api.logStudyTime({ minutes: 10, date: '2026-10-20', request_id });
  await fixture.api.logStudyTime({ minutes: 10, date: '2026-10-20', request_id });
  assert.deepEqual(fixture.requests[0].data, fixture.requests[1].data);
  assert.equal(fixture.requests[0].data.request_id, request_id);
  await fixture.api.logStudyTime({ minutes: 10 });
  await fixture.api.logStudyTime({ minutes: 10 });
  assert.notEqual(fixture.requests[2].data.request_id, fixture.requests[3].data.request_id);
});

test('image-practice completion refreshes visible progress after an authentication replay', async () => {
  const fixture = client({ expired: true });
  await fixture.practice.complete('image-round');
  assert.equal(fixture.refreshCount(), 1);
  assert.ok(fixture.events.includes('emby:progress-changed'));
  assert.equal(fixture.requests[1].url, '/api/learning/practice/image-round/complete/');
});

test('planner completion refreshes visible progress after the save succeeds', async () => {
  const fixture = client();
  await fixture.schedule.completeScheduleItem(7);
  assert.deepEqual(fixture.events, ['emby:progress-changed']);
});

test('standalone reading retains its checkpoint through authentication replay and refreshes progress', async () => {
  const fixture = client({ expired: true });
  const body = { current_page: 3, seconds: 15, request_id: webcrypto.randomUUID() };
  await fixture.deck.saveReadingProgress('reader', body);
  assert.deepEqual(fixture.requests.map(row => row.data), [body, body]);
  assert.ok(fixture.events.includes('emby:progress-changed'));
});


test('course seconds retain the supplied checkpoint through authentication replay', async () => {
  const fixture = client({ expired: true });
  const body = { slide_id: 'lecture', current_page: 2, seconds: 17, request_id: webcrypto.randomUUID() };
  await fixture.api.updateProgress(body);
  assert.deepEqual(fixture.requests.map(row => row.data), [body, body]);
  assert.ok(fixture.events.includes('emby:progress-changed'));
});
