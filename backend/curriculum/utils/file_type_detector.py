"""
Centralized File Type Detection Utility

Provides consistent file type detection across the application.
"""

import os
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class FileTypeDetector:
    """Centralized file type detection with multiple methods"""
    
    SUPPORTED_FORMATS = ['pdf', 'pptx', 'ppt', 'docx']
    
    # Magic byte signatures for file types
    MAGIC_BYTES = {
        'pdf': [b'%PDF'],
        'pptx': [b'PK\x03\x04'],  # ZIP-based format
        'docx': [b'PK\x03\x04'],  # ZIP-based format  
        'ppt': [b'\xD0\xCF\x11\xE0'],  # Old Office format
    }
    
    @classmethod
    def detect_file_type(cls, file_path: str, method: str = 'auto') -> Optional[str]:
        """
        Detect file type using specified method
        
        Args:
            file_path: Path to the file
            method: Detection method ('extension', 'magic_bytes', 'auto')
            
        Returns:
            File type (pdf, pptx, ppt, docx) or None if unsupported
        """
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return None
        
        if method == 'extension':
            return cls._detect_from_extension(file_path)
        elif method == 'magic_bytes':
            return cls._detect_from_magic_bytes(file_path)
        elif method == 'auto':
            # Try magic bytes first (more reliable), fall back to extension
            detected = cls._detect_from_magic_bytes(file_path)
            if detected:
                return detected
            return cls._detect_from_extension(file_path)
        else:
            raise ValueError(f"Unknown detection method: {method}")
    
    @classmethod
    def _detect_from_extension(cls, file_path: str) -> Optional[str]:
        """Detect file type from file extension"""
        try:
            extension = Path(file_path).suffix.lower().lstrip('.')
            if extension in cls.SUPPORTED_FORMATS:
                return extension
            return None
        except Exception as e:
            logger.error(f"Error detecting file type from extension: {e}")
            return None
    
    @classmethod
    def _detect_from_magic_bytes(cls, file_path: str) -> Optional[str]:
        """Detect file type from magic bytes (file header)"""
        try:
            with open(file_path, 'rb') as f:
                header = f.read(8)
            
            # Check each file type
            for file_type, signatures in cls.MAGIC_BYTES.items():
                for signature in signatures:
                    if header.startswith(signature):
                        # Special handling for ZIP-based formats (PPTX/DOCX)
                        if file_type in ['pptx', 'docx']:
                            return cls._distinguish_office_format(file_path)
                        return file_type
            
            return None
            
        except Exception as e:
            logger.error(f"Error detecting file type from magic bytes: {e}")
            return None
    
    @classmethod
    def _distinguish_office_format(cls, file_path: str) -> str:
        """
        Distinguish between PPTX and DOCX (both use ZIP format)
        
        Args:
            file_path: Path to ZIP-based Office file
            
        Returns:
            'pptx' or 'docx'
        """
        try:
            # Read more content to distinguish formats
            with open(file_path, 'rb') as f:
                content = f.read(2000).lower()
            
            # Look for format-specific strings
            if b'ppt' in content or b'presentation' in content:
                return 'pptx'
            elif b'word' in content or b'document' in content:
                return 'docx'
            else:
                # Default to PPTX if we can't determine
                # (could also check file extension as fallback)
                extension = Path(file_path).suffix.lower().lstrip('.')
                if extension in ['pptx', 'docx']:
                    return extension
                return 'pptx'
                
        except Exception as e:
            logger.error(f"Error distinguishing Office format: {e}")
            return 'pptx'  # Default fallback
    
    @classmethod
    def is_supported(cls, file_type: str) -> bool:
        """Check if file type is supported"""
        return file_type in cls.SUPPORTED_FORMATS
    
    @classmethod
    def validate_file_type(cls, file_path: str, expected_type: str = None) -> tuple[bool, str, str]:
        """
        Validate file type and detect mismatches
        
        Args:
            file_path: Path to file
            expected_type: Expected file type (from metadata)
            
        Returns:
            Tuple (is_valid, detected_type, message)
        """
        detected_type = cls.detect_file_type(file_path)
        
        if not detected_type:
            return False, None, "Unsupported or unrecognized file type"
        
        if not cls.is_supported(detected_type):
            return False, detected_type, f"File type '{detected_type}' is not supported"
        
        if expected_type and detected_type != expected_type:
            return True, detected_type, f"File type mismatch: expected '{expected_type}', detected '{detected_type}'"
        
        return True, detected_type, "File type is valid"


# Convenience functions for backward compatibility
def detect_file_type(file_path: str) -> Optional[str]:
    """Convenience function for file type detection"""
    return FileTypeDetector.detect_file_type(file_path)


def is_supported_file_type(file_type: str) -> bool:
    """Convenience function to check if file type is supported"""
    return FileTypeDetector.is_supported(file_type)