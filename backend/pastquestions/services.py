import requests
from .models import GeneratedMCQ, GeneratedEssay, PastQuestionUpload


RAPIDAPI_KEY = "Ye2b9507f2bmsh2ab87b5b1a01727p1890dajsn024e36a56f93"


# -----------------------------------
# 1. ENTRY POINT (TRIGGER)
# -----------------------------------
def process_past_questions_async(upload_id):
    upload = PastQuestionUpload.objects.get(id=upload_id)

    return generate_ai_questions(
        content=upload.file_content,
        block_id=upload.block_id,
        upload_id=upload_id
    )


# -----------------------------------
# 2. AI PROCESSING CORE
# -----------------------------------
def generate_ai_questions(content, block_id, upload_id):

    prompt = f"""
You are an academic assistant.

Task:
- Group questions by topic
- Generate MCQs (4 options each)
- Generate essay questions

Return STRICT JSON ONLY.

Content:
{content}
"""

    response = requests.post(
        "https://gemini-1-5-flash.p.rapidapi.com/",
        headers={
            "x-rapidapi-key": RAPIDAPI_KEY,
            "Content-Type": "application/json"
        },
        json={
            "model": "gemini-1.5-flash",
            "messages": [
                {"role": "user", "content": prompt}
            ]
        },
        timeout=60
    )

    try:
        ai_data = response.json()
    except Exception:
        return {"error": "AI response failed"}

    topics = ai_data.get("topics", [])

    for topic in topics:
        topic_name = topic.get("name", "general")

        # MCQs
        for mcq in topic.get("mcqs", []):
            GeneratedMCQ.objects.create(
                question=mcq["q"],
                options=mcq["options"],
                correct=mcq["correct"],
                topic_id=topic_name
            )

        # Essays
        for essay in topic.get("essays", []):
            GeneratedEssay.objects.create(
                question=essay,
                model_answer="",
                topic_id=topic_name
            )

    return ai_data