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
        Convert PDF pages to PNG images using PyMuPDF (fitz)
        
        Args:
            pdf_path: Path to PDF file
            output_dir: Directory to save images
            dpi: Resolution for rendered images (default 150)
            
        Returns:
            Tuple (success: bool, list of image paths)
        """
        try:
            import fitz  # PyMuPDF
            
            os.makedirs(output_dir, exist_ok=True)
            
            logger.info(f"Converting PDF to images: {pdf_path}")
            logger.info(f"DPI: {dpi}, Output dir: {output_dir}")
            
            doc = fitz.open(pdf_path)
            image_paths = []
            
            logger.info(f"PDF has {len(doc)} pages")
            
            # zoom factor for DPI. fitz default is 72 dpi.
            zoom = dpi / 72.0
            mat = fitz.Matrix(zoom, zoom)
            
            for page_number in range(len(doc)):
                page = doc.load_page(page_number)
                pix = page.get_pixmap(matrix=mat)
                
                # Save as PNG
                image_filename = f"page_{page_number + 1:04d}.png"
                image_path = os.path.join(output_dir, image_filename)
                
                pix.save(image_path)
                image_paths.append(image_path)
                logger.info(f"✓ Saved page {page_number + 1}: {image_path} ({pix.width}x{pix.height})")
            
            doc.close()
            logger.info(f"✓ Successfully converted {len(image_paths)} pages to images")
            return True, image_paths
            
        except ImportError:
            logger.error("PyMuPDF (fitz) not installed - install with: pip install PyMuPDF")
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
        """Keep rendered files alive until the caller has stored all pages."""
        from .document_rendering import render_document, cleanup_render
        result = {'success': False, 'file_type': file_type, 'slide_images': [],
                  'page_count': 0, 'error': None, 'converted_pptx': None, 'converted_pdf': None,
                  'temp_dir': tempfile.mkdtemp(prefix='emby-render-')}
        try:
            rendered = render_document(input_file_path, file_type, result['temp_dir'], ocr=True)
            result.update(success=True, slide_images=rendered['image_paths'],
                          pages=rendered['pages'], text_extraction=rendered['text_extraction'],
                          page_count=rendered['page_count'], converted_pdf=rendered['pdf_path'])
            return True, result
        except Exception as exc:
            logger.warning('Document rendering failed (%s)', type(exc).__name__)
            cleanup_render(result)
            result.update(temp_dir=None, error='Document conversion failed. Check the file and conversion service.')
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
