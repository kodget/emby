const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const test = require('node:test');
const ts = require('typescript');
const context = { exports: {} };
vm.runInNewContext(ts.transpileModule(fs.readFileSync('lib/reading-recorder.ts', 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText, context);
const { ReadingRecorder } = context.exports;
const settle = () => new Promise(resolve => setImmediate(resolve));

function fixture({ pending = [], send, maxPage } = {}) {
  let now = 0, serial = 0, active = true, stored = [];
  const requests = [], errors = [], rejected = [];
  const recorder = new ReadingRecorder({ page: 1, pending, maxPage,
    now: () => now, id: () => `request-${++serial}`, active: () => active,
    send: async data => { requests.push({ ...data }); await send?.(data); },
    persist: queue => { stored = JSON.parse(JSON.stringify(queue)); },
    unavailable: error => error?.code === 'reading_page_unavailable',
    status: (error, checkpoint) => { errors.push(error); rejected.push(checkpoint); },
  });
  return { recorder, requests, errors, rejected, advance: ms => { now += ms; recorder.tick(); },
    stored: () => stored, revoke: () => { active = false; } };
}

test('only visible loaded intervals count, including short visits and fractions', async () => {
  const f = fixture();
  f.advance(20000); // Loading, not reading.
  f.recorder.visible(true);
  f.advance(400);
  f.recorder.turn(2);
  f.advance(700);
  f.recorder.visible(false);
  f.advance(50000);
  f.recorder.visible(true);
  f.advance(1000);
  f.recorder.checkpoint();
  await settle();
  assert.equal(f.requests.reduce((n, row) => n + row.seconds, 0), 2);
  assert.equal(f.requests.at(-1).current_page, 2);
});

test('suspended timers cannot turn computer sleep into hours of reading', async () => {
  const f = fixture(); f.recorder.visible(true);
  f.advance(3600000); f.recorder.checkpoint();
  await settle();
  assert.equal(f.requests[0].seconds, 2);
});

test('failed saves keep the exact payload through retry and reload', async () => {
  let fail = true;
  const f = fixture({ send: () => { if (fail) throw new Error('offline'); } });
  f.recorder.visible(true); f.advance(1000); f.recorder.checkpoint();
  await settle();
  assert.equal(f.errors.at(-1), true);
  assert.equal(f.stored().length, 1);
  f.recorder.turn(3);
  await settle();
  assert.equal(f.requests.length, 1);
  const reloaded = fixture({ pending: f.stored() });
  assert.equal(reloaded.recorder.page, 3);
  reloaded.recorder.retry(); await settle();
  assert.deepEqual(reloaded.requests[0], f.requests[0]);
  assert.equal(reloaded.requests[1].current_page, 3);
  assert.deepEqual(reloaded.stored(), []);
});

test('page checkpoints wait behind an earlier save and cannot overtake it', async () => {
  let release;
  const first = new Promise(resolve => { release = resolve; });
  let count = 0;
  const f = fixture({ send: () => ++count === 1 ? first : undefined });
  f.recorder.turn(2); f.recorder.turn(3);
  await settle();
  assert.equal(f.requests.length, 1);
  release(); await settle();
  assert.deepEqual(f.requests.map(row => row.current_page), [2, 3]);
});

test('changing account or losing class access stops queued writes and time', async () => {
  const f = fixture({ send: () => { throw new Error('offline'); } });
  f.recorder.turn(2); await settle();
  f.revoke(); f.recorder.retry(); f.recorder.visible(true); f.advance(1000); f.recorder.checkpoint();
  await settle();
  assert.equal(f.requests.length, 1);
  assert.equal(f.recorder.queue.length, 1);
});

test('a removed queued page clamps display without relabelling time, and only explicit discard unblocks later saves', async () => {
  const pending = [{ current_page: 99, seconds: 17, request_id: 'removed' }];
  const f = fixture({ pending, maxPage: 3, send: data => {
    if (data.current_page === 99) throw { code: 'reading_page_unavailable' };
  } });
  assert.equal(f.recorder.page, 3);
  f.recorder.retry(); await settle();
  assert.deepEqual(f.requests[0], { current_page: 99, seconds: 17, request_id: 'removed' });
  f.recorder.turn(2); await settle();
  assert.equal(f.requests.length, 1);
  assert.equal(f.rejected.at(-1).seconds, 17);
  f.recorder.discardUnavailable(); await settle();
  assert.deepEqual(f.requests[1], { current_page: 2, seconds: 0, request_id: 'request-1' });
  assert.deepEqual(f.stored(), []);
  assert.equal(f.errors.at(-1), false);
});

test('ordinary failures cannot be discarded and a removed page may recover through exact retry', async () => {
  let code = 'offline';
  const f = fixture({ send: () => { if (code) throw { code }; } });
  f.recorder.turn(2); await settle();
  f.recorder.discardUnavailable(); await settle();
  assert.equal(f.recorder.queue.length, 1);
  code = 'reading_page_unavailable'; f.recorder.retry(); await settle();
  const rejected = f.requests.at(-1);
  code = ''; f.recorder.retry(); await settle();
  assert.deepEqual(f.requests.at(-1), rejected);
  assert.equal(f.recorder.queue.length, 0);
  assert.equal(f.rejected.at(-1), undefined);
});

test('discard cannot skip an in-flight retry, another rejected page, or another account', async () => {
  let release, hold = false;
  const f = fixture({ pending: [{ current_page: 8, seconds: 10, request_id: 'first' },
    { current_page: 9, seconds: 20, request_id: 'second' }], send: async () => {
      if (hold) await new Promise(resolve => { release = resolve; });
      throw { code: 'reading_page_unavailable' };
    } });
  f.recorder.retry(); await settle();
  hold = true; f.recorder.retry(); await settle();
  f.recorder.discardUnavailable();
  assert.equal(f.recorder.queue.length, 2);
  hold = false; release(); await settle();
  f.recorder.discardUnavailable(); f.recorder.discardUnavailable(); await settle();
  assert.equal(f.recorder.queue.length, 1);
  assert.equal(f.rejected.at(-1).request_id, 'second');
  f.revoke(); f.recorder.discardUnavailable();
  assert.equal(f.recorder.queue.length, 1);
});
