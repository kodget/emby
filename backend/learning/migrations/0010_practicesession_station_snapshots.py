from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('learning', '0009_learningevent_idempotency_key_and_more')]
    operations = [migrations.AddField(
        model_name='practicesession', name='station_snapshots',
        field=models.JSONField(default=list, blank=True),
    )]
