"""
RAG (Retrieval Augmented Generation) Service
Handles PDF chunking, embedding generation, and similarity search
"""

import logging
from typing import List, Dict, Tuple

from django.utils import timezone

from .models import Slide, SlideChunk, SlideProcessingStatus
from .content_extractor import extract_text_from_slide

logger = logging.getLogger(__name__)

class RAGService:
    """Service for chunking PDFs and retrieving relevant content.

    The embedding model (sentence-transformers / torch) is heavy, so it is
    loaded lazily on first use rather than at import time. This keeps server
    boot fast and makes RAG an optional dependency.
    """

    def __init__(self):
        self._model = None
        self.chunk_size = 800  # words per chunk
        self.chunk_overlap = 100  # words overlap between chunks

    @property
    def model(self):
        """Lazy-load the embedding model on first access."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            logger.info("Loading embedding model 'all-MiniLM-L6-v2' (first use)...")
            self._model = SentenceTransformer('all-MiniLM-L6-v2')
        return self._model
    
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
        """Extract text, chunk it, and generate embeddings for a slide"""
        try:
            # Check if already processed
            status, created = SlideProcessingStatus.objects.get_or_create(slide=slide)
            if status.is_embedded:
                logger.info(f"Slide {slide.id} already processed")
                return True
            
            # Delete existing chunks
            SlideChunk.objects.filter(slide=slide).delete()
            
            # Extract text from PDF - use Cloudinary file or file_url
            file_url = None
            if slide.file:
                # Cloudinary file exists - get its URL
                file_url = slide.file.url
            elif slide.file_url:
                # Legacy file_url exists
                file_url = slide.file_url
            
            if not file_url:
                logger.error(f"Slide {slide.id} has no file or file_url")
                status.error_message = "No file URL"
                status.save()
                return False
            
            pages = extract_text_from_slide(file_url, slide.file_type or 'pdf')
            
            if not pages:
                logger.error(f"No text extracted from slide {slide.id}")
                status.error_message = "No text extracted"
                status.save()
                return False
            
            # Chunk each page
            all_chunks = []
            for page in pages:
                page_chunks = self.chunk_text(page['text'], page['page_number'])
                all_chunks.extend(page_chunks)
            
            if not all_chunks:
                logger.error(f"No chunks created for slide {slide.id}")
                status.error_message = "No chunks created"
                status.save()
                return False
            
            # Generate embeddings and save chunks
            chunk_objects = []
            for chunk_data in all_chunks:
                embedding = self.generate_embedding(chunk_data['text'])
                if embedding:
                    chunk_objects.append(SlideChunk(
                        slide=slide,
                        chunk_index=chunk_data['chunk_index'],
                        text=chunk_data['text'],
                        page_number=chunk_data['page_number'],
                        word_count=chunk_data['word_count'],
                        embedding=embedding
                    ))
            
            # Bulk create chunks
            SlideChunk.objects.bulk_create(chunk_objects)
            
            # Update status
            status.is_chunked = True
            status.is_embedded = True
            status.chunk_count = len(chunk_objects)
            status.processed_at = timezone.now()
            status.error_message = ""
            status.save()
            
            logger.info(f"Successfully processed slide {slide.id} with {len(chunk_objects)} chunks")
            return True
            
        except Exception as e:
            logger.error(f"Error processing slide {slide.id}: {e}")
            status.error_message = str(e)
            status.save()
            return False
    
    def find_relevant_chunks(self, slide: Slide, query: str, top_k: int = 5) -> List[Tuple[SlideChunk, float]]:
        """Find the most relevant chunks for a query"""
        import numpy as np
        from sklearn.metrics.pairwise import cosine_similarity
        try:
            # Ensure slide is processed
            status = SlideProcessingStatus.objects.filter(slide=slide).first()
            if not status or not status.is_embedded:
                logger.warning(f"Slide {slide.id} not processed, processing now...")
                self.process_slide(slide)
            
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
            chunks = SlideChunk.objects.filter(slide=slide).order_by('chunk_index')[:max_chunks]
            context_parts = [chunk.text for chunk in chunks]
        else:
            context_parts = [chunk.text for chunk, score in relevant_chunks]
        
        return "\n\n".join(context_parts)

# Global instance
rag_service = RAGService()
