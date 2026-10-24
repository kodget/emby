const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");
const ts = require("typescript");

const compiled = ts.transpileModule(fs.readFileSync(path.join(__dirname, "../lib/api.ts"), "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true },
}).outputText;

function setup(refresh, { browser = true, refreshToken = "refresh-old" } = {}) {
  const values = new Map([["token", "expired"], ["user", "cached-user"]]);
  if (refreshToken) values.set("refreshToken", refreshToken);
  const calls = [];
  const retries = [];
  let reject;
  const instance = (config) => { retries.push(config); return Promise.resolve({ data: "retried" }); };
  instance.interceptors = {
    request: { use: () => {} },
    response: { use: (_, handler) => { reject = handler; } },
  };
  const axios = {
    create: () => instance,
    isAxiosError: (error) => error?.isAxiosError === true,
    post: (...args) => { calls.push(args); return refresh(...args); },
  };
  const window = { location: { href: "/dashboard" } };
  const context = {
    exports: {}, process: { env: {} },
    require: (name) => { assert.equal(name, "axios"); return axios; },
    ...(browser ? { window, sessionStorage: {
      getItem: (key) => values.get(key) ?? null,
      setItem: (key, value) => values.set(key, value),
      removeItem: (key) => values.delete(key),
    } } : {}),
  };
  vm.runInNewContext(compiled, context);
  return { reject, values, calls, retries, window };
}
const unauthorized = (url = "/auth/profile/") => ({
  isAxiosError: true, response: { status: 401 }, config: { url, headers: {} },
});
const failure = (status) => ({ isAxiosError: true, ...(status ? { response: { status } } : {}) });

test("network errors and server outages retain the session for another attempt", async () => {
  for (const status of [undefined, 500, 503]) {
    const issue = failure(status);
    const client = setup(() => Promise.reject(issue));
    await assert.rejects(client.reject(unauthorized()), (error) => error === issue);
    assert.equal(client.values.get("token"), "expired");
    assert.equal(client.values.get("refreshToken"), "refresh-old");
    assert.equal(client.window.location.href, "/dashboard");
    assert.equal(client.calls[0][2].timeout, 20000);
  }
});

test("rejected refresh credentials clear the session and redirect", async () => {
  for (const status of [400, 401, 403]) {
    const client = setup(() => Promise.reject(failure(status)));
    await assert.rejects(client.reject(unauthorized()));
    assert.equal(client.values.size, 0);
    assert.equal(client.window.location.href, "/signin");
  }
});

test("public login failures do not refresh or clear an existing account", async () => {
  const client = setup(() => { throw new Error("Unexpected refresh"); });
  const error = unauthorized("/auth/login/");
  await assert.rejects(client.reject(error), (result) => result === error);
  assert.equal(client.calls.length, 0);
  assert.equal(client.values.get("user"), "cached-user");
});

test("server-side or config-less errors are returned without browser access", async () => {
  const client = setup(() => { throw new Error("Unexpected refresh"); }, { browser: false });
  await assert.rejects(client.reject(unauthorized()));
  await assert.rejects(client.reject({ response: { status: 401 } }));
  assert.equal(client.calls.length, 0);
});

test("concurrent requests share one refresh and use the rotated credentials", async () => {
  let finish;
  const client = setup(() => new Promise((resolve) => { finish = resolve; }));
  const first = client.reject(unauthorized());
  const second = client.reject(unauthorized("/api/content/"));
  assert.equal(client.calls.length, 1);
  finish({ data: { access: "new-access", refresh: "new-refresh" } });
  await Promise.all([first, second]);
  assert.equal(client.retries.length, 2);
  assert.ok(client.retries.every((request) => request.headers.Authorization === "Bearer new-access" && request._retry));
  assert.equal(client.values.get("token"), "new-access");
  assert.equal(client.values.get("refreshToken"), "new-refresh");
});

test("authentication replay preserves multipart upload bytes and request identity", async () => {
  for (const url of ["/api/slides/upload_and_process/", "/api/decks/"]) {
    const client = setup(() => Promise.resolve({ data: { access: "renewed" } }));
    const body = new FormData();
    body.append("file", new Blob(["%PDF-1.7\nsource"]), "lecture.pdf");
    body.append("request_id", "6fdb2816-5016-448d-8b60-b82cf9ae8aa0");
    const error = unauthorized(url);
    error.config.data = body;
    await client.reject(error);
    assert.equal(client.retries[0].data, body);
    assert.equal(client.retries[0].data.get("request_id"), "6fdb2816-5016-448d-8b60-b82cf9ae8aa0");
    assert.equal(await client.retries[0].data.get("file").text(), "%PDF-1.7\nsource");
  }
});

test("queued failures settle and a later request can retry after an outage", async () => {
  let fail;
  let attempts = 0;
  const client = setup(() => ++attempts === 1
    ? new Promise((_, reject) => { fail = reject; })
    : Promise.resolve({ data: { access: "recovered" } }));
  const first = client.reject(unauthorized());
  const second = client.reject(unauthorized());
  const done = Promise.allSettled([first, second]);
  fail(failure(503));
  assert.ok((await done).every((result) => result.status === "rejected"));
  await client.reject(unauthorized());
  assert.equal(attempts, 2);
  assert.equal(client.values.get("token"), "recovered");
});

test("malformed refresh success neither stores an invalid token nor logs out", async () => {
  const client = setup(() => Promise.resolve({ data: {} }));
  await assert.rejects(client.reject(unauthorized()), /invalid session response/);
  assert.equal(client.values.get("token"), "expired");
  assert.equal(client.window.location.href, "/dashboard");
});

test("a retried request cannot enter another refresh loop", async () => {
  const client = setup(() => { throw new Error("Unexpected refresh"); });
  const error = unauthorized();
  error.config._retry = true;
  await assert.rejects(client.reject(error));
  assert.equal(client.calls.length, 0);
});
