import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('curriculum', '0018_course_reading_checkpoints'),
    ]

    operations = [
        migrations.AddField(
            model_name='slidechatmessage',
            name='deck',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='chat_messages',
                to='curriculum.slidedeck',
            ),
        ),
        migrations.AddConstraint(
            model_name='slidechatmessage',
            constraint=models.CheckConstraint(
                condition=models.Q(('slide__isnull', True), ('deck__isnull', True), _connector='OR'),
                name='chat_message_one_content_source',
            ),
        ),
        migrations.AddIndex(
            model_name='slidechatmessage',
            index=models.Index(fields=['user', 'deck', 'created_at'], name='chat_deck_history_idx'),
        ),
    ]
