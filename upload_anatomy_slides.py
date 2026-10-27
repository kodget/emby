"""
Upload anatomy slides to the backend systematically.
This script uploads slides one by one with proper tracking and error handling.
"""

import requests
import os
import time
from pathlib import Path

# Configuration
API_BASE_URL = "http://localhost:8000/api"
ANATOMY_FOLDER = Path(r"c:\Users\USER\emby\anatomy")

# You'll need to get an authentication token first
# Login to get token
def get_auth_token(email, password):
    """Login and get authentication token"""
    response = requests.post(
        f"{API_BASE_URL}/auth/signin/",
        json={"email": email, "password": password}
    )
    if response.status_code == 200:
        data = response.json()
        return data.get('access_token') or data.get('token')
    else:
        print(f"❌ Login failed: {response.status_code}")
        print(response.text)
        return None

def get_or_create_subject(token, subject_name):
    """Get or create Anatomy subject"""
    headers = {"Authorization": f"Bearer {token}"}
    
    # Try to get existing subjects
    response = requests.get(f"{API_BASE_URL}/curriculum/subjects/", headers=headers)
    if response.status_code == 200:
        subjects = response.json().get('results', [])
        for subject in subjects:
            if subject['name'].lower() == subject_name.lower():
                return subject['id']
    
    # Create new subject if not found
    response = requests.post(
        f"{API_BASE_URL}/curriculum/subjects/",
        headers=headers,
        json={"name": subject_name, "description": "Human Anatomy"}
    )
    if response.status_code == 201:
        return response.json()['id']
    return None

def get_or_create_block(token, subject_id, block_name, order):
    """Get or create block"""
    headers = {"Authorization": f"Bearer {token}"}
    
    # Try to get existing blocks
    response = requests.get(
        f"{API_BASE_URL}/curriculum/subjects/{subject_id}/blocks/",
        headers=headers
    )
    if response.status_code == 200:
        blocks = response.json().get('results', [])
        for block in blocks:
            if block['name'].lower() == block_name.lower():
                return block['id']
    
    # Create new block
    response = requests.post(
        f"{API_BASE_URL}/curriculum/subjects/{subject_id}/blocks/",
        headers=headers,
        json={"name": block_name, "order": order}
    )
    if response.status_code == 201:
        return response.json()['id']
    return None

def get_or_create_subblock(token, block_id, subblock_name, order):
    """Get or create sub-block"""
    headers = {"Authorization": f"Bearer {token}"}
    
    # Try to get existing sub-blocks
    response = requests.get(
        f"{API_BASE_URL}/curriculum/blocks/{block_id}/sub-blocks/",
        headers=headers
    )
    if response.status_code == 200:
        subblocks = response.json().get('results', [])
        for subblock in subblocks:
            if subblock['name'].lower() == subblock_name.lower():
                return subblock['id']
    
    # Create new sub-block
    response = requests.post(
        f"{API_BASE_URL}/curriculum/blocks/{block_id}/sub-blocks/",
        headers=headers,
        json={"name": subblock_name, "order": order}
    )
    if response.status_code == 201:
        return response.json()['id']
    return None

def upload_slide(token, subblock_id, file_path, title):
    """Upload a single slide"""
    headers = {"Authorization": f"Bearer {token}"}
    
    with open(file_path, 'rb') as f:
        files = {'file': (os.path.basename(file_path), f)}
        data = {
            'title': title,
            'sub_block': subblock_id
        }
        
        print(f"  📤 Uploading: {title}...")
        response = requests.post(
            f"{API_BASE_URL}/curriculum/slides/",
            headers=headers,
            files=files,
            data=data
        )
        
        if response.status_code == 201:
            slide_data = response.json()
            print(f"  ✅ Uploaded successfully! Slide ID: {slide_data.get('id')}")
            return slide_data
        else:
            print(f"  ❌ Upload failed: {response.status_code}")
            print(f"  Response: {response.text}")
            return None

def upload_neuroanatomy_slides(token):
    """Upload all neuroanatomy slides"""
    print("\n" + "="*60)
    print("🧠 UPLOADING NEUROANATOMY SLIDES")
    print("="*60 + "\n")
    
    # Setup structure
    print("📋 Setting up course structure...")
    subject_id = get_or_create_subject(token, "Anatomy")
    if not subject_id:
        print("❌ Failed to create/get Anatomy subject")
        return
    print(f"✅ Subject ID: {subject_id}")
    
    block_id = get_or_create_block(token, subject_id, "Third Block", 3)
    if not block_id:
        print("❌ Failed to create/get Third Block")
        return
    print(f"✅ Block ID: {block_id}")
    
    subblock_id = get_or_create_subblock(token, block_id, "Neuroanatomy", 2)
    if not subblock_id:
        print("❌ Failed to create/get Neuroanatomy sub-block")
        return
    print(f"✅ Sub-block ID: {subblock_id}\n")
    
    # Get slides
    neuro_folder = ANATOMY_FOLDER / "Third block" / "Neuro"
    slides = list(neuro_folder.glob("*.pdf")) + list(neuro_folder.glob("*.pptx"))
    slides = [s for s in slides if not s.name.startswith('.') and not s.name.endswith('.docx.pdf')]
    
    print(f"📚 Found {len(slides)} slides to upload\n")
    
    # Upload each slide
    successful = 0
    failed = 0
    
    for i, slide_path in enumerate(slides, 1):
        # Clean up title
        title = slide_path.stem
        title = title.replace('_', ' ').replace('  ', ' ').strip()
        
        print(f"\n[{i}/{len(slides)}] {title}")
        print("-" * 60)
        
        result = upload_slide(token, subblock_id, slide_path, title)
        
        if result:
            successful += 1
            # Wait a bit between uploads to avoid overwhelming the server
            if i < len(slides):
                print("  ⏳ Waiting 2 seconds before next upload...")
                time.sleep(2)
        else:
            failed += 1
    
    # Summary
    print("\n" + "="*60)
    print("📊 UPLOAD SUMMARY")
    print("="*60)
    print(f"✅ Successful: {successful}")
    print(f"❌ Failed: {failed}")
    print(f"📊 Total: {len(slides)}")
    print("="*60 + "\n")

def main():
    import sys
    
    print("\n🚀 ANATOMY SLIDE UPLOADER")
    print("="*60)
    print("This script will upload slides to your local backend")
    print("Make sure Django and Celery are running!")
    print("="*60 + "\n")
    
    # Get credentials from command line arguments
    if len(sys.argv) < 3:
        print("Usage: python upload_anatomy_slides.py <email> <password>")
        print("\nExample:")
        print("  python upload_anatomy_slides.py user@example.com mypassword")
        sys.exit(1)
    
    email = sys.argv[1]
    password = sys.argv[2]
    
    print(f"🔐 Logging in as {email}...")
    token = get_auth_token(email, password)
    
    if not token:
        print("❌ Failed to get authentication token. Exiting.")
        return
    
    print("✅ Successfully authenticated!\n")
    
    # Upload neuroanatomy slides
    upload_neuroanatomy_slides(token)
    
    print("\n✅ All done! Check your Celery worker logs to see processing status.")
    print("🌐 Visit http://localhost:3000 to view the uploaded slides.\n")

if __name__ == "__main__":
    main()
