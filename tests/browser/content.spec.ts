import { test, expect, type Page, type Route } from "@playwright/test";

const profile = {
  id: 12,
  user_id: 42,
  username: "uploader",
  full_name: "Test Uploader",
  email: "uploader@example.test",
  photo_url: null,
  class_role: "material_uploader",
  school_name: "Test School",
  set_name: "Year 1",
  class_group: 1,
  class_code: "123456",
  email_verified: true,
  onboarding_completed: true,
  class_head_verified: false,
  class_head_verification_requested: false,
  class_head_rejection_reason: "",
  can_access_app: true,
  is_premium: false,
  subscription_tier: "free",
  subscription_expires_at: null,
  streak: 0,
  is_staff: false,
  is_superuser: false,
};
const subject = { id: "anatomy", name: "Anatomy" };
const block = {
  id: "upper",
  subject: "anatomy",
  name: "Upper limb",
  sub_blocks: [],
  topics: [],
};
const sub = { id: "hand", block: "upper", name: "Hand" };
const topic = {
  id: "opaque-topic-42",
  block: "upper",
  sub_block: "hand",
  name: "Bones",
};

async function fixtures(
  page: Page,
  handler?: (route: Route, url: URL) => Promise<boolean | void>,
  identity = profile,
) {
  await page.addInitScript((user) => {
    sessionStorage.setItem("token", "isolated-browser-access");
    sessionStorage.setItem("refreshToken", "isolated-browser-refresh");
    sessionStorage.setItem("user", JSON.stringify(user));
  }, identity);
  await page.routeWebSocket("ws://127.0.0.1:8600/**", () => {});
  await page.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.origin === new URL(test.info().project.use.baseURL!).origin)
      return route.continue();
    if (url.origin !== "http://127.0.0.1:8600") return route.abort();
    if (route.request().method() === "OPTIONS")
      return route.fulfill({
        status: 204,
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Headers": "*",
          "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
        },
      });
    if (await handler?.(route, url)) return;
    const data: Record<string, unknown> = {
      "/auth/profile/": identity,
      "/api/subjects/": [subject],
      "/api/blocks/": [block],
      "/api/credits/balance/": { balance: 20 },
      "/api/sub-blocks/": [sub],
      "/api/topics/": [topic],
      "/api/topics/opaque-topic-42/": topic,
      "/api/blocks/upper/": block,
      "/api/sub-blocks/hand/": sub,
    };
    await route.fulfill({ json: data[url.pathname] ?? [] });
  });
}

test("mock exams choose explicit scopes, show shortages and recheck availability at start", async ({
  page,
}) => {
  test.setTimeout(120000);
  const requested: string[] = [];
  let starts = 0;
  await fixtures(
    page,
    async (route, url) => {
      if (url.pathname === "/api/quiz-attempts/mock-options/") {
        requested.push(
          `${url.searchParams.get("scope_type")}:${url.searchParams.get("scope_id")}`,
        );
        await route.fulfill({
          json: {
            available: {
              easy: { mcq: 5, theory: 2 },
              medium: { mcq: 3, theory: 1 },
              hard: { mcq: 1, theory: 0 },
            },
          },
        });
        return true;
      }
      if (
        url.pathname === "/api/quiz-attempts/" &&
        route.request().method() === "POST"
      ) {
        starts++;
        expect(route.request().postDataJSON()).toEqual({
          exam_type: "mock",
          scope_type: "submodule",
          scope_id: "hand",
          is_timed: false,
          configuration: {
            mcq_count: starts === 1 ? 3 : 2,
            theory_count: 1,
            difficulty: "medium",
            question_source: "hierarchy",
          },
        });
        if (starts === 1)
          await route.fulfill({
            status: 400,
            json: {
              code: "insufficient_questions",
              available: { mcq: "2", theory: "1" },
              error: "Only 2 MCQs and 1 written question remain.",
            },
          });
        else await route.fulfill({ json: { id: "scoped-mock" } });
        return true;
      }
      if (url.pathname === "/api/quiz-attempts/scoped-mock/") {
        await route.fulfill({
          json: {
            id: "scoped-mock",
            exam_type: "mock",
            status: "in_progress",
            is_timed: false,
            questions: [
              {
                id: "mock-q",
                question_type: "mcq",
                question_text: "Saved scoped question",
                difficulty: "medium",
                option_a: "First",
                option_b: "Second",
                option_c: "Third",
                option_d: "Fourth",
              },
            ],
            responses: [],
          },
        });
        return true;
      }
    },
    { ...profile, class_role: "class_head", class_head_verified: true },
  );
  // Compile the local development attempt route before timing the user navigation.
  await page.request.get("/quiz/attempt/scoped-mock");
  await page.goto("/quiz/mock");
  await page
    .getByRole("combobox", { name: "Course", exact: true })
    .selectOption("anatomy");
  await expect(page.getByRole("status")).toContainText("3 MCQs and 1 written");
  await page
    .getByRole("combobox", { name: "Exam scope", exact: true })
    .selectOption("module");
  await page
    .getByRole("combobox", { name: "Module", exact: true })
    .selectOption("upper");
  await expect.poll(() => requested).toContain("module:upper");
  await page
    .getByRole("combobox", { name: "Exam scope", exact: true })
    .selectOption("submodule");
  await page
    .getByRole("combobox", { name: "Submodule", exact: true })
    .selectOption("hand");
  await expect(
    page.getByRole("button", { name: "Start mock exam", exact: true }),
  ).toBeDisabled();
  await page
    .getByRole("button", { name: "Use available questions", exact: true })
    .click();
  await page
    .getByRole("checkbox", { name: "Timed exam", exact: true })
    .uncheck();
  await page
    .getByRole("button", { name: "Start mock exam", exact: true })
    .click();
  await expect(
    page.getByRole("alert").filter({ hasText: "Only 2 MCQs" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Start mock exam", exact: true }),
  ).toBeDisabled();
  await page
    .getByRole("button", { name: "Use available questions", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Start mock exam", exact: true })
    .click();
  await expect(page).toHaveURL(/attempt\/scoped-mock$/);
  await expect(
    page.getByText("Saved scoped question", { exact: true }),
  ).toBeVisible();
  expect(requested).toEqual([
    "course:anatomy",
    "module:upper",
    "submodule:hand",
  ]);
  expect(starts).toBe(2);
});

test("mock results show saved explanations, topic totals and fractional written marks after reload", async ({
  page,
}) => {
  test.setTimeout(120000);
  const mcq = {
    id: "mock-result-mcq",
    question_type: "mcq",
    question_text: "Which component?",
    correct_option: "B",
    option_b: "Second component",
    explanation: "The source identifies the second component.",
  };
  const theory = {
    id: "mock-result-written",
    question_type: "theory",
    question_text: "Explain its arrangement.",
    maximum_marks: 2,
    ideal_answer: "The model arrangement.",
  };
  await fixtures(page, async (route, url) => {
    if (url.pathname.endsWith("/mock-result/result/")) {
      await route.fulfill({
        json: {
          id: "mock-result",
          exam_type: "mock",
          status: "submitted",
          answers_released: true,
          mcq_score: 1,
          mcq_total: 2,
          theory_score: "1.50",
          theory_total: 1,
          overall_percentage: 62.5,
          theory_grading_pending: false,
          grading: {
            status: "completed",
            completed_questions: 1,
            total_questions: 1,
            can_retry: false,
          },
          questions: [mcq, theory],
          responses: [
            { question: mcq, selected_option: "B", is_correct: true },
            {
              question: theory,
              text_answer: "My saved arrangement.",
              ai_score: "1.50",
              ai_evaluation_status: "completed",
              ai_feedback: { feedback: "One detail was omitted." },
            },
          ],
          topic_breakdown: [
            {
              topic_name: "Hand anatomy",
              correct: 1,
              total: 2,
              percentage: 50,
            },
          ],
          analysis_data: { total_maximum_marks: 4, theory_maximum_marks: 2 },
        },
      });
      return true;
    }
    if (url.pathname.endsWith("/mock-result/missed/")) {
      await route.fulfill({ json: { missed_questions: [], total_missed: 0 } });
      return true;
    }
  });
  await page.goto("/quiz/attempt/mock-result/results");
  await expect(
    page.getByText("Explanation: The source identifies the second component.", {
      exact: true,
    }),
  ).toBeVisible();
  await expect(page.getByText("Hand anatomy", { exact: true })).toBeVisible();
  await expect(page.getByText("1/2 (50%)", { exact: true })).toBeVisible();
  await expect(
    page.getByText("Overall mark: 2.5 / 4", { exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByText("Written mark: 1.50 / 2", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("My saved arrangement.", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Feedback: One detail was omitted.", { exact: true }),
  ).toBeVisible();
});

test("deck practice shows shortages and sends only the chosen deck and difficulty", async ({
  page,
}) => {
  let starts = 0;
  await fixtures(page, async (route, url) => {
    if (url.pathname === "/api/slides/") {
      await route.fulfill({
        json: [{ id: "practice-deck", title: "Saved anatomy deck" }],
      });
      return true;
    }
    if (url.pathname === "/api/quiz-attempts/practice-options/") {
      expect(url.searchParams.get("slide")).toBe("practice-deck");
      await route.fulfill({
        json: {
          slide: "practice-deck",
          title: "Saved anatomy deck",
          maximum: 20,
          available: { easy: 5, medium: 5, hard: 2 },
        },
      });
      return true;
    }
    if (url.pathname === "/api/quiz-attempts/") {
      starts++;
      expect(route.request().postDataJSON()).toMatchObject({
        slide: "practice-deck",
        exam_type: "practice",
        configuration: { mcq_count: 2, theory_count: 0, difficulty: "hard" },
      });
      // Simulate a bank edit after availability was displayed.
      await route.fulfill({
        status: 400,
        json: {
          error: "Only 1 hard questions are available in this deck.",
          available: 1,
          code: "insufficient_questions",
        },
      });
      return true;
    }
  });
  await page.goto("/quiz?slide=practice-deck");
  await expect(
    page.getByText("5 medium questions available in this deck."),
  ).toBeVisible();
  await page.getByRole("spinbutton", { name: "Number of questions" }).fill("6");
  await expect(
    page.getByRole("button", { name: "Start practice", exact: true }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "Use 5 available questions" }).click();
  await page
    .getByRole("combobox", { name: "Difficulty", exact: true })
    .selectOption("hard");
  await page.getByRole("button", { name: "Use 2 available questions" }).click();
  await page
    .getByRole("button", { name: "Start practice", exact: true })
    .click();
  await expect(
    page.getByText("1 hard question available in this deck."),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Start practice", exact: true }),
  ).toBeDisabled();
  expect(starts).toBe(1);
});

test("reader and study session enter saved deck practice without generating questions", async ({
  page,
}) => {
  test.setTimeout(120000);
  const providerCalls: string[] = [];
  await fixtures(page, async (route, url) => {
    if (
      route.request().method() === "POST" &&
      /generate|quiz-attempts\/$/.test(url.pathname)
    )
      providerCalls.push(url.pathname);
    return readerResponse(route, url);
  });
  await page.goto("/read/anatomy/reader-a");
  await page.getByRole("button", { name: "Quiz", exact: true }).click();
  await expect(
    page.getByRole("link", { name: "Choose practice questions" }),
  ).toHaveAttribute("href", "/quiz?slide=reader-a");
  expect(providerCalls).toEqual([]);
  await page.goto("/session?step=3");
  await page.getByRole("button", { name: "Start Practice Quiz" }).click();
  await expect(
    page.getByRole("heading", { name: "Practise one deck", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Start practice", exact: true }),
  ).toBeDisabled();
  expect(providerCalls).toEqual([]);
});

test("practice answer failure is visible, reload restores saved answers and results show correct answers", async ({
  page,
}) => {
  let saves = 0;
  let selected: string | null = null;
  let submitted = false;
  const question = {
    id: "practice-q",
    question_type: "mcq",
    question_text: "Which component is described?",
    difficulty: "medium",
    option_a: "First",
    option_b: "Second",
    option_c: "Third",
    option_d: "Fourth",
  };
  await fixtures(page, async (route, url) => {
    if (url.pathname === "/api/quiz-attempts/practice-test/answer/") {
      saves++;
      if (saves === 1)
        await route.fulfill({
          status: 503,
          json: { error: "Answer storage temporarily unavailable." },
        });
      else {
        selected = route.request().postDataJSON().selected_option;
        await route.fulfill({ json: { status: "Answer recorded" } });
      }
      return true;
    }
    if (url.pathname === "/api/quiz-attempts/practice-test/submit/") {
      expect(selected).toBe("B");
      submitted = true;
      await route.fulfill({
        json: {
          id: "practice-test",
          status: "submitted",
          mcq_score: 1,
          overall_percentage: 100,
        },
      });
      return true;
    }
    if (
      [
        "/api/quiz-attempts/practice-test/",
        "/api/quiz-attempts/practice-test/result/",
      ].includes(url.pathname)
    ) {
      const q = submitted ? { ...question, correct_option: "B" } : question;
      await route.fulfill({
        json: {
          id: "practice-test",
          status: submitted ? "submitted" : "in_progress",
          exam_type: "practice",
          is_timed: false,
          questions: [q],
          responses: selected
            ? [
                {
                  question: q,
                  selected_option: selected,
                  ...(submitted ? { is_correct: true } : {}),
                },
              ]
            : [],
          flagged_questions: [],
          mcq_total: 1,
          mcq_score: submitted ? 1 : 0,
          overall_percentage: submitted ? 100 : 0,
          theory_total: 0,
        },
      });
      return true;
    }
    if (url.pathname === "/api/quiz-attempts/practice-test/missed/") {
      await route.fulfill({ json: { missed_questions: [], total_missed: 0 } });
      return true;
    }
  });
  await page.goto("/quiz/attempt/practice-test");
  await page.getByRole("button", { name: "B. Second", exact: true }).click();
  await expect(
    page
      .getByRole("alert")
      .filter({ hasText: "Your last change was not saved" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "B. Second", exact: true }),
  ).toHaveAttribute("aria-pressed", "false");
  await page.getByRole("button", { name: "B. Second", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "B. Second", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await page.reload();
  await expect(
    page.getByRole("button", { name: "B. Second", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: "Submit", exact: true }).click();
  await page.getByRole("button", { name: "Submit Exam", exact: true }).click();
  await expect(page).toHaveURL(/practice-test\/results/);
  await expect(
    page.getByText("Correct answer: B — Second", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Correct · Your answer: B", { exact: true }),
  ).toBeVisible();
  expect(saves).toBe(2);
});

test("written assessment answers retry, reload and clear before submission", async ({
  page,
}) => {
  let saved = "";
  let saves = 0;
  let submitted = false;
  const question = {
    id: "written-q",
    question_type: "theory",
    question_text: "Explain the arrangement.",
    difficulty: "medium",
  };
  await fixtures(page, async (route, url) => {
    if (url.pathname === "/api/quiz-attempts/written-test/answer/") {
      saves++;
      const value = route.request().postDataJSON().text_answer;
      expect(typeof value).toBe("string");
      if (saves === 1)
        await route.fulfill({
          status: 503,
          json: { error: "Written answer could not be saved." },
        });
      else {
        saved = value;
        await route.fulfill({ json: { status: "Answer recorded" } });
      }
      return true;
    }
    if (url.pathname === "/api/quiz-attempts/written-test/submit/") {
      expect(saved).toBe("Final answer for submission");
      submitted = true;
      await route.fulfill({
        json: { id: "written-test", status: "submitted" },
      });
      return true;
    }
    if (
      [
        "/api/quiz-attempts/written-test/",
        "/api/quiz-attempts/written-test/result/",
      ].includes(url.pathname)
    ) {
      await route.fulfill({
        json: {
          id: "written-test",
          exam_type: "mock",
          status: submitted ? "submitted" : "in_progress",
          is_timed: false,
          questions: [question],
          responses: [{ question, text_answer: saved }],
          mcq_total: 0,
          theory_total: 1,
        },
      });
      return true;
    }
  });
  await page.goto("/quiz/attempt/written-test");
  await page
    .getByRole("textbox", { name: "Written answer" })
    .fill("First saved answer");
  await expect(
    page.getByRole("button", { name: "Retry saving written answers" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Retry saving written answers" })
    .click();
  await expect.poll(() => saved).toBe("First saved answer");
  await page.reload();
  await expect(
    page.getByRole("textbox", { name: "Written answer" }),
  ).toHaveValue("First saved answer");
  await page.getByRole("textbox", { name: "Written answer" }).fill("");
  await expect.poll(() => saved).toBe("");
  await page
    .getByRole("textbox", { name: "Written answer" })
    .fill("Final answer for submission");
  await page.getByRole("button", { name: "Submit", exact: true }).click();
  await page.getByRole("button", { name: "Submit Exam", exact: true }).click();
  await expect.poll(() => submitted).toBe(true);
});

test("formal assessment head saves a private paper, reloads it and publishes fixed settings", async ({
  page,
}) => {
  let paper: any = null;
  let published = false;
  await fixtures(
    page,
    async (route, url) => {
      if (!url.pathname.startsWith("/api/formal-assessments/")) return;
      const method = route.request().method();
      if (url.pathname.endsWith("/publish/")) {
        expect(route.request().postDataJSON()).toEqual({ revision: 2 });
        expect(paper).toMatchObject({
          title: "Upper limb assessment",
          mcq_count: 1,
          theory_count: 0,
          duration_minutes: 25,
        });
        expect(paper.questions[0]).toMatchObject({
          correct_option: "B",
          explanation: "The second component is correct.",
        });
        published = true;
        paper = { ...paper, published_at: "2026-10-19T12:00:00Z", revision: 3 };
        await route.fulfill({ json: paper });
        return true;
      }
      if (method === "POST" || method === "PATCH") {
        paper = {
          ...route.request().postDataJSON(),
          id: "formal-paper",
          revision: method === "POST" ? 1 : 2,
        };
        await route.fulfill({ json: paper });
        return true;
      }
      await route.fulfill({
        json:
          url.pathname === "/api/formal-assessments/"
            ? { can_manage: true, assessments: paper ? [paper] : [] }
            : paper,
      });
      return true;
    },
    { ...profile, class_role: "class_head", class_head_verified: true },
  );
  await page.goto("/quiz/assessments");
  await page
    .getByRole("button", { name: "Create assessment", exact: true })
    .click();
  await page.getByLabel("Assessment title").fill("Upper limb assessment");
  await page.getByLabel("Time limit (minutes)").fill("25");
  await page.getByRole("button", { name: "Add MCQ", exact: true }).click();
  await page
    .getByLabel("Question 1 text")
    .fill("Which component is described?");
  for (const [letter, value] of Object.entries({
    A: "First",
    B: "Second",
    C: "Third",
    D: "Fourth",
  })) {
    await page
      .getByLabel(`Question 1 option ${letter}`, { exact: true })
      .fill(value);
  }
  await page.getByLabel("Question 1 correct option").selectOption("B");
  await page
    .getByLabel("Question 1 explanation")
    .fill("The second component is correct.");
  await page.getByRole("button", { name: "Save draft", exact: true }).click();
  await expect(
    page.getByText("Private draft saved.", { exact: true }),
  ).toBeVisible();
  await page.reload();
  await page.getByRole("button", { name: "Edit draft", exact: true }).click();
  await expect(page.getByLabel("Question 1 text")).toHaveValue(
    "Which component is described?",
  );
  await page
    .getByRole("button", {
      name: "Save and publish reviewed paper",
      exact: true,
    })
    .click();
  await expect(
    page.getByText(
      "Published. Students in your class can now start their one attempt.",
      { exact: true },
    ),
  ).toBeVisible();
  await expect(page.getByLabel("Assessment title")).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "Close new entries", exact: true }),
  ).toBeVisible();
  expect(published).toBe(true);
});

test("AI assessment suggestions resume after reload, preserve edits and require review before publishing", async ({
  page,
}) => {
  test.setTimeout(120000);
  const manual = {
    question_type: "mcq",
    question_text: "Manual question to preserve",
    difficulty: "medium",
    option_a: "One",
    option_b: "Two",
    option_c: "Three",
    option_d: "Four",
    correct_option: "B",
    explanation: "Manual explanation",
    maximum_marks: 1,
  };
  const suggestion = {
    ...manual,
    question_text: "Generated source question",
    explanation: "Supported explanation",
    source_title: "Class source document",
    source_page: 3,
    source_quote: "A quotation supporting the generated answer.",
  };
  let paper: any = {
    id: "ai-paper",
    title: "AI assisted class paper",
    revision: 1,
    duration_minutes: 30,
    mcq_count: 2,
    theory_count: 0,
    questions: [manual],
    generation: null,
    has_ai_questions: false,
  };
  let retry = false;
  let published = false;
  await fixtures(
    page,
    async (route, url) => {
      if (url.pathname === "/api/slides/") {
        await route.fulfill({
          json: url.searchParams.has("page")
            ? {
                results: [
                  { id: "class-source", title: "Class source document" },
                ],
                next: null,
              }
            : { results: [], next: "/api/slides/?page=2" },
        });
        return true;
      }
      if (!url.pathname.startsWith("/api/formal-assessments/")) return;
      const method = route.request().method();
      if (url.pathname.endsWith("/generation/")) {
        if (method === "GET") {
          paper.generation = {
            ...paper.generation,
            status: retry ? "completed" : "failed",
            generated: retry ? 1 : 0,
            questions: retry ? [suggestion] : [],
          };
          await route.fulfill({ json: paper.generation });
          return true;
        }
        const body = route.request().postDataJSON();
        expect(body.revision).toBe(paper.revision);
        if (body.operation === "generate") {
          expect(body.source_ids).toEqual(["class-source"]);
          paper.generation = {
            id: 17,
            base_revision: paper.revision,
            status: "pending",
            generated: 0,
            target: 1,
            questions: [],
            error_code: "",
          };
        } else if (body.operation === "retry") {
          retry = true;
          paper.generation.status = "pending";
        } else if (body.operation === "apply") {
          paper = {
            ...paper,
            revision: paper.revision + 1,
            has_ai_questions: true,
            questions: [manual, suggestion],
            generation: { ...paper.generation, status: "applied" },
          };
        } else throw new Error("Unexpected drafting operation");
        await route.fulfill({ json: paper });
        return true;
      }
      if (url.pathname.endsWith("/publish/")) {
        expect(route.request().postDataJSON()).toEqual({
          revision: paper.revision,
          review_confirmed: true,
        });
        expect(paper.questions[0]).toEqual(manual);
        published = true;
        paper.published_at = "2026-10-20T12:00:00Z";
        await route.fulfill({ json: paper });
        return true;
      }
      if (method === "PATCH") {
        paper = {
          ...paper,
          ...route.request().postDataJSON(),
          revision: paper.revision + 1,
        };
      }
      await route.fulfill({
        json:
          url.pathname === "/api/formal-assessments/"
            ? { can_manage: true, assessments: [paper] }
            : paper,
      });
      return true;
    },
    { ...profile, class_role: "class_head", class_head_verified: true },
  );
  await page.goto("/quiz/assessments");
  await page.getByRole("button", { name: "Edit draft", exact: true }).click();
  await page.getByLabel("Class source document", { exact: true }).check();
  await page
    .getByRole("button", {
      name: "Save draft and generate suggestions",
      exact: true,
    })
    .click();
  await expect(
    page.getByText("0 of 1 suggestions saved", { exact: false }),
  ).toBeVisible();
  await page.reload();
  await page.getByRole("button", { name: "Edit draft", exact: true }).click();
  await page
    .getByRole("button", { name: "Retry generation", exact: true })
    .click();
  await expect(
    page.getByRole("button", {
      name: "Add reviewed suggestions to draft",
      exact: true,
    }),
  ).toBeEnabled();
  await page
    .getByText("Suggestion 1: Generated source question", { exact: true })
    .click();
  await expect(
    page.getByText("Source: Class source document, page 3", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText(suggestion.source_quote, { exact: true }),
  ).toBeVisible();
  await page
    .getByLabel("Assessment title", { exact: true })
    .fill("Unsaved title");
  await expect(
    page.getByRole("button", {
      name: "Add reviewed suggestions to draft",
      exact: true,
    }),
  ).toBeDisabled();
  await page
    .getByLabel("Assessment title", { exact: true })
    .fill("AI assisted class paper");
  await page
    .getByRole("button", {
      name: "Add reviewed suggestions to draft",
      exact: true,
    })
    .click();
  await expect(
    page.getByRole("textbox", { name: "Question 1 text", exact: true }),
  ).toHaveValue(manual.question_text);
  await expect(
    page.getByRole("textbox", { name: "Question 2 text", exact: true }),
  ).toHaveValue(suggestion.question_text);
  const publish = page.getByRole("button", {
    name: "Save and publish reviewed paper",
    exact: true,
  });
  const review = page.getByRole("checkbox", {
    name: "I have reviewed every generated question",
    exact: false,
  });
  await expect(publish).toBeDisabled();
  await review.check();
  await page
    .getByRole("textbox", { name: "Question 2 explanation", exact: true })
    .fill("Reviewed explanation");
  await expect(review).not.toBeChecked();
  await expect(publish).toBeDisabled();
  await review.check();
  await publish.click();
  await expect(
    page.getByText(
      "Published. Students in your class can now start their one attempt.",
      { exact: true },
    ),
  ).toBeVisible();
  expect(published).toBe(true);
});

test("formal assessment student resumes one attempt and sees pending written grading without answer keys", async ({
  page,
}) => {
  let submitted = false;
  let starts = 0;
  const question = {
    id: "formal-question",
    question_type: "theory",
    question_text: "Explain the arrangement.",
    difficulty: "medium",
  };
  const attempt = () => ({
    id: "formal-attempt",
    assessment: "formal-paper",
    exam_type: "formal",
    status: submitted ? "submitted" : "in_progress",
    questions: [question],
    responses: [{ question, text_answer: "My saved written response" }],
    mcq_total: 0,
    theory_total: 1,
    is_timed: true,
    duration_minutes: 25,
    time_remaining_seconds: submitted ? 0 : 1200,
    theory_grading_pending: submitted,
    answers_released: false,
  });
  await fixtures(page, async (route, url) => {
    if (url.pathname === "/api/formal-assessments/") {
      await route.fulfill({
        json: {
          can_manage: false,
          assessments: [
            {
              id: "formal-paper",
              title: "Class paper",
              duration_minutes: 25,
              mcq_count: 0,
              theory_count: 1,
              published_at: "2026-10-19T12:00:00Z",
              attempt: {
                id: "formal-attempt",
                status: submitted ? "submitted" : "in_progress",
              },
            },
          ],
        },
      });
      return true;
    }
    if (url.pathname === "/api/formal-assessments/formal-paper/start/") {
      starts++;
      expect(route.request().postDataJSON()).toEqual({});
      await route.fulfill({ json: attempt() });
      return true;
    }
    if (url.pathname === "/api/quiz-attempts/formal-attempt/submit/") {
      submitted = true;
      await route.fulfill({ json: attempt() });
      return true;
    }
    if (
      [
        "/api/quiz-attempts/formal-attempt/",
        "/api/quiz-attempts/formal-attempt/result/",
      ].includes(url.pathname)
    ) {
      await route.fulfill({ json: attempt() });
      return true;
    }
    if (url.pathname === "/api/quiz-attempts/formal-attempt/missed/") {
      await route.fulfill({
        json: {
          missed_questions: [],
          total_missed: null,
          answers_released: false,
        },
      });
      return true;
    }
  });
  await page.goto("/quiz/assessments");
  await expect(
    page.getByRole("button", { name: "Create assessment", exact: true }),
  ).toHaveCount(0);
  await page
    .getByRole("button", { name: "Resume attempt", exact: true })
    .click();
  await expect(
    page.getByRole("textbox", { name: "Written answer" }),
  ).toHaveValue("My saved written response");
  await page.getByRole("button", { name: "Submit", exact: true }).click();
  await page.getByRole("button", { name: "Submit Exam", exact: true }).click();
  await expect(page).toHaveURL(/formal-attempt\/results/);
  await expect(
    page.getByText("Written grading is pending", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText(
      "Answer keys will be available after your class head closes entries and releases them.",
      { exact: true },
    ),
  ).toBeVisible();
  await expect(
    page.getByText("My saved written response", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Certificate eligible", { exact: true }),
  ).toHaveCount(0);
  await page.goto("/quiz/assessments");
  await page.getByRole("button", { name: "View result", exact: true }).click();
  await expect(page).toHaveURL(/formal-attempt\/results/);
  expect(starts).toBe(2);
});

test("saved assessment grading retries without losing answers and shows fractional final marks after refresh", async ({
  page,
}) => {
  let state = "failed";
  let retries = 0;
  let released = false;
  const questions = [
    {
      id: "grade-mcq",
      question_type: "mcq",
      question_text: "Choose the component.",
      maximum_marks: 1,
      difficulty: "medium",
      option_a: "First",
      option_b: "Second",
      option_c: "Third",
      option_d: "Fourth",
    },
    {
      id: "grade-written",
      question_type: "theory",
      question_text: "Describe the arrangement.",
      maximum_marks: 2,
      difficulty: "medium",
    },
    {
      id: "grade-blank",
      question_type: "theory",
      question_text: "Explain the function.",
      maximum_marks: 2,
      difficulty: "medium",
    },
  ];
  await fixtures(page, async (route, url) => {
    if (url.pathname === "/api/quiz-attempts/graded-formal/retry-grading/") {
      retries++;
      if (retries === 1)
        await route.fulfill({
          status: 503,
          json: { error: "Grading queue unavailable. Retry shortly." },
        });
      else {
        state = "pending";
        await route.fulfill({
          status: 202,
          json: { grading: { status: state } },
        });
      }
      return true;
    }
    if (url.pathname === "/api/quiz-attempts/graded-formal/result/") {
      const completed = state === "completed";
      await route.fulfill({
        json: {
          id: "graded-formal",
          assessment: "class-paper",
          exam_type: "formal",
          status: "submitted",
          answers_released: released,
          theory_grading_pending: !completed,
          mcq_score: 1,
          mcq_total: 1,
          theory_total: 2,
          theory_score: completed ? "1.50" : "0.00",
          overall_percentage: completed ? 50 : 100,
          analysis_data: {
            theory_maximum_marks: 4,
            ...(completed ? { total_maximum_marks: 5 } : {}),
          },
          feedback: released
            ? {
                note: "Observed responses do not establish the cause of a mistake.",
                mcq: { correct: 1, incorrect: 0, unanswered: 0 },
                difficulty_breakdown: [
                  {
                    difficulty: "medium",
                    correct: 1,
                    incorrect: 0,
                    unanswered: 0,
                    total: 1,
                    sufficient_evidence: false,
                  },
                ],
                questions_to_review: [
                  {
                    question_id: "grade-written",
                    question_number: 2,
                    question_text: "Describe the arrangement.",
                    outcome: "graded",
                    next_step: "Revise the missing arrangement detail.",
                    criteria_to_review: [
                      {
                        criterion: "Arrangement",
                        marks_allocated: 2,
                        marks_awarded: 1.5,
                        feedback: "One detail is missing.",
                      },
                    ],
                  },
                ],
              }
            : null,
          grading: {
            status: state,
            can_retry: state === "failed",
            completed_questions: completed ? 2 : 1,
            total_questions: 2,
          },
          questions: questions.map((q) => ({
            ...q,
            ...(released && q.question_type === "mcq"
              ? { correct_option: "B" }
              : {}),
          })),
          responses: [
            { question: questions[0], selected_option: "B", is_correct: true },
            {
              question: questions[1],
              text_answer: "My persisted explanation.",
              ai_score: completed ? "1.50" : null,
              ai_evaluation_status: completed ? "completed" : "failed",
              ai_feedback: { feedback: "Reference-based feedback." },
              ai_rubric_breakdown: [
                {
                  criterion: "Arrangement",
                  marks_allocated: 2,
                  marks_awarded: 1.5,
                  feedback: "One detail is missing.",
                },
              ],
            },
            {
              question: questions[2],
              text_answer: "",
              ai_score: "0.00",
              ai_evaluation_status: "completed",
            },
          ],
        },
      });
      return true;
    }
    if (url.pathname === "/api/quiz-attempts/graded-formal/missed/") {
      await route.fulfill({
        json: { missed_questions: [], total_missed: released ? 0 : null },
      });
      return true;
    }
  });
  await page.goto("/quiz/attempt/graded-formal/results");
  await expect(
    page.getByText(
      "Grading could not finish. Your answers and completed marks are saved.",
      { exact: true },
    ),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Retry grading", exact: true })
    .click();
  await expect(
    page.getByRole("alert").filter({ hasText: "Grading queue unavailable" }),
  ).toBeVisible();
  await expect(
    page.getByText("My persisted explanation.", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Retry grading", exact: true })
    .click();
  await expect(
    page.getByText("Your written answers are queued for grading.", {
      exact: true,
    }),
  ).toBeVisible();
  state = "completed";
  await page
    .getByRole("button", { name: "Refresh result", exact: true })
    .click();
  await expect(
    page.getByText("Written grading complete.", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Overall mark: 2.5 / 5", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Written mark: 1.50 / 2", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Written mark: 0.00 / 2", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Feedback: Reference-based feedback.", { exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByText("Study guidance from this paper", { exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Retry grading", exact: true }),
  ).toHaveCount(0);
  released = true;
  await page
    .getByRole("button", { name: "Refresh result", exact: true })
    .click();
  await expect(
    page.getByText("Feedback: Reference-based feedback.", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Arrangement: 1.5 / 2", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Study guidance from this paper", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Revise the missing arrangement detail.", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText(/too few questions to infer a pattern/),
  ).toBeVisible();
  expect(retries).toBe(2);
});

test("assessment history opens preserved legacy responses without offering resume or verified marks", async ({
  page,
}) => {
  test.setTimeout(120000);
  let writes = 0;
  const record = {
    id: "old-record",
    exam_type: "formal",
    status: "in_progress",
    historical_read_only: true,
    history_notice:
      "The original question versions were not saved. This record is read-only.",
    recorded_result: null,
    questions: [],
    responses: [{ text_answer: "My saved historical answer" }],
    question_ids: [],
    flagged_questions: [],
    is_timed: false,
    time_remaining_seconds: null,
  };
  await fixtures(page, async (route, url) => {
    if (url.pathname === "/api/quiz-attempts/") {
      await route.fulfill({ json: { results: [record], next: null } });
      return true;
    }
    if (url.pathname.startsWith("/api/quiz-attempts/old-record/")) {
      if (route.request().method() !== "GET") writes++;
      await route.fulfill({
        json: url.pathname.endsWith("/missed/")
          ? { missed_questions: [] }
          : record,
      });
      return true;
    }
  });
  await page.request.get("/quiz/attempt/old-record/results");
  await page.goto("/quiz/history");
  await expect(
    page.getByText("Historical record — unverified", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("link", { name: "View historical record", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Historical assessment record" }),
  ).toBeVisible();
  await expect(
    page.getByText("My saved historical answer", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("This attempt was never submitted.", { exact: true }),
  ).toBeVisible();
  await page.goto("/quiz/attempt/old-record");
  await expect(page).toHaveURL(/old-record\/results$/);
  await expect(
    page.getByRole("button", { name: "Submit Exam", exact: true }),
  ).toHaveCount(0);
  expect(writes).toBe(0);
});

test("analytics shows study-only evidence and ignores stale period responses", async ({
  page,
}) => {
  test.setTimeout(120000);
  let releaseOld: (() => void) | undefined;
  let oldRequested = false;
  const report = (days: number) => ({
    window_days: days,
    is_premium: false,
    include_detail: false,
    overview: {
      has_data: true,
      attempted: 0,
      correct: 0,
      incorrect: 0,
      accuracy: null,
      sessions: 2,
      study_minutes: days,
    },
    improvement: {
      direction: "insufficient_data",
      earlier_accuracy: null,
      recent_accuracy: null,
      change: null,
      note: "More scored items are needed.",
    },
    consistency: {
      active_days: 1,
      window_days: days,
      current_streak: 1,
      longest_streak: 1,
      active_rate: 1 / days,
      total_minutes: days,
      average_minutes_per_active_day: days,
    },
    daily_activity: [{ date: "2026-10-20", minutes: days, sessions: 2 }],
    by_assessment: [],
    practice: {},
    evidence: {
      note: `Evidence for ${days} days includes today's study.`,
      historical_assessments_excluded: 1,
      assessments_awaiting_written_grades: 0,
    },
  });
  await fixtures(page, async (route, url) => {
    if (url.pathname !== "/api/learning/analytics/") return;
    const days = Number(url.searchParams.get("days"));
    if (days === 7) {
      oldRequested = true;
      await new Promise<void>((resolve) => {
        releaseOld = resolve;
      });
    }
    await route.fulfill({ json: report(days) });
    return true;
  });
  await page.goto("/analytics");
  await expect(
    page.getByText("Evidence for 30 days includes today's study.", {
      exact: true,
    }),
  ).toBeVisible();
  await page.getByRole("button", { name: "7 days", exact: true }).click();
  await expect.poll(() => oldRequested).toBe(true);
  await page.getByRole("button", { name: "90 days", exact: true }).click();
  await expect(
    page.getByText("Evidence for 90 days includes today's study.", {
      exact: true,
    }),
  ).toBeVisible();
  const oldResponse = page.waitForResponse(
    (response) =>
      response.url().includes("/api/learning/analytics/") &&
      response.url().includes("days=7"),
  );
  releaseOld?.();
  await oldResponse;
  await expect(
    page.getByText("Evidence for 90 days includes today's study.", {
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByText("Not enough activity yet", { exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByText(
      "1 historical assessments excluded; 0 assessments awaiting written grades.",
      { exact: true },
    ),
  ).toBeVisible();
});

for (const premium of [false, true]) {
  test(`question bank coverage remains visible without activity for ${premium ? "premium" : "free"} students`, async ({
    page,
  }) => {
    test.setTimeout(120000);
    await fixtures(
      page,
      async (route, url) => {
        if (url.pathname !== "/api/learning/analytics/") return;
        await route.fulfill({
          json: {
            window_days: 30,
            is_premium: premium,
            include_detail: premium,
            overview: {
              has_data: false,
              attempted: 0,
              correct: 0,
              accuracy: null,
              sessions: 0,
              study_minutes: 0,
            },
            improvement: {
              direction: "insufficient_data",
              note: "More evidence is needed.",
            },
            consistency: {
              active_days: 0,
              window_days: 30,
              current_streak: 0,
              active_rate: 0,
              average_minutes_per_active_day: 0,
            },
            daily_activity: [],
            by_assessment: [],
            practice: {},
            question_bank: {
              total: 10,
              seen: 2,
              unseen: 8,
              answered: 1,
              missed: 1,
              percent_seen: 20,
            },
            ...(premium
              ? { topics: { tracked_nodes: 0, weakest: [], strongest: [] } }
              : {}),
          },
        });
        return true;
      },
      { ...profile, is_premium: premium },
    );
    await page.goto("/analytics");
    await expect(
      page.getByText("Not enough activity yet", { exact: true }),
    ).toBeVisible();
    const bank = page.getByRole("region", { name: "Question bank coverage" });
    await expect(bank).toContainText("2 of 10 seen");
    await expect(bank).toContainText("20% seen");
    await expect(bank).toContainText("all-time");
  });
}

test("class analytics retries and uses the actual roster names, points and streaks", async ({
  page,
}) => {
  test.setTimeout(120000);
  let failed = true;
  await fixtures(
    page,
    async (route, url) => {
      if (url.pathname !== "/auth/class/members/") return;
      if (failed) {
        failed = false;
        await route.fulfill({ status: 503, json: {} });
        return true;
      }
      await route.fulfill({
        json: [
          {
            id: 1,
            user: {
              id: 10,
              first_name: "Ada",
              last_name: "Okafor",
              username: "ada",
            },
            total_points: 20,
            streak_days: 4,
          },
          {
            id: 2,
            user: { id: 11, first_name: "", last_name: "", username: "sam" },
            total_points: 60,
            streak_days: 2,
          },
        ],
      });
      return true;
    },
    { ...profile, class_role: "class_head", class_head_verified: true },
  );
  await page.goto("/class/analytics");
  await expect(
    page.getByText("Could not load class analytics. Please try again."),
  ).toBeVisible();
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await expect(
    page.getByText("Average Points", { exact: true }).locator(".."),
  ).toContainText("40");
  await expect(
    page.getByText("Average Streak", { exact: true }).locator(".."),
  ).toContainText("3 days");
  const leaders = page
    .getByRole("heading", { name: "Top members by points" })
    .locator("..");
  await expect(leaders).toContainText("Ada Okafor");
  await expect(leaders).toContainText("sam");
  await expect(
    leaders.getByText("sam", { exact: true }).locator(".."),
  ).toContainText("60 points");
});

test("header streak refreshes after activity and ignores a superseded response", async ({
  page,
}) => {
  test.setTimeout(120000);
  let calls = 0;
  let held: Route | undefined;
  await fixtures(page, async (route, url) => {
    if (url.pathname === "/api/stats/me/") {
      calls++;
      if (calls === 2) {
        held = route;
        return true;
      }
      await route.fulfill({ json: { current_streak: calls >= 3 ? 4 : 1 } });
      return true;
    }
    return readerResponse(route, url);
  });
  await page.goto("/read/anatomy/reader-a");
  await expect(
    page.getByRole("button", { name: "Current streak", exact: true }),
  ).toHaveText("1");
  // A saved page is a real API mutation and triggers the shared refresh hook.
  await page
    .getByRole("navigation", { name: "Page navigation" })
    .getByRole("button", { name: "Next" })
    .click();
  await expect.poll(() => Boolean(held)).toBe(true);
  await page
    .getByRole("navigation", { name: "Page navigation" })
    .getByRole("button", { name: "Next" })
    .click();
  await expect(
    page.getByRole("button", { name: "Current streak", exact: true }),
  ).toHaveText("4");
  await held?.fulfill({ json: { current_streak: 99 } }).catch(() => {});
  await expect(
    page.getByRole("button", { name: "Current streak", exact: true }),
  ).toHaveText("4");
});

test("upload validation leaves the form usable and a failed upload can be retried", async ({
  page,
}) => {
  test.setTimeout(120000);
  let uploads = 0;
  const requestIds: string[] = [];
  await fixtures(page, async (route, url) => {
    if (url.pathname === "/api/slides/upload_and_process/") {
      uploads++;
      expect(route.request().headers()["content-type"]).toContain(
        "multipart/form-data; boundary=",
      );
      expect(route.request().postData()).not.toContain('name="topic"');
      expect(route.request().postData()).toContain(
        'name="title"\r\n\r\nlecture',
      );
      const requestId = route
        .request()
        .postData()
        ?.match(/name="request_id"\r\n\r\n([^\r]+)/)?.[1];
      expect(requestId).toMatch(/^[0-9a-f-]{36}$/);
      requestIds.push(requestId!);
      await route.fulfill(
        uploads === 1
          ? {
              status: 502,
              json: { error: "File storage is unavailable. Please try again." },
            }
          : { status: 201, json: { id: "saved-slide", page_count: 0 } },
      );
      return true;
    }
  });
  await page.goto("/courses/anatomy/upper/hand/opaque-topic-42");
  await page
    .getByRole("button", { name: "Upload slides", exact: true })
    .click();
  await page.getByRole("button", { name: "Anatomy", exact: true }).click();
  await page.getByRole("button", { name: "Upper limb", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Bones", exact: true }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Hand", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Bones", exact: true }),
  ).toHaveCount(0);
  const file = page.locator('input[type="file"]');
  await file.setInputFiles({
    name: "bad.exe",
    mimeType: "application/octet-stream",
    buffer: Buffer.from("MZ"),
  });
  await expect(
    page.getByRole("alert").filter({ hasText: "Choose a PDF" }),
  ).toBeVisible();
  await expect(file).toBeAttached();
  await file.setInputFiles({
    name: "lecture.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("%PDF-1.7\nsource"),
  });
  await page.locator('form button[type="submit"]').click();
  await expect(page.locator('form [role="alert"]')).toContainText(
    "File storage is unavailable",
  );
  await expect(page.locator("#slide-title")).toHaveValue("lecture");
  await expect(page.locator('form button[type="submit"]')).toBeEnabled();
  await page.locator('form button[type="submit"]').click();
  await expect(page.locator("#slide-title")).toHaveCount(0);
  expect(uploads).toBe(2);
  expect(requestIds[0]).toBe(requestIds[1]);
});

test("upload progress refreshes expired login, shows page counts and survives automatic retry on mobile", async ({
  page,
}) => {
  test.setTimeout(120000);
  await page.setViewportSize({ width: 390, height: 844 });
  let polls = 0,
    refreshes = 0;
  let phase = "rendering";
  await fixtures(page, async (route, url) => {
    if (url.pathname === "/api/slides/upload_and_process/") {
      await route.fulfill({
        status: 201,
        json: { id: "saved-slide", page_count: 0 },
      });
      return true;
    }
    if (url.pathname === "/auth/token/refresh/") {
      refreshes++;
      await route.fulfill({ json: { access: "refreshed-upload-access" } });
      return true;
    }
    if (url.pathname === "/api/slides/saved-slide/status/") {
      polls++;
      if (polls === 1)
        await route.fulfill({ status: 401, json: { detail: "Token expired" } });
      else {
        expect(route.request().headers().authorization).toBe(
          "Bearer refreshed-upload-access",
        );
        await route.fulfill({
          json:
            phase === "rendering"
              ? {
                  status: "converting_to_jpg",
                  reading_ready: false,
                  progress: { phase: "rendering", completed: 4, total: 16 },
                }
              : phase === "retry"
                ? {
                    status: "failed",
                    next_attempt_at: new Date(Date.now() + 60000).toISOString(),
                    attempts: 1,
                  }
                : { status: "indexing", reading_ready: true },
        });
      }
      return true;
    }
  });
  await page.goto("/courses/anatomy/upper/hand/opaque-topic-42");
  await page
    .getByRole("button", { name: "Upload slides", exact: true })
    .click();
  await page.getByRole("button", { name: "Anatomy", exact: true }).click();
  await page.getByRole("button", { name: "Upper limb", exact: true }).click();
  await page.locator('input[type="file"]').setInputFiles({
    name: "lecture.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.concat([
      Buffer.from("%PDF-1.7\n"),
      Buffer.alloc(2 * 1024 * 1024, 32),
    ]),
  });
  await page.locator('form button[type="submit"]').click();
  const progress = page.getByRole("region", { name: "Upload progress" });
  await expect(progress).toContainText("Rendering pages 4 of 16");
  expect(refreshes).toBe(1);
  phase = "retry";
  await expect(progress).toContainText("Automatic retry scheduled");
  phase = "ready";
  await expect(progress).toContainText(
    "Ready to read. AI study tools prepare separately.",
  );
  await expect(
    progress.getByRole("link", { name: "Open document" }),
  ).toHaveAttribute("href", "/read/upper/saved-slide");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});

test("standalone upload preserves its request after response loss and creates a new intent for edits", async ({
  page,
}) => {
  test.setTimeout(120000);
  const requestIds: string[] = [];
  await fixtures(page, async (route, url) => {
    if (url.pathname === "/api/decks/" && route.request().method() === "POST") {
      expect(route.request().headers()["content-type"]).toContain(
        "multipart/form-data; boundary=",
      );
      const requestId = route
        .request()
        .postData()
        ?.match(/name="request_id"\r\n\r\n([^\r]+)/)?.[1];
      expect(requestId).toMatch(/^[0-9a-f-]{36}$/);
      requestIds.push(requestId!);
      await route.fulfill({
        status: 502,
        json: { detail: "Response lost. Try again." },
      });
      return true;
    }
  });
  await page.goto("/decks");
  await expect(
    page.getByText("PDF, PPTX, PPT, DOCX • Max 100 MB", { exact: true }),
  ).toBeVisible();
  const file = page.locator('input[type="file"]');
  await file.setInputFiles({
    name: "empty.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.alloc(0),
  });
  await expect(
    page.getByRole("alert").filter({ hasText: "The file is empty" }),
  ).toBeVisible();
  await file.setInputFiles({
    name: "lecture.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("%PDF-1.7\nsource"),
  });
  const button = page.getByRole("button", {
    name: "Upload Document",
    exact: true,
  });
  await button.click();
  await expect.poll(() => requestIds.length).toBe(1);
  await expect(button).toBeEnabled();
  await button.click();
  await expect.poll(() => requestIds.length).toBe(2);
  await expect(button).toBeEnabled();
  await page.getByPlaceholder("e.g., Anatomy Lecture 01").fill("Changed title");
  await button.click();
  await expect.poll(() => requestIds.length).toBe(3);
  await expect(button).toBeEnabled();
  await expect(
    page.getByRole("alert").filter({ hasText: "Response lost. Try again." }),
  ).toBeVisible();
  expect(requestIds[0]).toBe(requestIds[1]);
  expect(requestIds[2]).not.toBe(requestIds[1]);
});

test("standalone uploads are hidden from students", async ({ page }) => {
  await fixtures(page, undefined, { ...profile, class_role: "student" });
  await page.goto("/decks");
  await expect(
    page.getByRole("heading", { name: "Documents", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Upload Document", exact: true }),
  ).toHaveCount(0);
  await expect(page.locator('input[type="file"]')).toHaveCount(0);
});

test("topic navigation filters slides and materials to the selected branch", async ({
  page,
}) => {
  const queries: URL[] = [];
  await fixtures(page, async (route, url) => {
    if (["/api/slides/", "/api/materials/"].includes(url.pathname)) {
      queries.push(url);
      await route.fulfill({ json: [] });
      return true;
    }
  });
  await page.goto("/courses/anatomy/upper/hand/opaque-topic-42");
  await expect(
    page.getByRole("heading", { name: "Bones", exact: true }),
  ).toBeVisible();
  expect(queries.length).toBeGreaterThanOrEqual(2);
  for (const url of queries) {
    expect(url.searchParams.get("subject")).toBe("anatomy");
    expect(url.searchParams.get("block")).toBe("upper");
    expect(url.searchParams.get("sub_block")).toBe("hand");
    expect(url.searchParams.get("topic")).toBe("opaque-topic-42");
  }
});

test("an API outage is displayed as an error with retry instead of an empty topic", async ({
  page,
}) => {
  let outage = true;
  let documentNavigations = 0;
  page.on("request", (request) => {
    if (request.isNavigationRequest()) documentNavigations++;
  });
  await fixtures(page, async (route, url) => {
    if (url.pathname === "/api/slides/" && outage) {
      await route.fulfill({ status: 503, json: {} });
      return true;
    }
  });
  await page.goto("/courses/anatomy/upper/hand/opaque-topic-42");
  await expect(
    page
      .getByRole("alert")
      .filter({ hasText: "Could not load these materials" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "No materials available" }),
  ).toHaveCount(0);
  outage = false;
  await page.getByRole("button", { name: "Try again", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "No materials available" }),
  ).toBeVisible();
  expect(documentNavigations).toBe(1);
});

test("a three-segment sub-block course path opens materials and exposes slide text retry", async ({
  page,
}) => {
  let retries = 0;
  await fixtures(page, async (route, url) => {
    if (
      url.pathname === "/api/slides/" &&
      url.searchParams.get("sub_block") === "hand"
    ) {
      await route.fulfill({
        json: [
          {
            id: "reader-a",
            title: "Scanned lecture",
            subject: "anatomy",
            block: "upper",
            sub_block: "hand",
            topic: null,
            file_type: "pdf",
            page_count: 1,
          },
        ],
      });
      return true;
    }
    if (url.pathname === "/api/materials/") {
      await route.fulfill({ json: [] });
      return true;
    }
    if (url.pathname === "/api/slides/reader-a/content/") {
      await route.fulfill({
        json: {
          total_pages: 1,
          can_reprocess: true,
          text_extraction: { status: "failed", missing_pages: [1] },
          pages: [
            { page_number: 1, image_url: readerImage, width: 400, height: 300 },
          ],
        },
      });
      return true;
    }
    if (url.pathname === "/api/slides/reader-a/reprocess/") {
      retries++;
      await route.fulfill({ json: { task_id: "isolated-task" } });
      return true;
    }
    return readerResponse(route, url);
  });
  await page.goto("/courses/anatomy/upper/hand");
  await expect(
    page.getByRole("heading", { name: "Hand", exact: true }),
  ).toBeVisible();
  await page.getByRole("link", { name: /Scanned lecture/ }).click();
  const notice = page.getByRole("status", { name: "Document text status" });
  await expect(notice).toContainText("pages 1");
  await notice
    .getByRole("button", { name: "Retry AI preparation", exact: true })
    .click();
  await expect(notice).toContainText("Processing queued");
  expect(retries).toBe(1);
});

test("a direct topic path at the third course segment is resolved as a topic", async ({
  page,
}) => {
  const queries: URL[] = [];
  await fixtures(page, async (route, url) => {
    if (["/api/slides/", "/api/materials/"].includes(url.pathname)) {
      queries.push(url);
      await route.fulfill({ json: [] });
      return true;
    }
  });
  await page.goto("/courses/anatomy/upper/opaque-topic-42");
  await expect(
    page.getByRole("heading", { name: "Bones", exact: true }),
  ).toBeVisible();
  expect(new Set(queries.map((url) => url.pathname))).toEqual(
    new Set(["/api/slides/", "/api/materials/"]),
  );
  for (const url of queries) {
    expect(url.searchParams.get("sub_block")).toBeNull();
    expect(url.searchParams.get("topic")).toBe("opaque-topic-42");
  }
});

test("a topic with an opaque ID resolves its real parent instead of guessing from its name", async ({
  page,
}) => {
  const blockRequests: string[] = [];
  await fixtures(page, async (route, url) => {
    if (url.pathname.startsWith("/api/blocks/"))
      blockRequests.push(url.pathname);
  });
  await page.goto("/courses/opaque-topic-42");
  await expect(
    page.getByRole("heading", { name: "Bones", exact: true }),
  ).toBeVisible();
  expect(blockRequests).toContain("/api/blocks/upper/");
  expect(blockRequests).not.toContain("/api/blocks/opaque-topic/");
});

test("a reader renews private page links on return without losing the current page", async ({
  page,
}) => {
  let pagesRequests = 0;
  const image =
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jYzQAAAAASUVORK5CYII=";
  const pages = [1, 2].map((n) => ({
    id: n,
    slide_number: n,
    image_url: image,
    width: 1,
    height: 1,
  }));
  await fixtures(page, async (route, url) => {
    if (url.pathname === "/api/decks/private-deck/") {
      await route.fulfill({
        json: {
          id: "private-deck",
          title: "Private deck",
          file_type: "pdf",
          processing_status: "completed",
          pages,
        },
      });
      return true;
    }
    if (url.pathname === "/api/decks/private-deck/pages/") {
      pagesRequests++;
      await route.fulfill({ json: pages });
      return true;
    }
  });
  await page.goto("/decks/private-deck");
  await expect(page.getByAltText("Page 1")).toBeVisible();
  await page.getByTitle("Next page", { exact: true }).click();
  await expect(page.getByAltText("Page 2")).toBeVisible();
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await expect.poll(() => pagesRequests).toBeGreaterThan(0);
  await expect(page.getByAltText("Page 2")).toBeVisible();
});

test("a renewed class denial clears a previously opened deck", async ({
  page,
}) => {
  const image =
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jYzQAAAAASUVORK5CYII=";
  await fixtures(page, async (route, url) => {
    if (url.pathname === "/api/decks/private-deck/") {
      await route.fulfill({
        json: {
          id: "private-deck",
          title: "Private deck",
          file_type: "pdf",
          processing_status: "completed",
          pages: [
            { id: 1, slide_number: 1, image_url: image, width: 1, height: 1 },
          ],
        },
      });
      return true;
    }
    if (url.pathname === "/api/decks/private-deck/pages/") {
      await route.fulfill({ status: 404, json: { detail: "Not found" } });
      return true;
    }
  });
  await page.goto("/decks/private-deck");
  await expect(page.getByAltText("Page 1")).toBeVisible();
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await expect(
    page.getByText("This document is no longer available to your class."),
  ).toBeVisible();
  await expect(page.getByAltText("Page 1")).toHaveCount(0);
});

test("a processing deck stops its loading state when class access is revoked", async ({
  page,
}) => {
  let denied = false;
  await fixtures(page, async (route, url) => {
    if (url.pathname === "/api/decks/processing-deck/") {
      await route.fulfill(
        denied
          ? { status: 404, json: {} }
          : {
              json: {
                id: "processing-deck",
                title: "Processing deck",
                file_type: "pdf",
                file_size: 1024,
                processing_status: "processing",
                pages: [],
              },
            },
      );
      return true;
    }
  });
  await page.goto("/decks/processing-deck");
  await expect(page.getByText("Preparing your document")).toBeVisible();
  denied = true;
  await expect(
    page.getByText("This document is no longer available to your class."),
  ).toBeVisible();
  await expect(page.getByText("Preparing your document")).toHaveCount(0);
});

test("reading a saved page does not wait for suggested videos", async ({
  page,
}) => {
  let releaseVideos!: () => void;
  const waiting = new Promise<void>((resolve) => {
    releaseVideos = resolve;
  });
  const image =
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jYzQAAAAASUVORK5CYII=";
  await fixtures(page, async (route, url) => {
    if (url.pathname === "/api/slides/reading-slide/") {
      await route.fulfill({
        json: {
          id: "reading-slide",
          title: "Readable deck",
          subject: "anatomy",
          block: "upper",
          file_type: "pdf",
          page_count: 1,
        },
      });
      return true;
    }
    if (url.pathname === "/api/slides/reading-slide/content/") {
      await route.fulfill({
        json: {
          slide_id: "reading-slide",
          total_pages: 1,
          pages: [
            {
              page_number: 1,
              image_url: image,
              width: 1,
              height: 1,
              text_blocks: [],
            },
          ],
        },
      });
      return true;
    }
    if (url.pathname === "/api/slides/reading-slide/suggest-videos/") {
      await waiting;
      await route.fulfill({ json: { videos: [] } });
      return true;
    }
  });
  try {
    await page.goto("/read/anatomy/reading-slide");
    await expect(page.getByAltText("Page 1", { exact: true })).toBeVisible();
    await expect(
      page.getByText("Loading slide...", { exact: true }),
    ).toHaveCount(0);
  } finally {
    releaseVideos();
  }
});

test("opening a material rechecks access instead of using its cached file link", async ({
  page,
}) => {
  let accessChecks = 0;
  await fixtures(page, async (route, url) => {
    if (url.pathname === "/api/materials/") {
      await route.fulfill({
        json: [
          {
            id: "private-notes",
            title: "Private notes",
            material_type: "pdf",
            file_url: "https://expired.example.test/notes.pdf",
            file_size: 100,
            created_at: "2026-10-16T09:00:00Z",
          },
        ],
      });
      return true;
    }
    if (url.pathname === "/api/materials/private-notes/") {
      accessChecks++;
      await route.fulfill({ status: 404, json: {} });
      return true;
    }
  });
  await page.goto("/courses/anatomy/upper/hand/opaque-topic-42");
  await page.getByRole("button", { name: /Private notes/ }).click();
  await expect(
    page.getByRole("alert").filter({ hasText: "Could not open this file" }),
  ).toBeVisible();
  expect(accessChecks).toBe(1);
});

const readerImage =
  "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jYzQAAAAASUVORK5CYII=";

test("extraction warning names missing pages and supports failed retry then successful refresh", async ({
  page,
}) => {
  let attempts = 0;
  let complete = false;
  await fixtures(page, async (route, url) => {
    if (url.pathname === "/api/slides/reader-a/content/") {
      await route.fulfill({
        json: {
          total_pages: 5,
          can_reprocess: true,
          text_extraction: {
            status: complete ? "complete" : "partial",
            missing_pages: complete ? [] : [2, 4],
          },
          pages: [1, 2, 3, 4, 5].map((page_number) => ({
            page_number,
            image_url: readerImage,
            width: 400,
            height: 300,
          })),
        },
      });
      return true;
    }
    if (url.pathname === "/api/slides/reader-a/reprocess/") {
      attempts++;
      await route.fulfill(
        attempts === 1
          ? { status: 503, json: {} }
          : { json: { task_id: "isolated-task" } },
      );
      return true;
    }
    return readerResponse(route, url);
  });
  await page.goto("/read/anatomy/reader-a");
  const notice = page.getByRole("status", { name: "Document text status" });
  await expect(notice).toContainText("pages 2, 4");
  await expect(page.getByAltText("Page 1", { exact: true })).toBeVisible();
  await notice.getByRole("button", { name: "Retry AI preparation" }).click();
  await expect(notice.getByRole("alert")).toContainText("could not be queued");
  await notice.getByRole("button", { name: "Retry AI preparation" }).click();
  await expect(notice).toContainText("Processing queued");
  expect(attempts).toBe(2);
  complete = true;
  await notice
    .getByRole("button", { name: "Refresh extraction status" })
    .click();
  await expect(page.getByAltText("Page 1", { exact: true })).toBeVisible();
  await expect(notice).toHaveCount(0);
});

test("extraction warning lets students read but reserves retry for authorized uploaders", async ({
  page,
}) => {
  await fixtures(page, async (route, url) => {
    if (url.pathname === "/api/slides/reader-a/content/") {
      await route.fulfill({
        json: {
          total_pages: 1,
          can_reprocess: false,
          text_extraction: { status: "failed", missing_pages: [1] },
          pages: [
            { page_number: 1, image_url: readerImage, width: 400, height: 300 },
          ],
        },
      });
      return true;
    }
    return readerResponse(route, url);
  });
  await page.goto("/read/anatomy/reader-a");
  await expect(
    page.getByRole("status", { name: "Document text status" }),
  ).toContainText("Ask the uploader or class head");
  await expect(
    page.getByRole("button", { name: "Retry AI preparation" }),
  ).toHaveCount(0);
  await expect(page.getByAltText("Page 1", { exact: true })).toBeVisible();
});

test("extraction does not present a legacy unchecked cache as complete", async ({
  page,
}) => {
  await fixtures(page, readerResponse);
  await page.goto("/read/anatomy/reader-a");
  await expect(
    page.getByRole("status", { name: "Document text status" }),
  ).toContainText("has not finished reading");
  await expect(page.getByAltText("Page 1", { exact: true })).toBeVisible();
});

test("standalone extraction reports unreadable text while keeping the original pages visible", async ({
  page,
}) => {
  const pages = [1, 2].map((slide_number) => ({
    slide_number,
    image_url: readerImage,
    width: 400,
    height: 300,
  }));
  await fixtures(page, async (route, url) => {
    if (url.pathname === "/api/decks/extraction-deck/") {
      await route.fulfill({
        json: {
          id: "extraction-deck",
          title: "Scanned document",
          file_type: "pdf",
          processing_status: "completed",
          pages,
          text_extraction: { status: "partial", missing_pages: [2] },
        },
      });
      return true;
    }
    if (url.pathname === "/api/decks/extraction-deck/pages/") {
      await route.fulfill({ json: pages });
      return true;
    }
  });
  await page.goto("/decks/extraction-deck");
  await expect(
    page.getByRole("status", { name: "Document text status" }),
  ).toContainText("pages 2");
  await expect(page.getByAltText("Page 1", { exact: true })).toBeVisible();
});

async function readerResponse(route: Route, url: URL) {
  const match = url.pathname.match(
    /^\/api\/slides\/(reader-[ab])\/(content\/)?$/,
  );
  if (!match) return false;
  await route.fulfill({
    json: match[2]
      ? {
          total_pages: 3,
          pages: [1, 2, 3].map((page_number) => ({
            page_number,
            image_url: readerImage,
            width: 400,
            height: 300,
            text: `Page ${page_number}`,
          })),
        }
      : {
          id: match[1],
          title: `Lecture ${match[1]}`,
          subject: "anatomy",
          file_type: "pdf",
          page_count: 3,
        },
  });
  return true;
}

test("background upload preparation waits for saved pages and opens the reader automatically", async ({
  page,
}) => {
  let ready = false;
  let checks = 0;
  await fixtures(page, async (route, url) => {
    if (url.pathname === "/api/slides/reader-a/content/" && !ready) {
      checks++;
      await route.fulfill({
        status: 202,
        json: {
          slide_id: "reader-a",
          title: "Saved lecture",
          total_pages: 0,
          pages: [],
          processing: true,
          processing_status: "converting_to_jpg",
        },
      });
      return true;
    }
    return readerResponse(route, url);
  });
  await page.goto("/read/anatomy/reader-a");
  await expect(
    page
      .getByRole("status")
      .filter({ hasText: "Upload saved. Preparing your slide pages..." }),
  ).toBeVisible();
  await expect(
    page.getByRole("alert").filter({ hasText: "Could not load this document" }),
  ).toHaveCount(0);
  ready = true;
  await expect(page.getByAltText("Page 1", { exact: true })).toBeVisible();
  expect(checks).toBeGreaterThan(0);
  await expect(
    page.getByText("Upload saved. Preparing your slide pages..."),
  ).toHaveCount(0);
});

test("visual slide preparation keeps scanned pages readable and sends the selected page to chat", async ({
  page,
}) => {
  test.setTimeout(180000);
  let ready = false;
  let sent = false;
  await fixtures(page, async (route, url) => {
    if (url.pathname === "/api/slides/reader-a/content/") {
      await route.fulfill({
        json: {
          total_pages: 2,
          can_reprocess: true,
          ai_index: { status: ready ? "complete" : "running" },
          text_extraction: {
            status: ready ? "complete" : "failed",
            missing_pages: ready ? [] : [1, 2],
          },
          pages: [1, 2].map((page_number) => ({
            page_number,
            image_url: readerImage,
            width: 400,
            height: 300,
            text: "",
          })),
        },
      });
      return true;
    }
    if (url.pathname === "/api/slides/reader-a/status/") {
      await route.fulfill({
        json: {
          reading_ready: true,
          status: "indexing",
          ai_index: { status: ready ? "complete" : "running" },
          question_bank: {
            status: "not_requested",
            mcq_target: 15,
            theory_target: 10,
            mcq_by_difficulty: {},
            theory_by_difficulty: {},
          },
        },
      });
      return true;
    }
    if (url.pathname === "/api/ai/chat/") {
      const body = route.request().postDataJSON();
      expect(body.slide_id).toBe("reader-a");
      expect(body.page_number).toBe(2);
      expect(body.slide_image_base64).toBeUndefined();
      sent = true;
      await route.fulfill({
        json: { response: "The image shows the heart. [Page 2]" },
      });
      return true;
    }
    return readerResponse(route, url);
  });
  await page.goto("/read/anatomy/reader-a");
  await expect(page.getByAltText("Page 1", { exact: true })).toBeVisible();
  const notice = page.getByRole("status", { name: "Document text status" });
  await expect(notice).toContainText("Ready to read");
  await expect(
    notice.getByRole("button", { name: "Retry AI preparation" }),
  ).toHaveCount(0);
  await page
    .getByRole("navigation", { name: "Page navigation" })
    .getByRole("button", { name: "Next" })
    .click();
  await page
    .getByRole("textbox", { name: "Ask the Emby tutor" })
    .fill("Explain the diagram");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(
    page.getByText("The image shows the heart. [Page 2]", { exact: true }),
  ).toBeVisible();
  expect(sent).toBe(true);
  ready = true;
  await expect(notice).toHaveCount(0, { timeout: 25000 });
  await expect(page.getByAltText("Page 2", { exact: true })).toBeVisible();
});

test("reader page failures have a working retry instead of an empty document", async ({
  page,
}) => {
  let failed = true;
  await fixtures(page, async (route, url) => {
    if (url.pathname === "/api/slides/reader-a/content/" && failed) {
      await route.fulfill({ status: 503, json: {} });
      return true;
    }
    return readerResponse(route, url);
  });
  await page.goto("/read/anatomy/reader-a");
  await expect(
    page.getByRole("alert").filter({ hasText: "Could not load this document" }),
  ).toBeVisible();
  failed = false;
  await page.getByRole("button", { name: "Try again", exact: true }).click();
  await expect(page.getByAltText("Page 1", { exact: true })).toBeVisible();
});

test("reader navigation saves immediately and resumes the saved page after reload", async ({
  page,
}) => {
  let savedPage = 1;
  const minutes: number[] = [];
  await fixtures(page, async (route, url) => {
    if (url.pathname === "/api/progress/") {
      await route.fulfill({
        json: [{ slide: "reader-a", current_page: savedPage }],
      });
      return true;
    }
    if (url.pathname === "/api/progress/update_progress/") {
      const body = route.request().postDataJSON();
      savedPage = body.current_page;
      minutes.push(body.seconds);
      await route.fulfill({ json: body });
      return true;
    }
    return readerResponse(route, url);
  });
  await page.goto("/read/anatomy/reader-a");
  await expect(page.getByAltText("Page 1", { exact: true })).toBeVisible();
  await expect(
    page
      .getByRole("navigation", { name: "Page navigation" })
      .getByRole("button", { name: "Previous" }),
  ).toBeDisabled();
  await page
    .getByRole("navigation", { name: "Page navigation" })
    .getByRole("button", { name: "Next" })
    .click();
  await expect.poll(() => savedPage).toBe(2);
  await page.reload();
  await expect(page.getByAltText("Page 2", { exact: true })).toBeVisible();
  await page
    .getByRole("navigation", { name: "Page navigation" })
    .getByRole("button", { name: "Next" })
    .click();
  await expect.poll(() => savedPage).toBe(3);
  await expect(
    page
      .getByRole("navigation", { name: "Page navigation" })
      .getByRole("button", { name: "Next" }),
  ).toBeDisabled();
  expect(
    minutes.every(
      (value) => Number.isInteger(value) && value >= 0 && value < 60,
    ),
  ).toBe(true);
});

test("a failed position save can be retried without losing the visible page", async ({
  page,
}) => {
  let fail = true,
    saved = 0;
  await fixtures(page, async (route, url) => {
    if (url.pathname === "/api/progress/update_progress/") {
      if (!fail) saved = route.request().postDataJSON().current_page;
      await route.fulfill(fail ? { status: 503, json: {} } : { json: {} });
      return true;
    }
    return readerResponse(route, url);
  });
  await page.goto("/read/anatomy/reader-a");
  await page
    .getByRole("navigation", { name: "Page navigation" })
    .getByRole("button", { name: "Next" })
    .click();
  await expect(
    page.getByRole("button", { name: "Retry saving" }),
  ).toBeVisible();
  fail = false;
  await page.getByRole("button", { name: "Retry saving" }).click();
  await expect.poll(() => saved).toBe(2);
  await expect(page.getByAltText("Page 2", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Retry saving" })).toHaveCount(
    0,
  );
});

test("course reading preserves failed timed checkpoints across reload and excludes hidden time", async ({
  page,
}) => {
  test.setTimeout(120000);
  await page.clock.install();
  let fail = true,
    savedPage = 2;
  const writes: any[] = [];
  await fixtures(page, async (route, url) => {
    if (url.pathname === "/api/progress/") {
      await route.fulfill({
        json: [{ slide: "reader-a", current_page: savedPage }],
      });
      return true;
    }
    if (url.pathname === "/api/progress/update_progress/") {
      const body = route.request().postDataJSON();
      writes.push(body);
      if (!fail) savedPage = body.current_page;
      await route.fulfill(fail ? { status: 503, json: {} } : { json: body });
      return true;
    }
    return readerResponse(route, url);
  });
  await page.goto("/read/anatomy/reader-a");
  await expect(page.getByAltText("Page 2", { exact: true })).toBeVisible();
  await page.clock.runFor(16000);
  await expect(
    page.getByRole("button", { name: "Retry saving", exact: true }),
  ).toBeVisible();
  const failedCheckpoint = writes[0];
  // The first interval begins before the resumed image finishes loading.
  expect(failedCheckpoint.seconds).toBeGreaterThan(0);
  expect(failedCheckpoint.seconds).toBeLessThanOrEqual(16);
  await page
    .getByRole("navigation", { name: "Page navigation" })
    .getByRole("button", { name: "Next" })
    .click();
  fail = false;
  await page.reload();
  await expect(page.getByAltText("Page 3", { exact: true })).toBeVisible();
  await expect.poll(() => savedPage).toBe(3);
  expect(
    writes.findLast((row) => row.request_id === failedCheckpoint.request_id),
  ).toEqual(failedCheckpoint);
  expect(
    writes.filter((row) => row.request_id === failedCheckpoint.request_id),
  ).toHaveLength(2);
  await page.clock.runFor(16000);
  await page.evaluate(() => {
    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      get: () => "hidden",
    });
    document.dispatchEvent(new Event("visibilitychange"));
  });
  await expect
    .poll(() =>
      page.evaluate(() =>
        Object.keys(sessionStorage)
          .filter((key) => key.startsWith("emby:course-reading:"))
          .every(
            (key) => JSON.parse(sessionStorage.getItem(key)!).length === 0,
          ),
      ),
    )
    .toBe(true);
  const total = writes.reduce((sum, row) => sum + row.seconds, 0);
  await page.clock.runFor(30000);
  expect(writes.reduce((sum, row) => sum + row.seconds, 0)).toBe(total);
});

test("course reading clamps an outdated saved page before recording new time", async ({
  page,
}) => {
  test.setTimeout(120000);
  await page.clock.install();
  const writes: any[] = [];
  await fixtures(page, async (route, url) => {
    if (url.pathname === "/api/progress/") {
      await route.fulfill({ json: [{ slide: "reader-a", current_page: 99 }] });
      return true;
    }
    if (url.pathname === "/api/progress/update_progress/") {
      writes.push(route.request().postDataJSON());
      await route.fulfill({ json: {} });
      return true;
    }
    return readerResponse(route, url);
  });
  await page.goto("/read/anatomy/reader-a");
  await expect(page.getByAltText("Page 3", { exact: true })).toBeVisible();
  await page.clock.runFor(16000);
  await expect.poll(() => writes.length).toBeGreaterThan(0);
  expect(writes.every((row) => row.current_page === 3 && row.seconds > 0)).toBe(
    true,
  );
});

for (const mode of ["course", "standalone"] as const) {
  test(`${mode} reading recovers an explicitly discarded removed-page save after reload`, async ({
    page,
  }) => {
    test.setTimeout(120000);
    const source = mode === "course" ? "reader-a" : "removed-reader";
    const namespace = mode === "course" ? "course-reading" : "deck-reading";
    const key = `emby:${namespace}:${JSON.stringify([42, 1, "material_uploader"])}:${source}`;
    const removed = {
      current_page: 99,
      seconds: 17,
      request_id: "d04f1891-d519-4457-81dc-a32c22443a07",
    };
    const writes: any[] = [];
    let savedPage = 1;
    await fixtures(page, async (route, url) => {
      const progress =
        mode === "course"
          ? "/api/progress/"
          : `/api/decks/${source}/reading-progress/`;
      const save =
        mode === "course" ? "/api/progress/update_progress/" : progress;
      if (url.pathname === save && route.request().method() === "POST") {
        const body = route.request().postDataJSON();
        writes.push(body);
        if (body.current_page === 99) {
          await route.fulfill({
            status: 400,
            json: { code: "reading_page_unavailable", detail: "Page removed" },
          });
        } else {
          savedPage = body.current_page;
          await route.fulfill({ json: body });
        }
        return true;
      }
      if (url.pathname === progress) {
        await route.fulfill({
          json:
            mode === "course"
              ? [{ slide: source, current_page: savedPage }]
              : { current_page: savedPage, total_seconds: 0 },
        });
        return true;
      }
      if (mode === "course") return readerResponse(route, url);
      const pages = [1, 2, 3].map((n) => ({
        id: n,
        slide_number: n,
        image_url: readerImage,
      }));
      if (url.pathname === `/api/decks/${source}/pages/`) {
        await route.fulfill({ json: pages });
        return true;
      }
      if (url.pathname === `/api/decks/${source}/`) {
        await route.fulfill({
          json: {
            id: source,
            title: "Changed document",
            file_type: "pdf",
            page_count: 3,
            processing_status: "completed",
            pages,
          },
        });
        return true;
      }
    });
    await page.addInitScript(
      ({ key, removed }) => {
        if (!sessionStorage.getItem(`${key}:seeded`)) {
          sessionStorage.setItem(key, JSON.stringify([removed]));
          sessionStorage.setItem(`${key}:seeded`, "true");
        }
      },
      { key, removed },
    );
    await page.goto(
      mode === "course" ? `/read/anatomy/${source}` : `/decks/${source}`,
    );
    await expect(page.getByAltText("Page 3", { exact: true })).toBeVisible();
    await expect(
      page
        .getByRole("alert")
        .filter({ hasText: "Page 99 is no longer available" }),
    ).toContainText("17 seconds");
    await page.reload();
    await expect(
      page.getByRole("button", { name: "Discard this save", exact: true }),
    ).toBeVisible();
    await expect(page.getByAltText("Page 3", { exact: true })).toBeVisible();
    expect(
      writes.filter((row) => row.request_id === removed.request_id).length,
    ).toBeGreaterThanOrEqual(2);
    expect(
      writes
        .filter((row) => row.request_id === removed.request_id)
        .every((row) => row.current_page === 99 && row.seconds === 17),
    ).toBe(true);
    const previous =
      mode === "course"
        ? page
            .getByRole("navigation", { name: "Page navigation" })
            .getByRole("button", { name: "Previous" })
        : page.getByTitle("Previous page", { exact: true });
    await previous.click();
    expect(savedPage).toBe(1); // Later saves remain queued until the student chooses recovery.
    await page
      .getByRole("button", { name: "Discard this save", exact: true })
      .click();
    await expect.poll(() => savedPage).toBe(2);
    await expect(
      page.getByRole("button", { name: "Discard this save", exact: true }),
    ).toHaveCount(0);
    await expect
      .poll(() =>
        page.evaluate(
          (key) =>
            JSON.parse(sessionStorage.getItem(key) ?? "[]").some(
              (row: any) => row.current_page === 99,
            ),
          key,
        ),
      )
      .toBe(false);
    expect(
      writes
        .filter((row) => row.request_id !== removed.request_id)
        .every((row) => row.current_page <= 3),
    ).toBe(true);
  });
}

test("course reading waits for the page image and stops when progress access is revoked", async ({
  page,
}) => {
  test.setTimeout(120000);
  await page.clock.install();
  let imageRequest: Route | undefined,
    revoked = false;
  const writes: any[] = [];
  await fixtures(page, async (route, url) => {
    if (url.pathname === "/api/reader-image/") {
      imageRequest = route;
      return true;
    }
    if (url.pathname === "/api/slides/reader-a/content/") {
      await route.fulfill({
        json: {
          total_pages: 3,
          pages: [1, 2, 3].map((page_number) => ({
            page_number,
            image_url: "http://127.0.0.1:8600/api/reader-image/",
            text: "Page",
          })),
        },
      });
      return true;
    }
    if (url.pathname === "/api/progress/update_progress/") {
      writes.push(route.request().postDataJSON());
      await route.fulfill(revoked ? { status: 403, json: {} } : { json: {} });
      return true;
    }
    return readerResponse(route, url);
  });
  await page.goto("/read/anatomy/reader-a", { waitUntil: "domcontentloaded" });
  await expect.poll(() => Boolean(imageRequest)).toBe(true);
  await page.clock.runFor(30000);
  expect(writes).toEqual([]);
  await imageRequest!.fulfill({
    contentType: "image/svg+xml",
    body: '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300"><rect width="400" height="300" fill="white"/></svg>',
  });
  await expect
    .poll(() =>
      page
        .getByAltText("Page 1", { exact: true })
        .evaluate((el: HTMLImageElement) => el.complete && el.naturalWidth > 0),
    )
    .toBe(true);
  await page.clock.runFor(16000);
  await expect.poll(() => writes.some((row) => row.seconds >= 15)).toBe(true);
  revoked = true;
  await page.clock.runFor(16000);
  await expect(
    page
      .getByRole("alert")
      .filter({ hasText: "no longer available to your class" }),
  ).toBeVisible();
  await expect(
    page.getByRole("article", { name: "Study material" }),
  ).toHaveCount(0);
  const before = writes.length;
  await page.clock.runFor(30000);
  expect(writes).toHaveLength(before);
});

test("mobile reader expands and zooms a page without horizontal layout overflow", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await fixtures(page, readerResponse);
  await page.goto("/read/anatomy/reader-a");
  await page
    .getByRole("button", { name: "Expand page 1", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.getByRole("button", { name: "Zoom in", exact: true }).click();
  await expect(page.getByLabel("Zoom level")).toHaveText("125%");
  await page.getByRole("button", { name: "Fit page", exact: true }).click();
  await expect(page.getByLabel("Zoom level")).toHaveText("100%");
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});

test("late AI replies cannot appear in another document", async ({ page }) => {
  const premium = {
    ...profile,
    class_role: "class_head",
    class_head_verified: true,
    is_premium: true,
  };
  let pending: Route | undefined;
  await fixtures(
    page,
    async (route, url) => {
      if (url.pathname === "/auth/profile/") {
        await route.fulfill({ json: premium });
        return true;
      }
      if (url.pathname === "/api/ai/chat/") {
        pending = route;
        return true;
      }
      return readerResponse(route, url);
    },
    premium,
  );
  await page.goto(
    "/read/anatomy/reader-a?session=true&step=1&queue=reader-a,reader-b",
  );
  await page.getByRole("button", { name: "Summarise", exact: true }).click();
  await expect.poll(() => Boolean(pending)).toBe(true);
  await page
    .locator("footer")
    .getByRole("button", { name: "Next", exact: true })
    .click();
  await expect(page).toHaveURL(/reader-b\?/);
  await expect(
    page
      .getByRole("article", { name: "Study material" })
      .getByAltText("Page 1", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Lecture reader-b — Page 1", { exact: true }),
  ).toBeVisible();
  await pending!.fulfill({
    json: { response: "PRIVATE REPLY FROM THE PREVIOUS DOCUMENT" },
  });
  await expect(page.getByLabel("Ask the Emby tutor")).toBeEnabled();
  await expect(
    page.getByText("PRIVATE REPLY FROM THE PREVIOUS DOCUMENT"),
  ).toHaveCount(0);
});

test("standalone reading resumes, records visible time and restores the saved page after reload", async ({
  page,
}) => {
  test.setTimeout(120000);
  let savedPage = 2;
  const writes: {
    current_page: number;
    seconds: number;
    request_id: string;
  }[] = [];
  await page.clock.install();
  await fixtures(page, async (route, url) => {
    if (url.pathname === "/api/decks/timed-reader/pages/") {
      await route.fulfill({
        json: [1, 2, 3].map((n) => ({
          id: n,
          slide_number: n,
          image_url: readerImage,
        })),
      });
      return true;
    }
    if (url.pathname === "/api/decks/timed-reader/") {
      await route.fulfill({
        json: {
          id: "timed-reader",
          title: "Timed reader",
          file_type: "pdf",
          page_count: 3,
          processing_status: "completed",
          pages: [1, 2, 3].map((n) => ({
            id: n,
            slide_number: n,
            image_url: readerImage,
          })),
        },
      });
      return true;
    }
    if (url.pathname === "/api/decks/timed-reader/reading-progress/") {
      if (route.request().method() === "POST") {
        const body = route.request().postDataJSON();
        writes.push(body);
        savedPage = body.current_page;
      }
      await route.fulfill({
        json: {
          deck_id: "timed-reader",
          current_page: savedPage,
          total_seconds: 0,
          completed: false,
        },
      });
      return true;
    }
  });
  await page.goto("/decks/timed-reader");
  await expect(page.getByAltText("Page 2", { exact: true })).toBeVisible();
  await page.clock.runFor(16000);
  await expect
    .poll(() => writes.reduce((n, row) => n + row.seconds, 0))
    .toBeGreaterThanOrEqual(15);
  await page.evaluate(() => {
    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      get: () => "hidden",
    });
    document.dispatchEvent(new Event("visibilitychange"));
  });
  await expect.poll(() => writes.length).toBeGreaterThanOrEqual(2);
  const before = writes.reduce((n, row) => n + row.seconds, 0);
  await page.clock.runFor(30000);
  expect(writes.reduce((n, row) => n + row.seconds, 0)).toBe(before);
  await page.evaluate(() => {
    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      get: () => "visible",
    });
    document.dispatchEvent(new Event("visibilitychange"));
  });
  await page.getByTitle("Next page", { exact: true }).click();
  await expect.poll(() => savedPage).toBe(3);
  await page.reload();
  await expect(page.getByAltText("Page 3", { exact: true })).toBeVisible();
});

test("standalone reading keeps navigation during a failed resume and retries unsent progress after reload", async ({
  page,
}) => {
  test.setTimeout(120000);
  let loadFailed = true,
    saveFailed = true;
  const writes: any[] = [];
  await fixtures(page, async (route, url) => {
    if (url.pathname === "/api/decks/retry-reader/") {
      await route.fulfill({
        json: {
          id: "retry-reader",
          title: "Retry reader",
          file_type: "pdf",
          page_count: 3,
          processing_status: "completed",
          pages: [1, 2, 3].map((n) => ({
            id: n,
            slide_number: n,
            image_url: readerImage,
          })),
        },
      });
      return true;
    }
    if (url.pathname === "/api/decks/retry-reader/reading-progress/") {
      if (route.request().method() === "POST") {
        writes.push(route.request().postDataJSON());
        if (saveFailed) {
          await route.fulfill({ status: 503, json: {} });
          return true;
        }
      } else if (loadFailed) {
        await route.fulfill({ status: 503, json: {} });
        return true;
      }
      await route.fulfill({
        json: {
          deck_id: "retry-reader",
          current_page: 3,
          total_seconds: 0,
          completed: true,
        },
      });
      return true;
    }
  });
  await page.goto("/decks/retry-reader");
  await expect(
    page
      .getByRole("alert")
      .filter({ hasText: "Could not load your saved reading position" }),
  ).toBeVisible();
  await page.getByTitle("Next page", { exact: true }).click();
  loadFailed = false;
  await page.getByRole("button", { name: "Retry reading progress" }).click();
  await expect(page.getByAltText("Page 2", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("alert").filter({ hasText: "has not synced" }),
  ).toBeVisible();
  const first = writes[0];
  saveFailed = false;
  await page.reload();
  await expect(page.getByAltText("Page 2", { exact: true })).toBeVisible();
  await expect
    .poll(
      () => writes.filter((row) => row.request_id === first.request_id).length,
    )
    .toBeGreaterThanOrEqual(2);
  expect(writes.findLast((row) => row.request_id === first.request_id)).toEqual(
    first,
  );
  await expect(
    page.getByRole("alert").filter({ hasText: "has not synced" }),
  ).toHaveCount(0);
});

test("standalone reader recovers from load failure and clamps page controls on mobile", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  let fail = true;
  await fixtures(page, async (route, url) => {
    if (url.pathname === "/api/decks/reader-deck/") {
      await route.fulfill(
        fail
          ? { status: 503, json: {} }
          : {
              json: {
                id: "reader-deck",
                title: "Mobile deck",
                file_type: "pdf",
                processing_status: "completed",
                pages: [1, 2].map((n) => ({
                  id: n,
                  slide_number: n,
                  image_url: readerImage,
                  width: 400,
                  height: 300,
                })),
              },
            },
      );
      return true;
    }
  });
  await page.goto("/decks/reader-deck");
  await expect(
    page.getByRole("alert").filter({ hasText: "Could not load this document" }),
  ).toBeVisible();
  fail = false;
  await page.getByRole("button", { name: "Try again", exact: true }).click();
  await expect(page.getByAltText("Page 1", { exact: true })).toBeVisible();
  await page.getByLabel("Page number").fill("99");
  await expect(page.getByAltText("Page 2", { exact: true })).toBeVisible();
  await expect(page.getByTitle("Next page", { exact: true })).toBeDisabled();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});

test("standalone deck chat sends whole-deck scope and restores persisted history", async ({
  page,
}) => {
  const deck = {
    id: "chat-deck",
    title: "Whole deck anatomy",
    file_type: "pdf",
    processing_status: "completed",
    page_count: 2,
    text_extraction: { status: "complete", total_pages: 2, missing_pages: [] },
    pages: [1, 2].map((slide_number) => ({
      id: slide_number,
      slide_number,
      extracted_text: `Extracted text for page ${slide_number}`,
      image_url: readerImage,
      width: 400,
      height: 300,
    })),
  };
  let history: Array<{
    role: "user" | "assistant";
    content: string;
    created_at: string;
  }> = [];
  await fixtures(page, async (route, url) => {
    if (url.pathname === "/api/decks/chat-deck/") {
      await route.fulfill({ json: deck });
      return true;
    }
    if (url.pathname === "/api/decks/chat-deck/reading-progress/") {
      await route.fulfill({
        json: {
          current_page: 1,
          total_pages: 2,
          total_seconds: 0,
          completed: false,
        },
      });
      return true;
    }
    if (url.pathname === "/api/ai/chat/history/") {
      expect(url.searchParams.get("deck_id")).toBe("chat-deck");
      await route.fulfill({
        json: { messages: history, disclaimer: "For education only." },
      });
      return true;
    }
    if (url.pathname === "/api/ai/chat/") {
      const body = route.request().postDataJSON();
      expect(body).toEqual({
        deck_id: "chat-deck",
        message: "What is on page two?",
        page_number: 1,
      });
      history = [
        {
          role: "user",
          content: body.message,
          created_at: new Date().toISOString(),
        },
        {
          role: "assistant",
          content: "Page two covers the femoral nerve. [Page 2]",
          created_at: new Date().toISOString(),
        },
      ];
      await route.fulfill({ json: { response: history[1].content } });
      return true;
    }
  });

  await page.goto("/decks/chat-deck");
  await page
    .getByRole("button", { name: "Ask AI about this document" })
    .click();
  await page
    .getByRole("textbox", { name: "Ask about this document" })
    .fill("What is on page two?");
  await page.getByRole("button", { name: "Send question" }).click();
  await expect(
    page.getByText("Page two covers the femoral nerve. [Page 2]", {
      exact: true,
    }),
  ).toBeVisible();

  await page.reload();
  await page
    .getByRole("button", { name: "Ask AI about this document" })
    .click();
  await expect(
    page.getByText("What is on page two?", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Page two covers the femoral nerve. [Page 2]", {
      exact: true,
    }),
  ).toBeVisible();
});

test("standalone deck chat keeps failed questions retryable without saving them", async ({
  page,
}) => {
  const deck = {
    id: "chat-deck",
    title: "Whole deck anatomy",
    file_type: "pdf",
    processing_status: "completed",
    page_count: 2,
    text_extraction: { status: "complete", total_pages: 2, missing_pages: [] },
    pages: [1, 2].map((slide_number) => ({
      id: slide_number,
      slide_number,
      extracted_text: `Extracted text for page ${slide_number}`,
      image_url: readerImage,
      width: 400,
      height: 300,
    })),
  };
  let history: Array<{
    role: "user" | "assistant";
    content: string;
    created_at: string;
  }> = [];
  let attempts = 0;
  await fixtures(page, async (route, url) => {
    if (url.pathname === "/api/decks/chat-deck/") {
      await route.fulfill({ json: deck });
      return true;
    }
    if (url.pathname === "/api/decks/chat-deck/reading-progress/") {
      await route.fulfill({
        json: {
          current_page: 1,
          total_pages: 2,
          total_seconds: 0,
          completed: false,
        },
      });
      return true;
    }
    if (url.pathname === "/api/decks/chat-deck/question-bank/") {
      await route.fulfill({
        json: { slide_id: null, can_generate: false, needs_assignment: false },
      });
      return true;
    }
    if (url.pathname === "/api/ai/chat/history/") {
      await route.fulfill({
        json: { messages: history, disclaimer: "For education only." },
      });
      return true;
    }
    if (url.pathname === "/api/ai/chat/") {
      attempts += 1;
      const body = route.request().postDataJSON();
      expect(body).toEqual({
        deck_id: "chat-deck",
        message: "What is on page two?",
        page_number: 1,
      });
      if (attempts === 1) {
        await route.fulfill({
          status: 502,
          json: {
            error:
              "The AI provider could not complete the request. Please try again.",
          },
        });
        return true;
      }
      const timestamp = new Date().toISOString();
      history = [
        { role: "user", content: body.message, created_at: timestamp },
        {
          role: "assistant",
          content: "Page two covers the femoral nerve. [Page 2]",
          created_at: timestamp,
        },
      ];
      await route.fulfill({ json: { response: history[1].content } });
      return true;
    }
  });

  await page.goto("/decks/chat-deck");
  await page
    .getByRole("button", { name: "Ask AI about this document" })
    .click();
  const question = page.getByRole("textbox", {
    name: "Ask about this document",
  });
  await question.fill("What is on page two?");
  await page.getByRole("button", { name: "Send question" }).click();
  const providerError = page.getByText(
    "The AI provider could not complete the request. Please try again.",
    { exact: true },
  );
  await expect(providerError).toBeVisible();
  await expect(question).toHaveValue("What is on page two?");
  await expect(
    page.getByText("What is on page two?", { exact: true }),
  ).toHaveCount(0);

  await page.getByRole("button", { name: "Send question" }).click();
  await expect(
    page.getByText("Page two covers the femoral nerve. [Page 2]", {
      exact: true,
    }),
  ).toBeVisible();
  await expect(providerError).toHaveCount(0);
  expect(attempts).toBe(2);

  await page.reload();
  await page
    .getByRole("button", { name: "Ask AI about this document" })
    .click();
  await expect(
    page.getByText("What is on page two?", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Page two covers the femoral nerve. [Page 2]", {
      exact: true,
    }),
  ).toBeVisible();
});

test("standalone reader reports a download failure visibly", async ({
  page,
}) => {
  const pages = [
    { id: 1, slide_number: 1, image_url: readerImage, width: 400, height: 300 },
  ];
  await fixtures(page, async (route, url) => {
    if (url.pathname === "/api/decks/reader-deck/") {
      await route.fulfill({
        json: {
          id: "reader-deck",
          title: "Download deck",
          file_type: "pdf",
          processing_status: "completed",
          pages,
        },
      });
      return true;
    }
    if (url.pathname === "/api/decks/reader-deck/pages/") {
      await route.fulfill({ status: 503, json: {} });
      return true;
    }
  });
  await page.goto("/decks/reader-deck");
  await page.getByTitle("Download page", { exact: true }).click();
  await expect(
    page.getByRole("alert").filter({ hasText: "Could not download this page" }),
  ).toBeVisible();
  await expect(page.getByTitle("Download page", { exact: true })).toBeEnabled();
});

test("a processing connection failure can be retried through to readable pages", async ({
  page,
}) => {
  let failed = false,
    recovered = false;
  await fixtures(page, async (route, url) => {
    if (url.pathname !== "/api/decks/processing-deck/") return;
    await route.fulfill(
      recovered
        ? {
            json: {
              id: "processing-deck",
              title: "Recovered deck",
              file_type: "pdf",
              processing_status: "completed",
              pages: [
                {
                  id: 1,
                  slide_number: 1,
                  image_url: readerImage,
                  width: 400,
                  height: 300,
                },
              ],
            },
          }
        : !failed
          ? {
              json: {
                id: "processing-deck",
                title: "Processing deck",
                file_type: "pdf",
                processing_status: "processing",
                pages: [],
              },
            }
          : { status: 503, json: {} },
    );
    return true;
  });
  await page.goto("/decks/processing-deck");
  await expect(page.getByText("Preparing your document")).toBeVisible();
  failed = true;
  await expect(
    page
      .getByRole("alert")
      .filter({ hasText: "Could not check document processing" }),
  ).toBeVisible();
  recovered = true;
  await page.getByRole("button", { name: "Try again", exact: true }).click();
  await expect(page.getByAltText("Page 1", { exact: true })).toBeVisible();
});

test("the course reader clears an open page when renewed access is denied", async ({
  page,
}) => {
  let denied = false;
  await fixtures(page, async (route, url) => {
    if (denied && url.pathname.startsWith("/api/slides/reader-a/")) {
      await route.fulfill({ status: 404, json: {} });
      return true;
    }
    return readerResponse(route, url);
  });
  await page.goto("/read/anatomy/reader-a");
  await expect(page.getByAltText("Page 1", { exact: true })).toBeVisible();
  denied = true;
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await expect(page).toHaveURL(/\/courses$/);
  await expect(page.getByAltText("Page 1", { exact: true })).toHaveCount(0);
});

test("late resource generation cannot replace the next document's resources", async ({
  page,
}) => {
  const premium = {
    ...profile,
    class_role: "class_head",
    class_head_verified: true,
    is_premium: true,
  };
  let pending: Route | undefined;
  await fixtures(
    page,
    async (route, url) => {
      if (url.pathname === "/api/ai/resources/") {
        if (route.request().postDataJSON().slide_id === "reader-a")
          pending = route;
        else
          await route.fulfill({
            json: {
              textbooks: [
                {
                  title: "Current document reference",
                  chapter: "Current chapter",
                  reason: "Current document",
                },
              ],
            },
          });
        return true;
      }
      return readerResponse(route, url);
    },
    premium,
  );
  await page.goto(
    "/read/anatomy/reader-a?session=true&step=1&queue=reader-a,reader-b",
  );
  await page.getByRole("button", { name: "Books", exact: true }).click();
  await expect.poll(() => Boolean(pending)).toBe(true);
  await page
    .locator("footer")
    .getByRole("button", { name: "Next", exact: true })
    .click();
  await expect(page).toHaveURL(/reader-b\?/);
  await page.getByRole("button", { name: "Books", exact: true }).click();
  await expect(
    page.getByText("Current document reference", { exact: true }),
  ).toBeVisible();
  const received = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/ai/resources/") &&
      response.request().postDataJSON().slide_id === "reader-a",
  );
  await pending!.fulfill({
    json: {
      textbooks: [
        {
          title: "Previous document private reference",
          chapter: "Old",
          reason: "Old",
        },
      ],
    },
  });
  await received;
  await page.getByRole("button", { name: "Videos", exact: true }).click();
  await page.getByRole("button", { name: "Books", exact: true }).click();
  await expect(
    page.getByText("Current document reference", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Previous document private reference"),
  ).toHaveCount(0);
});

test("resource links distinguish real YouTube results from search suggestions", async ({
  page,
}) => {
  const premium = {
    ...profile,
    class_role: "class_head",
    class_head_verified: true,
    is_premium: true,
  };
  await fixtures(
    page,
    async (route, url) => {
      if (url.pathname === "/api/ai/resources/") {
        await route.fulfill({
          json: {
            youtube: [
              {
                title: "Femoral nerve anatomy",
                query: "femoral nerve anatomy",
                reason: "Relevant to this slide.",
              },
            ],
            textbooks: [
              {
                title: "Clinical Anatomy",
                author: "Sample Author",
                chapter: "Lower limb",
                reason: "Covers this topic.",
              },
            ],
            mcqs: [],
          },
        });
        return true;
      }
      if (url.pathname === "/api/ai/video-suggestions/") {
        await route.fulfill({
          json: {
            source: "youtube_api",
            videos: [
              {
                title: "Femoral nerve dissection",
                channel: "Anatomy Learning",
                duration: "8:24",
                video_id: "verified-video-id",
                url: "https://www.youtube.com/watch?v=verified-video-id",
                thumbnail:
                  "https://i.ytimg.com/vi/verified-video-id/mqdefault.jpg",
              },
            ],
          },
        });
        return true;
      }
      return readerResponse(route, url);
    },
    premium,
  );

  await page.goto("/read/anatomy/reader-a");
  await page.getByRole("button", { name: "Videos", exact: true }).click();
  await expect(
    page.getByText("YouTube video results", { exact: true }),
  ).toBeVisible();
  const watchLink = page.getByRole("link", {
    name: /Femoral nerve dissection.*Watch on YouTube/,
  });
  await expect(watchLink).toHaveAttribute(
    "href",
    "https://www.youtube.com/watch?v=verified-video-id",
  );
  await expect(watchLink).toHaveAttribute("rel", "noopener noreferrer");

  await page.getByRole("button", { name: "Books", exact: true }).click();
  await expect(
    page.getByText("AI-Suggested References", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText(
      "Suggestions are not verified editions or direct book links.",
      { exact: true },
    ),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Search book catalogs" }),
  ).toHaveAttribute(
    "href",
    "https://www.google.com/search?tbm=bks&q=Clinical%20Anatomy%20Sample%20Author",
  );
});

test("video query fallback is labeled as a search rather than a verified video", async ({
  page,
}) => {
  const premium = {
    ...profile,
    class_role: "class_head",
    class_head_verified: true,
    is_premium: true,
  };
  await fixtures(
    page,
    async (route, url) => {
      if (url.pathname === "/api/ai/resources/") {
        await route.fulfill({
          json: {
            youtube: [
              {
                title: "Muscle attachment overview",
                query: "upper limb muscle attachments",
                reason: "Review the attachments.",
              },
            ],
            textbooks: [],
            mcqs: [],
          },
        });
        return true;
      }
      if (url.pathname === "/api/ai/video-suggestions/") {
        await route.fulfill({
          json: {
            source: "ai_suggestions",
            videos: [
              {
                title: "Muscle attachment overview",
                query: "upper limb muscle attachments",
                reason: "Review the attachments.",
              },
            ],
          },
        });
        return true;
      }
      return readerResponse(route, url);
    },
    premium,
  );

  await page.goto("/read/anatomy/reader-a");
  await page.getByRole("button", { name: "Videos", exact: true }).click();
  await expect(
    page.getByText("Video search suggestions", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText(
      "Suggestions open YouTube search results, not a specific verified video.",
      { exact: true },
    ),
  ).toBeVisible();
  await expect(
    page.getByRole("link", {
      name: /Muscle attachment overview.*Search on YouTube/,
    }),
  ).toHaveAttribute(
    "href",
    "https://www.youtube.com/results?search_query=upper%20limb%20muscle%20attachments",
  );
});

test("flashcard generation resumes its saved job after reload and allows retry after failure", async ({
  page,
}) => {
  test.setTimeout(120000);
  const premium = {
    ...profile,
    class_role: "class_head",
    class_head_verified: true,
    is_premium: true,
  };
  let generationRequests = 0;
  let statusRequests = 0;
  await page.clock.install();
  await fixtures(
    page,
    async (route, url) => {
      if (url.pathname === "/api/ai/resources/") {
        await route.fulfill({ json: { youtube: [], textbooks: [], mcqs: [] } });
        return true;
      }
      if (url.pathname === "/api/flashcards/") {
        await route.fulfill({ json: { count: 0, results: [] } });
        return true;
      }
      if (url.pathname === "/api/ai/generate-flashcards/") {
        generationRequests++;
        await route.fulfill({
          status: 202,
          json: { job_id: `flashcard-job-${generationRequests}` },
        });
        return true;
      }
      if (url.pathname === "/api/ai/flashcards/flashcard-job-1/") {
        statusRequests++;
        await route.fulfill({
          json: {
            job_id: "flashcard-job-1",
            status: statusRequests === 1 ? "running" : "failed",
            requested_count: 5,
            generated_count: 0,
            error:
              statusRequests === 1
                ? null
                : "The source could not be processed.",
            completed_at: statusRequests === 1 ? null : "2026-10-23T10:00:00Z",
          },
        });
        return true;
      }
      if (url.pathname === "/api/ai/flashcards/flashcard-job-2/") {
        await route.fulfill({
          json: {
            job_id: "flashcard-job-2",
            status: "running",
            requested_count: 5,
            generated_count: 0,
            error: null,
            completed_at: null,
          },
        });
        return true;
      }
      return readerResponse(route, url);
    },
    premium,
  );

  await page.goto("/read/anatomy/reader-a");
  await page.getByRole("button", { name: "Cards", exact: true }).click();
  await page
    .getByRole("button", { name: "Generate Flashcards", exact: true })
    .click();
  await expect.poll(() => generationRequests).toBe(1);
  await page.clock.fastForward(3000);
  await expect.poll(() => statusRequests).toBe(1);
  await page.reload();
  await page.getByRole("button", { name: "Cards", exact: true }).click();
  expect(
    await page.evaluate(() =>
      sessionStorage.getItem("flashcard-generation:reader-a"),
    ),
  ).toBe("flashcard-job-1");
  await page.clock.fastForward(3000);
  await expect.poll(() => statusRequests).toBe(2);

  await expect(
    page.getByText("The source could not be processed.", { exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(() =>
      sessionStorage.getItem("flashcard-generation:reader-a"),
    ),
  ).toBeNull();
  await page
    .getByRole("button", { name: "Generate Flashcards", exact: true })
    .click();
  await expect.poll(() => generationRequests).toBe(2);
  await expect(
    page.getByRole("button", { name: "Generating...", exact: true }),
  ).toBeDisabled();
});

test("flashcard shortfalls are shown and can be filled in a second generation", async ({
  page,
}) => {
  test.setTimeout(120000);
  const premium = {
    ...profile,
    class_role: "class_head",
    class_head_verified: true,
    is_premium: true,
  };
  let generationRequests = 0;
  let statusRequests = 0;
  let generatedCount = 0;
  await page.clock.install();
  await fixtures(
    page,
    async (route, url) => {
      if (url.pathname === "/api/ai/resources/") {
        await route.fulfill({ json: { youtube: [], textbooks: [], mcqs: [] } });
        return true;
      }
      if (url.pathname === "/api/flashcards/") {
        const results = Array.from({ length: generatedCount }, (_, index) => ({
          id: index + 1,
          front: `Question ${index + 1}`,
          back: `Answer ${index + 1}`,
          explanation: "",
        }));
        await route.fulfill({ json: { count: results.length, results } });
        return true;
      }
      if (url.pathname === "/api/ai/generate-flashcards/") {
        generationRequests++;
        await route.fulfill({
          status: 202,
          json: { job_id: `shortfall-job-${generationRequests}` },
        });
        return true;
      }
      if (url.pathname.startsWith("/api/ai/flashcards/shortfall-job-")) {
        statusRequests++;
        const completed = url.pathname.endsWith("shortfall-job-1/") ? 3 : 5;
        generatedCount = completed;
        await route.fulfill({
          json: {
            job_id: url.pathname.includes("shortfall-job-1")
              ? "shortfall-job-1"
              : "shortfall-job-2",
            status: "completed",
            requested_count: 5,
            generated_count: completed,
            error: null,
            completed_at: "2026-10-23T10:00:00Z",
          },
        });
        return true;
      }
      return readerResponse(route, url);
    },
    premium,
  );

  await page.goto("/read/anatomy/reader-a");
  await page.getByRole("button", { name: "Cards", exact: true }).click();
  await page
    .getByRole("button", { name: "Generate Flashcards", exact: true })
    .click();
  await expect.poll(() => generationRequests).toBe(1);
  await page.clock.fastForward(3000);
  await expect.poll(() => statusRequests).toBe(1);
  await expect(
    page.getByText(
      "Generated 3 of 5 requested cards. Generate the remaining cards to continue.",
      { exact: true },
    ),
  ).toBeVisible();
  await expect(page.getByText("Question 3", { exact: true })).toBeVisible();

  await page
    .getByRole("button", { name: "Generate remaining cards", exact: true })
    .click();
  await expect.poll(() => generationRequests).toBe(2);
  await page.clock.fastForward(3000);
  await expect.poll(() => statusRequests).toBe(2);
  await expect(page.getByText("Question 5", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Generate remaining cards", exact: true }),
  ).toHaveCount(0);
});

test("standalone page download succeeds after reauthorizing its file link", async ({
  page,
}) => {
  let accessChecks = 0;
  const pages = [
    { id: 1, slide_number: 1, image_url: readerImage, width: 400, height: 300 },
  ];
  await fixtures(page, async (route, url) => {
    if (url.pathname === "/api/decks/reader-deck/") {
      await route.fulfill({
        json: {
          id: "reader-deck",
          title: "Download deck",
          file_type: "pdf",
          processing_status: "completed",
          pages,
        },
      });
      return true;
    }
    if (url.pathname === "/api/decks/reader-deck/pages/") {
      accessChecks++;
      await route.fulfill({ json: pages });
      return true;
    }
  });
  await page.goto("/decks/reader-deck");
  const download = page.waitForEvent("download");
  await page.getByTitle("Download page", { exact: true }).click();
  expect(await (await download).failure()).toBeNull();
  expect(accessChecks).toBeGreaterThan(0);
});

test("a broken standalone page has a working image retry", async ({ page }) => {
  let broken = true;
  await fixtures(page, async (route, url) => {
    const pages = [
      {
        id: 1,
        slide_number: 1,
        image_url: broken ? "https://storage.invalid/broken.jpg" : readerImage,
        width: 400,
        height: 300,
      },
    ];
    if (url.pathname === "/api/decks/reader-deck/") {
      await route.fulfill({
        json: {
          id: "reader-deck",
          title: "Image retry",
          file_type: "pdf",
          processing_status: "completed",
          pages,
        },
      });
      return true;
    }
    if (url.pathname === "/api/decks/reader-deck/pages/") {
      await route.fulfill({ json: pages });
      return true;
    }
  });
  await page.goto("/decks/reader-deck");
  await expect(
    page
      .getByRole("alert")
      .filter({ hasText: "This page could not be displayed" }),
  ).toBeVisible();
  broken = false;
  await page.getByRole("button", { name: "Try again", exact: true }).click();
  await expect(page.getByAltText("Page 1", { exact: true })).toHaveAttribute(
    "src",
    readerImage,
  );
  await expect(
    page.getByText("This page could not be displayed.", { exact: false }),
  ).toHaveCount(0);
});

test("a failed saved-position lookup cannot overwrite it and supports retry", async ({
  page,
}) => {
  let failed = true;
  const writes: number[] = [];
  await page.clock.install();
  await fixtures(page, async (route, url) => {
    if (url.pathname === "/api/progress/") {
      await route.fulfill(
        failed
          ? { status: 503, json: {} }
          : { json: [{ slide: "reader-a", current_page: 3 }] },
      );
      return true;
    }
    if (url.pathname === "/api/progress/update_progress/") {
      writes.push(route.request().postDataJSON().current_page);
      await route.fulfill({ json: {} });
      return true;
    }
    return readerResponse(route, url);
  });
  await page.goto("/read/anatomy/reader-a");
  await expect(
    page.getByRole("button", { name: "Retry saved position" }),
  ).toBeVisible();
  await page.clock.fastForward(61000);
  expect(writes).toEqual([]);
  failed = false;
  await page.getByRole("button", { name: "Retry saved position" }).click();
  await expect(page.getByAltText("Page 3", { exact: true })).toBeVisible();
  await page.clock.runFor(16000);
  await expect.poll(() => writes).toEqual([3]);
});

test("reading home retries a failed library request and reopens a recent document", async ({
  page,
}) => {
  test.setTimeout(90000);
  let failed = true;
  await fixtures(page, async (route, url) => {
    if (url.pathname === "/api/subjects/" && failed) {
      await route.fulfill({ status: 503, json: {} });
      return true;
    }
    if (["/api/progress/recent/", "/api/progress/"].includes(url.pathname)) {
      await route.fulfill({
        json: [
          {
            id: 1,
            slide: "reader-a",
            current_page: 2,
            total_pages: 3,
            progress_percentage: 66,
          },
        ],
      });
      return true;
    }
    return readerResponse(route, url);
  });
  await page.goto("/read");
  await expect(
    page
      .getByRole("alert")
      .filter({ hasText: "Could not load your reading library" }),
  ).toBeVisible();
  await expect(
    page.getByText("No subjects available yet.", { exact: false }),
  ).toHaveCount(0);
  failed = false;
  await page.getByRole("button", { name: "Try again", exact: true }).click();
  const recent = page.getByRole("link").filter({ hasText: "Lecture reader-a" });
  await expect(recent).toHaveAttribute("href", "/read/anatomy/reader-a");
  await recent.click();
  await expect(page).toHaveURL(/\/read\/anatomy\/reader-a$/, {
    timeout: 45000,
  });
  await expect(page.getByAltText("Page 2", { exact: true })).toBeVisible();
});

test("document library retries a failed list and opens the saved deck", async ({
  page,
}) => {
  test.setTimeout(90000);
  let failed = true;
  const deck = {
    id: "reader-deck",
    title: "Library document",
    file_type: "pdf",
    file_size: 1000,
    processing_status: "completed",
    page_count: 1,
    pages: [
      {
        id: 1,
        slide_number: 1,
        image_url: readerImage,
        width: 400,
        height: 300,
      },
    ],
  };
  await fixtures(page, async (route, url) => {
    if (url.pathname === "/api/decks/") {
      await route.fulfill(
        failed ? { status: 503, json: {} } : { json: [deck] },
      );
      return true;
    }
    if (url.pathname === "/api/decks/reader-deck/") {
      await route.fulfill({ json: deck });
      return true;
    }
  });
  await page.goto("/decks");
  await expect(
    page
      .getByRole("alert")
      .filter({ hasText: "Could not load your documents" }),
  ).toBeVisible();
  await expect(page.getByText("No documents yet", { exact: true })).toHaveCount(
    0,
  );
  failed = false;
  await page.getByRole("button", { name: "Try again", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Library document" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "View", exact: true }).click();
  await expect(page).toHaveURL(/\/decks\/reader-deck$/, { timeout: 45000 });
  await expect(page.getByAltText("Page 1", { exact: true })).toBeVisible();
});

test("saved question bank shows 5 each and permits an uploader to retry without interrupting reading", async ({
  page,
}) => {
  let attempts = 0;
  let ready = false;
  await fixtures(page, async (route, url) => {
    if (url.pathname === "/api/slides/reader-a/content/") {
      await route.fulfill({
        json: {
          total_pages: 1,
          can_reprocess: true,
          text_extraction: { status: "complete" },
          pages: [
            { page_number: 1, image_url: readerImage, width: 400, height: 300 },
          ],
        },
      });
      return true;
    }
    if (url.pathname === "/api/slides/reader-a/status/") {
      await route.fulfill({
        json: {
          question_bank: {
            status: ready ? "completed" : "partial",
            mcq_target: 15,
            theory_target: 10,
            mcq_by_difficulty: ready
              ? { easy: 5, medium: 5, hard: 5 }
              : { easy: 3 },
            theory_by_difficulty: ready ? { easy: 2, medium: 4, hard: 4 } : {},
            represented_pages: [1],
            source_pages: 5,
            needs_review: ready ? 0 : 2,
          },
        },
      });
      return true;
    }
    if (url.pathname === "/api/slides/reader-a/generate-questions/") {
      attempts++;
      expect(route.request().postDataJSON()).toEqual({ force: true });
      ready = attempts > 1;
      await route.fulfill(
        ready
          ? { status: 202, json: { queued: true } }
          : { status: 503, json: {} },
      );
      return true;
    }
    return readerResponse(route, url);
  });
  await page.goto("/read/anatomy/reader-a");
  const notice = page.getByRole("status", { name: "Saved question bank" });
  await expect(notice).toContainText("Target: 15 (5 each)");
  await expect(notice).toContainText("2 question(s) awaiting review");
  await notice
    .getByRole("button", { name: "Retry question generation" })
    .click();
  await expect(notice.getByRole("alert")).toBeVisible();
  await expect(page.getByAltText("Page 1", { exact: true })).toBeVisible();
  await notice
    .getByRole("button", { name: "Retry question generation" })
    .click();
  await expect(notice).toContainText("5 easy, 5 medium, 5 hard");
  await expect(notice).toContainText("Bank ready");
  await expect(notice).toContainText("cite 1 of 5 source pages");
  expect(attempts).toBe(2);
});

test("saved question bank failure does not stop reading or offer students a generation button", async ({
  page,
}) => {
  let statusRequests = 0;
  await fixtures(
    page,
    async (route, url) => {
      if (url.pathname === "/api/slides/reader-a/status/") {
        statusRequests++;
        if (statusRequests === 2) {
          await route.fulfill({ status: 503, json: {} });
        } else {
          await route.fulfill({
            json: {
              question_bank: {
                status: statusRequests === 1 ? "running" : "failed",
                mcq_target: 15,
                theory_target: 10,
                mcq_by_difficulty: {},
                theory_by_difficulty: {},
              },
            },
          });
        }
        return true;
      }
      return readerResponse(route, url);
    },
    { ...profile, class_role: "student" },
  );
  await page.goto("/read/anatomy/reader-a");
  const notice = page.getByRole("status", { name: "Saved question bank" });
  await expect(page.getByAltText("Page 1", { exact: true })).toBeVisible();
  await expect
    .poll(() => statusRequests, { timeout: 20000 })
    .toBeGreaterThanOrEqual(3);
  await expect(notice).toContainText("uploader or class head");
  await expect(notice.getByRole("alert")).toHaveCount(0);
  await expect(
    notice.getByRole("button", { name: "Retry question generation" }),
  ).toHaveCount(0);
});

test("standalone bank assignment filters modules and recovers after a failed submission", async ({
  page,
}) => {
  let linked = false;
  let requests = 0;
  await fixtures(page, async (route, url) => {
    if (url.pathname === "/api/decks/bank-deck/") {
      await route.fulfill({
        json: {
          id: "bank-deck",
          title: "Standalone bank",
          file_type: "pdf",
          processing_status: "completed",
          text_extraction: { status: "complete" },
          pages: [
            {
              slide_number: 1,
              image_url: readerImage,
              width: 400,
              height: 300,
            },
          ],
        },
      });
      return true;
    }
    if (url.pathname === "/api/blocks/") {
      await route.fulfill({
        json: [
          block,
          { id: "wrong", name: "Other course module", subject: "other" },
        ],
      });
      return true;
    }
    if (url.pathname === "/api/decks/bank-deck/question-bank/") {
      if (route.request().method() === "POST") {
        requests++;
        expect(route.request().postDataJSON()).toEqual({
          subject: "anatomy",
          block: "upper",
        });
        if (requests === 1) {
          await route.fulfill({ status: 503, json: {} });
          return true;
        }
        linked = true;
      }
      await route.fulfill({
        json: linked
          ? {
              slide_id: "explicit-source-9",
              can_generate: true,
              needs_assignment: false,
              question_bank: {
                status: "completed",
                mcq_target: 15,
                theory_target: 10,
                mcq_by_difficulty: { easy: 5, medium: 5, hard: 5 },
                theory_by_difficulty: { easy: 2, medium: 4, hard: 4 },
              },
            }
          : {
              slide_id: null,
              can_generate: true,
              needs_assignment: true,
              question_bank: null,
            },
      });
      return true;
    }
  });
  await page.goto("/decks/bank-deck");
  const setup = page.getByLabel("Standalone question setup");
  await setup
    .getByRole("combobox", { name: "Course", exact: true })
    .selectOption("anatomy");
  await expect(
    setup
      .getByRole("combobox", { name: "Module", exact: true })
      .locator("option"),
  ).toHaveCount(2);
  await setup
    .getByRole("combobox", { name: "Module", exact: true })
    .selectOption("upper");
  await setup.getByRole("button", { name: "Prepare saved questions" }).click();
  await expect(setup.getByRole("alert")).toContainText("Could not prepare");
  await expect(page.getByAltText("Page 1", { exact: true })).toBeVisible();
  await setup.getByRole("button", { name: "Prepare saved questions" }).click();
  await expect(
    page.getByRole("status", { name: "Saved question bank" }),
  ).toContainText("5 easy, 5 medium, 5 hard");
  await page.reload();
  await expect(
    page.getByRole("status", { name: "Saved question bank" }),
  ).toContainText("Bank ready");
  await expect(page.getByLabel("Standalone question setup")).toHaveCount(0);
  expect(requests).toBe(2);
});

test("standalone bank setup reserves assignment for uploaders while students keep reading", async ({
  page,
}) => {
  await fixtures(
    page,
    async (route, url) => {
      if (url.pathname === "/api/decks/student-bank/") {
        await route.fulfill({
          json: {
            id: "student-bank",
            title: "Student deck",
            file_type: "pdf",
            processing_status: "completed",
            pages: [
              {
                slide_number: 1,
                image_url: readerImage,
                width: 400,
                height: 300,
              },
            ],
          },
        });
        return true;
      }
      if (url.pathname === "/api/decks/student-bank/question-bank/") {
        await route.fulfill({
          json: { slide_id: null, can_generate: false, needs_assignment: true },
        });
        return true;
      }
    },
    { ...profile, class_role: "student" },
  );
  await page.goto("/decks/student-bank");
  await expect(page.getByLabel("Standalone question setup")).toContainText(
    "Ask the uploader or class head",
  );
  await expect(page.getByLabel("Course", { exact: true })).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Prepare saved questions" }),
  ).toHaveCount(0);
  await expect(page.getByAltText("Page 1", { exact: true })).toBeVisible();
});

test("production repair: class hub opens credit-funded library tutor and preserves failed question", async ({
  page,
}) => {
  test.setTimeout(120000);
  let sends = 0;
  await fixtures(page, async (route, url) => {
    if (url.pathname === "/auth/class/my-class/") {
      await route.fulfill({
        json: {
          id: 1,
          set_name: "Year 1",
          school_name: "Test School",
          member_count: 5,
          class_heads: [],
          code: "123456",
        },
      });
      return true;
    }
    if (url.pathname === "/api/ai/chat/history/") {
      await route.fulfill({ json: { messages: [] } });
      return true;
    }
    if (url.pathname === "/api/ai/chat/") {
      expect(route.request().postDataJSON()).toEqual({
        scope: "library",
        message: "Explain the femoral nerve",
      });
      sends++;
      await route.fulfill(
        sends === 1
          ? {
              status: 502,
              json: { error: "Provider unavailable. Please retry." },
            }
          : {
              json: {
                response: "The femoral nerve is described in your lecture [1].",
                balance: 19,
                sources: [{ citation: 1, title: "Anatomy lecture", page: 2 }],
              },
            },
      );
      return true;
    }
  });
  await page.goto("/class");
  await expect(
    page.getByRole("heading", { name: "My class", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: /Class subjects/ }),
  ).toHaveAttribute("href", "/courses");
  await page.getByRole("button", { name: "Ask AI tutor", exact: true }).click();
  await page
    .getByRole("textbox", { name: "Question for AI tutor" })
    .fill("Explain the femoral nerve");
  await page.getByRole("button", { name: "Send question" }).click();
  await expect(
    page.getByRole("alert").filter({ hasText: "Provider unavailable" }),
  ).toBeVisible();
  await expect(
    page.getByRole("textbox", { name: "Question for AI tutor" }),
  ).toHaveValue("Explain the femoral nerve");
  await page.getByRole("button", { name: "Send question" }).click();
  await expect(
    page.getByText("The femoral nerve is described in your lecture [1]."),
  ).toBeVisible();
  await page.getByText("Slide sources", { exact: true }).click();
  await expect(page.getByText("[1] Anatomy lecture · Page 2")).toBeVisible();
});

test("production repair: manual battle reaches lobby and recognizes user ID rather than profile ID", async ({
  page,
}) => {
  test.setTimeout(120000);
  let payload: any;
  await fixtures(page, async (route, url) => {
    if (
      url.pathname === "/api/battles/" &&
      route.request().method() === "POST"
    ) {
      payload = route.request().postDataJSON();
      await route.fulfill({ status: 201, json: { id: 91 } });
      return true;
    }
    if (url.pathname === "/api/battles/91/") {
      await route.fulfill({
        json: {
          id: 91,
          code: "ABC234",
          host: 42,
          questions: payload.manual_questions,
        },
      });
      return true;
    }
  });
  await page.routeWebSocket("ws://127.0.0.1:8600/ws/battle/91/**", (socket) => {
    socket.send(
      JSON.stringify({
        type: "battle_state",
        state: {
          status: "scheduled",
          current_question_index: -1,
          total_questions: 1,
        },
        participants: [],
      }),
    );
  });
  await page.goto("/battles/create");
  await page.getByLabel("Battle title", { exact: true }).fill("Revision game");
  await page
    .getByRole("textbox", { name: "Question 1 text" })
    .fill("Which option is correct?");
  for (let i = 1; i <= 4; i++)
    await page
      .getByRole("textbox", { name: `Question 1 option ${i}` })
      .fill(`Answer ${i}`);
  await page
    .getByRole("radio", { name: "Question 1 correct answer 2" })
    .check();
  await page.getByRole("button", { name: "Create lobby", exact: true }).click();
  await expect(page).toHaveURL(/battles\/91$/);
  await expect(page.getByText("ABC234", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Start Battle", exact: true }),
  ).toBeVisible();
  expect(payload.question_source).toBe("manual");
  expect(payload.manual_questions[0].correct_index).toBe(1);
  await page.getByText("Review questions before starting (1)").click();
  await expect(page.getByText("Correct answer: Answer 2")).toBeVisible();
});

test("production repair: profile privacy controls save and survive reload", async ({
  page,
}) => {
  test.setTimeout(120000);
  let privacy = { public_profile: true, public_rank: true };
  await fixtures(page, async (route, url) => {
    if (url.pathname === "/api/stats/me/") {
      if (route.request().method() === "PATCH")
        privacy = { ...privacy, ...route.request().postDataJSON() };
      await route.fulfill({
        json: { id: 9, points: 10, current_streak: 0, rank: 1, ...privacy },
      });
      return true;
    }
  });
  await page.goto("/profile");
  await page
    .getByRole("checkbox", { name: "Public profile", exact: true })
    .uncheck();
  await expect.poll(() => privacy.public_profile).toBe(false);
  await expect(
    page.getByRole("checkbox", { name: "Public ranking", exact: true }),
  ).toBeEnabled();
  await page
    .getByRole("checkbox", { name: "Public ranking", exact: true })
    .uncheck();
  await expect.poll(() => privacy.public_rank).toBe(false);
  await page.reload();
  await expect(
    page.getByRole("checkbox", { name: "Public profile", exact: true }),
  ).not.toBeChecked();
  await expect(
    page.getByRole("checkbox", { name: "Public ranking", exact: true }),
  ).not.toBeChecked();
});
