import { test, expect, type Page, type Route } from "@playwright/test";

const applicant = {
  id: 5000, user_id: 42, username: "test-applicant", full_name: "Test Applicant",
  email: "applicant@example.test", photo_url: null, class_role: "class_head",
  school_name: "Test School", set_name: "Year 1", class_code: "123456", class_group: 1,
  email_verified: false, onboarding_completed: true, class_head_verified: false,
  class_head_verification_requested: true, class_head_rejection_reason: "",
  can_access_app: false, is_premium: false, subscription_tier: "free",
  subscription_expires_at: null, streak: 0, created_at: "2026-10-13T12:00:00Z",
  is_staff: false, is_superuser: false,
};
const administrator = { ...applicant, id: 1, user_id: 1, username: "admin", full_name: "Test Admin",
  class_role: "student", can_access_app: true, is_staff: true, is_superuser: true };

async function signedIn(page: Page, profile = applicant) {
  await page.addInitScript((user) => {
    sessionStorage.setItem("token", "isolated-browser-access");
    sessionStorage.setItem("refreshToken", "isolated-browser-refresh");
    sessionStorage.setItem("user", JSON.stringify(user));
  }, profile);
}

async function fixtures(page: Page, handler: (route: Route, path: string) => Promise<boolean | void>) {
  await page.routeWebSocket("ws://127.0.0.1:8600/**", () => {});
  await page.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.origin === "http://127.0.0.1:3100") return route.continue();
    if (url.origin !== "http://127.0.0.1:8600") return route.abort();
    if (route.request().method() === "OPTIONS") return route.fulfill({ status: 204, headers: {
      "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*", "Access-Control-Allow-Methods": "GET,POST,PUT,OPTIONS",
    } });
    if (await handler(route, url.pathname)) return;
    return route.fulfill({ json: [] });
  });
}

test("email callback succeeds and consumes its token once in Strict Mode", async ({ page }) => {
  let requests = 0;
  await fixtures(page, async (route, path) => {
    if (path === "/auth/verify-email/") {
      requests++;
      expect(route.request().postDataJSON()).toEqual({ token: "test-link" });
      await route.fulfill({ json: { message: "Email verified successfully" } });
      return true;
    }
  });
  await page.goto("/verify-email?token=test-link");
  await expect(page.getByText("Email verified", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Sign in", exact: true })).toBeVisible();
  expect(requests).toBe(1);
});

test("invalid email links show recovery instructions", async ({ page }) => {
  await fixtures(page, async (route, path) => {
    if (path === "/auth/verify-email/") {
      await route.fulfill({ status: 400, json: { error: "This verification link expired. Request a new email." } });
      return true;
    }
  });
  await page.goto("/verify-email?token=expired");
  await expect(page.getByRole("alert").filter({ hasText: "expired" })).toBeVisible();
  await expect(page.getByText("Sign in to request a new verification email from your account.")).toBeVisible();
});

test("rejected applicant can request another review on a mobile viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  let profile = { ...applicant, class_head_verification_requested: false, class_head_rejection_reason: "Please confirm your class details." };
  await signedIn(page, profile);
  await fixtures(page, async (route, path) => {
    if (path === "/auth/profile/") { await route.fulfill({ json: profile }); return true; }
    if (path === "/auth/class-head/request-verification/") {
      profile = { ...profile, class_head_verification_requested: true, class_head_rejection_reason: "" };
      await route.fulfill({ json: { message: "Your request is pending administrator review.", user: profile } });
      return true;
    }
  });
  await page.goto("/verification-pending");
  await expect(page.getByText("Please confirm your class details.")).toBeVisible();
  await page.getByRole("button", { name: "Request another review" }).click();
  await expect(page.getByText("Your request is pending administrator review.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Request another review" })).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("status outage retains sign-in and can be retried", async ({ page }) => {
  await signedIn(page);
  let outage = true;
  await fixtures(page, async (route, path) => {
    if (path === "/auth/profile/") {
      await route.fulfill(outage ? { status: 503, json: {} } : { json: applicant });
      return true;
    }
  });
  await page.goto("/verification-pending");
  await expect(page.getByRole("alert").filter({ hasText: "still signed in" })).toBeVisible();
  expect(await page.evaluate(() => sessionStorage.getItem("token"))).toBe("isolated-browser-access");
  outage = false;
  await page.getByRole("button", { name: "Check status" }).click();
  await expect(page.getByText("Your class-head application is waiting for review.")).toBeVisible();
  await expect(page).toHaveURL(/verification-pending/);
});

test("resend displays the server cooldown after rate limiting", async ({ page }) => {
  await signedIn(page);
  await fixtures(page, async (route, path) => {
    if (path === "/auth/profile/") { await route.fulfill({ json: applicant }); return true; }
    if (path === "/auth/resend-verification/") {
      await route.fulfill({ status: 429, json: { error: "Please wait before requesting another email.", retry_after: 60 } });
      return true;
    }
  });
  await page.goto("/verification-pending");
  await page.getByRole("button", { name: "Resend verification email" }).click();
  await expect(page.getByRole("button", { name: /Resend in \d+s/ })).toBeDisabled();
  await expect(page.getByRole("alert").filter({ hasText: "Please wait" })).toBeVisible();
});

test("admin rejection sends the account identity and a reason", async ({ page }) => {
  await signedIn(page, administrator);
  let submitted: unknown;
  await fixtures(page, async (route, path) => {
    if (path === "/auth/profile/") { await route.fulfill({ json: administrator }); return true; }
    if (path === "/auth/class-head/pending/" || path === "/auth/admin/users/") { await route.fulfill({ json: [applicant] }); return true; }
    if (path === "/auth/class-head/verify/") {
      submitted = route.request().postDataJSON();
      await route.fulfill({ json: { message: "Class head rejected successfully", user: { ...applicant, class_head_verification_requested: false } } });
      return true;
    }
  });
  await page.goto("/admin/users");
  await page.getByRole("button", { name: "Reject Test Applicant", exact: true }).click();
  await expect(page.getByRole("button", { name: "Reject application", exact: true })).toBeDisabled();
  await page.getByLabel("Reason for rejection").fill("Please confirm class membership.");
  await page.getByRole("button", { name: "Reject application", exact: true }).click();
  await expect(page.getByText("Class head rejected successfully")).toBeVisible();
  expect(submitted).toEqual({ user_id: 42, approved: false, rejection_reason: "Please confirm class membership." });
});

test("staff without platform administrator access cannot load admin data", async ({ page }) => {
  const staff = { ...administrator, is_superuser: false, is_platform_admin: false };
  let adminRequests = 0;
  await signedIn(page, staff);
  await fixtures(page, async (route, path) => {
    if (path === "/auth/profile/") { await route.fulfill({ json: staff }); return true; }
    if (path.startsWith("/auth/admin/") || path === "/auth/class-head/pending/") adminRequests++;
  });
  await page.goto("/admin/users");
  await expect(page).toHaveURL(/\/admin\/login$/);
  await expect(page.getByRole("button", { name: "Reject Test Applicant", exact: true })).toHaveCount(0);
  expect(adminRequests).toBe(0);
});

test("platform administrators can review users without a staff flag", async ({ page }) => {
  const platformAdmin = { ...administrator, is_staff: false, is_superuser: false, is_platform_admin: true };
  await signedIn(page, platformAdmin);
  await fixtures(page, async (route, path) => {
    if (path === "/auth/profile/") { await route.fulfill({ json: platformAdmin }); return true; }
    if (path === "/auth/class-head/pending/" || path === "/auth/admin/users/") {
      await route.fulfill({ json: [applicant] }); return true;
    }
  });
  await page.goto("/admin/users");
  await expect(page.getByRole("button", { name: "Reject Test Applicant", exact: true })).toBeVisible();
  await expect(page).toHaveURL(/\/admin\/users$/);
});

test("a full class leaves its pending applicant reviewable", async ({ page }) => {
  await signedIn(page, administrator);
  await fixtures(page, async (route, path) => {
    if (path === "/auth/profile/") { await route.fulfill({ json: administrator }); return true; }
    if (path === "/auth/class-head/pending/" || path === "/auth/admin/users/") { await route.fulfill({ json: [applicant] }); return true; }
    if (path === "/auth/class-head/verify/") {
      await route.fulfill({ status: 400, json: ["This class already has the maximum of 3 active approved class heads."] });
      return true;
    }
  });
  await page.goto("/admin/users");
  await page.getByRole("button", { name: "Approve Test Applicant", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "maximum of 3" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Reject Test Applicant", exact: true })).toBeEnabled();
});

test("generic admin edits omit protected approval fields and preserve JSON types", async ({ page }) => {
  await signedIn(page, administrator);
  let submitted: unknown;
  const schema = [{ app_label: "accounts", app_name: "Accounts", models: [{
    model_name: "profile", verbose_name: "Profile", verbose_name_plural: "Profiles",
    fields: [
      { name: "id", verbose_name: "ID", type: "BigAutoField", primary_key: true, auto_created: true, editable: false },
      { name: "class_head_verified", verbose_name: "Approved", type: "BooleanField", editable: false },
      { name: "photo_url", verbose_name: "Photo URL", type: "URLField", editable: true },
      { name: "class_capabilities", verbose_name: "Capabilities", type: "JSONField", editable: true },
    ],
  }] }];
  await fixtures(page, async (route, path) => {
    if (path === "/auth/profile/") { await route.fulfill({ json: administrator }); return true; }
    if (path === "/auth/admin/schema/") { await route.fulfill({ json: schema }); return true; }
    if (path === "/auth/admin/data/accounts/profile/5000/") {
      if (route.request().method() === "PUT") {
        submitted = route.request().postDataJSON();
        await route.fulfill({ json: { status: "updated" } });
      } else {
        await route.fulfill({ json: { id: 5000, class_head_verified: false, photo_url: "", class_capabilities: [] } });
      }
      return true;
    }
  });
  await page.goto("/admin/manage/accounts/profile/5000");
  await expect(page.getByText("Read only", { exact: true })).toBeVisible();
  await page.getByLabel("Photo URL").fill("https://example.test/photo.png");
  await page.getByLabel("Capabilities").fill("[]");
  await page.getByRole("button", { name: "Save Changes" }).click();
  await expect.poll(() => submitted).toEqual({ photo_url: "https://example.test/photo.png", class_capabilities: [] });
});
