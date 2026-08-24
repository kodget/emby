import json
import logging
from typing import List, Dict, Any
from .ai_question_generator import _generate, _strip_json_fences, Gemini429Exception

logger = logging.getLogger(__name__)

class AIFlashcardGenerator:
    """
    Service class for generating flashcards directly from slide/note text.
    """
    
    @staticmethod
    def generate_flashcards_from_text(text: str, slide, topic, count: int) -> List[Dict[str, Any]]:
        """
        Generate flashcards from text.
        """
        subject_name = slide.subject.name if slide and slide.subject else "General"
        topic_name = topic.name if topic else (slide.title if slide else "")
        source = text.strip()[:15000]
        
        prompt = f"""You are a medical educator creating highly effective spaced-repetition flashcards for Nigerian medical students.
        
SUBJECT: {subject_name}
TOPIC: {topic_name}
SOURCE MATERIAL:
{source}

TASK: Create exactly {count} flashcards strictly grounded in the SOURCE MATERIAL above.
Each flashcard must have a concise 'front' (the question or prompt) and a clear, accurate 'back' (the answer).
Include a brief 'explanation' for context where appropriate.

RESPOND ONLY WITH VALID JSON. NO MARKDOWN CODE BLOCKS. NO PREAMBLE.

Format:
[
  {{
    "front": "What is the primary function of...?",
    "back": "To produce...",
    "explanation": "This occurs because..."
  }}
]
"""
        raw = _generate([prompt])
        data = json.loads(_strip_json_fences(raw))
        if not isinstance(data, list):
            if isinstance(data, dict) and "flashcards" in data:
                data = data["flashcards"]
            else:
                data = [data]
                
        # Validate/clean
        cleaned = []
        for item in data[:count]:
            front = item.get("front", item.get("question", "")).strip()
            back = item.get("back", item.get("answer", "")).strip()
            if front and back:
                cleaned.append({
                    "front": front,
                    "back": back,
                    "explanation": item.get("explanation", "").strip(),
                })
        return cleaned

