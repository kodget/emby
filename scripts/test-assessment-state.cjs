const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const test = require('node:test');
const ts = require('typescript');

function setup() {
  let now = 100000;
  class Clock extends Date { static now() { return now; } }
  const code = ts.transpileModule(fs.readFileSync(path.join(__dirname, '../store/quiz-attempt-slice.ts'), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true },
  }).outputText;
  const module = { exports: {} };
  vm.runInNewContext(code, { module, exports: module.exports, Date: Clock,
    require: name => name === '@/lib/api' ? {} : require(name) });
  const api = module.exports;
  const attempt = { id: 'mock-1', status: 'in_progress', is_timed: true, time_remaining_seconds: 100,
    questions: [{ id: 'written', question_type: 'theory' }],
    responses: [{ question: { id: 'written' }, text_answer: 'Saved draft' }] };
  let state = api.default(undefined, api.loadAttempt.pending('load-1', attempt.id));
  state = api.default(state, api.loadAttempt.fulfilled(attempt, 'load-1', attempt.id));
  return { api, state, advance: ms => { now += ms; } };
}

test('timer uses elapsed time after background suspension', () => {
  const { api, state, advance } = setup();
  advance(65000);
  const ticked = api.default(state, api.tickTimer());
  assert.equal(ticked.timeRemainingSeconds, 35);
  advance(40000);
  assert.equal(api.default(ticked, api.tickTimer()).timeRemainingSeconds, 0);
});

test('old save response cannot overwrite a newer written draft', () => {
  const { api, state } = setup();
  const changed = api.default(state, api.setTheoryAnswer({ questionId: 'written', text: 'New draft' }));
  const saved = api.default(changed, api.saveAnswer.fulfilled({ question_id: 'written', text_answer: 'Saved draft' }, 'save-1', { attemptId: 'mock-1' }));
  assert.equal(saved.answers.written.text_answer, 'New draft');
  const cleared = api.default(saved, api.setTheoryAnswer({ questionId: 'written', text: '' }));
  assert.equal(cleared.questionStatuses.written, 'unanswered');
  const savedEmpty = api.default(cleared, api.saveAnswer.fulfilled({ question_id: 'written', text_answer: '' }, 'save-2', { attemptId: 'mock-1' }));
  assert.equal(savedEmpty.questionStatuses.written, 'unanswered');
});

test('failed automatic submission is visible and retryable', () => {
  const { api, state } = setup();
  const pending = api.default(state, api.autoSubmitAttempt.pending('submit-1', 'mock-1'));
  assert.equal(pending.submitting, true);
  const failed = api.default(pending, api.autoSubmitAttempt.rejected(null, 'submit-1', 'mock-1', 'Server unavailable'));
  assert.equal(failed.submitting, false);
  assert.equal(failed.isSubmitted, false);
  assert.equal(failed.error, 'Server unavailable');
});
