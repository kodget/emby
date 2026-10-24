# Single-deck practice — local verification, 2026-10-19

Scope: item 12, newly created MCQ practice attempts. Mock/formal policy and legacy assessment lifecycle repairs remain item 13. No production deployment or database operation was performed.

## Behaviour

- `/api/quiz-attempts/` requires one visible curriculum source for practice, including a standalone deck's explicit linked source. Course/module references must agree with that source. Practice is MCQ-only, 1–20 questions, at exactly one difficulty.
- Selection uses the saved current bank, excludes review holds and stale sources, and deduplicates stems. It does not generate questions or spend credits. The bank target remains **15 = 5 easy + 5 medium + 5 hard**. The 20-question attempt ceiling does not promise 20 questions at each difficulty.
- `/api/quiz-attempts/practice-options/` reports available counts for an authorized deck. A shortage at creation returns an error and the actual available count without creating an attempt. The screen offers an explicit smaller count; it never silently borrows questions from another deck or difficulty.
- Missed-question practice also requires one deck and difficulty. It draws from previously submitted wrong responses that remain eligible in the current bank.
- New attempts persist their ordered IDs and private question snapshots, including the answer key and bank version. Later edits do not change the questions or marking of an existing attempt. Answers, explanations and evidence quotes stay hidden while the attempt is active, including inside nested response serializers. Results/missed-answer endpoints reject active practice attempts.
- Answers must belong to the selected attempt and use A–D. Answer saves and submission lock the same attempt row. Server deadlines reject late answers; submission after a deadline records `auto_submitted`. Timed practice accepts 1–180 whole minutes; untimed practice has no duration.
- Submission recomputes correctness from the saved selections and original answer keys. Unanswered questions count toward the denominator. The score, completion, points and activity update are transactional. Retries/concurrent submissions return the saved result without awarding again.
- The browser restores saved answers on refresh, exposes save failures, prevents submission while an answer save is pending, and ignores stale attempt loads/responses. Results show correct, incorrect and unanswered questions with their correct answers. The old unsupported claim that missed questions automatically create flashcards was removed.
- Both readers link to practice with the canonical source ID. The reader Quiz tab uses this saved-bank flow instead of ephemeral page MCQs. Study sessions ask the student to select a deck and retain the session return route.
- The unused legacy `/api/quiz/generate/` creator returns HTTP 410 with a link to `/quiz`; its unscoped selection and answer-key exposure no longer create new quizzes. Existing legacy history endpoints remain available. Broader mock/formal creation has not been certified by this repair.

## Migration and evidence

Additive migration `curriculum/0012_practice_question_snapshots` adds private snapshots and changes the attempt's slide relationship to `SET_NULL`. Deleting a source slide preserves its attempt; this is not a certification of arbitrary course, user or question deletion. Historical attempts are not backfilled with invented question versions.

Automated evidence is recorded in the main repair tracker. Backend checks use only `tests.integration_settings` and a disposable local PostgreSQL database. New tests cover scope, counts/types, shortage, exact difficulty, review/staleness, saved versions, hidden answers, reload, deterministic scoring, retries/concurrent submission, deadlines and source deletion. Browser checks use isolated API fixtures, without provider traffic.

The first browser results journey timed out while the development server compiled the results route. Its trace showed a successful submission and a pending local results-page request; rerunning the same assertions passed. Windows Playwright teardown needed the owned Next server processes stopped after test completion. No production build or hosted acceptance is implied.

## Hosted acceptance still required

Apply the additive migration through the normal reviewed release process, then test a real curriculum deck and a linked standalone deck as a student. Confirm exact availability, a shortage, refresh/reconnect, a timed expiry, retrying submission and result review. Check class isolation with a second class. Validate sample questions medically through the separate question-bank review process. Mock/formal assessment rules, global analytics/awards and whole-app release acceptance remain separate tracker items.
