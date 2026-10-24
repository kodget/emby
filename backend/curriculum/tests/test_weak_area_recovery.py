"""Historical cache duplicates must not break writes or drive student recommendations."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import connection, transaction, IntegrityError, close_old_connections
from django.test import TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from curriculum.models import Block, SubBlock, Topic, QuizQuestion, UserStats
from curriculum.tests.test_bank_recovery import BankFixture, mcq
from learning import events, selection, notifications
from learning.analytics_evidence import Evidence
from learning.models import ActivityType, LearningEvent, WeakArea


class WeakFixture(BankFixture):
    def setUp(self):
        super().setUp()
        self.block = Block.objects.create(id='revision-block', name='Module', subject=self.slide.subject)
        self.sub = SubBlock.objects.create(id='revision-sub', name='Needs revision', block=self.block)
        self.strong = SubBlock.objects.create(id='strong-sub', name='Already strong', block=self.block)

    def cache(self, **changes):
        data = dict(user=self.user, scope='SUB_BLOCK', subject=self.slide.subject,
                    block=self.block, sub_block=self.sub, attempted=99, correct=0, mastery=0,
                    label='Outdated private label')
        data.update(changes)
        return WeakArea.objects.create(**data)

    def evidence(self, sub=None, correct=1, total=8, days=0, **changes):
        data = dict(user=self.user, activity=ActivityType.QUESTION_ANSWERED,
                    subject=self.slide.subject, block=self.block, sub_block=sub or self.sub,
                    total_count=total, correct_count=correct, occurred_at=timezone.now()-timedelta(days=days))
        data.update(changes)
        return LearningEvent.objects.create(**data)

    def question(self, name, sub=None, **changes):
        data = mcq(name)
        data.pop('source_page'); data.pop('source_quote')
        data.update(id=name, question_type='mcq', source_type='manual', subject=self.slide.subject,
                    block=self.block, sub_block=sub or self.sub)
        data.update(changes)
        return QuizQuestion.objects.create(**data)


class WeakAreaRecoveryTests(WeakFixture, TestCase):
    def test_duplicate_legacy_rows_are_preserved_and_one_is_adopted_for_new_writes(self):
        older = self.cache(attempted=5, correct=1)
        latest = self.cache(attempted=10, correct=2)
        now = timezone.now()
        WeakArea.objects.filter(pk=older.pk).update(updated_at=now-timedelta(days=1))
        WeakArea.objects.filter(pk=latest.pk).update(updated_at=now)
        original = WeakArea.objects.filter(pk=older.pk).values().get()
        event = events.record(self.user, ActivityType.QUESTION_ANSWERED, subject=self.slide.subject,
            block=self.block, sub_block=self.sub, total_count=3, correct_count=2,
            idempotency_key='new-evidence', award_xp=False)
        latest.refresh_from_db()
        self.assertEqual(latest.canonical_key, 'SUB_BLOCK:revision-sub')
        self.assertEqual((latest.attempted, latest.correct), (13, 4))
        self.assertEqual(WeakArea.objects.filter(pk=older.pk).values().get(), original)
        self.assertEqual(WeakArea.objects.filter(scope='SUB_BLOCK').count(), 2)
        events.record(self.user, event.activity, subject=self.slide.subject, block=self.block,
                      sub_block=self.sub, total_count=3, correct_count=2,
                      idempotency_key='new-evidence', award_xp=False)
        latest.refresh_from_db(); self.assertEqual(latest.attempted, 13)

    def test_database_rejects_two_current_write_keys_but_preserves_nullable_history(self):
        self.cache(); self.cache()
        self.cache(canonical_key='SUB_BLOCK:revision-sub')
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.cache(canonical_key='SUB_BLOCK:revision-sub')
        self.assertEqual(WeakArea.objects.count(), 3)

    def test_failed_adoption_rolls_back_event_and_historical_row(self):
        row = self.cache()
        with patch('learning.models.WeakArea.save', side_effect=RuntimeError('failed cache write')):
            with self.assertRaises(RuntimeError):
                events.record(self.user, ActivityType.QUESTION_ANSWERED,
                    subject=self.slide.subject, block=self.block, sub_block=self.sub,
                    total_count=3, correct_count=1, award_xp=False)
        row.refresh_from_db()
        self.assertIsNone(row.canonical_key)
        self.assertEqual(row.attempted, 99)
        self.assertFalse(LearningEvent.objects.exists())

    def test_historical_backfill_does_not_move_last_practice_backwards(self):
        self.cache(last_practised_at=timezone.now())
        before = WeakArea.objects.get().last_practised_at
        events.record(self.user, ActivityType.QUESTION_ANSWERED, subject=self.slide.subject,
            block=self.block, sub_block=self.sub, total_count=3, correct_count=1,
            occurred_at=timezone.now()-timedelta(days=4), award_xp=False)
        self.assertEqual(WeakArea.objects.get(canonical_key='SUB_BLOCK:revision-sub').last_practised_at, before)

    def test_cache_only_weakness_cannot_select_questions_or_appear_in_helpers(self):
        self.cache(); self.question('cached-only')
        self.assertEqual(selection.select_questions(self.user, count=10, weak_areas_only=True), [])
        self.assertEqual(events.weakest(self.user, scope='SUB_BLOCK'), [])
        self.assertEqual(events.strongest(self.user, scope='SUB_BLOCK'), [])

    def test_weak_only_excludes_a_strong_sibling_even_when_the_parent_is_weak(self):
        weak = self.question('weak')
        self.question('strong', sub=self.strong)
        self.evidence(total=20, correct=0)
        self.evidence(sub=self.strong, total=4, correct=4)
        chosen = selection.select_questions(self.user, count=10, weak_areas_only=True)
        self.assertEqual([q.pk for q in chosen], [weak.pk])
        self.assertEqual(events.strongest(self.user, scope='SUB_BLOCK')[0]['id'], 'SUB_BLOCK:strong-sub')

    def test_weakness_threshold_period_and_minimum_match_the_report(self):
        self.question('available')
        self.evidence(correct=2, total=3, days=30)  # Outside 30 local calendar days.
        self.assertEqual(selection.select_questions(self.user, count=10, weak_areas_only=True), [])
        self.evidence(correct=0, total=2)
        self.assertEqual(selection.select_questions(self.user, count=10, weak_areas_only=True), [])
        self.evidence(correct=7, total=8)  # 7/10: weak despite being above the old .70 threshold.
        self.assertEqual(len(selection.select_questions(self.user, count=10, weak_areas_only=True)), 1)
        self.evidence(correct=2, total=2)  # 9/12 = .75: strong.
        self.assertEqual(selection.select_questions(self.user, count=10, weak_areas_only=True), [])

    def test_selection_does_not_offer_held_malformed_or_inconsistent_questions(self):
        good = self.question('good')
        self.question('held', needs_review=True)
        self.question('bad-answer', correct_option='')
        self.question('wrong-parent', block=None)
        self.evidence()
        self.assertEqual([q.pk for q in selection.select_questions(self.user, count=10)], [good.pk])
        self.assertEqual(selection.select_questions(self.user, count=0), [])
        self.assertEqual(selection.select_questions(self.user, count=-1), [])

    def test_old_class_evidence_does_not_affect_selection_or_reminders(self):
        self.evidence(); self.cache(); self.question('private')
        self.user.profile.class_group = None; self.user.profile.save()
        self.assertEqual(selection.select_questions(self.user, count=10, weak_areas_only=True), [])
        with patch('learning.notifications.schedule', return_value=None) as scheduled:
            notifications.build_for_user(self.user)
        self.assertFalse(any(call.args[1] == 'WEAK_AREA' for call in scheduled.call_args_list))

    def test_revision_reminder_uses_current_evidence_and_stable_node_identity(self):
        self.cache()
        with patch('learning.notifications.schedule', return_value=None) as scheduled:
            notifications.build_for_user(self.user)
        self.assertFalse(any(call.args[1] == 'WEAK_AREA' for call in scheduled.call_args_list))
        self.evidence()
        with patch('learning.notifications.schedule', return_value=None) as scheduled:
            notifications.build_for_user(self.user)
        calls = [call for call in scheduled.call_args_list if call.args[1] == 'WEAK_AREA']
        self.assertEqual(len(calls), 1)
        self.assertIn('Needs revision', calls[0].args[2])
        self.assertNotIn('Outdated private label', calls[0].args[2])
        self.assertIn('SUB_BLOCK:revision-sub', calls[0].kwargs['dedupe_key'])
        self.evidence(correct=30, total=30)
        with patch('learning.notifications.schedule', return_value=None) as scheduled:
            notifications.build_for_user(self.user)
        self.assertFalse(any(call.args[1] == 'WEAK_AREA' for call in scheduled.call_args_list))

    def test_current_evidence_wins_over_a_stale_cached_streak(self):
        UserStats.objects.create(user=self.user, current_streak=99, last_activity_date=timezone.localdate()-timedelta(days=1))
        with patch('learning.notifications.schedule', return_value=None) as scheduled:
            notifications.build_for_user(self.user)
        self.assertFalse(any(call.args[1] == 'STREAK_AT_RISK' for call in scheduled.call_args_list))

    def test_large_topic_rollup_has_bounded_queries_and_preserves_renamed_labels(self):
        topics = [Topic(id=f'rollup-{i}', name=f'Topic {i}', block=self.block, sub_block=self.sub) for i in range(300)]
        Topic.objects.bulk_create(topics)
        evidence = Evidence(self.user, 30)
        at = timezone.now()
        evidence.window = [dict(at=at, nodes=[(('TOPIC', topic.pk, topic.name), 1, 3)]) for topic in topics]
        evidence.window.append(dict(at=at, nodes=[(('TOPIC', topics[0].pk, 'Old label'), 0, 2)]))
        with CaptureQueriesContext(connection) as queries:
            groups = evidence.topics(scope='SUB_BLOCK', limit=None)
        self.assertLessEqual(len(queries), 4)
        self.assertEqual(groups['weakest'][0]['attempted'], 902)
        self.assertEqual(groups['weakest'][0]['correct'], 300)
        with CaptureQueriesContext(connection) as queries:
            groups = evidence.topics(scope='TOPIC', limit=None)
        self.assertEqual(len(queries), 0)
        self.assertEqual(groups['tracked_nodes'], 300)


@skipUnless(connection.vendor == 'postgresql', 'PostgreSQL row locks required')
class WeakAreaConcurrencyTests(WeakFixture, TransactionTestCase):
    def test_simultaneous_new_results_adopt_only_one_legacy_row(self):
        self.cache(attempted=0, correct=0); self.cache(attempted=0, correct=0)
        barrier = Barrier(2)
        def run(index):
            close_old_connections()
            try:
                user = User.objects.get(pk=self.user.pk)
                barrier.wait(timeout=15)
                events.record(user, ActivityType.QUESTION_ANSWERED, subject=self.slide.subject,
                    block=self.block, sub_block=self.sub, correct_count=1, total_count=2,
                    idempotency_key=f'parallel-{index}', award_xp=False)
            finally: close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool: list(pool.map(run, range(2)))
        self.assertEqual(WeakArea.objects.filter(scope='SUB_BLOCK').count(), 2)
        current = WeakArea.objects.get(canonical_key='SUB_BLOCK:revision-sub')
        self.assertEqual((current.attempted, current.correct), (4, 2))
