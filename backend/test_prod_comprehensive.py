"""
Comprehensive production readiness test.
Tests: auth, slide content, text extraction, LLM, flashcards, MCQs, quizzes, analytics, credits.

Run: python test_prod_comprehensive.py
"""
import os, sys, json, django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

import requests
from django.contrib.auth import get_user_model
from curriculum.models import Slide, SlideContent
from curriculum.tasks import _extract_text_from_content
from curriculum.llm import providers, is_configured, chat

PROD_BASE = "https://emby-jkwv.onrender.com"
PASS = True
FAIL = False

results = []

def check(name, passed, detail=""):
    status = "✅ PASS" if passed else "❌ FAIL"
    results.append((name, passed, detail))
    print(f"{status}  {name}")
    if detail:
        print(f"       {detail}")

# ─────────────────────────────────────────────────────────────────────────────
# 1. LLM CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────
print("\n── 1. LLM Configuration ──────────────────────────────────────────")
p = providers()
check("LLM providers configured", len(p) > 0,
      f"{len(p)} provider(s): {[x.name for x in p]}")

if p:
    try:
        result = chat([{"role": "user", "content": "Reply with the single word: WORKING"}],
                      max_tokens=10)
        check("LLM API call succeeds", "WORKING" in result.upper() or len(result) > 0,
              f"Response: {result[:80]}")
    except Exception as e:
        check("LLM API call succeeds", False, str(e))

# ─────────────────────────────────────────────────────────────────────────────
# 2. SLIDE CONTENT & TEXT EXTRACTION
# ─────────────────────────────────────────────────────────────────────────────
print("\n── 2. Slide Content & Text Extraction ───────────────────────────")
slides_with_content = SlideContent.objects.select_related("slide").all()
check("SlideContent records exist", slides_with_content.count() > 0,
      f"{slides_with_content.count()} records")

extractable = 0
no_text = 0
for sc in slides_with_content[:20]:
    text = _extract_text_from_content(sc.content_data)
    if len(text.strip()) >= 100:
        extractable += 1
    else:
        no_text += 1

check("Slides have extractable text (>=100 chars)", extractable > 0,
      f"{extractable} extractable, {no_text} insufficient (from first 20)")

# Show a sample extraction
sample = slides_with_content.first()
if sample:
    text = _extract_text_from_content(sample.content_data)
    keys = list(sample.content_data.keys()) if sample.content_data else []
    check("content_data structure readable", True, f"Keys: {keys}, text extracted: {len(text)} chars")

# ─────────────────────────────────────────────────────────────────────────────
# 3. CREDIT MANAGEMENT (local)
# ─────────────────────────────────────────────────────────────────────────────
print("\n── 3. Credit Management System ──────────────────────────────────")
try:
    from credits.services import CreditManager, InsufficientCreditsError
    from credits.models import CreditAction

    User = get_user_model()
    test_user = User.objects.first()
    if test_user:
        balance = CreditManager.get_user_balance(test_user)
        check("CreditManager.get_user_balance works", True, f"Balance: {balance}")

        actions = list(CreditAction.objects.values_list("action_type", flat=True))
        check("CreditAction records exist (seeded)", len(actions) > 0,
              f"{len(actions)} actions: {actions[:5]}")

        # Try reserving credits for flashcard generation
        try:
            reservation = CreditManager.reserve_credits(test_user, "GENERATE_FLASHCARDS")
            CreditManager.refund_credits(test_user, reservation["reserved_amount"],
                                         action="REFUND_TEST", tx_id=reservation["transaction_id"])
            check("Credit reservation + refund cycle works", True,
                  f"Reserved & refunded {reservation['reserved_amount']} credits")
        except InsufficientCreditsError as e:
            check("Credit reservation + refund cycle works", False,
                  f"INSUFFICIENT CREDITS — user has {balance} credits. This blocks AI generation!")
    else:
        check("Test user exists", False, "No users in database")
except Exception as e:
    check("Credit management importable", False, str(e))

# ─────────────────────────────────────────────────────────────────────────────
# 4. TASK IMPORTS (ensure all tasks importable)
# ─────────────────────────────────────────────────────────────────────────────
print("\n── 4. Celery Task Imports ────────────────────────────────────────")
try:
    from curriculum.tasks import (
        generate_questions_task,
        generate_ai_flashcards_from_slide_task,
        analyze_quiz_attempt_task,
        process_slide_task,
    )
    check("All Celery tasks importable", True)
except Exception as e:
    check("All Celery tasks importable", False, str(e))

# ─────────────────────────────────────────────────────────────────────────────
# 5. LOCAL FLASHCARD GENERATION (end-to-end with real LLM)
# ─────────────────────────────────────────────────────────────────────────────
print("\n── 5. Flashcard Generation (local, real LLM) ────────────────────")
if slides_with_content.exists() and p:
    # Find a slide with enough text
    good_slide_content = None
    for sc in slides_with_content[:20]:
        t = _extract_text_from_content(sc.content_data)
        if len(t.strip()) >= 100:
            good_slide_content = sc
            break

    if good_slide_content:
        try:
            from curriculum.services.ai_flashcard_generator import AIFlashcardGenerator
            text = _extract_text_from_content(good_slide_content.content_data)
            cards = AIFlashcardGenerator.generate_flashcards_from_text(
                text=text,
                slide=good_slide_content.slide,
                topic=getattr(good_slide_content.slide, 'topic', None),
                count=2,
            )
            check("Flashcard generation with real LLM", len(cards) > 0,
                  f"Generated {len(cards)} cards. Front: {cards[0]['front'][:60] if cards else 'none'}")
        except Exception as e:
            check("Flashcard generation with real LLM", False, str(e))
    else:
        check("Flashcard generation with real LLM", False,
              "No slide with sufficient text found")

# ─────────────────────────────────────────────────────────────────────────────
# 6. LOCAL MCQ GENERATION (end-to-end)
# ─────────────────────────────────────────────────────────────────────────────
print("\n── 6. MCQ Generation (local, real LLM) ──────────────────────────")
if good_slide_content and p:
    try:
        from curriculum.services.ai_question_generator import AIQuestionGenerator
        text = _extract_text_from_content(good_slide_content.content_data)
        qs = AIQuestionGenerator.generate_questions(
            text=text,
            slide=good_slide_content.slide,
            count=2,
            difficulty="medium",
        )
        check("MCQ generation with real LLM", len(qs) > 0,
              f"Generated {len(qs)} MCQs. Q: {qs[0].get('question','')[:60] if qs else 'none'}")
    except Exception as e:
        check("MCQ generation with real LLM", False, str(e))

# ─────────────────────────────────────────────────────────────────────────────
# 7. PRODUCTION API HEALTH CHECKS (no auth needed)
# ─────────────────────────────────────────────────────────────────────────────
print("\n── 7. Production API Endpoints ──────────────────────────────────")
try:
    r = requests.get(f"{PROD_BASE}/health/", timeout=15)
    check("Production /health/ endpoint", r.status_code == 200, r.text[:80])

    r = requests.post(f"{PROD_BASE}/auth/login/",
                      json={"email": "notexist@test.com", "password": "wrong"},
                      timeout=15)
    check("Production /auth/login/ responds (401 expected)", r.status_code == 401,
          f"Got {r.status_code}")

    r = requests.get(f"{PROD_BASE}/api/subjects/",
                     headers={"Authorization": "Bearer invalid"}, timeout=15)
    check("Production /api/subjects/ responds (401 expected)", r.status_code == 401,
          f"Got {r.status_code}")
except Exception as e:
    check("Production reachable", False, str(e))

# ─────────────────────────────────────────────────────────────────────────────
# 8. ANALYTICS ENDPOINTS (local)
# ─────────────────────────────────────────────────────────────────────────────
print("\n── 8. Analytics / Learning URLs ─────────────────────────────────")
try:
    from django.urls import reverse
    urls_to_check = [
        ("learning:analytics", {}),
    ]
    # Just check the views import cleanly
    from learning import views as lv
    check("Learning views importable", True)
    from curriculum import views as cv
    check("Curriculum views importable", True)
    from curriculum import ai_views as av
    check("Curriculum ai_views importable", True)
except Exception as e:
    check("Analytics views importable", False, str(e))

# ─────────────────────────────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "═"*60)
print("SUMMARY")
print("═"*60)
passed = sum(1 for _, p, _ in results if p)
failed = sum(1 for _, p, _ in results if not p)
print(f"✅ {passed} passed   ❌ {failed} failed   ({len(results)} total)\n")

if failed:
    print("FAILURES TO FIX:")
    for name, p, detail in results:
        if not p:
            print(f"  ❌ {name}")
            if detail:
                print(f"     {detail}")
