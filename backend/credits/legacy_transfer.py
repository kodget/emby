"""Conservative transfer of the ledger removed by learning.0005.

This deliberately does not run as a migration: mixed old/new financial ledgers
need reconciliation and must never be merged by guessing which rows overlap.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from uuid import UUID

from django.contrib.auth import get_user_model
from django.core.serializers.json import DjangoJSONEncoder
from django.db import connections, transaction
from django.db.migrations.recorder import MigrationRecorder
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import CreditLot, CreditPackage, CreditTransaction, LegacyCreditRecord


LOT_TABLE = "learning_creditlot"
TRANSACTION_TABLE = "learning_credittransaction"
PACKAGE_TABLE = "learning_creditpackage"
SOURCE_TABLES = (LOT_TABLE, TRANSACTION_TABLE, PACKAGE_TABLE)
TRANSFER_MIGRATION = ("credits", "0003_legacycreditrecord")
CONVERSION_MIGRATION = ("learning", "0004_migrate_old_credits")
DROP_MIGRATION = ("learning", "0005_pushsubscription_and_more")
PROVENANCE_KEY = "_legacy_credit_transfer"
LOT_FIELDS = (
    "user_id", "source", "original_amount", "remaining_amount", "granted_at",
    "expires_at", "created_at",
)
TRANSACTION_FIELDS = (
    "user_id", "type", "amount", "balance_before", "balance_after", "action",
    "description", "created_at",
)
REQUIRED_COLUMNS = {
    LOT_TABLE: {"id", *LOT_FIELDS, "updated_at", "allocation_date", "purchase_reference"},
    TRANSACTION_TABLE: {
        "id", *TRANSACTION_FIELDS, "reference_lot_id", "lot_breakdown", "metadata",
    },
    PACKAGE_TABLE: {
        "id", "name", "credits", "price_naira", "is_active", "created_at", "updated_at",
    },
}


class LegacyTransferError(Exception):
    """A known condition requires operator review without changing data."""


class _ArchiveEncoder(DjangoJSONEncoder):
    def default(self, value):
        # DjangoJSONEncoder truncates datetimes to milliseconds; an audit archive
        # must preserve the database's full microsecond precision.
        if isinstance(value, datetime):
            return value.isoformat()
        return super().default(value)


def _canonical(value):
    return json.loads(json.dumps(value, cls=_ArchiveEncoder, sort_keys=True))


def _digest(payload):
    data = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _timestamp(value):
    parsed = value if isinstance(value, datetime) else parse_datetime(value)
    if parsed is None or timezone.is_naive(parsed):
        raise LegacyTransferError("Legacy timestamps must include a timezone; review the source database timezone before transferring.")
    return parsed


def _read_sources(connection):
    result = {}
    with connection.cursor() as cursor:
        for table in SOURCE_TABLES:
            cursor.execute(f"SELECT * FROM {connection.ops.quote_name(table)} ORDER BY id")
            names = [column[0] for column in cursor.description]
            if not REQUIRED_COLUMNS[table].issubset(names):
                raise LegacyTransferError("Legacy schema differs from the known migration schema. Review it before transferring.")
            rows = []
            for values in cursor.fetchall():
                row = dict(zip(names, values))
                # SQLite's raw cursor does not apply model field converters.
                # Its stored datetimes are UTC when USE_TZ is enabled.
                for name in ("granted_at", "expires_at", "created_at", "updated_at"):
                    value = row.get(name)
                    if value is not None:
                        parsed = value if isinstance(value, datetime) else parse_datetime(value)
                        if parsed is None:
                            raise LegacyTransferError("A legacy timestamp cannot be parsed. Review the source data.")
                        if connection.vendor == "sqlite" and timezone.is_naive(parsed):
                            if not connection.timezone:
                                raise LegacyTransferError("Legacy transfer requires USE_TZ=True.")
                            parsed = timezone.make_aware(parsed, connection.timezone)
                        row[name] = _timestamp(parsed)
                if table == TRANSACTION_TABLE:
                    row["id"] = str(UUID(str(row["id"])))
                    for name in ("metadata", "lot_breakdown"):
                        if isinstance(row[name], str):
                            row[name] = json.loads(row[name])
                if table == PACKAGE_TABLE:
                    row["is_active"] = bool(row["is_active"])
                rows.append(_canonical(row))
            result[table] = rows
    return result


def _validate_sources(rows, database):
    lots = {str(row["id"]): row for row in rows[LOT_TABLE]}
    user_ids = {row["user_id"] for table in (LOT_TABLE, TRANSACTION_TABLE) for row in rows[table]}
    existing = set(get_user_model().objects.using(database).filter(pk__in=user_ids).values_list("pk", flat=True))
    if existing != user_ids:
        raise LegacyTransferError("Legacy credits reference missing users. Restore or reconcile those accounts first.")
    for lot in lots.values():
        if not 0 <= lot["remaining_amount"] <= lot["original_amount"]:
            raise LegacyTransferError("A legacy lot has an invalid balance. Reconcile it before transferring.")
    for row in rows[TRANSACTION_TABLE]:
        if not isinstance(row["metadata"], dict) or PROVENANCE_KEY in row["metadata"]:
            raise LegacyTransferError("Legacy transaction metadata cannot be safely extended. Review it before transferring.")
        if not isinstance(row["lot_breakdown"], list):
            raise LegacyTransferError("Legacy lot breakdown must be a list. Review it before transferring.")
        references = []
        if row["reference_lot_id"] is not None:
            references.append(str(row["reference_lot_id"]))
        for item in row["lot_breakdown"]:
            if not isinstance(item, dict) or "lot_id" not in item:
                raise LegacyTransferError("A legacy lot breakdown has an unknown format. Review it before transferring.")
            references.append(str(item["lot_id"]))
        if any(ref not in lots or lots[ref]["user_id"] != row["user_id"] for ref in references):
            raise LegacyTransferError("Legacy transaction lot references are missing or belong to another user. Reconcile them first.")


def _target_values(table, row, lot_ids):
    if table == LOT_TABLE:
        return {name: row[name] for name in LOT_FIELDS}
    breakdown = [dict(item, lot_id=str(lot_ids[str(item["lot_id"])])) for item in row["lot_breakdown"]]
    metadata = dict(row["metadata"])
    metadata[PROVENANCE_KEY] = {
        "source_table": TRANSACTION_TABLE,
        "source_pk": row["id"],
        "lot_breakdown": breakdown,
        "reference_lot_id": lot_ids.get(str(row["reference_lot_id"])),
    }
    return {
        **{name: row[name] for name in TRANSACTION_FIELDS},
        "reference_id": f"legacy-learning:{row['id']}",
        "metadata": metadata,
    }


def _verify(rows, archive, database):
    expected_keys = {(table, str(row["id"])) for table in SOURCE_TABLES for row in rows[table]}
    if set(archive) != expected_keys:
        raise LegacyTransferError("Source rows differ from the recorded transfer. Do not merge or rerun an altered ledger automatically.")
    lot_ids = {key[1]: record.target_pk for key, record in archive.items() if key[0] == LOT_TABLE}
    for table in SOURCE_TABLES:
        for row in rows[table]:
            record = archive[(table, str(row["id"]))]
            if record.payload != row or record.source_digest != _digest(row):
                raise LegacyTransferError("Source rows changed after transfer. Reconciliation is required.")
            if table == PACKAGE_TABLE:
                if record.target_pk is not None or record.target_model:
                    raise LegacyTransferError("Legacy package provenance was modified. Reconciliation is required.")
                continue
            model = CreditLot if table == LOT_TABLE else CreditTransaction
            if record.target_model != model._meta.label_lower:
                raise LegacyTransferError("Transfer provenance was modified. Reconciliation is required.")
            values = _target_values(table, row, lot_ids)
            actual = model.objects.using(database).filter(pk=record.target_pk).values(*values).first()
            if actual is None or _canonical(actual) != values:
                raise LegacyTransferError("Transferred destination rows changed or are missing. Reconciliation is required.")
    for table, model in ((LOT_TABLE, CreditLot), (TRANSACTION_TABLE, CreditTransaction)):
        if model.objects.using(database).count() != len(rows[table]):
            raise LegacyTransferError("The destination contains unrelated credit rows. Reconciliation is required.")


def transfer_legacy_credits(*, database="default", apply=False):
    """Inspect or atomically copy a pristine source ledger into empty target tables.

    No source row is changed, no migrations are applied, and packages are archived
    only: legacy price_naira and the new base-price-plus-fee field differ in meaning.
    """
    connection = connections[database]
    with transaction.atomic(using=database):
        tables = set(connection.introspection.table_names())
        if "django_migrations" not in tables:
            raise LegacyTransferError("No migration history exists. This is not a recoverable legacy ledger.")
        applied = MigrationRecorder(connection).applied_migrations()
        if DROP_MIGRATION in applied:
            raise LegacyTransferError("learning.0005 is already applied. This command cannot recover dropped rows; inspect a separate restored backup.")
        if CONVERSION_MIGRATION not in applied:
            raise LegacyTransferError("learning.0004 must already be applied. Rehearse that exact targeted migration on a backup first; do not migrate all apps.")
        if TRANSFER_MIGRATION not in applied:
            raise LegacyTransferError("Apply the targeted credits.0003 migration first, without applying learning.0005.")
        target_models = (CreditLot, CreditTransaction, CreditPackage, LegacyCreditRecord)
        needed = {*SOURCE_TABLES, *(model._meta.db_table for model in target_models)}
        if not needed.issubset(tables):
            raise LegacyTransferError("Required source or target tables are missing. Restore and inspect a separate backup; do not recreate empty legacy tables.")
        if apply and connection.vendor == "postgresql":
            quoted = ", ".join(connection.ops.quote_name(name) for name in sorted(needed))
            with connection.cursor() as cursor:
                cursor.execute(f"LOCK TABLE {quoted} IN SHARE ROW EXCLUSIVE MODE")
        elif apply and connection.vendor != "sqlite":
            raise LegacyTransferError("Transfer writes are supported only on PostgreSQL and isolated SQLite rehearsals.")
        rows = _read_sources(connection)
        _validate_sources(rows, database)
        archive = {(record.source_table, record.source_pk): record for record in LegacyCreditRecord.objects.using(database).all()}
        cutoff = timezone.now()
        active_balance = sum(
            row["remaining_amount"] for row in rows[LOT_TABLE]
            if row["remaining_amount"] > 0 and (row["expires_at"] is None or _timestamp(row["expires_at"]) > cutoff)
        )
        report = {
            "mode": "apply" if apply else "dry-run",
            "lots": len(rows[LOT_TABLE]),
            "transactions": len(rows[TRANSACTION_TABLE]),
            "packages_archived_only": len(rows[PACKAGE_TABLE]),
            "active_credit_balance": active_balance,
            "status": "ready",
        }
        if archive:
            _verify(rows, archive, database)
            report["status"] = "already-transferred-and-verified"
            return report
        if any(model.objects.using(database).exists() for model in (CreditLot, CreditTransaction)):
            raise LegacyTransferError("The destination ledger is not empty. Automatic merging could double-credit users; reconcile both ledgers first.")
        if not apply:
            return report
        lot_ids = {}
        for table in SOURCE_TABLES:
            for row in rows[table]:
                target = None
                if table != PACKAGE_TABLE:
                    model = CreditLot if table == LOT_TABLE else CreditTransaction
                    values = _target_values(table, row, lot_ids)
                    target = model.objects.using(database).create(**values)
                    # auto_now_add would otherwise rewrite historical timestamps.
                    model.objects.using(database).filter(pk=target.pk).update(created_at=_timestamp(row["created_at"]))
                    if table == LOT_TABLE:
                        lot_ids[str(row["id"])] = target.pk
                record = LegacyCreditRecord.objects.using(database).create(
                    source_table=table, source_pk=str(row["id"]),
                    source_digest=_digest(row), payload=row,
                    target_model=target._meta.label_lower if target else "",
                    target_pk=target.pk if target else None,
                )
                archive[(table, str(row["id"]))] = record
        _verify(rows, archive, database)
        report["status"] = "transferred-and-verified"
        return report
