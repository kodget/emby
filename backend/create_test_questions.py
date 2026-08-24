#!/usr/bin/env python
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from curriculum.models import QuizQuestion, Subject, Block

def create_test_questions():
    """Create test questions for task 4.2 validation"""
    
    print("Creating test questions for Quiz Attempt ViewSet testing...")
    
    # Get or create test subject and block
    anatomy_subject, created = Subject.objects.get_or_create(
        id='anatomy-test',
        defaults={
            'name': 'Anatomy Test',
            'description': 'Test subject for quiz system',
            'order': 1
        }
    )
    
    anatomy_block, created = Block.objects.get_or_create(
        id='anatomy-block-test',
        defaults={
            'name': 'Anatomy Block Test',
            'description': 'Test block for quiz system',
            'subject': anatomy_subject,
            'order': 1
        }
    )
    
    print(f"Using subject: {anatomy_subject.name} ({anatomy_subject.id})")
    print(f"Using block: {anatomy_block.name} ({anatomy_block.id})")
    
    # Create MCQ questions with different difficulties
    mcq_questions_data = [
        # Easy MCQ questions
        {
            'id': 'mcq_easy_1',
            'question_text': 'What is the largest bone in the human body?',
            'option_a': 'Femur',
            'option_b': 'Tibia',
            'option_c': 'Humerus',
            'option_d': 'Fibula',
            'correct_option': 'A',
            'explanation': 'The femur (thighbone) is the longest and strongest bone in the human body.',
            'difficulty': 'easy'
        },
        {
            'id': 'mcq_easy_2', 
            'question_text': 'How many chambers does a human heart have?',
            'option_a': 'Two',
            'option_b': 'Three',
            'option_c': 'Four',
            'option_d': 'Five',
            'correct_option': 'C',
            'explanation': 'The human heart has four chambers: two atria and two ventricles.',
            'difficulty': 'easy'
        },
        {
            'id': 'mcq_easy_3',
            'question_text': 'Which organ produces insulin?',
            'option_a': 'Liver',
            'option_b': 'Pancreas',
            'option_c': 'Kidney',
            'option_d': 'Stomach',
            'correct_option': 'B',
            'explanation': 'The pancreas produces insulin, which regulates blood glucose levels.',
            'difficulty': 'easy'
        },
        # Medium MCQ questions  
        {
            'id': 'mcq_medium_1',
            'question_text': 'Which nerve innervates the diaphragm?',
            'option_a': 'Vagus nerve',
            'option_b': 'Phrenic nerve',
            'option_c': 'Intercostal nerves',
            'option_d': 'Accessory nerve',
            'correct_option': 'B',
            'explanation': 'The phrenic nerve (C3-C5) provides motor innervation to the diaphragm.',
            'difficulty': 'medium'
        },
        {
            'id': 'mcq_medium_2',
            'question_text': 'What type of joint is the shoulder joint?',
            'option_a': 'Hinge joint',
            'option_b': 'Pivot joint', 
            'option_c': 'Ball and socket joint',
            'option_d': 'Gliding joint',
            'correct_option': 'C',
            'explanation': 'The shoulder joint is a ball and socket joint allowing movement in multiple planes.',
            'difficulty': 'medium'
        },
        {
            'id': 'mcq_medium_3',
            'question_text': 'Which artery supplies blood to the myocardium?',
            'option_a': 'Pulmonary artery',
            'option_b': 'Aorta',
            'option_c': 'Coronary arteries',
            'option_d': 'Carotid arteries',
            'correct_option': 'C',
            'explanation': 'The coronary arteries supply oxygenated blood to the heart muscle (myocardium).',
            'difficulty': 'medium'
        },
        # Hard MCQ questions
        {
            'id': 'mcq_hard_1',
            'question_text': 'Which structure passes through the foramen ovale?',
            'option_a': 'Maxillary division of trigeminal nerve',
            'option_b': 'Mandibular division of trigeminal nerve',
            'option_c': 'Ophthalmic division of trigeminal nerve',
            'option_d': 'Facial nerve',
            'correct_option': 'B',
            'explanation': 'The mandibular division of the trigeminal nerve (CN V3) passes through the foramen ovale.',
            'difficulty': 'hard'
        },
        {
            'id': 'mcq_hard_2',
            'question_text': 'What is the embryological origin of the thymus?',
            'option_a': 'First pharyngeal pouch',
            'option_b': 'Second pharyngeal pouch', 
            'option_c': 'Third pharyngeal pouch',
            'option_d': 'Fourth pharyngeal pouch',
            'correct_option': 'C',
            'explanation': 'The thymus develops from the ventral portion of the third pharyngeal pouch.',
            'difficulty': 'hard'
        }
    ]
    
    # Create theory questions with different difficulties
    theory_questions_data = [
        # Easy theory questions
        {
            'id': 'theory_easy_1',
            'question_text': 'Describe the basic structure and function of a typical neuron.',
            'ideal_answer': 'A typical neuron consists of a cell body (soma) containing the nucleus, dendrites that receive signals, and an axon that transmits signals. The function is to receive, process, and transmit information through electrical and chemical signals.',
            'difficulty': 'easy',
            'maximum_marks': 10
        },
        {
            'id': 'theory_easy_2',
            'question_text': 'Explain the difference between arteries and veins.',
            'ideal_answer': 'Arteries carry oxygenated blood away from the heart (except pulmonary artery), have thick muscular walls, and higher pressure. Veins carry deoxygenated blood toward the heart (except pulmonary veins), have thinner walls, lower pressure, and contain valves to prevent backflow.',
            'difficulty': 'easy',
            'maximum_marks': 10
        },
        # Medium theory questions
        {
            'id': 'theory_medium_1', 
            'question_text': 'Describe the anatomical boundaries and contents of the axilla.',
            'ideal_answer': 'The axilla has four walls: anterior (pectoralis major/minor), posterior (subscapularis, latissimus dorsi, teres major), medial (serratus anterior, ribs 1-4), and lateral (intertubercular groove of humerus). Contents include axillary vessels, brachial plexus, lymph nodes, and fat.',
            'difficulty': 'medium',
            'maximum_marks': 15
        },
        {
            'id': 'theory_medium_2',
            'question_text': 'Explain the cardiac cycle including the phases of systole and diastole.',
            'ideal_answer': 'The cardiac cycle consists of systole (contraction) and diastole (relaxation). Systole includes isovolumic contraction and ejection phases. Diastole includes isovolumic relaxation, rapid filling, and atrial kick. The cycle is coordinated by electrical conduction system.',
            'difficulty': 'medium', 
            'maximum_marks': 15
        },
        # Hard theory questions
        {
            'id': 'theory_hard_1',
            'question_text': 'Describe the embryological development of the cardiovascular system, including formation of the heart tube and subsequent chamber development.',
            'ideal_answer': 'Cardiovascular development begins with formation of cardiogenic mesoderm. The heart tube forms from fusion of endocardial tubes, then undergoes looping. Chamber development involves septation of atria and ventricles through growth of septa primum/secundum and interventricular septum. Outflow tract separation creates aorta and pulmonary trunk.',
            'difficulty': 'hard',
            'maximum_marks': 20
        }
    ]
    
    # Create MCQ questions
    mcq_created = 0
    for q_data in mcq_questions_data:
        question, created = QuizQuestion.objects.get_or_create(
            id=q_data['id'],
            defaults={
                'question_text': q_data['question_text'],
                'question_type': 'mcq',
                'option_a': q_data['option_a'],
                'option_b': q_data['option_b'],
                'option_c': q_data['option_c'],
                'option_d': q_data['option_d'],
                'correct_option': q_data['correct_option'],
                'explanation': q_data['explanation'],
                'difficulty': q_data['difficulty'],
                'subject': anatomy_subject,
                'block': anatomy_block
            }
        )
        if created:
            mcq_created += 1
    
    # Create theory questions
    theory_created = 0
    for q_data in theory_questions_data:
        question, created = QuizQuestion.objects.get_or_create(
            id=q_data['id'],
            defaults={
                'question_text': q_data['question_text'],
                'question_type': 'theory',
                'ideal_answer': q_data['ideal_answer'],
                'difficulty': q_data['difficulty'],
                'maximum_marks': q_data['maximum_marks'],
                'subject': anatomy_subject,
                'block': anatomy_block
            }
        )
        if created:
            theory_created += 1
    
    print(f"✓ Created {mcq_created} new MCQ questions")
    print(f"✓ Created {theory_created} new theory questions")
    print(f"Total questions now: {QuizQuestion.objects.count()}")
    
    # Show breakdown by difficulty
    for difficulty in ['easy', 'medium', 'hard']:
        mcq_count = QuizQuestion.objects.filter(question_type='mcq', difficulty=difficulty).count()
        theory_count = QuizQuestion.objects.filter(question_type='theory', difficulty=difficulty).count()
        print(f"  {difficulty.capitalize()}: {mcq_count} MCQ, {theory_count} theory")

if __name__ == '__main__':
    create_test_questions()