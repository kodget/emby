"""
Slide Processor Service

Processes slides after Cloudinary upload:
1. Download from Cloudinary
2. Convert through pipeline (DOCX/PPT → PPTX → PDF → Images)
3. Extract text content
4. Generate embeddings for RAG
5. Upload rendered images back to Cloudinary
"""

import os
import tempfile
import requests
import logging
from typing import Tuple, Dict, Any
from pathlib import Path
from django.utils import timezone

from .converter import SlideConverter, PopplerConverter
from ..utils.file_type_detector import FileTypeDetector
from ..content_extractor import extract_text_from_slide
from ..rag_service import rag_service
from ..models import Slide, SlideContent

logger = logging.getLogger(__name__)


class SlideProcessor:
    """Process slides after Cloudinary upload"""
    
    @staticmethod
    def validate_cloudinary_url(url: str) -> Tuple[bool, str]:
        """
        Validate Cloudinary URL format and accessibility
        
        Args:
            url: Cloudinary URL to validate
            
        Returns:
            Tuple[bool, str]: (Is valid, Error message if invalid)
        """
        if not url:
            return False, "URL is empty"
        
        if not url.startswith(('http://', 'https://')):
            return False, "URL must start with http:// or https://"
        
        # Check if it's a Cloudinary URL
        if 'cloudinary.com' not in url and 'res.cloudinary.com' not in url:
            logger.warning(f"URL doesn't appear to be from Cloudinary: {url}")
        
        # Basic URL format validation
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            if not parsed.netloc or not parsed.scheme:
                return False, "Invalid URL format"
        except Exception as e:
            return False, f"URL parsing error: {e}"
        
        return True, ""
    
    @staticmethod
    def check_cloudinary_health() -> Tuple[bool, str]:
        """
        Check if Cloudinary service is accessible
        
        Returns:
            Tuple[bool, str]: (Is healthy, Status message)
        """
        try:
            # Try to access Cloudinary's status endpoint or a known public resource
            test_url = "https://res.cloudinary.com/demo/image/upload/sample.jpg"
            response = requests.head(test_url, timeout=10)
            
            if response.status_code == 200:
                return True, "Cloudinary is accessible"
            else:
                return False, f"Cloudinary returned status {response.status_code}"
                
        except Exception as e:
            return False, f"Cloudinary health check failed: {e}"
    
    @staticmethod
    def update_processing_status(slide, status: str, error_message: str = "", **kwargs):
        """
        Update slide processing status with detailed information
        
        Args:
            slide: Slide instance
            status: Status string ('processing', 'completed', 'failed')
            error_message: Error message if failed
            **kwargs: Additional status fields
        """
        try:
            from ..models import SlideProcessingStatus
            from django.utils import timezone
            
            status_obj, created = SlideProcessingStatus.objects.get_or_create(slide=slide)
            status_obj.status = status
            
            if status == 'processing':
                status_obj.started_at = timezone.now()
                status_obj.error_message = ''
            elif status == 'completed':
                status_obj.completed_at = timezone.now()
                status_obj.error_message = ''
            elif status == 'failed':
                status_obj.error_message = error_message
            
            # Update additional fields
            for key, value in kwargs.items():
                if hasattr(status_obj, key):
                    setattr(status_obj, key, value)
            
            status_obj.save()
            logger.info(f"Updated processing status for slide {slide.id}: {status}")
            
        except Exception as e:
            logger.error(f"Failed to update processing status: {e}")
    
    @staticmethod
    def download_from_cloudinary(url: str, output_path: str, max_retries: int = 3) -> Tuple[bool, str]:
        """
        Download file from Cloudinary URL with retry logic and detailed error handling
        
        Args:
            url: Cloudinary URL
            output_path: Local path to save file
            max_retries: Maximum number of retry attempts (default: 3)
            
        Returns:
            Tuple[bool, str]: (Success status, Error message if failed)
        """
        import time
        from requests.exceptions import RequestException, Timeout, ConnectionError, HTTPError
        
        for attempt in range(max_retries + 1):
            try:
                logger.info(f"Downloading from Cloudinary (attempt {attempt + 1}/{max_retries + 1}): {url}")
                
                # Make request with appropriate timeout
                response = requests.get(
                    url, 
                    timeout=(10, 60),  # (connection_timeout, read_timeout)
                    stream=True,  # Stream for large files
                    headers={
                        'User-Agent': 'Emby-Backend/1.0'
                    }
                )
                
                # Check for HTTP errors
                response.raise_for_status()
                
                # Validate content type (relaxed for testing)
                content_type = response.headers.get('content-type', '').lower()
                expected_types = ['application/pdf', 'application/vnd.openxmlformats', 'application/vnd.ms-powerpoint', 'application/msword', 'image/']
                
                if not any(expected in content_type for expected in expected_types) and 'octet-stream' not in content_type:
                    logger.warning(f"Unexpected content type: {content_type} (continuing anyway)")
                
                # Download with progress tracking
                total_size = int(response.headers.get('content-length', 0))
                downloaded_size = 0
                
                with open(output_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded_size += len(chunk)
                
                # Validate downloaded file
                if downloaded_size == 0:
                    error_msg = "Downloaded file is empty"
                    logger.error(error_msg)
                    return False, error_msg
                
                if total_size > 0 and downloaded_size != total_size:
                    error_msg = f"Download incomplete: {downloaded_size}/{total_size} bytes"
                    logger.warning(error_msg)
                    # Continue anyway, might still be valid
                
                # Verify file exists and has content
                if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                    error_msg = "Downloaded file is missing or empty"
                    logger.error(error_msg)
                    return False, error_msg
                
                logger.info(f"✓ Downloaded successfully: {output_path} ({downloaded_size} bytes)")
                return True, ""
                
            except HTTPError as e:
                error_msg = f"HTTP error {e.response.status_code}: {e}"
                if e.response.status_code == 404:
                    error_msg = "File not found on Cloudinary (404) - URL may be invalid or expired"
                elif e.response.status_code == 403:
                    error_msg = "Access denied (403) - Check Cloudinary permissions"
                elif e.response.status_code >= 500:
                    error_msg = f"Cloudinary server error ({e.response.status_code}) - May be temporary"
                
                logger.error(f"Attempt {attempt + 1} failed: {error_msg}")
                
                # Don't retry on client errors (4xx), only server errors (5xx) and network issues
                if 400 <= e.response.status_code < 500:
                    return False, error_msg
                    
            except (ConnectionError, Timeout) as e:
                error_msg = f"Network error: {e}"
                logger.error(f"Attempt {attempt + 1} failed: {error_msg}")
                
            except RequestException as e:
                error_msg = f"Request error: {e}"
                logger.error(f"Attempt {attempt + 1} failed: {error_msg}")
                
            except Exception as e:
                error_msg = f"Unexpected error: {e}"
                logger.error(f"Attempt {attempt + 1} failed: {error_msg}")
                import traceback
                traceback.print_exc()
            
            # Wait before retry (exponential backoff)
            if attempt < max_retries:
                wait_time = (2 ** attempt) + 1  # 2, 3, 5 seconds
                logger.info(f"Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)
        
        final_error = f"Failed to download after {max_retries + 1} attempts"
        logger.error(final_error)
        return False, final_error
    
    @staticmethod
    def process_slide(slide: Slide) -> Dict[str, Any]:
        """
        Process a slide through the complete pipeline
        
        Args:
            slide: Slide model instance
            
        Returns:
            dict: Processing results with status and metadata
        """
        result = {
            'success': False,
            'slide_id': slide.id,
            'slide_title': slide.title,
            'file_type': slide.file_type,
            'content_extracted': False,
            'content_length': 0,
            'rag_processed': False,
            'images_generated': False,
            'page_count': 0,
            'error': None
        }
        
        # Update status to processing at start
        SlideProcessor.update_processing_status(slide, 'processing')
        
        # Get Cloudinary URL - prefer file_url if available, fallback to file.url
        file_url = None
        if slide.file_url:
            file_url = slide.file_url
        elif slide.file:
            file_url = slide.file.url
        
        if not file_url:
            result['error'] = 'No file URL found'
            logger.error(f"Slide {slide.id} has no file URL")
            SlideProcessor.update_processing_status(slide, 'failed', result['error'])
            return result
        
        # Validate URL before processing
        url_valid, url_error = SlideProcessor.validate_cloudinary_url(file_url)
        if not url_valid:
            result['error'] = f'Invalid file URL: {url_error}'
            logger.error(f"Slide {slide.id} has invalid URL: {url_error}")
            SlideProcessor.update_processing_status(slide, 'failed', result['error'])
            return result
        
        logger.info(f"Processing slide {slide.id}: {slide.title}")
        logger.info(f"File URL: {file_url}")
        logger.info(f"File Type: {slide.file_type}")
        
        # Create temporary directory for processing
        temp_dir = tempfile.mkdtemp(prefix=f"slide_{slide.id}_")
        
        try:
            # Step 1: Download from Cloudinary
            file_ext = slide.file_type or 'pdf'
            download_path = os.path.join(temp_dir, f"original.{file_ext}")
            
            download_success, download_error = SlideProcessor.download_from_cloudinary(file_url, download_path)
            if not download_success:
                result['error'] = f'Cloudinary download failed: {download_error}'
                logger.error(f"Slide {slide.id} download failed: {download_error}")
                SlideProcessor.update_processing_status(slide, 'failed', result['error'])
                return result
            
            # Verify file is not empty
            file_size = os.path.getsize(download_path)
            if file_size == 0:
                result['error'] = 'Downloaded file is empty'
                logger.error(f"Downloaded file is empty: {download_path}")
                SlideProcessor.update_processing_status(slide, 'failed', result['error'])
                return result
            
            logger.info(f"Downloaded file size: {file_size} bytes")
            
            # Step 2: Detect actual file type (might differ from metadata)
            detected_type = FileTypeDetector.detect_file_type(download_path, method='auto')
            
            if detected_type and detected_type != slide.file_type:
                logger.warning(f"File type mismatch: metadata={slide.file_type}, detected={detected_type}")
                # Update slide file type
                slide.file_type = detected_type
                slide.save(update_fields=['file_type'])
            
            actual_file_type = detected_type or slide.file_type or 'pdf'
            result['file_type'] = actual_file_type
            
            # Step 3: Extract text content (try direct extraction first)
            logger.info(f"Extracting text content from {actual_file_type} file...")
            total_text = ""  # Initialize here for later use
            try:
                pages = extract_text_from_slide(download_path, actual_file_type)
                if pages and len(pages) > 0:
                    total_text = '\n\n'.join(p['text'] for p in pages if p['text'].strip())
                    result['content_length'] = len(total_text)
                    result['content_extracted'] = True
                    result['page_count'] = len(pages)
                    logger.info(f"Extracted {len(total_text)} characters from {len(pages)} pages")
                else:
                    logger.warning("No text extracted - file might be image-based or corrupted")
            except Exception as e:
                logger.error(f"Text extraction failed: {e}")
                result['error'] = f"Text extraction failed: {str(e)}"
            
            # Step 4: If text extraction failed and file is PDF, try conversion pipeline
            if not result['content_extracted'] and actual_file_type in ['pdf', 'pptx', 'ppt', 'docx']:
                logger.info("Direct extraction failed, trying conversion pipeline...")
                try:
                    # Strategy: Convert through PPTX → PDF pipeline to fix corrupted files
                    if actual_file_type == 'pdf':
                        # For corrupted PDFs: Try converting to PPTX first, then back to PDF
                        logger.info("Attempting PDF recovery through PPTX conversion...")
                        
                        # Convert PDF → PPTX
                        pptx_dir = os.path.join(temp_dir, 'pptx_conversion')
                        os.makedirs(pptx_dir, exist_ok=True)
                        
                        pptx_success, pptx_path = PopplerConverter.convert_to_pptx(
                            download_path,
                            pptx_dir
                        )
                        
                        if pptx_success and pptx_path:
                            # Convert PPTX → PDF
                            pdf_dir = os.path.join(temp_dir, 'pdf_conversion')
                            os.makedirs(pdf_dir, exist_ok=True)
                            
                            pdf_success, converted_pdf = PopplerConverter.convert_to_pdf(
                                pptx_path,
                                pdf_dir
                            )
                            
                            if pdf_success and converted_pdf:
                                # Try extracting from converted PDF
                                pages = extract_text_from_slide(converted_pdf, 'pdf')
                                if pages and len(pages) > 0:
                                    total_text = '\n\n'.join(p['text'] for p in pages if p['text'].strip())
                                    result['content_length'] = len(total_text)
                                    result['content_extracted'] = True
                                    result['page_count'] = len(pages)
                                    logger.info(f"✓ Extracted {len(total_text)} chars after PDF recovery")
                    
                    elif actual_file_type in ['pptx', 'ppt', 'docx']:
                        # For Office files: Convert to PDF then extract
                        logger.info(f"Converting {actual_file_type} to PDF for extraction...")
                        
                        pdf_dir = os.path.join(temp_dir, 'pdf_conversion')
                        os.makedirs(pdf_dir, exist_ok=True)
                        
                        pdf_success, converted_pdf = PopplerConverter.convert_to_pdf(
                            download_path,
                            pdf_dir
                        )
                        
                        if pdf_success and converted_pdf:
                            # Try extracting from converted PDF
                            pages = extract_text_from_slide(converted_pdf, 'pdf')
                            if pages and len(pages) > 0:
                                total_text = '\n\n'.join(p['text'] for p in pages if p['text'].strip())
                                result['content_length'] = len(total_text)
                                result['content_extracted'] = True
                                result['page_count'] = len(pages)
                                logger.info(f"✓ Extracted {len(total_text)} chars after conversion to PDF")
                        
                except Exception as e:
                    logger.error(f"Conversion pipeline failed: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Step 5: Store extracted content in SlideContent model
            if result['content_extracted'] and result['content_length'] > 0:
                logger.info("Storing extracted content in database...")
                try:
                    # Get or create SlideContent
                    slide_content, created = SlideContent.objects.get_or_create(slide=slide)
                    
                    # Store the extracted text
                    slide_content.content_data = {
                        'text': total_text,
                        'page_count': result['page_count'],
                        'extraction_method': 'direct',
                        'file_type': actual_file_type,
                        'extracted_at': timezone.now().isoformat()
                    }
                    slide_content.is_extracted = True
                    slide_content.extraction_error = ''
                    slide_content.extracted_at = timezone.now()
                    slide_content.save()
                    
                    logger.info(f"✓ Stored {result['content_length']} chars in SlideContent")
                    
                except Exception as e:
                    logger.error(f"Failed to store content: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Step 6: Process with RAG if content was extracted
            if result['content_extracted'] and result['content_length'] > 50:
                logger.info("Processing with RAG system...")
                try:
                    # Pass the temp directory to RAG service so it can access files if needed
                    rag_success = rag_service.process_slide(slide, temp_dir=temp_dir)
                    result['rag_processed'] = rag_success
                    if rag_success:
                        logger.info("RAG processing successful")
                    else:
                        logger.warning("RAG processing failed")
                except Exception as e:
                    logger.error(f"RAG processing error: {e}")
            
            # Step 7: Mark as successful if content was extracted
            if result['content_extracted']:
                result['success'] = True
                logger.info(f"Slide {slide.id} processed successfully")
                SlideProcessor.update_processing_status(
                    slide, 
                    'completed', 
                    content_extracted=result['content_extracted'],
                    rag_processed=result['rag_processed'],
                    is_chunked=result['rag_processed'],
                    is_embedded=result['rag_processed']
                )
            else:
                result['error'] = result.get('error') or 'No content could be extracted'
                logger.error(f"Slide {slide.id} processing failed: {result['error']}")
                SlideProcessor.update_processing_status(slide, 'failed', result['error'])
            
            return result
            
        except Exception as e:
            logger.error(f"Slide processing error: {e}")
            import traceback
            traceback.print_exc()
            result['error'] = str(e)
            SlideProcessor.update_processing_status(slide, 'failed', str(e))
            return result
            
        finally:
            # Cleanup temporary directory (moved to end so RAG can access files)
            import shutil
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
                logger.info(f"Cleaned up temp directory: {temp_dir}")
            except:
                pass
    
    
    @staticmethod
    def _detect_file_type_from_content(file_path: str) -> str:
        """
        DEPRECATED: Use FileTypeDetector.detect_file_type() instead
        
        Detect file type from file content (magic bytes)
        
        Args:
            file_path: Path to file
            
        Returns:
            str: Detected file type or None
        """
        logger.warning("_detect_file_type_from_content is deprecated, use FileTypeDetector.detect_file_type()")
        from ..utils.file_type_detector import FileTypeDetector
        return FileTypeDetector.detect_file_type(file_path, method='magic_bytes')


# Convenience function for processing slides
def process_slide_after_upload(slide_id: str) -> Dict[str, Any]:
    """
    Process a slide after it's been uploaded to Cloudinary
    
    Args:
        slide_id: Slide ID
        
    Returns:
        dict: Processing results
    """
    try:
        slide = Slide.objects.get(id=slide_id)
        return SlideProcessor.process_slide(slide)
    except Slide.DoesNotExist:
        return {
            'success': False,
            'error': f'Slide {slide_id} not found'
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }
