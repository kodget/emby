import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from curriculum.models import QuizQuestion, Subject, Block, Topic

def seed_questions():
    print("=== SEEDING PLENTIFUL QUESTIONS FOR EMBY DEV ENVIRONMENT ===")
    
    # 1. Anatomy questions
    anatomy_sub = Subject.objects.filter(name__icontains='anatomy').first()
    if anatomy_sub:
        print(f"Found Anatomy Subject: {anatomy_sub.name} ({anatomy_sub.id})")
        anatomy_block = Block.objects.filter(subject=anatomy_sub).first()
        if anatomy_block:
            print(f"Found Anatomy Block: {anatomy_block.name} ({anatomy_block.id})")
            anatomy_topic = Topic.objects.filter(block=anatomy_block).first()
            if anatomy_topic:
                print(f"Found Anatomy Topic: {anatomy_topic.name} ({anatomy_topic.id})")
            
            # Generate 20 MCQs for each difficulty (easy, medium, hard) = 60 MCQs
            mcq_data = []
            # First add some realistic ones
            mcq_data.extend([
                {
                    'id': 'anat_mcq_real_1',
                    'question_text': 'What is the primary action of the biceps brachii muscle?',
                    'option_a': 'Flexion and supination of the forearm',
                    'option_b': 'Extension of the forearm',
                    'option_c': 'Abduction of the arm',
                    'option_d': 'Adduction of the arm',
                    'correct_option': 'A',
                    'explanation': 'The biceps brachii is a powerful supinator of the forearm and also flexes the elbow.',
                    'difficulty': 'easy'
                },
                {
                    'id': 'anat_mcq_real_2',
                    'question_text': 'Which nerve is commonly compressed in carpal tunnel syndrome?',
                    'option_a': 'Ulnar nerve',
                    'option_b': 'Median nerve',
                    'option_c': 'Radial nerve',
                    'option_d': 'Axillary nerve',
                    'correct_option': 'B',
                    'explanation': 'Carpal tunnel syndrome involves compression of the median nerve as it passes beneath the flexor retinaculum.',
                    'difficulty': 'easy'
                },
                {
                    'id': 'anat_mcq_real_3',
                    'question_text': 'Which muscle initiates abduction of the shoulder joint (first 15 degrees)?',
                    'option_a': 'Deltoid',
                    'option_b': 'Supraspinatus',
                    'option_c': 'Infraspinatus',
                    'option_d': 'Subscapularis',
                    'correct_option': 'B',
                    'explanation': 'The supraspinatus muscle initiates abduction of the shoulder joint up to approximately 15 degrees, after which the deltoid takes over.',
                    'difficulty': 'medium'
                },
                {
                    'id': 'anat_mcq_real_4',
                    'question_text': 'Which nerve is at risk of injury in a fracture of the surgical neck of the humerus?',
                    'option_a': 'Radial nerve',
                    'option_b': 'Axillary nerve',
                    'option_c': 'Median nerve',
                    'option_d': 'Ulnar nerve',
                    'correct_option': 'B',
                    'explanation': 'The axillary nerve wraps around the surgical neck of the humerus and is vulnerable during fractures of this region.',
                    'difficulty': 'medium'
                }
            ])
            
            # Fill the rest dynamically to have a robust question pool
            for diff in ['easy', 'medium', 'hard']:
                for i in range(1, 25):
                    mcq_data.append({
                        'id': f'anat_mcq_{diff}_{i}',
                        'question_text': f'Anatomy {diff.capitalize()} MCQ {i}: Which of the following anatomical structures is key for upper limb function?',
                        'option_a': 'Option A (Correct Answer)',
                        'option_b': 'Option B',
                        'option_c': 'Option C',
                        'option_d': 'Option D',
                        'correct_option': 'A',
                        'explanation': f'This is a generated explanation for Anatomy {diff} question {i}.',
                        'difficulty': diff
                    })
            
            # Generate 10 theory questions for each difficulty = 30 theory questions
            theory_data = []
            theory_data.extend([
                {
                    'id': 'anat_theory_real_1',
                    'question_text': 'Describe the boundaries and contents of the cubital fossa.',
                    'ideal_answer': 'The cubital fossa is a triangular space at the elbow. Boundaries: Superiorly - line between epicondyles; Medially - pronator teres; Laterally - brachioradialis. Contents (medial to lateral): Median nerve, Brachial artery, Biceps tendon, Radial nerve.',
                    'difficulty': 'medium',
                    'maximum_marks': 15
                },
                {
                    'id': 'anat_theory_real_2',
                    'question_text': 'Explain Erb-Duchenne palsy (causes and presentation).',
                    'ideal_answer': 'Erb-Duchenne palsy results from upper trunk injury of the brachial plexus (C5-C6 roots). Presentation: Waiters tip hand deformity - arm adducted/internally rotated, elbow extended, forearm pronated.',
                    'difficulty': 'hard',
                    'maximum_marks': 20
                }
            ])
            
            for diff in ['easy', 'medium', 'hard']:
                for i in range(1, 15):
                    theory_data.append({
                        'id': f'anat_theory_{diff}_{i}',
                        'question_text': f'Anatomy {diff.capitalize()} Theory {i}: Discuss the clinical significance and anatomical relations of the brachial plexus.',
                        'ideal_answer': f'Model answer for Anatomy {diff} theory question {i}.',
                        'difficulty': diff,
                        'maximum_marks': 10 if diff == 'easy' else (15 if diff == 'medium' else 20)
                    })
            
            # Seed Anatomy questions
            mcq_count = 0
            for q in mcq_data:
                _, created = QuizQuestion.objects.get_or_create(
                    id=q['id'],
                    defaults={
                        'question_text': q['question_text'],
                        'question_type': 'mcq',
                        'option_a': q['option_a'],
                        'option_b': q['option_b'],
                        'option_c': q['option_c'],
                        'option_d': q['option_d'],
                        'correct_option': q['correct_option'],
                        'explanation': q['explanation'],
                        'difficulty': q['difficulty'],
                        'subject': anatomy_sub,
                        'block': anatomy_block,
                        'topic': anatomy_topic
                    }
                )
                if created:
                    mcq_count += 1
            
            theory_count = 0
            for q in theory_data:
                _, created = QuizQuestion.objects.get_or_create(
                    id=q['id'],
                    defaults={
                        'question_text': q['question_text'],
                        'question_type': 'theory',
                        'ideal_answer': q['ideal_answer'],
                        'difficulty': q['difficulty'],
                        'maximum_marks': q['maximum_marks'],
                        'subject': anatomy_sub,
                        'block': anatomy_block,
                        'topic': anatomy_topic
                    }
                )
                if created:
                    theory_count += 1
                    
            print(f"[OK] Seeded {mcq_count} new MCQs and {theory_count} new theory questions for Anatomy.")
            
    # 2. Physiology questions
    phys_sub = Subject.objects.filter(name__icontains='physiology').first()
    if phys_sub:
        print(f"Found Physiology Subject: {phys_sub.name} ({phys_sub.id})")
        phys_block = Block.objects.filter(subject=phys_sub).first()
        if phys_block:
            print(f"Found Physiology Block: {phys_block.name} ({phys_block.id})")
            phys_topic = Topic.objects.filter(block=phys_block).first()
            if phys_topic:
                print(f"Found Physiology Topic: {phys_topic.name} ({phys_topic.id})")
            
            mcq_data_phys = []
            for diff in ['easy', 'medium', 'hard']:
                for i in range(1, 25):
                    mcq_data_phys.append({
                        'id': f'phys_mcq_{diff}_{i}',
                        'question_text': f'Physiology {diff.capitalize()} MCQ {i}: Which physiological response is triggered under homeostatic regulation?',
                        'option_a': 'Option A (Correct Answer)',
                        'option_b': 'Option B',
                        'option_c': 'Option C',
                        'option_d': 'Option D',
                        'correct_option': 'A',
                        'explanation': f'This is a generated explanation for Physiology {diff} question {i}.',
                        'difficulty': diff
                    })
            
            theory_data_phys = []
            for diff in ['easy', 'medium', 'hard']:
                for i in range(1, 15):
                    theory_data_phys.append({
                        'id': f'phys_theory_{diff}_{i}',
                        'question_text': f'Physiology {diff.capitalize()} Theory {i}: Discuss the mechanisms of cellular transport and potential actions.',
                        'ideal_answer': f'Model answer for Physiology {diff} theory question {i}.',
                        'difficulty': diff,
                        'maximum_marks': 10 if diff == 'easy' else (15 if diff == 'medium' else 20)
                    })
            
            # Seed Physiology questions
            mcq_count = 0
            for q in mcq_data_phys:
                _, created = QuizQuestion.objects.get_or_create(
                    id=q['id'],
                    defaults={
                        'question_text': q['question_text'],
                        'question_type': 'mcq',
                        'option_a': q['option_a'],
                        'option_b': q['option_b'],
                        'option_c': q['option_c'],
                        'option_d': q['option_d'],
                        'correct_option': q['correct_option'],
                        'explanation': q['explanation'],
                        'difficulty': q['difficulty'],
                        'subject': phys_sub,
                        'block': phys_block,
                        'topic': phys_topic
                    }
                )
                if created:
                    mcq_count += 1
            
            theory_count = 0
            for q in theory_data_phys:
                _, created = QuizQuestion.objects.get_or_create(
                    id=q['id'],
                    defaults={
                        'question_text': q['question_text'],
                        'question_type': 'theory',
                        'ideal_answer': q['ideal_answer'],
                        'difficulty': q['difficulty'],
                        'maximum_marks': q['maximum_marks'],
                        'subject': phys_sub,
                        'block': phys_block,
                        'topic': phys_topic
                    }
                )
                if created:
                    theory_count += 1
                    
            print(f"[OK] Seeded {mcq_count} new MCQs and {theory_count} new theory questions for Physiology.")
            
    print(f"=== SEEDING COMPLETE: Total questions in database: {QuizQuestion.objects.count()} ===")

if __name__ == '__main__':
    seed_questions()
