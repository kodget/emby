"""
Slide Conversion Service

Handles conversion of documents (PDF, PPTX, DOCX) to standardized formats
and rendering to images for display.
"""

import os
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Tuple, List, Optional
import logging

logger = logging.getLogger(__name__)


# Import centralized file type detector
from ..utils.file_type_detector import FileTypeDetector


class LibreOfficeConverter:
    """Convert documents using LibreOffice"""
    
    SOFFICE_PATH = "soffice"  # Assumes soffice is in PATH
    
    @staticmethod
    def get_libreoffice_path() -> str:
        """Get LibreOffice executable path"""
        # Try common installation paths on Windows
        common_paths = [
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
            r"C:\Program Files\LibreOffice\soffice.exe",
        ]
        
        # First check if in PATH
        try:
            result = subprocess.run(
                ["where", "soffice"],
                capture_output=True,
                text=True,
                shell=True
            )
            if result.returncode == 0 and result.stdout.strip():
                path = result.stdout.strip().split('\n')[0]
                logger.info(f"Found soffice in PATH: {path}")
                return path
        except Exception as e:
            logger.debug(f"PATH check failed: {e}")
        
        # Check common paths
        for path in common_paths:
            if os.path.exists(path):
                logger.info(f"Found soffice at: {path}")
                return path
        
        logger.warning("LibreOffice not found in common paths, will attempt with 'soffice' command")
        # Default to soffice (assume it's in PATH)
        return LibreOfficeConverter.SOFFICE_PATH


class PopplerConverter:
    """Utilities for Poppler path detection"""
    
    @staticmethod
    def get_poppler_path() -> Optional[str]:
        """Get Poppler binary path"""
        # Try common installation paths
        common_paths = [
            r"C:\Release-26.02.0-0\poppler-26.02.0\Library\bin",
            r"C:\Release-26.02.0-0\poppler\Library\bin",
            r"C:\poppler\Library\bin",
            r"C:\Program Files\poppler\Library\bin",
            r"C:\Program Files (x86)\poppler\Library\bin",
        ]
        
        # First check if pdftoppm is in PATH
        try:
            result = subprocess.run(
                ["where", "pdftoppm"],
                capture_output=True,
                text=True,
                shell=True
            )
            if result.returncode == 0 and result.stdout.strip():
                logger.info("Found pdftoppm in PATH")
                return None  # Already in PATH
        except Exception as e:
            logger.debug(f"PATH check for pdftoppm failed: {e}")
        
        # Check common paths
        for path in common_paths:
            pdftoppm_exe = os.path.join(path, "pdftoppm.exe")
            if os.path.exists(pdftoppm_exe):
                logger.info(f"Found Poppler at: {path}")
                return path
        
        logger.warning("Poppler not found in common paths, will attempt with 'pdftoppm' command")
        return None
    
    @staticmethod
    def convert_to_pptx(input_path: str, output_dir: str) -> Tuple[bool, str]:
        """
        Convert document to PPTX format
        
        Args:
            input_path: Path to input file (PDF, DOCX, PPT)
            output_dir: Directory to save converted file
            
        Returns:
            Tuple (success: bool, output_path: str)
        """
        try:
            soffice_path = LibreOfficeConverter.get_libreoffice_path()
            
            # Ensure output directory exists
            os.makedirs(output_dir, exist_ok=True)
            
            logger.info(f"Converting to PPTX using: {soffice_path}")
            logger.info(f"Input: {input_path}")
            logger.info(f"Output dir: {output_dir}")
            
            # Run LibreOffice conversion
            result = subprocess.run([
                soffice_path,
                "--headless",
                "--convert-to",
                "pptx",
                input_path,
                "--outdir",
                output_dir
            ], capture_output=True, text=True, timeout=300)
            
            logger.info(f"LibreOffice stdout: {result.stdout}")
            
            if result.returncode != 0:
                logger.error(f"LibreOffice conversion failed with code {result.returncode}")
                logger.error(f"stderr: {result.stderr}")
                return False, ""
            
            # Determine output filename
            input_filename = Path(input_path).stem
            output_path = os.path.join(output_dir, f"{input_filename}.pptx")
            
            if os.path.exists(output_path):
                logger.info(f"✓ Successfully converted to PPTX: {output_path}")
                return True, output_path
            else:
                logger.error(f"Converted file not found: {output_path}")
                # List directory contents for debugging
                logger.error(f"Directory contents: {os.listdir(output_dir)}")
                return False, ""
                
        except subprocess.TimeoutExpired:
            logger.error("LibreOffice conversion timeout (300s)")
            return False, ""
        except Exception as e:
            logger.error(f"Conversion error: {e}")
            import traceback
            traceback.print_exc()
            return False, ""
    
    @staticmethod
    def convert_to_pdf(input_path: str, output_dir: str) -> Tuple[bool, str]:
        """
        Convert PPTX/DOCX to PDF
        
        Args:
            input_path: Path to input file (PPTX or DOCX)
            output_dir: Directory to save converted file
            
        Returns:
            Tuple (success: bool, output_path: str)
        """
        try:
            soffice_path = LibreOfficeConverter.get_libreoffice_path()
            
            os.makedirs(output_dir, exist_ok=True)
            
            logger.info(f"Converting to PDF using: {soffice_path}")
            logger.info(f"Input: {input_path}")
            logger.info(f"Output dir: {output_dir}")
            
            result = subprocess.run([
                soffice_path,
                "--headless",
                "--convert-to",
                "pdf",
                input_path,
                "--outdir",
                output_dir
            ], capture_output=True, text=True, timeout=300)
            
            logger.info(f"LibreOffice stdout: {result.stdout}")
            
            if result.returncode != 0:
                logger.error(f"PDF conversion failed with code {result.returncode}")
                logger.error(f"stderr: {result.stderr}")
                return False, ""
            
            input_filename = Path(input_path).stem
            output_path = os.path.join(output_dir, f"{input_filename}.pdf")
            
            if os.path.exists(output_path):
                logger.info(f"✓ Successfully converted to PDF: {output_path}")
                return True, output_path
            else:
                logger.error(f"Converted PDF not found: {output_path}")
                # List directory contents for debugging
                logger.error(f"Directory contents: {os.listdir(output_dir)}")
                return False, ""
                
        except subprocess.TimeoutExpired:
            logger.error("PDF conversion timeout (300s)")
            return False, ""
        except Exception as e:
            logger.error(f"PDF conversion error: {e}")
            import traceback
            traceback.print_exc()
            return False, ""


class PDFToImageConverter:
    """Convert PDF to images using pdf2image"""
    
    @staticmethod
    def convert_pdf_to_images(pdf_path: str, output_dir: str, dpi: int = 150) -> Tuple[bool, List[str]]:
        """
        Convert PDF pages to PNG images
        
        Args:
            pdf_path: Path to PDF file
            output_dir: Directory to save images
            dpi: Resolution for rendered images (default 150)
            
        Returns:
            Tuple (success: bool, list of image paths)
        """
        try:
            from pdf2image import convert_from_path
            
            os.makedirs(output_dir, exist_ok=True)
            
            logger.info(f"Converting PDF to images: {pdf_path}")
            logger.info(f"DPI: {dpi}, Output dir: {output_dir}")
            
            # Convert PDF pages to images
            pages = convert_from_path(pdf_path, dpi=dpi)
            
            image_paths = []
            pdf_filename = Path(pdf_path).stem
            
            logger.info(f"PDF has {len(pages)} pages")
            
            for page_number, page_image in enumerate(pages, 1):
                # Save as PNG
                image_filename = f"page_{page_number:04d}.png"
                image_path = os.path.join(output_dir, image_filename)
                
                page_image.save(image_path, 'PNG')
                image_paths.append(image_path)
                logger.info(f"✓ Saved page {page_number}: {image_path} ({page_image.width}x{page_image.height})")
            
            logger.info(f"✓ Successfully converted {len(pages)} pages to images")
            return True, image_paths
            
        except ImportError:
            logger.error("pdf2image not installed - install with: pip install pdf2image")
            return False, []
        except Exception as e:
            logger.error(f"PDF to image conversion error: {e}")
            import traceback
            traceback.print_exc()
            return False, []


class SlideConverter:
    """Main converter orchestrating the conversion pipeline"""
    
    MEDIA_DIRS = {
        'uploads': 'media/uploads',
        'converted': 'media/converted',
        'rendered': 'media/rendered',
    }
    
    @staticmethod
    def ensure_media_directories() -> None:
        """Create media directory structure"""
        for dir_path in SlideConverter.MEDIA_DIRS.values():
            os.makedirs(dir_path, exist_ok=True)
            logger.info(f"Media directory ready: {dir_path}")
    
    @staticmethod
    def convert_document(input_file_path: str, file_type: str, deck_id: str) -> Tuple[bool, dict]:
        """
        Convert document through full pipeline:
        1. Detect format
        2. Convert to PPTX (if needed)
        3. Convert to PDF
        4. Convert PDF to images
        5. Return paths to rendered slides
        
        Args:
            input_file_path: Path to uploaded file
            file_type: Detected file type (pdf, pptx, ppt, docx)
            deck_id: Unique identifier for this deck
            
        Returns:
            Tuple (success: bool, result_dict with paths and metadata)
        """
        result = {
            'success': False,
            'file_type': file_type,
            'converted_pptx': None,
            'converted_pdf': None,
            'slide_images': [],
            'page_count': 0,
            'error': None
        }
        
        try:
            # Create temporary working directory
            temp_dir = tempfile.mkdtemp(prefix=f"slides_{deck_id}_")
            logger.info(f"Working directory: {temp_dir}")
            logger.info(f"Input file: {input_file_path}")
            logger.info(f"File type: {file_type}")
            
            try:
                # Step 1: If PDF, skip to image conversion
                if file_type == 'pdf':
                    logger.info("File is PDF, skipping PPTX conversion")
                    pdf_path = input_file_path
                else:
                    # Step 2: Convert to PPTX
                    logger.info(f"Converting {file_type} to PPTX...")
                    convert_dir = os.path.join(temp_dir, 'pptx')
                    success, pptx_path = LibreOfficeConverter.convert_to_pptx(
                        input_file_path, 
                        convert_dir
                    )
                    
                    if not success:
                        result['error'] = 'Failed to convert to PPTX'
                        logger.error(result['error'])
                        return False, result
                    
                    result['converted_pptx'] = pptx_path
                    logger.info(f"✓ PPTX conversion successful: {pptx_path}")
                    
                    # Step 3: Convert PPTX to PDF
                    logger.info("Converting PPTX to PDF...")
                    pdf_dir = os.path.join(temp_dir, 'pdf')
                    success, pdf_path = LibreOfficeConverter.convert_to_pdf(pptx_path, pdf_dir)
                    
                    if not success:
                        result['error'] = 'Failed to convert to PDF'
                        logger.error(result['error'])
                        return False, result
                    
                    result['converted_pdf'] = pdf_path
                    logger.info(f"✓ PDF conversion successful: {pdf_path}")
                
                # Step 4: Convert PDF to images
                logger.info("Converting PDF to images...")
                images_dir = os.path.join(temp_dir, 'images')
                success, image_paths = PDFToImageConverter.convert_pdf_to_images(
                    pdf_path,
                    images_dir
                )
                
                if not success:
                    result['error'] = 'Failed to convert PDF to images'
                    logger.error(result['error'])
                    return False, result
                
                result['slide_images'] = image_paths
                result['page_count'] = len(image_paths)
                result['success'] = True
                
                logger.info(f"✓ Successfully converted document: {deck_id} with {len(image_paths)} pages")
                
                return True, result
                
            finally:
                # Clean up temporary directory
                shutil.rmtree(temp_dir, ignore_errors=True)
                logger.info(f"Cleaned up temporary directory: {temp_dir}")
        
        except Exception as e:
            logger.error(f"Document conversion pipeline error: {e}")
            import traceback
            traceback.print_exc()
            result['error'] = str(e)
            return False, result
    
    @staticmethod
    def get_slide_storage_path(deck_id: str, slide_number: int) -> str:
        """Get the storage path for a rendered slide"""
        slides_dir = os.path.join(
            SlideConverter.MEDIA_DIRS['rendered'],
            f"deck_{deck_id}"
        )
        os.makedirs(slides_dir, exist_ok=True)
        return os.path.join(slides_dir, f"slide_{slide_number:04d}.png")
