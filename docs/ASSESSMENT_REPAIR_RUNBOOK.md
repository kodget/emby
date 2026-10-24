# Assessment repair — item 13 locally verified

## Confirmed product decisions, 2026-10-19

- Mock exams: a student may choose a course, module or submodule. Single-deck practice remains separate.
- Formal assessments: class heads create them. They may write questions manually or use AI-assisted generation.
- The head chooses counts and timing, with hard ceilings of **50 MCQs, 5 theory questions and 150 minutes**.
- Each student gets **one attempt per published formal assessment**.
- These are the confirmed requirements. Delivery status is separated below; do not ask the user to repeat these decisions.

## First repair batch

The answer endpoint previously required an MCQ option even for a theory question, while the writing component did not invoke its save handler. A shared answer-saving service now validates the selected question and answer type, preserves written text (including an explicit empty answer), stamps server receipt time, ignores client scores, hides model answers and rejects writes to a closed/expired attempt. Existing private attempt snapshots are used when present; old attempts are not assigned invented historical versions.

The browser saves written drafts after a pause or blur, serializes saves, exposes failures with a retry action, and flushes drafts before manual submission. A delayed response cannot replace newer written text. Saved answers reload from the backend; clearing the field also persists. Timers calculate elapsed wall-clock time from the server's remaining-time response and resynchronize on tab visibility changes. Expiry fires once per mounted timer; a failed automatic submission remains visible and retryable. The server remains authoritative and rejects answers at or after the deadline.

This batch does not fix theory grading, validate mock selection, implement the formal paper authoring model or certify existing mock/formal results. No production operation has occurred.

## Second repair batch — private formal papers and one attempt

The new `/quiz/assessments` page lets an approved current class head save/reopen manual drafts, write MCQs with explanations and theory questions with model answers/marking rubrics, choose counts/time, and publish. Drafts may contain fewer questions than their chosen counts; every saved question must be complete and publication requires exactly the chosen counts. The API strictly validates whole-number limits, option keys, distinct options and rubric totals. Revision checks stop stale editors overwriting or publishing a different draft.

`FormalAssessment` stores private JSON questions outside `QuizQuestion` and the shared bank. Student lists/details contain metadata only; an authorized start supplies redacted snapshots. Published content/settings are immutable through the API. The old student-created formal path is rejected and the old formal configurator links to class papers, without a premium gate or unsupported certificate claims.

Migration **0013_formal_assessments** adds the paper, a protected attempt reference, a unique `(user, assessment)` constraint and private snapshot response identifiers. A paper-row lock serializes start/close/publication. Duplicate starts return the existing attempt, deadline and submitted status. Formal attempts cannot be deleted through the student API. Course/deck/question removal cannot reset these new attempts because their questions and scope are stored independently. Historical formal attempts are not retroactively assigned invented papers.

Formal answers use the shared validated answer endpoint. Submission locks the attempt, scores MCQs against its saved key, persists the outcome, updates stats and records one completion event transactionally. Duplicate/concurrent submits return the saved outcome. A failure recording completion rolls the whole submission back for retry. Existing formal MCQ point arithmetic is retained (quarter-point penalty for answered wrong MCQs, multiplier 2); unanswered MCQs remain in the score denominator.

Answer-release policy for this flow: heads explicitly close new entries, existing attempts retain their deadlines, and keys can be released only after no unexpired active attempts remain. Active attempts never receive keys. Students can review released MCQ/model answers after submission; they cannot start a new attempt after closure. Class membership and head approval are checked on each API request.

At this second checkpoint, theory grading was pending for versioned papers. The third batch below implements it. The legacy live-question grader/analysis remains excluded from these private papers. AI authoring is still outstanding.

Verification: 65 distinct affected backend tests on isolated PostgreSQL (64 together plus one added rollback test), 3 state tests and 3 browser journeys. Migration consistency passed. See the progress log for final TypeScript/cleanup evidence. No production migration or provider operation occurred.

## Third repair batch — saved-rubric grading, 2026-10-20

Submitting a new formal paper now records a durable grading job in the same transaction as the saved submission. Every written answer is graded against that attempt's immutable question, model answer and rubric. Unanswered questions receive zero without a provider call and remain in the total available marks. Strict validation rejects missing/duplicate criteria, invalid numbers, scores outside rubric bounds and totals that disagree with the criterion marks; malformed responses never become successful zero grades.

Migration **0014_durable_assessment_grading** adds the job and private grading evidence and converts written scores to two-decimal fields. The decimal range retains the previous 32-bit integer range. Fractional marks survive storage and API reloads. Final percentage is `(correct MCQs + written marks) / (MCQ count + all written maximum marks) * 100`. Until grading completes, results remain explicitly provisional. Existing MCQ points and the single completion event are preserved; final grading updates event evidence without another points/XP award.

Workers acquire a unique lease, keep provider calls outside database transactions and checkpoint each validated answer. Duplicate or expired workers cannot overwrite the current job. Each retry cycle permits three worker attempts, with automatic backoff; after exhaustion the owner can retry following a five-minute cooldown. Completed answers keep their marks. Ten-minute leases allow recovery after worker interruption. Queue failures leave the job saved for redelivery. Celery beat schedules recovery every five minutes; `recover_assessment_grading` is also available as an explicit management command. Recovery adopts earlier pending submissions for versioned formal papers only; it does not invent historical rubrics for legacy mock exams.

The results page shows grading progress, failure/retry controls and fractional final marks. Submitted answers remain visible; model answers, grading feedback and rubric breakdowns stay hidden until the head releases answers. Private input fingerprints and operational errors are never exposed in student responses.

Local evidence: **79 affected backend tests passed on isolated PostgreSQL**, including 14 grading tests. Those 14 passed again after the final decimal-field range adjustment. Three distinct browser journeys passed across runs: formal resume/submission, grading retry/final-result/answer-release and existing practice save/reload/results. The practice journey first timed out waiting for the results route after a successful submit response, then passed unchanged on its focused rerun. Strict TypeScript and migration consistency passed. Provider and broker calls were mocked; no claim of live AI marking accuracy is made.

Hosted acceptance requires migration 0014, a running worker and recovery scheduler, broker/worker interruption checks and representative subject-expert review of real grades. None of these production actions has been performed.

## Remaining hosted acceptance

The six implementation batches below complete the local item-13 scope. Hosted acceptance still requires the backup/migration process for migrations 0013–0016, real provider and worker/scheduler recovery, representative subject-expert review of generated questions and written grading, and student/head journeys on Render/Neon. No production sign-off is claimed. Historical records are preserved as explicitly unverified, not retroactively certified.

## Fourth repair batch — scoped mock exams, 2026-10-20

`/quiz/mock` offers explicit course, module and submodule selection with current availability by difficulty and question type. The existing Premium presentation for mock exams remains; subscription/payment policy is not redesigned here. The API requires `scope_type`/`scope_id`, rejects old topic/deck aliases and unscoped creation, validates parent consistency, and rejects unsupported selection sources. It retains the existing configurator's upper bounds of 100 MCQs/10 written questions and permits timed (1–180 whole minutes) or untimed exams. These mock limits are separate from the user's formal-paper limits.

Availability and start use the same eligible pool: current saved AI banks or structurally valid manual/past questions, with review holds, stale banks, invalid keys/rubrics, contradictory source ancestry and duplicate normalized stems excluded. Requested difficulty is exact. A shortage returns actual counts and creates no attempt; the UI offers an explicit smaller exam. Start rechecks availability. There is no generation request or credit charge during assembly.

Sampling rotates across the most specific available topic labels, falling back to submodule/module/course labels when a topic is absent. Within each label it rotates source files, randomizing rows and each round's group order. This is performed independently for MCQs and written questions. A large source cannot fill another source's available turn accidentally, and exhausted groups yield remaining slots to groups that still have questions.

Migration **0015_scoped_mock_attempts** stores the original class independently and changes attempt curriculum references to `SET_NULL`. New mocks save ordered question/key/rubric and coverage-label snapshots and use snapshot-only answer references. Removing a course or source question preserves the new attempt and its answers. Owner and original active-class checks continue even after source removal. Historical attempts keep their existing access checks and are not assigned a fabricated snapshot class.

New mock submissions reuse the transactionally saved assessment result and durable rubric grader, including zero for unanswered questions, fractional marks, complete denominators and recoverable dispatch. Duplicate/concurrent submissions record one completion and retain the existing mock MCQ points multiplier. Topic MCQ totals are calculated from saved versions, including unanswered MCQs; written marks remain separate until combined grading finishes. Results show saved explanations, topic totals and written feedback after submission. UI navigation and the old mock selector link to the new page.

Verification details are recorded in the latest progress-log entry. The local migration and provider mocks are not production acceptance.

Use only `tests.integration_settings` for backend verification. Ordinary settings load the real Neon environment. Provider calls must be mocked during local regression checks. Latest executed evidence is recorded in EMBY_REPAIR_PROGRESS.md.

## Fifth repair batch — private AI drafting, 2026-10-20

An approved class head can choose up to ten extracted class documents and one difficulty to fill the saved paper's missing question slots. Every selected document must receive a question, so document count cannot exceed missing slots. Manual questions remain intact. Generation uses verified current extraction, distributes slots across documents and positions within their page text, and preserves the chosen excerpts and source-version fingerprints. It does not claim exhaustive coverage of every page.

Migration **0016_formalassessment_ai_reviewed_at_and_more** adds private `AssessmentDraftJob` records and formal-paper AI review fields. Suggestions live outside the shared question bank. A worker generates one question per task, keeping provider calls outside transactions. Validation checks type, difficulty, MCQ options/key, complete theory rubrics and totals, duplicate stems, and an exact supporting quotation on the selected page. Quotation validation establishes textual provenance; it does not establish clinical correctness.

Each validated suggestion is checkpointed. Three attempts are allowed for the current missing question before the job needs a head-initiated retry after a five-minute cooldown; previously saved suggestions remain. Queue failures, lost deliveries and expired ten-minute worker leases are recoverable. Celery beat runs recovery every five minutes; `recover_assessment_drafts` is available for explicit recovery. Duplicate requests share the existing job, and concurrent workers cannot save twice. Provider errors are represented by safe codes rather than raw responses.

Workers never edit or publish the paper. The head inspects questions, answers, rubrics and source quotations, then explicitly adds the complete set of suggestions. Apply checks the saved revision and current source versions and appends only missing questions. Saving manual edits cancels unfinished or unapplied generation; late worker results cannot overwrite those edits. The editor disables apply/retry while it has unsaved changes and preserves those edits when suggestions are discarded. Generation progress survives leaving/reloading the page.

Papers that have received AI suggestions require an explicit review confirmation when publishing. Subsequent edits clear the browser confirmation; the backend records the publishing head and review timestamp. Existing strict count/time limits and single-attempt rules remain. Student and other-class responses never expose private jobs, source excerpts or draft keys.

Local evidence: **45 distinct backend checks passed across isolated PostgreSQL runs** (15 drafting, 16 formal-paper and 14 grading tests). The first combined run passed 42 tests; three additional drafting cases were added and the complete 15-test drafting suite passed, including simultaneous requests/apply and simultaneous workers. Existing manual authoring/publishing and the new AI reload/retry/provenance/edit-protection/review/publish browser journeys passed across runs. The AI browser test initially failed on an exact label selector despite the correct field/value being present; using the textbox's accessible role/name resolved the test selector, and the journey passed unchanged in its product behavior. TypeScript and migration consistency passed. Providers and broker calls were mocked.

Hosted acceptance still needs migration 0016, a worker and recovery scheduler, real provider interruption checks, and subject-expert review of representative generated questions. No production operation was performed. Remaining item-13 implementation: deeper evidence-based formal feedback and an explicit policy/flow for historical attempts without original snapshots.

## Sixth repair batch — saved-evidence feedback and historical records, 2026-10-20

Released formal results now include a deterministic study-guidance section. It counts correct, incorrect and unanswered MCQs against the saved answer keys, groups results by saved difficulty, and flags groups below three questions as limited evidence. Missed MCQs link to the saved question and explanation. Written guidance lists the exact rubric criteria that lost marks and their saved feedback; unanswered responses receive a concrete next step, and pending grades are not presented as established weaknesses. The observations describe that paper only and do not claim a cause for mistakes, a diagnosed misconception, or a prediction of future exam performance.

Feedback is withheld until the student has submitted and the head has released answers. It requires no additional provider call and is reproducible from the immutable attempt and saved responses. The results browser journey verifies withheld/released guidance alongside fractional marks and recovery.

Attempts with no original question snapshots and no versioned formal/mock ownership are historical records. Their answers and stored scores remain in the database, but they cannot be resumed, answered, flagged, submitted, regraded or deleted through the attempt API. Legacy grading/analysis tasks return before provider work. Historical serialization includes available saved responses and explicitly unverified recorded scores only; it never substitutes today's question text, keys or old AI narrative for the missing original versions. Missing source questions do not hide an otherwise authorized historical record. Existing foreign-class parent/question checks remain; snapshots still require their established access boundary.

`/quiz/history`, linked from the practice landing, lists available attempts and supports paginated loading and retry. New active attempts resume normally; completed attempts open their results. Historical entries open the read-only record, and direct navigation to an old active attempt redirects there. A never-submitted historical attempt is not presented as a completed zero-score exam. Responses already deleted by an earlier source cascade cannot be reconstructed and are not fabricated.

Verification: **165 backend tests passed together on isolated PostgreSQL**, covering feedback/history, analytics evidence, shared answers, formal papers, AI drafts, grading, scoped mocks, practice, and class boundaries. **Three browser journeys passed**: formal grading/release/study guidance; history and direct legacy-resume redirection; analytics study-only data and stale-period protection. Three assessment-state tests, strict TypeScript, route type generation and migration consistency passed. The earlier SQLite run passed 62 checks and failed one new fixture because its comparison statistics row had not been created; that fixture was corrected before the successful PostgreSQL run.

**Item 13 is locally verified.** Overall tracker: **10/20 locally verified, 5 in progress, 5 pending; 0 production sign-offs.** Continue with item 14's remaining shared counter/reconciliation work and other pending feature audits. Do not repeat completed assessment implementation unless a new regression warrants it.
