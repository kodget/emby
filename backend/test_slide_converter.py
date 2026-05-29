"""
Test script for slide converter pipeline
"""
import os
import sys
from pathlib import Path

# Add Poppler to PATH if needed
poppler_path = r"C:\Release-26.02.0-0\poppler-26.02.0\Library\bin"
if poppler_path not in os.environ['PATH']:
    os.environ['PATH'] += f";{poppler_path}"

from curriculum.services.converter import SlideConverter, FileTypeDetector

def test_converter():
    """Test the converter pipeline"""
    
    # Test 1: File type detection
    print("=" * 60)
    print("TEST 1: File Type Detection")
    print("=" * 60)
    
    test_file = "test.pdf"
    if os.path.exists(test_file):
        file_type = FileTypeDetector.detect_file_type(test_file)
        print(f"✓ Detected file type: {file_type}")
        assert file_type == "pdf", "Should detect as PDF"
    else:
        print(f"✗ Test file {test_file} not found")
        return False
    
    # Test 2: Converter setup
    print("\n" + "=" * 60)
    print("TEST 2: Converter Setup")
    print("=" * 60)
    
    SlideConverter.ensure_media_directories()
    print("✓ Media directories ready")
    
    # Test 3: Conversion pipeline (if test.pdf exists and is valid)
    print("\n" + "=" * 60)
    print("TEST 3: Conversion Pipeline")
    print("=" * 60)
    
    if os.path.exists(test_file):
        print(f"Converting {test_file}...")
        success, result = SlideConverter.convert_document(
            test_file,
            "pdf",
            "test_deck_123"
        )
        
        if success:
            print(f"✓ Conversion successful!")
            print(f"  - Pages: {result['page_count']}")
            print(f"  - Images: {len(result['slide_images'])} files created")
            if result['slide_images']:
                print(f"  - First image: {result['slide_images'][0]}")
            return True
        else:
            print(f"✗ Conversion failed: {result.get('error', 'Unknown error')}")
            return False
    else:
        print(f"✗ No test file available: {test_file}")
        return False

if __name__ == "__main__":
    try:
        success = test_converter()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"✗ Test error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
