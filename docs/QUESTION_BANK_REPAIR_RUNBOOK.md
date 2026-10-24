# Durable question banks — local checkpoint, 2026-10-19

Scope: item 11, saved question banks for both curriculum `Slide` and standalone `SlideDeck` uploads. The standalone reader now requests an explicit course/module association and uses the same durable bank workflow. Reading remains independent of generation. Single-deck practice is now locally verified separately in PRACTICE_REPAIR_RUNBOOK.md; its reader entry replaces ephemeral page MCQs. Formal assessment scoring remains unfinished and is not certified here.

## Standalone uploads

The reader asks the authorized uploader/class head to choose a course and module when a standalone deck has no curriculum association. The backend validates class ownership and hierarchy before creating a unique linked curriculum source. The one-to-one association is stored in additive migration `curriculum/0011_standalone_bank_source`; clients cannot set or swap that field directly. Matching IDs never create a link, and an existing assignment cannot be silently moved.

The linked source reuses the original private asset and rendered pages/text. No duplicate provider upload is made. A complete verified text cache is reused; unverified text still goes through the existing extraction guard in the background worker. Saved upgraded caches are not overwritten on repeated unchanged requests. Repeated or concurrent initial requests create only one source and one durable job. Subsequent reads and retries use `/api/decks/<id>/question-bank/`, with current deck permissions checked each time. Students see progress but cannot assign or regenerate.

The source version includes the standalone original, ownership, page text and extraction manifest. Changes invalidate old worker results and selection; an authorized retry refreshes the linked cache. Deleting the deck removes only its explicitly linked curriculum source and job. Generated question rows survive with a null source for historical attempts and cannot enter new bank selections. The old broad provider-prefix deletion was removed from the deck action; registered assets are retained for the separate item 8 orphan-reconciliation work.

The standalone reader supports failed assignment recovery, filters modules by the selected course, restores the association after refresh, and displays the same 5/5/5 counts, review holds and retry controls as the course reader.

## Confirmed policy

- The user chose **15 MCQs: 5 easy, 5 medium, 5 hard**. The existing additional theory target remains 10 (2 easy, 4 medium, 4 hard).
- Targets are server-owned in `learning/generation.py`. Bank size is separate from the maximum questions in a practice attempt. A deck with five medium MCQs cannot supply twenty distinct medium MCQs. Item 12 must report that availability honestly.
- A source that cannot support its target produces a partial/failed bank with actual counts. No fabricated answer or source quote is used to fill a quota.
- Generated questions belong to the source document's authorized class. The shared image-station catalogue has its own existing publication rules.

## Lifecycle and recovery

`request_generation` saves a pending database row before dispatching to Celery after transaction commit. Broker failure retains the request. The generation endpoint now queues work rather than doing provider calls within HTTP requests.

A worker locks the source and job in that order, claims a UUID lease, and extends its two-hour deadline before each provider request and after each saved response. Question-bank tasks have no Celery hard or soft execution time limit. Each completed source-window response is persisted immediately, so a later provider failure does not discard earlier questions; failures in one difficulty/type do not prevent remaining categories (including theory) from being attempted. Duplicate deliveries and force requests cannot take an active lease. Expired workers cannot save questions, finish jobs, or overwrite another worker's status. The provider still has a bounded per-request network timeout and retries/failover; an indefinitely hung network call must not hold a worker forever. An expired call may still consume provider capacity; no guarantee of exactly-once external billing is made.

Each batch is saved separately. Retries count valid, distinct questions in the current bank and fill only the shortfall. There are at most three worker attempts per retry cycle, with five minutes between automatic attempts. An authorized uploader/class head/platform administrator can explicitly start a fresh bounded retry cycle; a manual retry still cannot steal an active lease.

`recover_question_generation` dispatches due pending requests, retries partial/failed jobs and recovers expired leases in bounded sweeps. Exhausted jobs become failed instead of remaining running forever. `fix_stuck_slides` now requests this workflow; one existing MCQ no longer makes a bank complete. The unrelated standalone `SlidePage` signal no longer starts a curriculum-slide job by coincidentally matching an ID.

The Celery configuration schedules recovery every five minutes. **A worker alone does not execute that schedule.** The current Render blueprint has no Beat service. Hosted acceptance must verify an approved scheduler, or arrange a five-minute invocation of `python manage.py recover_question_generation` in the correct backend environment. The existing shared Beat schedule also includes credit and notification jobs; those jobs require their own acceptance before enabling that whole scheduler. No Render service was provisioned during this repair.

## Source versions, validation and review

The bank key includes the source identity, class/curriculum assignment, difficulty targets, validation policy, original file hash and complete extracted text. A replacement starts a separate bank key while retaining old question rows for existing attempt references. New selection rejects stale keys and changed source fingerprints. Legacy AI banks lacking verified source evidence are retained but excluded from new selections; they can be regenerated from the original. Manual and past-question workflows are preserved.

Every accepted generated question has a real source page and a 20–2,000-character quotation checked against that page after whitespace normalization. MCQs require four distinct nonempty options, one exact A–D answer and an explanation. Theory questions require an answer and a positive-integer marking rubric whose marks add up. Normalized duplicate stems, wrong difficulty, invalid references and provider oversupply are rejected or bounded. The bank only reports complete when all difficulty quotas are present.

The adapter preserves page labels and distributes source windows across the document, including its end when more than one window is selected. Fifteen questions cannot represent every topic in an arbitrarily long document. The reader reports the pages actually cited; it does not claim complete topical coverage.

The provider must explicitly return `needs_review=false` for ordinary practice eligibility. Flagged or missing-review-status rows are held outside practice and do not count toward quotas. A source quotation proves provenance, **not medical correctness or valid reasoning**. Provider grading of difficulty and ambiguity still needs representative human acceptance.

Generated document questions require human approval before new formal assessments can select them. In Django's QuizQuestion administration, the reviewer examines the question, answer, medical claims and source evidence, then uses the explicit human-review action. That action rechecks the current source, structure, quotation and quota, records `reviewed_at`, and writes the administrator's action to Django's audit log. Editing a generated question in that administration clears its approval and holds it for review again. The action cannot approve stale source versions or overfill a difficulty pool.

## User-visible progress

The authorized slide status endpoint now includes separate question-bank status, actual per-difficulty counts, targets, review counts and cited-page coverage. It does not expose lease tokens. The reader displays those fields, polls queued/running jobs and permits authorized uploaders to retry once text extraction is complete. Status/queue failures leave the document readable. Questions needing review and stale banks are excluded at new-selection entry points; historical attempts retain their existing question rows. Source quotations are withheld when a serializer is configured to hide active-attempt answers.

## Schema and rollout

New additive migrations:

- `learning/0007_question_generation_leases`: lease, recovery and source-identity fields.
- `curriculum/0010_bank_source_references`: bank key, page and review fields.
- `learning/0008_bank_source_references`: original/text source fingerprint, bank key and default MCQ target of 15.
- `curriculum/0011_standalone_bank_source`: explicit standalone-to-curriculum source association; existing decks remain unassigned until an authorized user chooses their course/module.

No question or attempt history is deleted by these migrations. Existing 50-question target values are updated when generation is requested, without marking old unverified rows as ready. Apply the migrations through the existing verified release procedure before starting updated web/worker code. Render/Neon backups, environment identity, scheduler operation, a worker restart mid-generation and a real representative provider sample still require hosted acceptance. No production migration, deployment, live provider call or individual credit debit was performed here.

## Reproduce local verification safely

From `backend`, use the isolated settings (they do not load production dotenv):

```powershell
$env:EMBY_TEST_POSTGRES='1'
..\.venv\Scripts\python.exe -m django test curriculum.tests.test_bank_recovery curriculum.tests.test_deck_banks --settings=tests.integration_settings --noinput
..\.venv\Scripts\python.exe -m django makemigrations --check --dry-run --settings=tests.integration_settings
```

The PostgreSQL test profile is restricted to the disposable cluster at `127.0.0.1:55432`. Providers and the broker are mocked; these tests do not exercise a real Redis transport or paid provider. From the project root, the browser checks are `npx playwright test tests/browser/content.spec.ts --grep "saved question bank"`; APIs are intercepted with localhost fixtures. Strict TypeScript is `npx tsc --noEmit --incremental false`.

Final executed test counts and any corrections are recorded in `EMBY_REPAIR_PROGRESS.md`. Do not add overlapping intermediate runs to the final distinct-test total.
