from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import ClassGroup, ClassRole, School
from curriculum.models import (
    BattleParticipant, Block, BrainBattle, Flashcard, FlashcardProgress,
    QuizQuestion, Subject, SubBlock, Topic,
)
from learning import analytics, battles as battle_service, dashboard, views
from learning.models import ActivityType, DashboardMessage, LearningEvent, QuestionExposure, WeakArea
from pastquestions import views as past_views
from pastquestions.models import PastQuestionUpload
from curriculum.views import BrainBattleViewSet


class RelatedClassAccessTests(TestCase):
    def setUp(self):
        school = School.objects.create(name="Class access school")
        self.users, self.groups, self.subjects, self.blocks, self.topics = [], [], [], [], []
        for i in range(2):
            group = ClassGroup.objects.create(school=school, set_name=f"Year {i}", code=f"45678{i}")
            user = User.objects.create_user(f"related-student-{i}")
            user.profile.class_group = group
            user.profile.class_role = ClassRole.MATERIAL_UPLOADER
            user.profile.save()
            subject = Subject.objects.create(id=f"related-course-{i}", name=f"Course {i}", class_group=group)
            block = Block.objects.create(id=f"related-module-{i}", name=f"Module {i}", subject=subject)
            sub_block = SubBlock.objects.create(id=f"related-submodule-{i}", name=f"Submodule {i}", block=block)
            topic = Topic.objects.create(id=f"related-topic-{i}", name=f"Topic {i}", block=block, sub_block=sub_block)
            self.users.append(user)
            self.groups.append(group)
            self.subjects.append(subject)
            self.blocks.append(block)
            self.topics.append(topic)
        self.factory = APIRequestFactory()

    def request(self, handler, *, method="get", data=None, user=None, **kwargs):
        request = getattr(self.factory, method)("/api/test/", data or {}, format="json")
        force_authenticate(request, user=user or self.users[0])
        return handler(request, **kwargs)

    @patch("pastquestions.views.process_past_question_upload")
    def test_past_upload_rejects_foreign_references_before_ai_and_database_write(self, process):
        for field, value in (("subject_id", self.subjects[1].pk),
                             ("block_id", self.blocks[1].pk), ("topic_id", self.topics[1].pk)):
            with self.subTest(field=field):
                response = self.request(past_views.upload_past_questions, method="post", data={
                    "content": "An examination", "subject_id": self.subjects[0].pk, field: value,
                })
                self.assertEqual(response.status_code, 404)
        self.assertFalse(PastQuestionUpload.objects.exists())
        process.assert_not_called()

    @patch("pastquestions.views.process_past_question_upload")
    def test_past_upload_requires_authorized_uploader(self, process):
        self.users[0].profile.class_role = ClassRole.STUDENT
        self.users[0].profile.save()
        response = self.request(past_views.upload_past_questions, method="post", data={
            "content": "Questions", "subject_id": self.subjects[0].pk,
        })
        self.assertEqual(response.status_code, 403)
        process.assert_not_called()

    @patch("pastquestions.views.process_past_question_upload", return_value={"created_mcq": 2})
    def test_past_upload_accepts_own_topic_and_infers_its_module(self, process):
        response = self.request(past_views.upload_past_questions, method="post", data={
            "content": "Questions", "subject_id": self.subjects[0].pk, "topic_id": self.topics[0].pk,
        })
        self.assertEqual(response.status_code, 201)
        upload = PastQuestionUpload.objects.get()
        self.assertEqual(upload.block, self.blocks[0])
        self.assertEqual(upload.topic, self.topics[0])
        process.assert_called_once_with(upload.pk)

    @patch("pastquestions.views.process_past_question_upload")
    def test_past_upload_rejects_mismatched_same_class_parents(self, process):
        other = Subject.objects.create(id="same-class-other-course", name="Other", class_group=self.groups[0])
        response = self.request(past_views.upload_past_questions, method="post", data={
            "content": "Questions", "subject_id": other.pk, "topic_id": self.topics[0].pk,
        })
        self.assertEqual(response.status_code, 400)
        process.assert_not_called()

    @patch("pastquestions.views.process_past_question_upload")
    def test_past_upload_requires_course_and_text_content(self, process):
        for data in ({"content": "Questions"}, {"content": {"unsafe": "object"}, "subject_id": self.subjects[0].pk}):
            self.assertEqual(self.request(past_views.upload_past_questions, method="post", data=data).status_code, 400)
        process.assert_not_called()

    def test_past_upload_status_hides_old_class_and_unassigned_records(self):
        uploads = [PastQuestionUpload.objects.create(uploaded_by=self.users[0], subject=subject,
                   file_content="Content", file_name="Private filename") for subject in (*self.subjects, None)]
        self.assertEqual(self.request(past_views.get_upload_status, upload_id=uploads[0].pk).status_code, 200)
        for upload in uploads[1:]:
            self.assertEqual(self.request(past_views.get_upload_status, upload_id=upload.pk).status_code, 404)

    def test_question_bank_counts_only_visible_questions_and_exposure(self):
        from curriculum.tests.test_bank_recovery import mcq
        for i, subject in enumerate(self.subjects):
            values = mcq(i)
            values.pop('source_page'); values.pop('source_quote')
            question = QuizQuestion.objects.create(id=f"related-question-{i}", question_type="mcq",
                source_type='manual', subject=subject, **values)
            QuestionExposure.objects.create(user=self.users[0], question=question,
                times_seen=1, times_answered=1, times_incorrect=i)
        self.assertEqual(analytics.question_bank(self.users[0]), {
            "total": 1, "seen": 1, "unseen": 0, "answered": 1, "missed": 0, "percent_seen": 100,
        })

    def make_weak_areas(self):
        return [WeakArea.objects.create(user=self.users[0], scope=WeakArea.Scope.TOPIC,
            topic=topic, label=f"Private topic {i}", attempted=10, correct=8,
            mastery=0.8, priority=i + 1) for i, topic in enumerate(self.topics)]

    def test_weak_area_lists_and_analytics_hide_previous_class_labels(self):
        self.make_weak_areas()
        self.make_dashboard_events()
        response = self.request(views.weak_areas)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([a["label"] for a in response.data["weakest"]], ["Topic 0"])
        self.assertEqual(response.data["strongest"], [])
        report = analytics.topic_performance(self.users[0])
        self.assertEqual(report["tracked_nodes"], 1)
        self.assertEqual(report["weakest"][0]["label"], "Topic 0")

    def test_weak_areas_reject_a_malformed_node_with_foreign_ancestor(self):
        WeakArea.objects.create(user=self.users[0], scope=WeakArea.Scope.TOPIC,
            topic=self.topics[0], subject=self.subjects[1], label="Mixed class", attempted=10)
        LearningEvent.objects.create(user=self.users[0], activity=ActivityType.QUESTION_ANSWERED,
            topic=self.topics[0], subject=self.subjects[1], total_count=10, correct_count=1)
        response = self.request(views.weak_areas)
        self.assertEqual(response.data["weakest"], [])
        self.assertFalse(response.data["has_data"])

    @patch("learning.dashboard.credits.balance", return_value={"remaining": 10})
    def test_dashboard_counts_and_revision_suggestion_use_current_class(self, balance):
        self.make_dashboard_events()
        for i, subject in enumerate(self.subjects):
            card = Flashcard.objects.create(user=self.users[0], subject=subject, front=f"Front {i}", back="Back")
            FlashcardProgress.objects.create(user=self.users[0], flashcard=card)
        context = dashboard.build_context(self.users[0])
        self.assertEqual(context["weakest_topic"], "Topic 0")
        self.assertEqual(context["questions_this_week"], 10)
        self.assertEqual(context["cards_due"], 1)

    @patch("learning.dashboard._generate", return_value=("Updated", "Current class message"))
    @patch("learning.dashboard.credits.balance", return_value={"remaining": 10})
    def test_dashboard_cache_is_invalidated_on_class_change(self, balance, generate):
        self.make_dashboard_events()
        context = dashboard.build_context(self.users[0])
        DashboardMessage.objects.create(user=self.users[0], headline="Old", body="Private topic 0",
            context=context, expires_at=timezone.now() + timedelta(hours=1))
        self.users[0].profile.class_group = self.groups[1]
        self.users[0].profile.save()
        response = dashboard.get_message(self.users[0])
        self.assertFalse(response["cached"])
        self.assertIn("Topic 1", response["body"])
        self.assertNotIn("Private topic 0", response["body"])
        generate.assert_not_called()

    @patch("learning.dashboard._generate", return_value=("Updated", "Current class message"))
    @patch("learning.dashboard.credits.balance", return_value={"remaining": 10})
    def test_dashboard_cache_rechecks_its_original_weak_area_source(self, balance, generate):
        sources = self.make_dashboard_events()
        context = dashboard.build_context(self.users[0])
        DashboardMessage.objects.create(user=self.users[0], headline="Old", body="Private topic 0",
            context=context, expires_at=timezone.now() + timedelta(hours=1))
        sources[0].topic = self.topics[1]
        sources[0].save()
        self.assertFalse(dashboard.get_message(self.users[0])["cached"])
        self.assertIsNone(DashboardMessage.objects.get(user=self.users[0]).context['weakest_topic'])
        generate.assert_not_called()

    @patch("learning.dashboard._generate")
    @patch("learning.dashboard.credits.balance", return_value={"remaining": 10})
    def test_dashboard_current_class_cache_does_not_repeat_provider_work(self, balance, generate):
        self.make_dashboard_events()
        context = dashboard.build_context(self.users[0])
        DashboardMessage.objects.create(user=self.users[0], headline="Own", body="Private topic 0",
            context=context, expires_at=timezone.now() + timedelta(hours=1))
        self.assertTrue(dashboard.get_message(self.users[0])["cached"])
        generate.assert_not_called()

    def make_dashboard_events(self):
        return [LearningEvent.objects.create(user=self.users[0], topic=topic,
            activity=ActivityType.QUESTION_ANSWERED, total_count=10, correct_count=2)
            for topic in self.topics]

    def battle(self, index=0, **kwargs):
        return BrainBattle.objects.create(host=self.users[index], class_group=self.groups[index],
            title=f"Private battle {index}", questions=[{"question": "Private question", "options": ["A", "B"],
            "correct_index": 0, "explanation": "Private explanation"}], **kwargs)

    def test_foreign_battle_codes_do_not_reveal_or_enrol(self):
        battle = self.battle(1)
        self.assertEqual(self.request(views.battle_lookup, code=battle.code).status_code, 404)
        self.assertEqual(self.request(views.battle_join, method="post", data={"code": battle.code}).status_code, 404)
        self.assertFalse(BattleParticipant.objects.filter(battle=battle, user=self.users[0]).exists())

    def test_prior_participant_cannot_read_answer_or_finish_foreign_battle(self):
        battle = self.battle(1)
        participant = BattleParticipant.objects.create(battle=battle, user=self.users[0])
        for handler, method, kwargs in (
            (views.battle_question, "get", {"index": 0}),
            (views.battle_leaderboard, "get", {}),
            (views.battle_answer, "post", {}),
            (views.battle_finish, "post", {}),
        ):
            with self.subTest(route=handler.__name__):
                self.assertEqual(self.request(handler, method=method, battle_id=battle.pk, **kwargs).status_code, 404)
        participant.refresh_from_db()
        self.assertEqual(participant.score, 0)
        self.assertIsNone(participant.finished_at)

    def test_same_class_battle_with_foreign_source_is_hidden(self):
        battle = self.battle(linked_subject=self.subjects[1])
        self.assertEqual(self.request(views.battle_lookup, code=battle.code).status_code, 404)

    def test_alternate_battle_route_cannot_bypass_class_or_source_access(self):
        own = self.battle(linked_subject=self.subjects[0])
        foreign = self.battle(1)
        malformed = self.battle(linked_subject=self.subjects[1])
        handler = BrainBattleViewSet.as_view({'get': 'retrieve'})
        self.assertEqual(self.request(handler, pk=own.pk).status_code, 200)
        for battle in (foreign, malformed):
            self.assertEqual(self.request(handler, pk=battle.pk).status_code, 404)

    def test_own_class_battle_can_be_joined_and_read(self):
        battle = self.battle(linked_subject=self.subjects[0])
        self.assertEqual(self.request(views.battle_join, method="post", data={"code": battle.code}).status_code, 201)
        unavailable = self.request(views.battle_question, battle_id=battle.pk, index=0)
        self.assertEqual(unavailable.status_code, 409)
        battle.questions = [
            *battle.questions,
            {"question": "Next question", "options": ["C", "D"], "correct_index": 1},
        ]
        battle.save(update_fields=["questions"])
        battle_service.advance_question(battle.host, battle.pk)
        response = self.request(views.battle_question, battle_id=battle.pk, index=0)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["question"], "Private question")
        self.assertNotIn("correct_index", response.data)
        self.assertNotIn("explanation", response.data)
        future = self.request(views.battle_question, battle_id=battle.pk, index=1)
        self.assertEqual(future.status_code, 409)

    def test_pending_class_head_and_inactive_class_cannot_look_up_battles(self):
        battle = self.battle()
        self.users[0].profile.class_role = ClassRole.CLASS_HEAD
        self.users[0].profile.save()
        self.assertEqual(self.request(views.battle_lookup, code=battle.code).status_code, 404)
        self.users[0].profile.class_role = ClassRole.STUDENT
        self.users[0].profile.save()
        self.groups[0].is_active = False
        self.groups[0].save()
        self.assertEqual(self.request(views.battle_lookup, code=battle.code).status_code, 404)
