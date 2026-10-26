from django.db import migrations, models
import django.db.models.deletion


def backfill(apps, schema_editor):
    Content = apps.get_model('curriculum', 'SlideContent')
    Page = apps.get_model('curriculum', 'SlideSearchPage')
    alias = schema_editor.connection.alias
    for content in Content.objects.using(alias).all().iterator(chunk_size=100):
        data = content.content_data
        if not isinstance(data, dict):
            continue
        rows = {}
        pages = data.get('pages')
        for index, page in enumerate(pages if isinstance(pages, list) else [], 1):
            if not isinstance(page, dict):
                continue
            number = page.get('page_number', page.get('slide_number', index))
            text = page.get('text') or page.get('extracted_text') or page.get('content')
            if type(number) is int and number > 0 and isinstance(text, str) and text.strip():
                rows[number] = text.strip()
        if not rows and isinstance(data.get('text'), str) and data['text'].strip():
            rows[1] = data['text'].strip()
        Page.objects.using(alias).bulk_create([
            Page(slide_id=content.slide_id, page_number=number, text=text) for number, text in rows.items()
        ], batch_size=200)


class Migration(migrations.Migration):
    dependencies = [('curriculum', '0029_documentindexjob')]
    operations = [
        migrations.CreateModel(name='SlideSearchPage', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('page_number', models.PositiveIntegerField()), ('text', models.TextField()),
            ('slide', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='search_pages', to='curriculum.slide')),
        ], options={'constraints': [models.UniqueConstraint(fields=('slide', 'page_number'), name='unique_slide_search_page')]}),
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
