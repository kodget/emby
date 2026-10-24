from django.db import migrations, models


class Migration(migrations.Migration):
    # Deliberately independent of learning.0005: adding a dependency before an
    # already-applied migration would invalidate existing deployment histories.
    dependencies = [("credits", "0002_alter_creditlot_source")]

    operations = [
        migrations.CreateModel(
            name="LegacyCreditRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source_table", models.CharField(max_length=64)),
                ("source_pk", models.CharField(max_length=100)),
                ("source_digest", models.CharField(max_length=64)),
                ("payload", models.JSONField()),
                ("target_model", models.CharField(blank=True, max_length=64)),
                ("target_pk", models.PositiveBigIntegerField(blank=True, null=True)),
                ("imported_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "constraints": [models.UniqueConstraint(fields=("source_table", "source_pk"), name="credits_unique_legacy_source")],
            },
        ),
    ]
