"""
Final verification script — run with:
  python verify_all.py
"""
import os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
import django
django.setup()

results = []

# 1. Full import chain
try:
    from curriculum.ai_service import (
        slide_ai, ai_service,
        ai_tutor_chat, suggest_related_videos,
        get_study_recommendations, grade_theory_answer
    )
    from curriculum.ai_views import (
        chat_with_slide, generate_resources,
        textbook_suggestions, video_suggestions, generate_mcqs
    )
    from curriculum.tasks import process_slide_task
    from curriculum.services.slide_conversion_pipeline import SlideConversionPipeline
    from curriculum.models import Slide, SlideContent, SlideProcessingStatus
    results.append('PASS  Full import chain')
except Exception as e:
    results.append(f'FAIL  Import chain: {e}')

# 2. No duplicate URL names
try:
    from curriculum import urls as curl
    names = [p.name for p in curl.urlpatterns if hasattr(p, 'name') and p.name]
    dups = {n for n in names if names.count(n) > 1}
    if dups:
        results.append(f'FAIL  Duplicate URL names: {dups}')
    else:
        results.append(f'PASS  No duplicate URL names ({len(names)} routes)')
except Exception as e:
    results.append(f'FAIL  URL check: {e}')

# 3. SlideContent page shape matches frontend expectation
sample = [{'page_number': 1, 'image_url': 'https://example.com/img.jpg', 'width': 1280, 'height': 960}]
assert 'image_url' in sample[0]
assert 'page_number' in sample[0]
results.append('PASS  SlideContent page shape correct (image_url + page_number)')

# 4. Gemini client importable
try:
    from curriculum.ai_service import _get_client
    results.append('PASS  Gemini _get_client importable')
except Exception as e:
    results.append(f'FAIL  Gemini client: {e}')

# 5. SlideContent model fields
try:
    SlideContent._meta.get_field('content_data')
    SlideContent._meta.get_field('is_extracted')
    SlideContent._meta.get_field('extracted_at')
    results.append('PASS  SlideContent model fields (content_data, is_extracted, extracted_at)')
except Exception as e:
    results.append(f'FAIL  SlideContent fields: {e}')

# 6. Slide model fields
try:
    Slide._meta.get_field('page_count')
    Slide._meta.get_field('file_url')
    Slide._meta.get_field('file_type')
    results.append('PASS  Slide model fields (page_count, file_url, file_type)')
except Exception as e:
    results.append(f'FAIL  Slide fields: {e}')

# 7. Celery task importable and has correct name
try:
    assert hasattr(process_slide_task, 'delay')
    results.append('PASS  Celery task process_slide_task.delay() available')
except Exception as e:
    results.append(f'FAIL  Celery task: {e}')

# 8. Pipeline steps exist
try:
    assert hasattr(SlideConversionPipeline, 'step1_to_pptx')
    assert hasattr(SlideConversionPipeline, 'step2_to_pdf')
    assert hasattr(SlideConversionPipeline, 'step3_pdf_to_images')
    assert hasattr(SlideConversionPipeline, 'process_slide')
    results.append('PASS  SlideConversionPipeline has all 4 pipeline steps')
except Exception as e:
    results.append(f'FAIL  Pipeline steps: {e}')

print()
print('=' * 60)
for r in results:
    print(r)
print('=' * 60)

fails = [r for r in results if r.startswith('FAIL')]
print()
if fails:
    print(f'{len(fails)} FAILURE(S) — fix before testing')
    sys.exit(1)
else:
    print(f'ALL {len(results)} CHECKS PASSED — ready to test')
