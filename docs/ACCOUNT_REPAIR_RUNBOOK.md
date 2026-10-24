# Account workflow repairs and release checks

These changes are local. The user confirmed Render for the backend and Neon for
PostgreSQL on 2026-10-13. No live migration, email, backup, restore or deployment
has been performed. Follow `PERSISTENCE_RUNBOOK.md` before production release.

## Implemented behavior

- Class-head registration saves one pending request and persistent in-app
  notifications for active staff/superusers. The class code is emailed after
  registration commits, with an explicit pending status. Knowing that code does
  not grant management/upload privileges. SMTP failure cannot undo registration.
- API and Django admin approval use the same transaction and class-row lock.
  Three active approved heads is the maximum. Repeat approval is harmless;
  rejection removes membership, records a reason/reviewer/time, and permits a
  new numbered request. Both request and decision notifications are durable.
- Replaying onboarding or joining another class cannot move class-head approval
  into a different class. Reactivating an inactive head cannot create a fourth
  active head. Generic admin fields cannot bypass the review path.
- Frontend review uses the account's `user_id`, separately from the profile's
  `id`. The review queue supports rejection reasons, empty/error states and
  refresh. Pending users can see rejection feedback and request another review.
- Verification links expire (default 24 hours), are single use, and bind the
  account and current email. Only a digest and issuance timestamp are stored.
  Authenticated resend has a shared database cooldown (default 60 seconds).
  The previously missing `/verify-email` page now handles success, invalid links,
  outages and resend. Onboarding and pending pages expose the email reminder.
- Email sending reports failure/unavailability without exposing provider error
  details or calling console output delivery. Signup succeeds even if SMTP fails.
  `sent` means the mail backend accepted the message, not inbox delivery proof.
- Password-reset links expire (default one hour), use stored digests and a
  cooldown, and are consumed atomically. Changing the email/password invalidates
  a prior link. Duplicate historical emails are not resolved by picking a user.
  Known, unknown, inactive and failed-delivery requests have the same public
  response; that response promises an attempt, not a delivered email.
- Session refresh retains credentials on network/server outages, shares one
  refresh across concurrent requests, and has a timeout. Explicitly rejected
  refresh credentials still require sign-in. Public login failures do not clear
  an unrelated session.

## Schema and compatibility

Apply `accounts.0003_class_head_review` before starting the new backend. It adds
request version, reviewer and review time; it does not delete or reapprove users.
Existing over-capacity classes or inconsistent historical roles need a reviewed
data audit; the repair does not silently remove their heads.

`credits.0003_legacycreditrecord` adds the recovery archive. The transfer is an
explicit command, not an automatic data migration. See `LEGACY_CREDIT_TRANSFER.md`.

The initial add-field operation in existing `curriculum.0002` no longer requests
an intermediate index. On PostgreSQL, adding an indexed text column and then
making it unique in the same migration scheduled its pattern-ops index twice,
which prevented a clean migration. The final field/schema is unchanged. Applied
databases do not rerun this migration. Backfill now uses the selected database
alias. No historical credit migration was rewritten.

Old opaque verification/reset links are rejected. Users can request fresh links
after rollout. New links require the same `SECRET_KEY` on all backend instances.
Review `FRONTEND_URL` (HTTPS in production), SMTP backend/credentials and sender.
Never print those credentials in logs or paste them into tickets.

Configuration defaults:

| Setting | Default |
| --- | --- |
| `EMAIL_VERIFICATION_MAX_AGE_SECONDS` | `86400` |
| `EMAIL_VERIFICATION_RESEND_SECONDS` | `60` |
| `PASSWORD_RESET_TIMEOUT` | `3600` |
| `PASSWORD_RESET_RESEND_SECONDS` | `60` |

## Local verification

`tests.integration_settings` never imports production settings or dotenv files.
Its PostgreSQL mode uses only a dedicated loopback cluster on port 55432 with
user `emby_test`, database `emby_tests`, and disposable `test_emby_tests`.
Do not substitute the Neon connection string.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -t backend -p 'test_*.py'
node --test scripts/test-class-head-guards.cjs scripts/test-auth-refresh.cjs
npx.cmd tsc --noEmit --incremental false
cd backend
$env:EMBY_TEST_POSTGRES='1'
..\.venv\Scripts\python.exe -m django test accounts.tests credits.tests --settings=tests.integration_settings --noinput
..\.venv\Scripts\python.exe -m django makemigrations --check --dry-run --settings=tests.integration_settings
```

Passed locally: 43 persistence tests, 36 account/email/password integration tests,
19 legacy-transfer integration tests, 16 frontend permission/session regressions,
8 browser account journeys, TypeScript, Django system check, and migration consistency. PostgreSQL 18.3 ran
the concurrent approval/reset tests; they were not skipped. Tests use a local
mail outbox and simulated provider failures. CI includes a disposable PostgreSQL
service and these checks but has not run remotely. Browser checks use headless Edge locally, simulated localhost API responses, and no external provider traffic. Run `npm run test:browser` (Linux CI installs Chromium first); the suite covers mobile reapplication, single-use verification callbacks, invalid links, outage recovery, resend cooldown, admin rejection, the full-class error, and protected generic-admin fields.

## Staging acceptance still required

1. Back up and restore to an isolated staging target. Compare Render web/worker
   target fingerprints and the expected Neon branch/database. Rehearse migrations.
2. Verify an actual signup email in a controlled inbox, click the full link, and
   exercise resend, expiry, already-used links and a temporary provider outage.
3. Register pending heads, check the administrator queue and notifications, then
   approve/reject/re-request. Confirm a fourth approval fails and decisions remain
   after refresh, a new session and redeployment.
4. Verify the class-code email timing/content and the rejected-user support flow.
   Confirm an approved head can manage its own active class and cannot transfer
   those privileges with another class code.
5. Exercise password reset in a controlled account; verify inbox delivery, replay
   rejection and failure recovery. Audit JWT/session revocation requirements
   separately; this repair does not claim all existing JWTs are revoked by reset.
6. Continue the hierarchy/upload/read phase and remaining checklist. These account
   tests are not evidence that the entire application works perfectly.

## Latest local verification checkpoint

On 2026-10-13, the complete frontend production build passed with TypeScript errors enforced (47 static pages generated). The build used a loopback test API URL; deployment must build with the intended environment. Local checks total 122: 43 persistence, 36 account/email/password, 19 legacy-transfer, 16 frontend guard/session, and 8 browser journeys. Browser fixtures simulate the API, and the backend integration suite separately uses PostgreSQL 18.3. No remote CI, Render deployment, Neon mutation, inbox delivery or backup/restore is claimed.
