"""
AI Service for Gemini Pro API integration
Handles textbook suggestions, video suggestions, and MCQ generation
"""

import requests
import json
import logging
from django.conf import settings
from django.core.cache import cache
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class GeminiAIService:
    """Service for interacting with Google Gemini AI directly"""
    
    def __init__(self):
        # Use direct Google Gemini API
        self.api_key = "AIzaSyCMbLJT6VzE4_g17lOeBkqb1uF2b0J7sKU"
        self.api_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent"
        self.timeout = 30
        
    def _make_request(self, prompt: str) -> Optional[str]:
        """Make request to Google Gemini API"""
        headers = {
            'Content-Type': 'application/json',
            'X-goog-api-key': self.api_key
        }
        
        data = {
            'contents': [
                {
                    'parts': [
                        {
                            'text': prompt
                        }
                    ]
                }
            ]
        }
        
        try:
            response = requests.post(
                self.api_url,
                headers=headers,
                json=data,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            result = response.json()
            
            # Extract the response text from Gemini's response format
            if 'candidates' in result and len(result['candidates']) > 0:
                candidate = result['candidates'][0]
                if 'content' in candidate and 'parts' in candidate['content']:
                    parts = candidate['content']['parts']
                    if len(parts) > 0 and 'text' in parts[0]:
                        return parts[0]['text']
            
            logger.error(f"Unexpected Gemini API response format: {result}")
            return None
            
        except requests.exceptions.Timeout:
            logger.error("Gemini API request timed out")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Gemini API request failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in Gemini API request: {e}")
            return None
    
    def get_textbook_suggestions(self, slide_title: str, slide_content: str, subject: str, slide_id: str = None) -> List[Dict[str, str]]:
        """Generate textbook suggestions for a slide using relevant chunks"""
        # Debug logging
        logger.info(f"=== TEXTBOOK SUGGESTIONS DEBUG ===")
        logger.info(f"Slide ID: {slide_id}")
        logger.info(f"Slide Title: {slide_title}")
        logger.info(f"Subject: {subject}")
        logger.info(f"Content Length: {len(slide_content) if slide_content else 0}")
        logger.info(f"Content Preview: {slide_content[:200] if slide_content else 'EMPTY'}")
        
        # If no content, return error instead of fallback
        if not slide_content or len(slide_content.strip()) < 50:
            logger.error(f"Insufficient slide content for {slide_title}")
            return [{
                "textbook": "ERROR: No slide content available",
                "chapter": "Cannot generate suggestions",
                "relevance": f"Slide content is empty or too short ({len(slide_content) if slide_content else 0} chars). Please check if the PDF was extracted correctly."
            }]
        
        # Use slide_id for cache key to avoid collisions
        cache_key = f"textbook_{slide_id}" if slide_id else f"textbook_{hash(slide_title + slide_content[:500])}"
        cached_result = cache.get(cache_key)
        if cached_result:
            logger.info(f"Returning cached result for {cache_key}")
            return cached_result
        
        # Use only first 2000 chars of content (most relevant chunks)
        content_preview = slide_content[:2000]
        
        prompt = f"""
        As a medical education expert, suggest 3 relevant textbooks for medical students studying this topic:
        
        Subject: {subject}
        Slide Title: {slide_title}
        Content Preview: {content_preview}
        
        For each textbook, provide:
        1. Textbook name and edition (appropriate for BMS/medical students)
        2. Specific chapter or section
        3. Brief explanation of why it's relevant
        
        Format your response as JSON:
        [
            {{
                "textbook": "Textbook Name, Edition",
                "chapter": "Chapter/Section",
                "relevance": "Why this is relevant"
            }}
        ]
        """
        
        response = self._make_request(prompt)
        if not response:
            return self._get_fallback_textbooks(subject)
        
        try:
            # Try to extract JSON from response
            json_start = response.find('[')
            json_end = response.rfind(']') + 1
            if json_start != -1 and json_end != -1:
                json_str = response[json_start:json_end]
                suggestions = json.loads(json_str)
                
                # Cache for 24 hours
                cache.set(cache_key, suggestions, 86400)
                return suggestions
        except (json.JSONDecodeError, ValueError):
            logger.error(f"Failed to parse textbook suggestions JSON: {response}")
        
        return self._get_fallback_textbooks(subject)
    
    def get_video_suggestions(self, slide_title: str, slide_content: str, subject: str, slide_id: str = None) -> List[Dict[str, str]]:
        """Generate video suggestions for a slide using relevant chunks"""
        # Debug logging
        logger.info(f"=== VIDEO SUGGESTIONS DEBUG ===")
        logger.info(f"Slide ID: {slide_id}")
        logger.info(f"Slide Title: {slide_title}")
        logger.info(f"Subject: {subject}")
        logger.info(f"Content Length: {len(slide_content) if slide_content else 0}")
        
        # If no content, return error instead of fallback
        if not slide_content or len(slide_content.strip()) < 50:
            logger.error(f"Insufficient slide content for {slide_title}")
            return [{
                "title": "ERROR: No slide content available",
                "channel": "System Error",
                "description": f"Slide content is empty or too short ({len(slide_content) if slide_content else 0} chars). Please check if the PDF was extracted correctly.",
                "duration": "0:00"
            }]
        
        # Use slide_id for cache key to avoid collisions
        cache_key = f"video_{slide_id}" if slide_id else f"video_{hash(slide_title + slide_content[:500])}"
        cached_result = cache.get(cache_key)
        if cached_result:
            logger.info(f"Returning cached result for {cache_key}")
            return cached_result
        
        # Use only first 2000 chars of content (most relevant chunks)
        content_preview = slide_content[:2000]
        
        prompt = f"""
        As a medical education expert, suggest 3 educational videos for medical students studying this topic:
        
        Subject: {subject}
        Slide Title: {slide_title}
        Content Preview: {content_preview}
        
        For each video, provide:
        1. Video title (realistic educational content)
        2. Channel/Creator name (real medical education channels)
        3. Brief explanation of what the video covers
        4. Estimated duration
        
        Format your response as JSON:
        [
            {{
                "title": "Video Title",
                "channel": "Channel Name",
                "description": "What this video covers",
                "duration": "X:XX"
            }}
        ]
        """
        
        response = self._make_request(prompt)
        if not response:
            return self._get_fallback_videos(subject)
        
        try:
            # Try to extract JSON from response
            json_start = response.find('[')
            json_end = response.rfind(']') + 1
            if json_start != -1 and json_end != -1:
                json_str = response[json_start:json_end]
                suggestions = json.loads(json_str)
                
                # Cache for 24 hours
                cache.set(cache_key, suggestions, 86400)
                return suggestions
        except (json.JSONDecodeError, ValueError):
            logger.error(f"Failed to parse video suggestions JSON: {response}")
        
        return self._get_fallback_videos(subject)
    
    def generate_mcqs(self, slide_title: str, slide_content: str, subject: str, slide_id: str = None) -> List[Dict[str, Any]]:
        """Generate 20 MCQs from slide content using relevant chunks"""
        # Debug logging
        logger.info(f"=== MCQ GENERATION DEBUG ===")
        logger.info(f"Slide ID: {slide_id}")
        logger.info(f"Slide Title: {slide_title}")
        logger.info(f"Subject: {subject}")
        logger.info(f"Content Length: {len(slide_content) if slide_content else 0}")
        
        # If no content, return error instead of fallback
        if not slide_content or len(slide_content.strip()) < 50:
            logger.error(f"Insufficient slide content for {slide_title}")
            return [{
                "question": f"ERROR: Cannot generate questions - slide content is empty or too short ({len(slide_content) if slide_content else 0} chars)",
                "options": {
                    "A": "Please check if the PDF was extracted correctly",
                    "B": "The slide file might be corrupted",
                    "C": "The file URL might be incorrect",
                    "D": "Contact support for assistance"
                },
                "correct_answer": "A",
                "explanation": "The slide content could not be extracted. Please verify the file is uploaded correctly to Cloudinary."
            }] * 5  # Return 5 error messages instead of 20
        
        # Use slide_id for cache key to avoid collisions
        cache_key = f"mcqs_{slide_id}" if slide_id else f"mcqs_{hash(slide_title + slide_content[:500])}"
        cached_result = cache.get(cache_key)
        if cached_result:
            logger.info(f"Returning cached result for {cache_key}")
            return cached_result
        
        # Use first 3000 chars of most relevant content
        content_preview = slide_content[:3000]
        
        prompt = f"""
        As a medical education expert, create 20 multiple choice questions from this content for medical students:
        
        Subject: {subject}
        Slide Title: {slide_title}
        Content: {content_preview}
        
        For each question, provide:
        1. Question text
        2. Four options (A, B, C, D)
        3. Correct answer (A, B, C, or D)
        4. Brief explanation of the correct answer
        
        Format your response as JSON:
        [
            {{
                "question": "Question text?",
                "options": {{
                    "A": "Option A",
                    "B": "Option B", 
                    "C": "Option C",
                    "D": "Option D"
                }},
                "correct_answer": "A",
                "explanation": "Why this answer is correct"
            }}
        ]
        """
        
        response = self._make_request(prompt)
        if not response:
            return self._get_fallback_mcqs(subject)
        
        try:
            # Try to extract JSON from response
            json_start = response.find('[')
            json_end = response.rfind(']') + 1
            if json_start != -1 and json_end != -1:
                json_str = response[json_start:json_end]
                mcqs = json.loads(json_str)
                
                # Ensure we have exactly 20 questions
                if len(mcqs) > 20:
                    mcqs = mcqs[:20]
                elif len(mcqs) < 20:
                    # Pad with fallback questions if needed
                    fallback = self._get_fallback_mcqs(subject)
                    mcqs.extend(fallback[:20-len(mcqs)])
                
                # Cache for 24 hours
                cache.set(cache_key, mcqs, 86400)
                return mcqs
        except (json.JSONDecodeError, ValueError):
            logger.error(f"Failed to parse MCQs JSON: {response}")
        
        return self._get_fallback_mcqs(subject)
    
    def _get_fallback_textbooks(self, subject: str) -> List[Dict[str, str]]:
        """Fallback textbook suggestions when AI fails"""
        fallbacks = {
            'anatomy': [
                {
                    "textbook": "Moore's Clinically Oriented Anatomy, 9th Edition",
                    "chapter": "Relevant chapter based on topic",
                    "relevance": "Comprehensive clinical anatomy reference"
                },
                {
                    "textbook": "Gray's Anatomy for Students, 4th Edition", 
                    "chapter": "Corresponding section",
                    "relevance": "Student-friendly anatomy textbook"
                },
                {
                    "textbook": "Netter's Atlas of Human Anatomy, 8th Edition",
                    "chapter": "Visual reference plates",
                    "relevance": "Excellent anatomical illustrations"
                }
            ],
            'physiology': [
                {
                    "textbook": "Guyton and Hall Textbook of Medical Physiology, 14th Edition",
                    "chapter": "Relevant chapter",
                    "relevance": "Comprehensive physiology reference"
                },
                {
                    "textbook": "Costanzo Physiology, 6th Edition",
                    "chapter": "Corresponding section", 
                    "relevance": "Concise physiology for medical students"
                },
                {
                    "textbook": "Boron & Boulpaep Medical Physiology, 3rd Edition",
                    "chapter": "Related chapter",
                    "relevance": "Detailed physiological mechanisms"
                }
            ]
        }
        
        return fallbacks.get(subject.lower(), fallbacks['anatomy'])
    
    def _get_fallback_videos(self, subject: str) -> List[Dict[str, str]]:
        """Fallback video suggestions when AI fails"""
        fallbacks = {
            'anatomy': [
                {
                    "title": "Anatomical Overview and Clinical Correlations",
                    "channel": "Acland's Video Atlas",
                    "description": "Detailed anatomical structures with clinical relevance",
                    "duration": "8:30"
                },
                {
                    "title": "Interactive Anatomy Walkthrough",
                    "channel": "Kenhub",
                    "description": "Step-by-step anatomical exploration",
                    "duration": "12:15"
                },
                {
                    "title": "Clinical Anatomy Essentials",
                    "channel": "Ninja Nerd",
                    "description": "Key anatomical concepts for medical students",
                    "duration": "15:45"
                }
            ],
            'physiology': [
                {
                    "title": "Physiological Mechanisms Explained",
                    "channel": "Armando Hasudungan",
                    "description": "Clear explanation of physiological processes",
                    "duration": "10:20"
                },
                {
                    "title": "Medical Physiology Concepts",
                    "channel": "Osmosis",
                    "description": "Visual physiology for medical students",
                    "duration": "7:45"
                },
                {
                    "title": "Integrated Physiology Review",
                    "channel": "Ninja Nerd",
                    "description": "Comprehensive physiological systems review",
                    "duration": "18:30"
                }
            ]
        }
        
        return fallbacks.get(subject.lower(), fallbacks['anatomy'])
    
    def _get_fallback_mcqs(self, subject: str) -> List[Dict[str, Any]]:
        """Fallback MCQs when AI fails"""
        fallback_mcqs = [
            {
                "question": "This is a sample question about the current topic. What is the most appropriate answer?",
                "options": {
                    "A": "Option A - First choice",
                    "B": "Option B - Second choice", 
                    "C": "Option C - Third choice",
                    "D": "Option D - Fourth choice"
                },
                "correct_answer": "A",
                "explanation": "This is the correct answer because it best addresses the question asked."
            }
        ] * 20  # Repeat to get 20 questions
        
        return fallback_mcqs

# Global instance
ai_service = GeminiAIService()