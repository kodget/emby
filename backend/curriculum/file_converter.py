"""
File Converter - Convert PPT/DOCX to PDF
"""
import os
import tempfile
import requests
from io import BytesIO


def download_file(url):
    """Download file from URL"""
    response = requests.get(url)
    response.raise_for_status()
    return BytesIO(response.content)


def convert_to_pdf(file_url, file_type):
    """
    Convert PPT/DOCX to PDF
    For now, returns the original URL since conversion requires external tools
    In production, use services like LibreOffice or cloud conversion APIs
    """
    # TODO: Implement actual conversion using:
    # - LibreOffice headless mode
    # - CloudConvert API
    # - Or similar service
    
    # For now, just return the original URL
    # PDFs don't need conversion
    if file_type == 'pdf':
        return file_url
    
    # For PPT/DOCX, we'll extract content directly without conversion
    return file_url
