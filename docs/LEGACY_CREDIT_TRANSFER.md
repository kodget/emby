# Preserve legacy credit records before learning.0005

`learning.0005_pushsubscription_and_more` deletes the old credit lot, transaction,
and package tables. The `credits` app initially creates new, empty tables; it does
not transfer these records. The release preflight intentionally blocks this case.

The new `credits.0003_legacycreditrecord` migration only creates an archive and
provenance table. It does not repair data that has already been dropped. It adds
no dependency before an already-applied migration and does not rewrite migration
history. Ordinary first installations and already-upgraded installations can
apply it normally.

## What the operator command does

`python manage.py transfer_legacy_credits` performs a dry run by default. It
requires `learning.0004_migrate_old_credits` and `credits.0003_legacycreditrecord`
to be applied, and `learning.0005` to remain pending. All three old source tables
must still exist. It never creates missing old tables or replays old monthly
balances to guess what a user should receive.

With `--apply --confirm-writes-paused`, one transaction:

1. Copies every legacy lot and transaction into an **empty** destination ledger.
2. Preserves amounts, expiration, original grants, historical balances and full
   timestamp precision. It maps old lot IDs to newly allocated IDs and preserves
   transaction UUIDs in `reference_id` and the archive. The reference lot and lot
   breakdown move into transaction metadata under `_legacy_credit_transfer`;
   existing metadata keys are retained.
3. Archives every original source field, including allocation date, purchase
   reference, original transaction breakdown and timestamps. Each archive row
   contains a SHA-256 digest and the destination identity where applicable.
4. Archives legacy packages **without activating new sale packages**. The old
   `price_naira` field and new `price` field (base price excluding a fee) do not
   establish the same pricing rules. A product owner must approve the exact new
   package prices before these are published.
5. Verifies all copied values and provenance before committing. PostgreSQL table
   locks prevent changes to the affected tables during the copy. A failure rolls
   back the entire transfer. Source tables remain unchanged.

An unchanged rerun verifies the transfer and does not grant duplicate credits.
Changed source rows, changed/missing destination rows, unrelated destination
credits, inconsistent balances, broken lot references or ambiguous metadata
stop the operation for reconciliation. It never silently merges old and new
balances. Packages already present in the new app remain untouched.

## Rehearse on a separate restored staging database

Use a verified backup and isolated staging services. Never point a rehearsal at
production. Pause every web process, worker, scheduler, admin and other writer;
keep them paused until the final migration and reconciliation are complete.
Table locks protect the command transaction only, not the time between commands.

First inspect the selected database and migration state:

```text
python manage.py persistence_report
python manage.py showmigrations learning credits
python manage.py migrate credits 0003_legacycreditrecord --plan
```

Review the plan: it must not include `learning.0005`. Apply the targeted setup:

```text
python manage.py migrate credits 0003_legacycreditrecord
```

If `learning.0004` is pending, review a separate targeted plan before applying it
on staging. Its historical conversion grants daily allocations and converts
remaining monthly balances; it is not a general recovery procedure. Its reverse
operation deletes legacy credit records. Do not roll it backward. If its existing
logic is not appropriate to the restored data, stop for a reviewed custom data
repair. Do not run an unrestricted `migrate` to reach this state.

```text
python manage.py migrate learning 0004_migrate_old_credits --plan
python manage.py migrate learning 0004_migrate_old_credits
python manage.py transfer_legacy_credits
python manage.py transfer_legacy_credits --apply --confirm-writes-paused
python manage.py transfer_legacy_credits
```

The second inspection must report `already-transferred-and-verified`. Compare
per-user balances, row counts, timestamps, source archive fields, transaction lot
mappings and active/expired credits. The JSON output contains summary counts and
active balance only; review full records privately in the staging database. Keep
the backup and the archive, which contain sensitive account/payment history, under
the same access restrictions as the production database.

## Final migration remains a separately reviewed operator action

`check_persistence_migrations` intentionally continues blocking while populated
legacy tables remain. No bypass flag has been added. The transfer's successful
output alone is not authorization to drop tables or deploy.

After staging rehearsal, verified backup, transfer reconciliation and approval of
the target database, an operator can inspect and explicitly apply the pending
`learning.0005` migration while all writers remain paused. Recheck migration state
and application balances before resuming services. Do not reverse the transfer by
deleting destination rows or by unapplying `learning.0004`; restore the separately
verified backup if rollback is required.

If `learning.0005` was already applied and records are missing, restore an older
backup into a separate database and investigate there. The archive introduced
here cannot reconstruct deleted records. If both old and new ledgers have data,
prepare a bespoke, reviewed reconciliation with payment and usage evidence.

## Isolated regression checks

These settings never load production settings or dotenv files:

```text
cd backend
..\.venv\Scripts\python.exe -m django test credits.tests.test_legacy_transfer --settings=tests.integration_settings
```

Set `EMBY_TEST_POSTGRES=1` only when the dedicated loopback test cluster described
in `tests.integration_settings` is running to exercise the PostgreSQL lock path.
