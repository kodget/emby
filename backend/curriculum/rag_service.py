"""
RAG (Retrieval Augmented Generation) Service
Handles PDF chunking, embedding generation, and similarity search
"""

import logging
from typing import List, Dict, Tuple
import threading
import concurrent.futures

from django.utils import timezone

from .models import Slide, SlideChunk, SlideProcessingStatus
from .services.document_extraction import ensure_slide_extraction, content_text

logger = logging.getLogger(__name__)

class RAGService:
    """Service for chunking PDFs and retrieving relevant content.

    The embedding model (sentence-transformers / torch) is heavy, so it is
    loaded lazily on first use rather than at import time. This keeps server
    boot fast and makes RAG an optional dependency.
    """

    def __init__(self):
        self._model = None
        self._model_future = None
        self._model_lock = threading.Lock()
        self._executor = None
        self.chunk_size = 800  # words per chunk
        self.chunk_overlap = 100  # words overlap between chunks

    @property
    def model(self):
        """Lazy-load the embedding model on first access with a timeout."""
        if self._model is not None:
            return self._model
            
        with self._model_lock:
            if self._model is not None:
                return self._model
                
            if self._model_future is None:
                def load_model():
                    from sentence_transformers import SentenceTransformer
                    logger.info("Loading embedding model 'all-MiniLM-L6-v2' (first use)...")
                    return SentenceTransformer('all-MiniLM-L6-v2')
                
                self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                self._model_future = self._executor.submit(load_model)
                
        try:
            self._model = self._model_future.result(timeout=15)
            if self._executor:
                self._executor.shutdown(wait=False)
                self._executor = None
            return self._model
        except concurrent.futures.TimeoutError:
            logger.warning("Embedding model is taking too long to load. Aborting this request safely.")
            raise TimeoutError("The AI model is currently booting up. Please try again in a few moments.")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            with self._model_lock:
                self._model_future = None
                if self._executor:
                    self._executor.shutdown(wait=False)
                    self._executor = None
            raise e
    
    def chunk_text(self, text: str, page_number: int = None) -> List[Dict]:
        """Split text into overlapping chunks"""
        words = text.split()
        chunks = []
        
        start = 0
        chunk_index = 0
        
        while start < len(words):
            end = start + self.chunk_size
            chunk_words = words[start:end]
            chunk_text = ' '.join(chunk_words)
            
            if chunk_text.strip():
                chunks.append({
                    'text': chunk_text,
                    'chunk_index': chunk_index,
                    'page_number': page_number,
                    'word_count': len(chunk_words)
                })
                chunk_index += 1
            
            start += (self.chunk_size - self.chunk_overlap)
        
        return chunks
    
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding vector for text"""
        try:
            embedding = self.model.encode(text, convert_to_numpy=True)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return None
    
    def process_slide(self, slide: Slide) -> bool:
        """Publish chunks only when every page and every embedding succeeded."""
        from django.db import transaction
        import hashlib
        from .models import SlideContent
        status, _ = SlideProcessingStatus.objects.get_or_create(slide=slide)
        try:
            data = ensure_slide_extraction(slide)
            digest = hashlib.sha256(content_text(data, require_complete=True).encode()).hexdigest()
            if (status.is_embedded and data.get('indexed_text_sha256') == digest
                    and SlideChunk.objects.filter(slide=slide).count() == status.chunk_count and status.chunk_count):
                return True
            chunk_objects = []
            for page in data['pages']:
                for chunk in self.chunk_text(page['text'], page['page_number']):
                    embedding = self.generate_embedding(chunk['text'])
                    if not embedding:
                        raise ValueError('An embedding could not be generated.')
                    chunk_objects.append(SlideChunk(
                        slide=slide, chunk_index=len(chunk_objects), text=chunk['text'],
                        page_number=chunk['page_number'], word_count=chunk['word_count'], embedding=embedding))
            if not chunk_objects:
                raise ValueError('No readable document text.')
            with transaction.atomic():
                # Serialize replacements so concurrent requests cannot combine two chunk sets.
                status = SlideProcessingStatus.objects.select_for_update().get(pk=status.pk)
                content = SlideContent.objects.select_for_update().get(slide=slide)
                current_text = content_text(content.content_data, require_complete=True)
                if hashlib.sha256(current_text.encode()).hexdigest() != digest:
                    raise ValueError('The extracted document changed during indexing.')
                SlideChunk.objects.filter(slide=slide).delete()
                SlideChunk.objects.bulk_create(chunk_objects)
                status.content_extracted = True
                status.is_chunked = True
                status.is_embedded = True
                status.chunk_count = len(chunk_objects)
                status.processed_at = timezone.now()
                status.error_message = ''
                status.save()
                content.content_data['indexed_text_sha256'] = digest
                content.save(update_fields=['content_data', 'updated_at'])
            return True
        except Exception as exc:
            logger.error('Error processing slide %s (%s)', slide.id, type(exc).__name__)
            status.error_message = 'Complete document text could not be indexed. Please retry processing.'
            status.is_embedded = False
            status.save(update_fields=['error_message', 'is_embedded'])
            return False

    def find_relevant_chunks(self, slide: Slide, query: str, top_k: int = 5) -> List[Tuple[SlideChunk, float]]:
        """Find the most relevant chunks for a query"""
        import numpy as np
        from sklearn.metrics.pairwise import cosine_similarity
        try:
            # Ensure slide is processed
            if not self.process_slide(slide):
                return []
            
            # Get all chunks for this slide
            chunks = SlideChunk.objects.filter(slide=slide, embedding__isnull=False)
            
            if not chunks.exists():
                logger.warning(f"No chunks found for slide {slide.id}")
                return []
            
            # Generate query embedding
            query_embedding = self.generate_embedding(query)
            if not query_embedding:
                return []
            
            # Calculate similarities
            query_vector = np.array(query_embedding).reshape(1, -1)
            similarities = []
            
            for chunk in chunks:
                chunk_vector = np.array(chunk.embedding).reshape(1, -1)
                similarity = cosine_similarity(query_vector, chunk_vector)[0][0]
                similarities.append((chunk, float(similarity)))
            
            # Sort by similarity and return top_k
            similarities.sort(key=lambda x: x[1], reverse=True)
            return similarities[:top_k]
            
        except Exception as e:
            logger.error(f"Error finding relevant chunks: {e}")
            return []
    
    def get_context_for_query(self, slide: Slide, query: str, max_chunks: int = 5) -> str:
        """Get relevant context text for a query"""
        relevant_chunks = self.find_relevant_chunks(slide, query, top_k=max_chunks)
        
        if not relevant_chunks:
            # Fallback to first few chunks if no relevant ones found
            if not SlideProcessingStatus.objects.filter(slide=slide, is_embedded=True).exists():
                return ''
            chunks = SlideChunk.objects.filter(slide=slide).order_by('chunk_index')[:max_chunks]
            context_parts = [chunk.text for chunk in chunks]
        else:
            context_parts = [chunk.text for chunk, score in relevant_chunks]
        
        return "\n\n".join(context_parts)

# Global instance
rag_service = RAGService()
