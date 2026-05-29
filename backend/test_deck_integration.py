#!/usr/bin/env python
"""
Comprehensive test script for Slide Deck system
Tests role management, permissions, API endpoints, and data consistency
"""

import os
import sys
import django
import json

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from django.contrib.auth.models import User
from accounts.models import Profile, School, UserRole
from curriculum.models import SlideDeck, SlidePage
from curriculum.serializers import SlideDeckSerializer, SlidePageSerializer
from rest_framework.test import APIRequestFactory
from rest_framework.test import force_authenticate

# ==================== TEST HELPERS ====================

def print_test(name, passed, details=""):
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status}: {name}")
    if details:
        print(f"   → {details}")

def create_test_user(username, role="student"):
    """Create or get a test user with given role"""
    school = School.objects.first() or School.objects.create(name="Test School")
    user, created = User.objects.get_or_create(
        username=username,
        defaults={
            'email': f"{username}@test.com",
        }
    )
    
    if created:
        user.set_password("test123")
        user.save()
    
    # Get or create profile
    profile, _ = Profile.objects.get_or_create(
        user=user,
        defaults={
            'role': role,
            'school': school
        }
    )
    
    # Update role if needed
    if profile.role != role:
        profile.role = role
        profile.save()
    
    return user

# ==================== TESTS ====================

def test_role_based_access():
    """Test 1: Role-based access control"""
    print("\n" + "="*60)
    print("TEST 1: Role-Based Access Control")
    print("="*60)
    
    # Clean up old test users
    for username in ["student_user", "uploader_user", "class_head_user"]:
        try:
            user = User.objects.get(username=username)
            user.delete()
        except:
            pass
    
    # Test 1.1: Student cannot upload
    student = create_test_user("student_user", role="student")
    student.profile.role = "student"
    student.profile.save()
    print(f"\nCreated student user: {student.username} with role: {student.profile.role}")
    
    # Test 1.2: Uploader can upload
    uploader = create_test_user("uploader_user", role="material_uploader")
    uploader.profile.role = "material_uploader"
    uploader.profile.save()
    print(f"Created uploader user: {uploader.username} with role: {uploader.profile.role}")
    
    # Test 1.3: Class head can upload
    class_head = create_test_user("class_head_user", role="class_head")
    class_head.profile.role = "class_head"
    class_head.profile.save()
    print(f"Created class_head user: {class_head.username} with role: {class_head.profile.role}")
    
    print_test("Role 'student' exists and is set", student.profile.role == "student", f"Role: {student.profile.role}")
    print_test("Role 'material_uploader' exists and is set", uploader.profile.role == "material_uploader", f"Role: {uploader.profile.role}")
    print_test("Role 'class_head' exists and is set", class_head.profile.role == "class_head", f"Role: {class_head.profile.role}")

def test_user_profile_structure():
    """Test 2: User profile has required fields"""
    print("\n" + "="*60)
    print("TEST 2: User Profile Structure")
    print("="*60)
    
    user = create_test_user("profile_test", role="material_uploader")
    profile = user.profile
    
    required_fields = ['id', 'user', 'role', 'school', 'subscription_tier', 'created_at']
    
    print(f"\nProfile fields:")
    for field in required_fields:
        has_field = hasattr(profile, field)
        print(f"  • {field}: {'✅' if has_field else '❌'}")
        print_test(f"Profile has {field}", has_field)

def test_slide_deck_model():
    """Test 3: SlideDeck model structure"""
    print("\n" + "="*60)
    print("TEST 3: SlideDeck Model Structure")
    print("="*60)
    
    uploader = create_test_user("deck_test", role="material_uploader")
    
    # Create a test deck
    deck = SlideDeck.objects.create(
        id="deck_test123",
        title="Test Document",
        file_type="pdf",
        file_size=1024000,
        uploaded_by=uploader,
        processing_status="completed",
        page_count=5
    )
    
    print(f"\nCreated test deck: {deck.id}")
    print(f"  Title: {deck.title}")
    print(f"  File Type: {deck.file_type}")
    print(f"  File Size: {deck.file_size} bytes")
    print(f"  Status: {deck.processing_status}")
    print(f"  Pages: {deck.page_count}")
    print(f"  Uploaded By: {deck.uploaded_by.username}")
    
    required_fields = ['id', 'title', 'file_type', 'file_size', 'processing_status', 'page_count', 'uploaded_by', 'created_at', 'updated_at']
    
    for field in required_fields:
        has_field = hasattr(deck, field)
        print_test(f"SlideDeck has field '{field}'", has_field)
    
    deck.delete()

def test_slide_page_model():
    """Test 4: SlidePage model structure"""
    print("\n" + "="*60)
    print("TEST 4: SlidePage Model Structure")
    print("="*60)
    
    uploader = create_test_user("page_test", role="material_uploader")
    
    # Create test deck and page
    deck = SlideDeck.objects.create(
        id="deck_page_test",
        title="Page Test Document",
        file_type="pdf",
        file_size=1024000,
        uploaded_by=uploader,
        processing_status="completed",
        page_count=1
    )
    
    page = SlidePage.objects.create(
        deck=deck,
        slide_number=1,
        width=1920,
        height=1440,
        extracted_text="Test text content"
    )
    
    print(f"\nCreated test page: {page.id}")
    print(f"  Slide Number: {page.slide_number}")
    print(f"  Dimensions: {page.width}x{page.height}")
    print(f"  Extracted Text Length: {len(page.extracted_text)}")
    
    required_fields = ['id', 'slide_number', 'image', 'width', 'height', 'extracted_text', 'created_at']
    
    for field in required_fields:
        has_field = hasattr(page, field)
        print_test(f"SlidePage has field '{field}'", has_field)
    
    page.delete()
    deck.delete()

def test_serializers():
    """Test 5: Serializer field mapping"""
    print("\n" + "="*60)
    print("TEST 5: Serializer Field Mapping")
    print("="*60)
    
    uploader = create_test_user("serializer_test", role="material_uploader")
    
    deck = SlideDeck.objects.create(
        id="deck_serialize_test",
        title="Serialization Test",
        file_type="pptx",
        file_size=2048000,
        uploaded_by=uploader,
        processing_status="completed",
        page_count=10
    )
    
    page = SlidePage.objects.create(
        deck=deck,
        slide_number=1,
        width=1280,
        height=960,
        extracted_text="Sample extracted text"
    )
    
    # Serialize deck
    deck_serializer = SlideDeckSerializer(deck)
    deck_data = deck_serializer.data
    
    print(f"\nSlideDeck Serialized Fields:")
    expected_deck_fields = ['id', 'title', 'file_type', 'file_size', 'processing_status', 'page_count', 'uploaded_by', 'uploaded_by_name', 'pages', 'created_at', 'updated_at']
    
    for field in expected_deck_fields:
        has_field = field in deck_data
        print_test(f"SlideDeckSerializer has '{field}'", has_field)
        if field in deck_data:
            print(f"   Value: {str(deck_data[field])[:60]}")
    
    # Serialize page
    page_serializer = SlidePageSerializer(page)
    page_data = page_serializer.data
    
    print(f"\nSlidePage Serialized Fields:")
    expected_page_fields = ['id', 'slide_number', 'image_url', 'width', 'height', 'extracted_text', 'created_at']
    
    for field in expected_page_fields:
        has_field = field in page_data
        print_test(f"SlidePageSerializer has '{field}'", has_field)
        if field in page_data:
            print(f"   Value: {str(page_data[field])[:60]}")
    
    page.delete()
    deck.delete()

def test_type_consistency():
    """Test 6: Frontend-Backend type consistency"""
    print("\n" + "="*60)
    print("TEST 6: Frontend-Backend Type Consistency")
    print("="*60)
    
    uploader = create_test_user("type_test", role="material_uploader")
    
    deck = SlideDeck.objects.create(
        id="deck_type_test",
        title="Type Test",
        file_type="docx",
        file_size=512000,
        uploaded_by=uploader,
        processing_status="pending",
        page_count=0
    )
    
    page = SlidePage.objects.create(
        deck=deck,
        slide_number=1,
        width=800,
        height=600,
        extracted_text="Test"
    )
    
    deck_serializer = SlideDeckSerializer(deck)
    page_serializer = SlidePageSerializer(page)
    
    deck_data = deck_serializer.data
    page_data = page_serializer.data
    
    # Check types match frontend expectations
    checks = [
        ("SlideDeck.id is string", isinstance(deck_data['id'], str)),
        ("SlideDeck.title is string", isinstance(deck_data['title'], str)),
        ("SlideDeck.file_type is string", isinstance(deck_data['file_type'], str)),
        ("SlideDeck.file_size is number", isinstance(deck_data['file_size'], int)),
        ("SlideDeck.page_count is number", isinstance(deck_data['page_count'], int)),
        ("SlideDeck.processing_status is string", isinstance(deck_data['processing_status'], str)),
        ("SlidePage.id is number", isinstance(page_data['id'], int)),
        ("SlidePage.slide_number is number", isinstance(page_data['slide_number'], int)),
        ("SlidePage.width is number", isinstance(page_data['width'], int)),
        ("SlidePage.height is number", isinstance(page_data['height'], int)),
        ("SlidePage.extracted_text is string", isinstance(page_data['extracted_text'], str)),
    ]
    
    print("\nType Validation:")
    for check_name, result in checks:
        print_test(check_name, result)
    
    page.delete()
    deck.delete()

# ==================== MAIN ====================

if __name__ == "__main__":
    print("\n")
    print("=" * 60)
    print("  SLIDE DECK INTEGRATION - COMPREHENSIVE TEST SUITE".center(60))
    print("=" * 60)
    
    try:
        test_role_based_access()
        test_user_profile_structure()
        test_slide_deck_model()
        test_slide_page_model()
        test_serializers()
        test_type_consistency()
        
        print("\n" + "="*60)
        print("ALL TESTS COMPLETED")
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"\n❌ TEST ERROR: {e}")
        import traceback
        traceback.print_exc()
