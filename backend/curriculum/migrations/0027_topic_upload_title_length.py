from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('curriculum', '0026_brain_battle_question_timing')]

    operations = [
        migrations.AlterField(model_name='topic', name='name', field=models.CharField(max_length=200)),
    ]
