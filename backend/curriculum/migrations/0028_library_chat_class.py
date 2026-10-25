from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('curriculum', '0027_topic_upload_title_length')]
    operations = [migrations.AddField(
        model_name='slidechatmessage', name='library_class',
        field=models.ForeignKey(blank=True, null=True, related_name='+',
                                on_delete=django.db.models.deletion.CASCADE, to='accounts.classgroup'),
    ), migrations.AddField(model_name='slidechatmessage', name='sources',
                           field=models.JSONField(default=list, blank=True))]
