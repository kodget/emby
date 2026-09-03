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
    def generate_flashcards_from_text(text: str, slide, topic, count: int, slide_image_base64: str = None, return_usage: bool = False) -> Any:
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
DO NOT use markdown formatting like **bold** or *italics* in your response. Respond in plain text.

Format:
[
  {{
    "front": "What is the primary function of...?",
    "back": "To produce...",
    "explanation": "This occurs because..."
  }}
]
"""
        if slide_image_base64:
            from curriculum.llm import chat_with_image
            try:
                if return_usage:
                    raw, tokens = chat_with_image(prompt=prompt, image_b64=slide_image_base64, max_tokens=4096, return_usage=True)
                else:
                    raw = chat_with_image(prompt=prompt, image_b64=slide_image_base64, max_tokens=4096)
            except Exception as e:
                logger.warning(f"Failed to use vision model, falling back to text: {e}")
                if return_usage:
                    raw, tokens = _generate([prompt], return_usage=True)
                else:
                    raw = _generate([prompt])
        else:
            if return_usage:
                raw, tokens = _generate([prompt], return_usage=True)
            else:
                raw = _generate([prompt])
                
        from curriculum.llm import parse_json
        data = parse_json(raw, default=[])
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
        
        if return_usage:
            return cleaned, tokens
        return cleaned

