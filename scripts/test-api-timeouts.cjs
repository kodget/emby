const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");
const ts = require("typescript");

const source = fs.readFileSync(path.join(__dirname, "../lib/api.ts"), "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2020,
    esModuleInterop: true,
  },
}).outputText;

test("slide chat requests allow the backend LLM call to finish", async () => {
  const calls = [];
  const api = {
    interceptors: {
      request: { use: () => {} },
      response: { use: () => {} },
    },
    post: (...args) => {
      calls.push(args);
      return Promise.resolve({ data: { response: "Answer" } });
    },
  };
  const axios = {
    create: () => api,
  };
  const context = {
    exports: {},
    process: { env: {} },
    require: (name) => {
      assert.equal(name, "axios");
      return axios;
    },
  };

  vm.runInNewContext(compiled, context);
  await context.exports.aiApi.chatWithSlide({
    slide_id: "slide-1",
    message: "Explain this topic",
  });

  assert.equal(calls.length, 1);
  assert.equal(calls[0][0], "/api/ai/chat/");
  assert.equal(calls[0][2].timeout, 120000);
});
