const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const test = require('node:test');
const ts = require('typescript');
const crypto = require('node:crypto');
const context = { exports: {}, crypto, sessionStorage: { getItem: () => '{"user_id":42,"class_group":1}' } };
vm.runInNewContext(ts.transpileModule(fs.readFileSync('lib/upload-intent.ts', 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText, context);
const { uploadIntent, uploadOwner } = context.exports;

test('an identical retry keeps its request ID but a new file or metadata changes it', () => {
  const file = {};
  const first = uploadIntent(null, file, 'original');
  assert.equal(uploadIntent(first, file, 'original'), first);
  assert.notEqual(uploadIntent(first, {}, 'original').requestId, first.requestId);
  assert.notEqual(uploadIntent(first, file, 'edited').requestId, first.requestId);
});

test('a changed account or class is a new upload intent', () => {
  const file = {};
  const first = uploadIntent(null, file, uploadOwner());
  context.sessionStorage.getItem = () => '{"user_id":42,"class_group":2}';
  assert.notEqual(uploadIntent(first, file, uploadOwner()).requestId, first.requestId);
  context.sessionStorage.getItem = () => '{"user_id":43,"class_group":1}';
  assert.notEqual(uploadIntent(first, file, uploadOwner()).requestId, first.requestId);
});
