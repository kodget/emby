"""
Slide Conversion Pipeline

EXACT FLOW:
ANY FILE TYPE → PPTX → PDF (for text extraction) → IMAGES (for rendering in frontend)

This service handles the complete conversion pipeline.
"""

import os
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Tuple, Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class SlideConversionPipeline:
    """Complete slide conversion pipeline"""
    
    @staticmethod
    def get_libreoffice_path() -> str:
        """Get LibreOffice executable path"""
        common_paths = [
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
            "/usr/bin/soffice",
            "/Applications/LibreOffice.app/Contents/MacOS/soffice"
        ]
        
        # Check if soffice is in PATH
        try:
            result = subprocess.run(
                ["where", "soffice"] if os.name == 'nt' else ["which", "soffice"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip().split('\n')[0]
        except:
            pass
        
        # Check common paths
        for path in common_paths:
            if os.path.exists(path):
                return path
        
        logger.warning("LibreOffice not found, will try 'soffice' command")
        return "soffice"
    
    @staticmethod
    def step1_to_pptx(input_file_path: str, output_dir: str) -> Tuple[bool, str]:
        """
        STEP 1: Convert ANY file type to PPTX
        
        Supported inputs: PDF, PPT, PPTX, DOCX, DOC
        Output: PPTX file
        """
        try:
            os.makedirs(output_dir, exist_ok=True)
            input_file_name = Path(input_file_path).stem
            output_path = os.path.join(output_dir, f"{input_file_name}.pptx")
            
            # If already PPTX, just copy
            if input_file_path.lower().endswith('.pptx'):
                shutil.copy(input_file_path, output_path)
                logger.info(f"✓ File is already PPTX: {output_path}")
                return True, output_path
            
            # Convert to PPTX using LibreOffice
            soffice_path = SlideConversionPipeline.get_libreoffice_path()
            logger.info(f"Converting to PPTX using: {soffice_path}")
            
            result = subprocess.run([
                soffice_path,
                "--headless",
                "--convert-to", "pptx",
                input_file_path,
                "--outdir", output_dir
            ], capture_output=True, text=True, timeout=300)
            
            if result.returncode != 0:
                logger.error(f"PPTX conversion failed: {result.stderr}")
                return False, ""
            
            if os.path.exists(output_path):
                logger.info(f"✓ Successfully converted to PPTX: {output_path}")
                return True, output_path
            else:
                logger.error(f"Output PPTX not found: {output_path}")
                logger.error(f"Directory contents: {os.listdir(output_dir)}")
                return False, ""
        
        except Exception as e:
            logger.error(f"Step 1 (to PPTX) failed: {e}")
            return False, ""
    
    @staticmethod
    def step2_to_pdf(pptx_file_path: str, output_dir: str) -> Tuple[bool, str]:
        """
        STEP 2: Convert PPTX to PDF for text extraction
        
        Input: PPTX file
        Output: PDF file
        """
        try:
            os.makedirs(output_dir, exist_ok=True)
            input_file_name = Path(pptx_file_path).stem
            output_path = os.path.join(output_dir, f"{input_file_name}.pdf")
            
            soffice_path = SlideConversionPipeline.get_libreoffice_path()
            logger.info(f"Converting PPTX to PDF: {pptx_file_path}")
            
            result = subprocess.run([
                soffice_path,
                "--headless",
                "--convert-to", "pdf",
                pptx_file_path,
                "--outdir", output_dir
            ], capture_output=True, text=True, timeout=300)
            
            if result.returncode != 0:
                logger.error(f"PDF conversion failed: {result.stderr}")
                return False, ""
            
            if os.path.exists(output_path):
                logger.info(f"✓ Successfully converted to PDF: {output_path}")
                return True, output_path
            else:
                logger.error(f"Output PDF not found: {output_path}")
                return False, ""
        
        except Exception as e:
            logger.error(f"Step 2 (to PDF) failed: {e}")
            return False, ""
    
    @staticmethod
    def step3_pdf_to_images(pdf_file_path: str, output_dir: str, dpi: int = 150) -> Tuple[bool, List[str]]:
        """
        STEP 3: Convert PDF to PNG images for frontend rendering
        
        Input: PDF file
        Output: PNG images (one per page)
        """
        try:
            from pdf2image import convert_from_path
            
            os.makedirs(output_dir, exist_ok=True)
            
            logger.info(f"Converting PDF to images (DPI={dpi}): {pdf_file_path}")
            
            # Convert PDF pages to images
            pages = convert_from_path(pdf_file_path, dpi=dpi)
            logger.info(f"PDF has {len(pages)} pages")
            
            image_paths = []
            for page_number, page_image in enumerate(pages, 1):
                image_filename = f"page_{page_number:04d}.png"
                image_path = os.path.join(output_dir, image_filename)
                
                page_image.save(image_path, 'PNG')
                image_paths.append(image_path)
                logger.info(f"✓ Saved page {page_number}: {image_path}")
            
            logger.info(f"✓ Successfully converted {len(pages)} pages to images")
            return True, image_paths
        
        except ImportError:
            logger.error("pdf2image not installed: pip install pdf2image")
            return False, []
        except Exception as e:
            logger.error(f"Step 3 (PDF to images) failed: {e}")
            return False, []
    
    @staticmethod
    def extract_text_from_pdf(pdf_file_path: str) -> str:
        """Extract text from PDF for RAG processing"""
        try:
            import fitz  # PyMuPDF
            
            doc = fitz.open(pdf_file_path)
            text = ""
            for page_num in range(len(doc)):
                page = doc[page_num]
                text += page.get_text()
                text += "\n---PAGE BREAK---\n"
            
            doc.close()
            logger.info(f"Extracted {len(text)} characters from PDF")
            return text
        except Exception as e:
            logger.error(f"Text extraction failed: {e}")
            return ""
    
    @staticmethod
    def process_slide(cloudinary_url: str, slide_id: str, original_file_type: str) -> Dict[str, Any]:
        """
        COMPLETE PIPELINE: Download → PPTX → PDF → IMAGES
        
        Args:
            cloudinary_url: URL of file in Cloudinary
            slide_id: ID of the slide
            original_file_type: Original file type (pdf, pptx, docx, etc.)
            
        Returns:
            Dictionary with results including image paths, text content, etc.
        """
        result = {
            'success': False,
            'slide_id': slide_id,
            'file_type': original_file_type,
            'image_paths': [],
            'text_content': '',
            'page_count': 0,
            'error': None
        }
        
        temp_dir = tempfile.mkdtemp(prefix=f"slide_{slide_id}_")
        logger.info(f"Working directory: {temp_dir}")
        
        try:
            # Step 0: Download file from Cloudinary
            logger.info(f"Downloading from Cloudinary: {cloudinary_url}")
            import requests
            
            response = requests.get(cloudinary_url, timeout=60)
            if response.status_code != 200:
                result['error'] = f"Failed to download: HTTP {response.status_code}"
                logger.error(result['error'])
                return result
            
            # Determine file extension
            file_ext = original_file_type.lower()
            if not file_ext.startswith('.'):
                file_ext = f".{file_ext}"
            
            original_file_path = os.path.join(temp_dir, f"original{file_ext}")
            with open(original_file_path, 'wb') as f:
                f.write(response.content)
            
            logger.info(f"Downloaded {len(response.content)} bytes")
            
            # STEP 1: Convert to PPTX
            logger.info("=== STEP 1: Converting to PPTX ===")
            pptx_dir = os.path.join(temp_dir, 'step1_pptx')
            success, pptx_path = SlideConversionPipeline.step1_to_pptx(original_file_path, pptx_dir)
            
            if not success:
                result['error'] = 'Failed to convert to PPTX'
                logger.error(result['error'])
                return result
            
            # STEP 2: Convert PPTX to PDF
            logger.info("=== STEP 2: Converting PPTX to PDF ===")
            pdf_dir = os.path.join(temp_dir, 'step2_pdf')
            success, pdf_path = SlideConversionPipeline.step2_to_pdf(pptx_path, pdf_dir)
            
            if not success:
                result['error'] = 'Failed to convert to PDF'
                logger.error(result['error'])
                return result
            
            # Extract text from PDF (for RAG)
            logger.info("Extracting text from PDF...")
            text_content = SlideConversionPipeline.extract_text_from_pdf(pdf_path)
            result['text_content'] = text_content
            
            # STEP 3: Convert PDF to images
            logger.info("=== STEP 3: Converting PDF to Images ===")
            images_dir = os.path.join(temp_dir, 'step3_images')
            success, image_paths = SlideConversionPipeline.step3_pdf_to_images(pdf_path, images_dir)
            
            if not success:
                result['error'] = 'Failed to convert PDF to images'
                logger.error(result['error'])
                return result
            
            result['image_paths'] = image_paths
            result['page_count'] = len(image_paths)
            result['success'] = True
            
            logger.info(f"✓ PIPELINE COMPLETE: {len(image_paths)} pages converted")
            return result
        
        except Exception as e:
            logger.error(f"Pipeline error: {e}")
            import traceback
            traceback.print_exc()
            result['error'] = str(e)
            return result
        
        finally:
            # Cleanup temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.info(f"Cleaned up temp directory: {temp_dir}")
