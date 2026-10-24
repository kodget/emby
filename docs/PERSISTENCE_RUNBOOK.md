# Emby persistence: deployment and recovery

Prepared 2026-10-13. These are operator steps, not a record of a completed production deployment or recovery. No production database, Cloudinary account, or hosting dashboard was accessed during this repair.

## What was established

- Baseline settings silently chose `backend/db.sqlite3` when no PostgreSQL configuration was supplied, including with `DEBUG=False`. The fix refuses missing/partial production database configuration and SQLite in production. It preserves the existing PostgreSQL URL/field configuration and local development SQLite.
- Both Render web and worker builds previously ran database migrations, admin creation, and achievement seeding. Builds now only install dependencies and collect static assets. The web service's release hook alone runs the migration preflight and migrations. Worker builds have no migration step.
- `learning.0005_pushsubscription_and_more` drops legacy credit tables; the new `credits` app creates different tables without transferring that history. The preflight blocks unattended migration when those tables contain data, including accounts that the preceding migration would convert into credits. It cannot recover data already dropped. Historical credit migrations are unchanged. The unrelated curriculum.0002 index correction is described in ACCOUNT_REPAIR_RUNBOOK.md.
- Original decks, materials and generated page images use Cloudinary fields/URLs. The inspected paths do not save originals into Django's local `MEDIA_ROOT`. There is no evidence yet that uploaded bytes were lost, as opposed to missing database references or inaccessible Cloudinary URLs.
- No automatic account/content reset was found in the Render scripts. Manual scripts such as `populate_curriculum.py` and `seed_onboarding.py` contain destructive resets; they are not deployment steps.

Render's default service filesystem is ephemeral, and a persistent disk cannot be shared between web and worker services. Shared PostgreSQL and the existing Cloudinary account are the appropriate persistence boundaries for this topology. [Render persistent disks](https://render.com/docs/disks)

These findings establish failure paths in source. They do **not** identify which path caused the reported incident. The user confirmed Neon PostgreSQL and a Render backend on 2026-10-13. Exact live service/database/branch identities and their contents remain unverified.

## Configuration before deploying this change

Use the **existing** database containing the expected records. Do not provision a new empty database as a remedy for missing data.

| Setting | Required behavior |
| --- | --- |
| `DEBUG` | `False` in production; `True` for local development SQLite. |
| `USE_SQLITE` | `False` or unset in production. Even a configured PostgreSQL URL cannot be overridden with SQLite in production. |
| `DATABASE_URL` | Preferred when already used: persistent PostgreSQL URL including host, user and database. Keep provider-required SSL options. Takes precedence over `DB_*`. Never log the value. |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST` | Alternative existing configuration: all four must be nonempty in production. Web, worker, scheduler and maintenance jobs must target the same database. |
| `DB_PORT`, `DB_SSLMODE` | Port defaults to `5432`. `DB_SSLMODE` optionally supplies the PostgreSQL `sslmode` when using individual fields; retain the provider's TLS requirements. For URLs use their query options. |
| `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET` | Keep the existing shared Cloudinary environment for web and worker. Configuration presence alone does not prove valid credentials or downloadable assets. |
| `REDIS_URL`, `CELERY_BROKER_URL` | Web and workers must share the intended broker. Existing job durability/recovery needs a separate phase; this DB change does not guarantee queued work survives a Redis restart. |
| `NEXT_PUBLIC_API_URL` | Vercel build must target the intended backend, including preview versus production. Rebuild frontend when changing a public build-time value. |
| `FRONTEND_URL`, `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` | Match the deployed frontend/backend environment; compare names/hosts without sharing secrets. |

The Blueprint retains the existing `DB_*` configuration rather than silently creating or switching databases. Its separate secret inputs do not prove web/worker equality: configure a shared environment group for the existing secrets or compare both reports below. Do not blindly apply the Blueprint before checking current dashboard settings.

## Release steps

1. Export and verify a backup; save the current deploy commit and service configuration privately. Check migration history and the preflight **before** approving a rollout. For legacy credits, pause credit writes during the transfer/release window; the preflight is an observation, not a lock against concurrent old-code writes.
2. From `backend/`, capture the read-only report separately from the web and worker services, then run the other read-only commands:

   ```sh
   python manage.py persistence_report > persistence-service.json
   python manage.py check_persistence_migrations --require-existing-database
   python manage.py showmigrations --plan
   ```

3. Keep both JSON reports in a private directory outside the repository, then run `python scripts/compare_persistence_reports.py <web-report-path> <worker-report-path>` from the repository root. It exits nonzero if the database target, Cloudinary account, or applied migration history differs. A changed host alias/pooler can change the database fingerprint without changing the underlying database; the operator must verify that alias mapping. Equal fingerprints establish matching configuration, not historical continuity or a working backup.
4. Rehearse this exact change on staging backed by a separate database and Cloudinary test assets. The release hook is `bash render_release.sh`: preflight, `migrate --noinput`, then `migrate --check`. A nonzero exit stops the hook. The account/archive migrations and PostgreSQL battle-index correction are documented in ACCOUNT_REPAIR_RUNBOOK.md.
5. Render's web `preDeployCommand` requires a paid service. If the existing web plan lacks this hook, omit that one Blueprint property and run `bash render_release.sh` once as a deliberate release job against the same database, after building and before starting the new revision. Do not move it into both build scripts or every worker start. Do not change the hosting plan without approval. [Render deployment lifecycle](https://render.com/docs/deploys)
6. If deploying multiple services, finish the controlled release step before rolling out workers that require the new schema. Render hooks do not themselves order all services in a Blueprint. Serialize releases; do not run simultaneous release jobs.
7. Deploy only after the separate production authorization, then capture another report and perform the acceptance check below.

Admin creation (`python manage.py create_admin`) and initial achievement catalogue seeding (`python manage.py seed_gamification`) are now explicit maintenance actions for an intentional setup. Existing users and awards need neither action on ordinary deploys. Review the admin environment carefully: its overwrite-password option and account promotion are intentional mutations.

The automatic release also refuses a database without migration history, rather than silently initializing a newly empty target. For an intentional first installation only, verify that this is a new environment with no existing data to recover, run the standalone preflight without `--require-existing-database`, and explicitly initialize with `python manage.py migrate --noinput`. Ordinary releases must retain the existing-database check. A populated but wrong database still requires the fingerprint/record comparison above.

The existing native build script also calls `apt-get` for LibreOffice/poppler. Its compatibility with the actual hosting runtime has not been tested here; a permission/install failure is a build issue, not proof of data loss. Address it separately from this persistence patch.

### If the migration guard stops the release

Do not disable the guard, fake migration history, or roll migrations backward. `learning.0004` has a reverse operation that deletes legacy lots and transactions.

Make a verified backup and restore a staging clone. Inspect the legacy and new credit tables on that clone. Design a transfer with explicit mappings for user references, package/lot identifiers, transaction history and idempotency references; reconcile balances, row counts and foreign keys. Only after that procedure has been reviewed and successfully rehearsed should an operator transfer production records and deliberately apply the destructive historical migration. An explicit conservative transfer is now available and locally tested; follow LEGACY_CREDIT_TRANSFER.md. It does not bypass the release guard or recover rows that were already deleted. If `0005` already ran, inspect backup history separately.

## Staging restart/redeploy acceptance

Use dedicated test accounts and a separate staging DB. Pause unrelated test traffic and scheduled jobs when comparing counts. Keep IDs and file hashes in a private test receipt, outside git.

1. Create an administrator, an approved class head and a student; a class with membership; subject/block/subblock/topic hierarchy; a small multipage PDF deck; a saved note and conversation. Also retain existing or create controlled sample questions, a completed attempt/response, an achievement award, and credit lots/transactions. Record exact record IDs and the approved-role flags. Do not use production reset/seed scripts for this fixture.
2. Capture `persistence_report` from web and worker. Record a private query/export of the selected records including class relationships, note/chat contents, answers and credit amounts. Counts alone cannot detect replacement records or changed content.
3. Open the original deck and representative derived page images as an authorized student. Download the actual bytes and record SHA-256 hashes (Windows: `Get-FileHash -Algorithm SHA256 -LiteralPath '<downloaded-file>'`; Unix: `sha256sum '<downloaded-file>'`). A database URL or a successful HTTP HEAD is not proof that the file is readable.
4. Restart web and worker, then repeat after a normal code redeploy. Reconnect using the same staging frontend/API.
5. Require the same IDs, relationships, role/approval flags, note/chat content, question bank, attempt/response, award and credit amounts. Compare reports and private samples. Download files again and require identical hashes; open the reader successfully independently of AI completion.
6. If records exist in direct database queries but not in the UI, capture the failing API method/path/status and redacted response; investigate authorization, class filters and frontend/backend URL alignment instead of restoring data.
7. Save the before/after reports, file hashes, deploy commits, timestamps, and outcome in the private staging receipt. Record any feature that could not create its sample as unverified. No successful result is claimed until this exercise actually runs.

## Backups and recovery

A PostgreSQL backup stores file references, not Cloudinary asset bytes. Protect both.

1. Identify the actual production database provider, its database/branch identity, PostgreSQL major version, backup retention, last successful backup, and available recovery window. Record who owns recovery and the acceptable data-loss/recovery-time targets. No backup schedule or retention policy has been verified in this audit.
2. Before migration, export a custom-format backup using matching PostgreSQL client tools from a trusted operator machine. Use a local PostgreSQL service definition and password file so credentials are not embedded in commands/logs:

   ```sh
   pg_dump --dbname="service=emby_source" --format=custom --no-owner --no-acl --file=emby-before-release.dump
   pg_restore --list emby-before-release.dump
   ```

   `emby_source` must be explicitly configured by the operator for the existing source database. Store the dump encrypted outside the application filesystem and repository, with restricted access, timestamp and checksum. Schedule recurring exports/provider backups through the deployed setup after its provider and approved retention are established. A dump remaining only on Render's local disk is insufficient.
3. Create a **separate, empty** recovery target and verify its host/database identity. Restore into that target only:

   ```sh
   pg_restore --dbname="service=emby_restore_test" --exit-on-error --no-owner --no-acl emby-before-release.dump
   ```

   Configure `emby_restore_test` separately; it must never alias production. Verify counts, foreign keys, sampled accounts/content/credits and application reads against the restored target. A successful dump command or archive listing alone is not a restore test.
4. Check Cloudinary's backup/version settings and export/inventory options for the **existing** account; preserve public IDs, resource types, versions and readable originals/derived assets. Test asset recovery in an isolated location. Account-specific retention and backup availability remain unverified. [Cloudinary backups and version management](https://cloudinary.com/documentation/backups_and_version_management)
5. If actual production uses Render Postgres, inspect its Recovery page for the available backup options; paid and free plans have different recovery capabilities. Do not infer those capabilities for the locally configured Neon service. [Render database recovery](https://render.com/docs/postgresql-backups)
6. For a past loss, stop destructive maintenance, retain current DB/file evidence, and investigate the old service/database/branch and backups before switching connections. If recoverable, restore to a separate target and compare before an authorized cutover. Recovery cannot be promised without an available, verified source.

### Rollback

This repair changes no database schema. If its configuration guard exposes a deployment misconfiguration, correct the configuration to the existing database. If code rollback is necessary, redeploy the previous compatible application revision while preserving the database and Cloudinary settings and the controlled release process. Do not restore the old SQLite fallback as a workaround.

Never use backward Django migrations or an in-place database restore as routine rollback here: historical credit rollback can delete data. If a migration incident needs recovery, restore a verified backup into a new isolated target, reconcile writes since the backup, and authorize a separate cutover. Keep the original database until recovery is validated.

## Exact redacted evidence needed to resolve the reported incident

Supply these text artifacts without `.env` files, passwords, tokens, cookies, SMTP/AI keys or credential-bearing URLs:

- Production hosting provider and service names/types; which DB provider/branch the backend uses; last known good and first affected deploy timestamps/commits.
- `persistence_report` JSON from web and worker (and scheduler if one exists), ideally before and after the affected deploy. It contains hashed configured targets, credential-presence booleans, model/through-table counts and migration names, not rows or credential values. Review the artifact before sharing.
- `check_persistence_migrations` outcome plus `showmigrations --plan`; the web/worker build, predeploy and start command text; whether a persistent disk is attached and its mount path. Scrub any inline secrets from commands/logs.
- Environment **names and set/unset status** for the table above, plus `CELERY_TASK_ALWAYS_EAGER`. For `NEXT_PUBLIC_API_URL`/`FRONTEND_URL`, public origins can be shared. Confirm web/worker database identity equality without sending connection strings.
- The sanitized exception type and surrounding build/start/API error lines from the affected deployment. Existing application logs may print request data or provider URLs; remove those sensitive values first.
- One affected record type and a locally checked conclusion: exists in intended DB, exists in a different DB, or absent in all checked DBs. Give a sample ID only if safe. Include the matching API path/status and redacted response if the UI hides an existing record.
- For one affected deck: Cloudinary asset exists/absent, original/derived download status, and before/after byte hash if available; no signed URLs are needed.
- Backup provider, retention and latest successful backup timestamp; whether a restore has ever been validated. This resolves recoverability separately from the deployment code fix.

## Local regression commands

From the repository root, use an isolated environment:

```sh
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r backend/tests/requirements-persistence.txt
.venv/Scripts/python.exe -m unittest discover -s backend/tests -t backend -p "test_*.py" -v
```

On Unix use `.venv/bin/python`. These tests import the configuration helper and mock the management-command database boundaries; they do not load `backend/.env`, connect to PostgreSQL, send email, call AI or fetch Cloudinary assets. They establish local guard/diagnostic behavior, not deployed persistence, provider delivery, migration compatibility or recovery success.
