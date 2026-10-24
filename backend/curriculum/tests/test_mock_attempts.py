from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from accounts.models import ClassGroup
from curriculum.models import Block, SubBlock, Subject, Topic, QuizQuestion, QuizAttempt, UserStats, AssessmentGradingJob
from curriculum.mock_attempts import balanced_sample
from curriculum import assessment_grading
from curriculum.tests.test_deck_practice import PracticeFixture
from curriculum.tests.test_bank_recovery import BankFixture, mcq, theory, TEXT
from curriculum.tests.test_assessment_grading import grade
from learning import generation
from learning.models import LearningEvent


class MockFixture(PracticeFixture):
    def setUp(self):
        BankFixture.setUp(self)
        self.block = Block.objects.create(id='mock-module', subject=self.slide.subject, name='Upper limb')
        self.sub = SubBlock.objects.create(id='mock-submodule', block=self.block, name='Hand')
        self.slide.block = self.block; self.slide.sub_block = self.sub
        self.slide.save(update_fields=['block', 'sub_block'])
        job = generation.claim_job(self.slide)
        for difficulty in ('easy', 'medium', 'hard'):
            generation.save_batch(job, self.slide, [mcq(f'{difficulty}-{i}', difficulty) for i in range(5)],
                                  TEXT, 'mcq', difficulty, 5)
        generation.save_batch(job, self.slide, [theory(i, 'medium') for i in range(2)], TEXT, 'theory', 'medium', 2)
        self.payload = {'exam_type': 'mock', 'scope_type': 'submodule', 'scope_id': self.sub.pk, 'is_timed': False,
                        'configuration': {'mcq_count': 2, 'theory_count': 2, 'difficulty': 'medium'}}

    def manual(self, pk, **changes):
        values = mcq(pk, 'medium')
        values.pop('source_page'); values.pop('source_quote')
        values.update(id=pk, question_type='mcq', source_type='manual', subject=self.slide.subject,
                      block=self.block, sub_block=self.sub)
        values.update(changes)
        return QuizQuestion.objects.create(**values)


class MockAttemptTests(MockFixture, TestCase):
    def test_all_three_scopes_and_difficulty_counts(self):
        for kind, obj in [('course', self.slide.subject), ('module', self.block), ('submodule', self.sub)]:
            response = self.api('mock_options', {'scope_type': kind, 'scope_id': obj.pk}, method='get')
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(response.data['available']['medium'], {'mcq': 5, 'theory': 2})
            data = self.create(scope_type=kind, scope_id=obj.pk)
            self.assertEqual(data['mcq_total'], 2)
            self.assertEqual(data['theory_total'], 2)
            self.assertEqual({q['difficulty'] for q in data['questions']}, {'medium'})
            self.assertEqual(data['configuration']['scope_name'], obj.name)

    def test_scope_is_required_and_legacy_topic_and_deck_are_rejected(self):
        for changes in [{'scope_id': None}, {'scope_type': 'topic'}, {'scope_type': []}, {'slide': self.slide.pk},
                        {'topic': self.sub.pk}, {'exam_type': 'timed'}, {'scope_id': {'bad': 'id'}}]:
            self.assertEqual(self.api(data={**self.payload, **changes}).status_code, 400)
        self.assertFalse(QuizAttempt.objects.exists())

    def test_foreign_scope_and_mismatched_same_class_parents(self):
        other = Subject.objects.create(id='other-course', name='Other', class_group=self.slide.class_group)
        self.assertEqual(self.api(data={**self.payload, 'subject': other.pk}).status_code, 400)
        group = ClassGroup.objects.create(school=self.slide.class_group.school, set_name='Year 2', code='987654')
        foreign = Subject.objects.create(id='foreign-course', name='Foreign', class_group=group)
        self.assertEqual(self.api(data={**self.payload, 'scope_type': 'course', 'scope_id': foreign.pk}).status_code, 404)

    def test_mislabeled_source_or_foreign_topic_cannot_enter_the_pool(self):
        other = Subject.objects.create(id='other-course', name='Other', class_group=self.slide.class_group)
        bad_block = Block.objects.create(id='bad-block', subject=other, name='Other module')
        self.manual('bad-parent', block=bad_block, sub_block=None)
        topic = Topic.objects.create(id='bad-topic', name='Private foreign topic', block=bad_block)
        self.slide.topic = topic; self.slide.save(update_fields=['topic'])
        # Manual questions are also checked; bank fingerprint rejection is not the only defence.
        self.manual('bad-source', source_slide=self.slide)
        response = self.api('mock_options', {'scope_type': 'course', 'scope_id': self.slide.subject_id}, method='get')
        self.assertEqual(response.data['available']['medium'], {'mcq': 0, 'theory': 0})

    def test_shortage_never_borrows_another_difficulty_or_submodule(self):
        sibling = SubBlock.objects.create(id='sibling-sub', name='Foot', block=self.block)
        self.manual('sibling', sub_block=sibling)
        response = self.api(data={**self.payload, 'configuration': {
            'mcq_count': 6, 'theory_count': 0, 'difficulty': 'medium'}})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(int(response.data['available']['mcq']), 5)
        self.assertFalse(QuizAttempt.objects.exists())

    def test_withdrawn_invalid_stale_and_duplicate_questions_are_unavailable(self):
        existing = QuizQuestion.objects.filter(question_type='mcq', difficulty='medium').first()
        self.manual('duplicate', question_text=existing.question_text)
        self.manual('withdrawn', needs_review=True)
        self.manual('no-key', correct_option='')
        self.manual('bad-source', source_type='ai_generated', bank_key='obsolete', source_slide=self.slide)
        response = self.api('mock_options', {'scope_type': 'course', 'scope_id': self.slide.subject_id}, method='get')
        self.assertEqual(response.data['available']['medium']['mcq'], 5)
        self.slide.file_url = 'https://storage.invalid/changed.pdf'; self.slide.save()
        response = self.api('mock_options', {'scope_type': 'course', 'scope_id': self.slide.subject_id}, method='get')
        self.assertEqual(response.data['available']['medium'], {'mcq': 1, 'theory': 0})  # valid manual duplicate

    def test_malformed_counts_difficulty_and_timing_do_not_create_attempts(self):
        for config in [None, [], {}, {'mcq_count': True, 'theory_count': 0, 'difficulty': 'medium'},
                       {'mcq_count': 101, 'theory_count': 0, 'difficulty': 'medium'},
                       {'mcq_count': 0, 'theory_count': 11, 'difficulty': 'medium'},
                       {'mcq_count': 0, 'theory_count': 0, 'difficulty': 'medium'},
                       {'mcq_count': 1, 'theory_count': 0, 'difficulty': 'mixed'},
                       {'mcq_count': 1, 'theory_count': 0, 'difficulty': 'medium', 'question_source': 'weak_areas'}]:
            self.assertEqual(self.api(data={**self.payload, 'configuration': config}).status_code, 400)
        for changes in [{'is_timed': 'true'}, {'is_timed': True, 'duration_minutes': 0},
                        {'is_timed': True, 'duration_minutes': 1.5}, {'duration_minutes': 10},
                        {'is_timed': True, 'duration_minutes': 181}]:
            self.assertEqual(self.api(data={**self.payload, **changes}).status_code, 400)
        self.assertFalse(QuizAttempt.objects.exists())

    def test_balancing_rotates_topics_and_sources_without_duplicates(self):
        rows = [{'id': f'{topic}-{source}-{i}', 'coverage_key': topic, 'source_key': source}
                for topic, source, count in [('a', 'large', 40), ('a', 'small', 4), ('b', 'only', 4)]
                for i in range(count)]
        for _ in range(10):
            chosen = balanced_sample(rows, 8)
            self.assertEqual(sum(q['coverage_key'] == 'a' for q in chosen), 4)
            self.assertEqual(sum(q['source_key'] == 'small' for q in chosen), 2)
            self.assertEqual(len({q['id'] for q in chosen}), 8)

    def test_answers_hidden_then_saved_versions_grade_and_review_after_source_removal(self):
        data = self.create(); aid = data['id']
        for q in data['questions']:
            self.assertNotIn('correct_option', q)
            self.assertNotIn('marking_rubric', q)
        self.api('answer', {'question_id': data['question_ids'][0], 'selected_option': 'B'}, aid)
        self.api('answer', {'question_id': data['question_ids'][2], 'text_answer': 'Stored answer'}, aid)
        QuizQuestion.objects.update(correct_option='A', ideal_answer='Edited later')
        self.slide.subject.delete()
        resumed = self.api('retrieve', pk=aid, method='get')
        self.assertEqual(resumed.status_code, 200, resumed.data)
        self.assertEqual(resumed.data['question_ids'], data['question_ids'])
        self.assertEqual(len(resumed.data['responses']), 2)
        self.assertEqual(self.api('submit', pk=aid).status_code, 200)
        with patch('curriculum.assessment_grading.grader.evaluate', return_value=grade()):
            self.assertTrue(assessment_grading.run(aid)['completed'])
        result = self.api('result', pk=aid, method='get')
        self.assertEqual(result.data['mcq_score'], 1)
        self.assertEqual(Decimal(result.data['theory_score']), Decimal('1.5'))
        self.assertAlmostEqual(result.data['overall_percentage'], 2.5 / 6 * 100)
        self.assertEqual(result.data['topic_breakdown'][0]['total'], 2)
        self.assertEqual(result.data['topic_breakdown'][0]['correct'], 1)
        self.assertEqual(result.data['questions'][0]['correct_option'], 'B')
        self.assertEqual(result.data['grading']['status'], 'completed')
        for _ in range(2):
            self.assertEqual(self.api('submit', pk=aid).status_code, 200)
        self.assertEqual(UserStats.objects.get(user=self.user).quizzes_taken, 1)
        self.assertEqual(LearningEvent.objects.filter(resource_id=aid).count(), 1)

    def test_owner_and_class_membership_control_snapshot_access(self):
        data = self.create()
        peer = User.objects.create_user('mock-peer')
        peer.profile.class_group = self.slide.class_group; peer.profile.save()
        self.assertEqual(self.api('retrieve', pk=data['id'], method='get', user=peer).status_code, 404)
        self.user.profile.class_group = None; self.user.profile.save()
        self.assertEqual(self.api('retrieve', pk=data['id'], method='get').status_code, 404)
        self.assertEqual(self.api('retry_grading', pk=data['id']).status_code, 404)

    def test_deadline_and_retry_preserve_submission_without_queue(self):
        data = self.create(is_timed=True, duration_minutes=20)
        aid = data['id']
        self.api('answer', {'question_id': data['question_ids'][2], 'text_answer': 'Saved answer'}, aid)
        QuizAttempt.objects.filter(pk=aid).update(deadline=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.api('answer', {'question_id': data['question_ids'][2], 'text_answer': 'Too late'}, aid).status_code, 400)
        with patch('curriculum.tasks.grade_saved_assessment_task.delay', side_effect=RuntimeError('offline')), self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.api('submit', pk=aid).data['status'], 'auto_submitted')
        attempt = QuizAttempt.objects.get(pk=aid)
        self.assertTrue(attempt.theory_grading_pending)
        self.assertEqual(attempt.grading_job.error_code, 'queue_unavailable')
        self.assertEqual(attempt.responses.get(snapshot_question_id=data['question_ids'][2]).text_answer, 'Saved answer')

    def test_completion_failure_rolls_back_before_retry(self):
        data = self.create()
        with patch('learning.events.record', side_effect=RuntimeError('storage failure')), self.assertRaises(RuntimeError):
            self.api('submit', pk=data['id'])
        attempt = QuizAttempt.objects.get(pk=data['id'])
        self.assertEqual(attempt.status, 'in_progress')
        self.assertFalse(AssessmentGradingJob.objects.filter(attempt=attempt).exists())
        self.assertEqual(self.api('submit', pk=data['id']).status_code, 200)
        self.assertEqual(LearningEvent.objects.filter(resource_id=attempt.pk).count(), 1)

    def test_theory_only_blank_and_mcq_only_are_final_without_provider(self):
        for mcqs, theories in [(0, 2), (2, 0)]:
            data = self.create(configuration={'mcq_count': mcqs, 'theory_count': theories, 'difficulty': 'medium'})
            with patch('curriculum.tasks.grade_saved_assessment_task.delay') as queue:
                self.api('submit', pk=data['id'])
                queue.assert_not_called()
            result = self.api('result', pk=data['id'], method='get').data
            self.assertFalse(result['theory_grading_pending'])
            self.assertTrue(result['theory_grading_completed'])
            self.assertEqual(result['overall_percentage'], 0)
            self.assertEqual(result['analysis_data']['total_maximum_marks'], mcqs + theories * 2)


@skipUnless(connection.vendor == 'postgresql', 'Requires PostgreSQL row locks')
class MockConcurrencyTests(MockFixture, TransactionTestCase):
    def test_concurrent_submit_records_one_completion(self):
        data = self.create(configuration={'mcq_count': 1, 'theory_count': 0, 'difficulty': 'medium'})
        self.api('answer', {'question_id': data['question_ids'][0], 'selected_option': 'B'}, data['id'])
        barrier = Barrier(2)
        def submit():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return self.api('submit', pk=data['id']).status_code
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: submit(), range(2)))
        self.assertEqual(results, [200, 200])
        self.assertEqual(UserStats.objects.get(user=self.user).quizzes_taken, 1)
        self.assertEqual(LearningEvent.objects.filter(resource_id=data['id']).count(), 1)
