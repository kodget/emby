import os
import re
import fitz
from django.core.management.base import BaseCommand
from curriculum.models import SteeplechaseQuestion
from django.conf import settings
import shutil

class Command(BaseCommand):
    help = 'Extracts Steeplechase questions from PDFs and populates the database.'

    def handle(self, *args, **kwargs):
        pdf_dir = r"C:\Users\USER\Downloads\emby\steeple"
        output_dir = r"C:\Users\USER\Downloads\emby\public\steeplechase\processed"
        os.makedirs(output_dir, exist_ok=True)
        
        # Clear existing steeplechase questions if you want to rerun it clean
        SteeplechaseQuestion.objects.all().delete()

        # Find all PDFs
        pdf_files = [f for f in os.listdir(pdf_dir) if f.endswith('.pdf')]
        
        total_questions_created = 0
        
        for pdf_file in pdf_files:
            pdf_path = os.path.join(pdf_dir, pdf_file)
            self.stdout.write(f"Processing PDF file...")
            doc = fitz.open(pdf_path)
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                # Get text blocks
                blocks = page.get_text("blocks")
                text_blocks = []
                for b in blocks:
                    # b: (x0, y0, x1, y1, text, block_no, block_type)
                    if b[6] == 0: # 0 means text
                        text_blocks.append({
                            'rect': fitz.Rect(b[:4]),
                            'text': b[4].strip()
                        })
                
                # Get images
                images = page.get_images(full=True)
                
                for i, img in enumerate(images):
                    xref = img[0]
                    # Attempt to find bounding box of image to match with text
                    try:
                        rects = page.get_image_rects(xref)
                    except ValueError:
                        # Sometimes get_image_rects fails for weird PDF images
                        continue
                        
                    if not rects:
                        continue
                    img_rect = rects[0]
                    
                    # Find closest text block to the right of the image, or vertically aligned
                    closest_block = None
                    min_dist = float('inf')
                    
                    for tb in text_blocks:
                        # vertical overlap
                        img_y_center = (img_rect.y0 + img_rect.y1) / 2
                        tb_y_center = (tb['rect'].y0 + tb['rect'].y1) / 2
                        dist = abs(img_y_center - tb_y_center)
                        
                        if dist < min_dist:
                            min_dist = dist
                            closest_block = tb
                            
                    if not closest_block or min_dist > 300: # Threshold for matching
                        continue
                        
                    raw_text = closest_block['text']
                    
                    # Parse the text to find questions
                    questions_to_create = []
                    
                    # Pattern 1: Q: ... A: ...
                    if "Q:" in raw_text and "A:" in raw_text:
                        q_match = re.search(r'Q:\s*(.*?)\s*A:\s*(.*)', raw_text, re.IGNORECASE | re.DOTALL)
                        if q_match:
                            questions_to_create.append({
                                'prompt': q_match.group(1).strip().replace('\n', ' '),
                                'answer': q_match.group(2).strip().replace('\n', ' ')
                            })
                    else:
                        # Pattern 2: A. ... B. ... or A: ... B: ...
                        matches = list(re.finditer(r'(?:^|\s)([A-Z])[\.:]\s*(.*?)(?=(?:\s[A-Z][\.:]|^[A-Z][\.:])|$)', raw_text, re.MULTILINE | re.DOTALL))
                        
                        if matches:
                            for m in matches:
                                label = m.group(1).upper()
                                ans = m.group(2).strip().replace('\n', ' ')
                                if len(ans) > 1: # Ignore empty
                                    questions_to_create.append({
                                        'prompt': f"Identify marked structure {label}",
                                        'answer': ans
                                    })
                        else:
                            # Just a plain text answer
                            ans = raw_text.replace('\n', ' ')
                            # Ignore page numbers or junk text (short length)
                            if len(ans) > 3 and not ans.isdigit():
                                questions_to_create.append({
                                    'prompt': "Identify the marked structure.",
                                    'answer': ans
                                })
                            
                    if not questions_to_create:
                        continue
                        
                    # Save image
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]
                    
                    safe_pdf_name = pdf_file.replace('.pdf', '').replace(' ', '_')
                    base_img_name = f"{safe_pdf_name}_p{page_num}_i{i}"
                    img_filename = f"{base_img_name}.{image_ext}"
                    img_path = os.path.join(output_dir, img_filename)
                    
                    with open(img_path, "wb") as f:
                        f.write(image_bytes)
                        
                    # Create DB records
                    for q_idx, q_data in enumerate(questions_to_create):
                        q_id = f"{base_img_name}_q{q_idx}"
                        
                        ans_list = [q_data['answer']] if q_data['answer'] else []
                        
                        SteeplechaseQuestion.objects.create(
                            id=q_id,
                            image_url=f"/steeplechase/processed/{img_filename}",
                            prompt=q_data['prompt'],
                            accepted_answers=ans_list,
                            source_file=pdf_file,
                            source_page=page_num
                        )
                        total_questions_created += 1

        self.stdout.write(self.style.SUCCESS(f'Successfully created {total_questions_created} steeplechase questions.'))
