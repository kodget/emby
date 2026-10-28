from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('curriculum', '0031_processing_progress_and_recovery')]
    operations = [
        migrations.AddField(model_name='flashcardgenerationjob', name='next_attempt_at',
                            field=models.DateTimeField(null=True, blank=True, db_index=True)),
        migrations.AddField(model_name='flashcardgenerationjob', name='attempts',
                            field=models.PositiveSmallIntegerField(default=0)),
        migrations.AddField(model_name='flashcardgenerationjob', name='tokens_used',
                            field=models.PositiveIntegerField(default=0)),
    ]
