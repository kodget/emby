import json
import logging
from typing import List, Dict, Any
from .ai_question_generator import _generate, _strip_json_fences, Gemini429Exception

logger = logging.getLogger(__name__)

class AIFlashcardGenerator:
    """
    Service class for generating flashcards directly from slide/note text.
    """

    MAX_SOURCE_WINDOW_CHARS = 8000

    @classmethod
    def _source_windows(cls, text: str, count: int) -> list[str]:
        """Sample bounded windows across the page-labelled source, including its end."""
        from learning.bank_sources import page_sources

        pages = page_sources(text) or {1: text.strip()}
        windows = []
        current = ''
        for page, body in pages.items():
            label = f'[Page {page}]\n'
            capacity = max(1, cls.MAX_SOURCE_WINDOW_CHARS - len(label) - 2)
            for offset in range(0, len(body), capacity):
                part = label + body[offset:offset + capacity]
                if current and len(current) + len(part) + 2 > cls.MAX_SOURCE_WINDOW_CHARS:
                    windows.append(current)
                    current = ''
                current = (current + '\n\n' + part).strip()
        if current:
            windows.append(current)

        if len(windows) <= count:
            return windows
        if count == 1:
            return [windows[len(windows) // 2]]
        return [
            windows[round(index * (len(windows) - 1) / (count - 1))]
            for index in range(count)
        ]
    
    @staticmethod
    def generate_flashcards_from_text(text: str, slide, topic, count: int, slide_image_base64: str = None, return_usage: bool = False) -> Any:
        """
        Generate flashcards from source windows sampled across the full extracted text.
        """
        subject_name = slide.subject.name if slide and slide.subject else "General"
        topic_name = topic.name if topic else (slide.title if slide else "")
        from curriculum.llm import parse_json

        if count <= 0:
            return ([], 0) if return_usage else []
        windows = AIFlashcardGenerator._source_windows(text, count)
        if not windows and slide_image_base64:
            windows = ['[Page 1]\nNo extracted text is available; use the attached slide image as source.']
        if not windows:
            return ([], 0) if return_usage else []

        per_window = count // len(windows)
        remainder = count % len(windows)
        cleaned = []
        total_tokens = 0
        seen_fronts = set()
        for index, source in enumerate(windows):
            window_count = per_window + (1 if index < remainder else 0)
            source_context = f"SOURCE MATERIAL:\n{source}\n"
            if len(windows) == 1 and slide_image_base64:
                source_context += "\nAlso refer to the provided image as source material."

            prompt = f"""You are a medical educator creating highly effective spaced-repetition flashcards for Nigerian medical students.

SUBJECT: {subject_name}
TOPIC: {topic_name}
{source_context}

TASK: Create exactly {window_count} flashcards strictly grounded in the supplied source window.
Each flashcard must have a concise 'front' (the question or prompt) and a clear, accurate 'back' (the answer).
Include a brief 'explanation' for context where appropriate. Use the page labels to spread useful cards across the source.

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
            if len(windows) == 1 and slide_image_base64:
                from curriculum.llm import chat_with_image
                try:
                    if return_usage:
                        raw, tokens = chat_with_image(
                            prompt=prompt, image_b64=slide_image_base64,
                            max_tokens=2048, return_usage=True,
                        )
                    else:
                        raw = chat_with_image(
                            prompt=prompt, image_b64=slide_image_base64, max_tokens=2048,
                        )
                        tokens = 0
                except Exception as exc:
                    logger.warning("Flashcard vision request failed; falling back to extracted text: %s", exc)
                    if return_usage:
                        raw, tokens = _generate([prompt], return_usage=True)
                    else:
                        raw = _generate([prompt])
                        tokens = 0
            else:
                if return_usage:
                    raw, tokens = _generate([prompt], return_usage=True)
                else:
                    raw = _generate([prompt])
                    tokens = 0

            total_tokens += tokens
            data = parse_json(raw, default=[])
            if not isinstance(data, list):
                data = data.get("flashcards", []) if isinstance(data, dict) else []
            for item in data:
                if not isinstance(item, dict):
                    continue
                front = item.get("front", item.get("question", ""))
                back = item.get("back", item.get("answer", ""))
                explanation = item.get("explanation", "")
                if not all(isinstance(value, str) for value in (front, back, explanation)):
                    continue
                front, back, explanation = front.strip(), back.strip(), explanation.strip()
                normalized_front = ' '.join(front.casefold().split())
                if front and back and normalized_front not in seen_fronts:
                    cleaned.append({
                        "front": front,
                        "back": back,
                        "explanation": explanation,
                    })
                    seen_fronts.add(normalized_front)

        if return_usage:
            return cleaned, total_tokens
        return cleaned
