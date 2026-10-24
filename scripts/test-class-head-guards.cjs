const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");
const ts = require("typescript");

const source = fs.readFileSync(path.join(__dirname, "../lib/guards.ts"), "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText;

function loadGuards(profile, { token = "access-token", raw, browser = true } = {}) {
  const values = new Map();
  if (token) values.set("token", token);
  if (raw !== undefined) values.set("user", raw);
  else if (profile) values.set("user", JSON.stringify(profile));
  const context = {
    exports: {},
    sessionStorage: { getItem: (key) => values.get(key) ?? null },
    ...(browser ? { window: {} } : {}),
  };
  vm.runInNewContext(compiled, context);
  return context.exports;
}

const classHead = {
  class_role: "class_head",
  class_head_verified: false,
  class_head_verification_requested: true,
  class_head_rejection_reason: "",
  onboarding_completed: true,
  subscription_tier: "free",
};

test("staff alone cannot open the platform admin interface", () => {
  const guards = loadGuards(null);
  assert.equal(guards.canAccessAdmin({ is_staff: true }), false);
  assert.equal(guards.canAccessAdmin({ is_platform_admin: 'true' }), false);
  assert.equal(guards.canAccessAdmin(null), false);
});

test("platform administrators and superusers can open the admin interface", () => {
  const guards = loadGuards(null);
  assert.equal(guards.canAccessAdmin({ is_platform_admin: true, is_staff: false }), true);
  assert.equal(guards.canAccessAdmin({ is_superuser: true }), true);
});

test("pending class heads cannot manage, upload or enter the app", () => {
  const guards = loadGuards(classHead);
  assert.equal(guards.isClassHead(), false);
  assert.equal(guards.canManageClass(), false);
  assert.equal(guards.canUploadMaterials(), false);
  assert.equal(guards.canAccessApp(), false);
  assert.equal(guards.getRedirectPath(), "/verification-pending");
});

test("rejected class heads retain no class-head privileges", () => {
  const guards = loadGuards({
    ...classHead,
    class_head_verification_requested: false,
    class_head_rejection_reason: "The class details need to be corrected.",
  });
  assert.equal(guards.canManageClass(), false);
  assert.equal(guards.canUploadMaterials(), false);
  assert.equal(guards.canAccessApp(), false);
  assert.equal(guards.isPremium(), false);
});

test("approved class heads gain management and upload access", () => {
  const guards = loadGuards({ ...classHead, class_head_verified: true });
  assert.equal(guards.isClassHead(), true);
  assert.equal(guards.canManageClass(), true);
  assert.equal(guards.canUploadMaterials(), true);
  assert.equal(guards.canAccessApp(), true);
  assert.equal(guards.getRedirectPath(), "/dashboard");
});

test("approval flags must be boolean true", () => {
  const guards = loadGuards({ ...classHead, class_head_verified: "false" });
  assert.equal(guards.isClassHeadVerified(), false);
  assert.equal(guards.canAccessApp(), false);
  assert.equal(guards.canUploadMaterials(), false);
});

test("material uploaders can upload without becoming class heads", () => {
  const guards = loadGuards({ ...classHead, class_role: "material_uploader" });
  assert.equal(guards.canUploadMaterials(), true);
  assert.equal(guards.isClassHead(), false);
  assert.equal(guards.canManageClass(), false);
});

test("ordinary students cannot upload", () => {
  assert.equal(loadGuards({ ...classHead, class_role: "student" }).canUploadMaterials(), false);
});

test("malformed cached profiles fail closed without crashing", () => {
  const guards = loadGuards(null, { raw: "{broken" });
  assert.equal(guards.getStoredProfile(), null);
  assert.equal(guards.canUploadMaterials(), false);
  assert.equal(guards.canAccessApp(), false);
  assert.equal(guards.getRedirectPath(), "/onboarding");
});

test("missing browser or authentication does not grant app access", () => {
  assert.equal(loadGuards(classHead, { browser: false }).getStoredProfile(), null);
  assert.equal(loadGuards(classHead, { browser: false }).canAccessApp(), false);
  assert.equal(loadGuards({ ...classHead, class_head_verified: true }, { token: null }).canAccessApp(), false);
});
