from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_alter_profile_subscription_tier"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.AddField(model_name="profile", name="class_head_request_version",
                            field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name="profile", name="class_head_reviewed_at",
                            field=models.DateTimeField(null=True, blank=True)),
        migrations.AddField(model_name="profile", name="class_head_reviewed_by",
                            field=models.ForeignKey(null=True, blank=True,
                                on_delete=django.db.models.deletion.SET_NULL,
                                related_name="reviewed_class_head_profiles", to=settings.AUTH_USER_MODEL)),
    ]
