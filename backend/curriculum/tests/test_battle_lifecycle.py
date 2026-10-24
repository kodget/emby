from datetime import timedelta
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from asgiref.sync import async_to_sync
from asgiref.testing import ApplicationCommunicator
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import ClassGroup, School
from curriculum.consumers import BattleConsumer
from curriculum.models import BattleAnswer, BattleParticipant, BrainBattle
from curriculum.serializers import BrainBattleSerializer
from learning import battles
from learning.models import ActivityType, LearningEvent
from learning import views as learning_views


QUESTIONS = [
    {
        "question": "First question?",
        "options": ["A", "B"],
        "correct_index": 0,
        "explanation": "A is correct.",
    },
    {
        "question": "Second question?",
        "options": ["C", "D"],
        "correct_index": 1,
    },
]


class BattleLifecycleTests(TestCase):
    def setUp(self):
        school = School.objects.create(name="Battle school")
        self.group = ClassGroup.objects.create(
            school=school, set_name="Year 1", code="812345"
        )
        self.host = User.objects.create_user("battle-host")
        self.player = User.objects.create_user("battle-player")
        self.late_player = User.objects.create_user("battle-late-player")
        self.player.profile.class_group = self.group
        self.player.profile.save(update_fields=["class_group"])
        self.late_player.profile.class_group = self.group
        self.late_player.profile.save(update_fields=["class_group"])
        self.battle = BrainBattle.objects.create(
            title="Battle lifecycle",
            host=self.host,
            class_group=self.group,
            questions=QUESTIONS,
            time_per_question=20,
        )

    def test_entry_closes_at_start_but_existing_players_can_rejoin(self):
        battle, participant, created = battles.join(self.player, self.battle.code)
        self.assertTrue(created)

        question = battles.advance_question(self.host, battle.pk)
        self.assertEqual(question["index"], 0)
        self.assertEqual(question["question"], QUESTIONS[0]["question"])

        rejoined_battle, rejoined, created_again = battles.join(
            self.player, self.battle.code
        )
        self.assertEqual(rejoined_battle.pk, battle.pk)
        self.assertEqual(rejoined.pk, participant.pk)
        self.assertFalse(created_again)
        with self.assertRaises(battles.BattleError) as error:
            battles.join(self.late_player, self.battle.code)
        self.assertEqual(error.exception.code, "started")

        for user, expected_status in (
            (self.player, 200),
            (self.late_player, 409),
        ):
            request = APIRequestFactory().post(
                "/api/learning/battles/join/",
                {"code": self.battle.code},
                format="json",
            )
            force_authenticate(request, user)
            response = learning_views.battle_join(request)
            self.assertEqual(response.status_code, expected_status)

    def test_server_time_scoring_is_persisted_and_replays_are_idempotent(self):
        battles.join(self.player, self.battle.code)
        battles.advance_question(self.host, self.battle.pk)
        now = timezone.now()
        BrainBattle.objects.filter(pk=self.battle.pk).update(
            current_question_started_at=now - timedelta(seconds=10)
        )
        self.battle.refresh_from_db()

        with patch("learning.battles.timezone.now", return_value=now):
            result = battles.submit_answer(self.player, self.battle, 0, 0)
            replay = battles.submit_answer(self.player, self.battle, 0, 0)

        self.assertEqual(result["points"], 500)
        self.assertFalse(result["replayed"])
        self.assertEqual(replay["points"], 500)
        self.assertTrue(replay["replayed"])
        participant = BattleParticipant.objects.get(battle=self.battle, user=self.player)
        self.assertEqual(participant.score, 500)
        self.assertEqual(participant.answered_count, 1)
        answer = BattleAnswer.objects.get(participant=participant, question_index=0)
        self.assertAlmostEqual(answer.seconds_taken, 10)

    def test_rest_answer_ignores_client_reported_elapsed_time(self):
        battles.join(self.player, self.battle.code)
        battles.advance_question(self.host, self.battle.pk)
        now = timezone.now()
        BrainBattle.objects.filter(pk=self.battle.pk).update(
            current_question_started_at=now - timedelta(seconds=10)
        )
        request = APIRequestFactory().post(
            "/api/learning/battles/1/answer/",
            {"index": 0, "selected_index": 0, "seconds_taken": 20000},
            format="json",
        )
        force_authenticate(request, self.player)

        with patch("learning.battles.timezone.now", return_value=now):
            response = learning_views.battle_answer(request, self.battle.pk)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["points"], 500)
        self.assertNotIn("correct_index", response.data)
        self.assertNotIn("explanation", response.data)
        self.assertAlmostEqual(
            BattleAnswer.objects.get(
                participant__battle=self.battle, participant__user=self.player
            ).seconds_taken,
            10,
        )

    def test_timeout_reveal_and_wrong_question_submissions_are_rejected(self):
        battles.join(self.player, self.battle.code)
        battles.advance_question(self.host, self.battle.pk)
        now = timezone.now()
        BrainBattle.objects.filter(pk=self.battle.pk).update(
            current_question_started_at=now - timedelta(seconds=21)
        )
        self.battle.refresh_from_db()

        with patch("learning.battles.timezone.now", return_value=now):
            with self.assertRaises(battles.BattleError) as error:
                battles.submit_answer(self.player, self.battle, 0, 0)
        self.assertEqual(error.exception.code, "time_expired")
        self.assertFalse(BattleAnswer.objects.exists())

        BrainBattle.objects.filter(pk=self.battle.pk).update(
            current_question_started_at=now
        )
        self.battle.refresh_from_db()
        battles.reveal_current_answer(self.host, self.battle.pk)
        with self.assertRaises(battles.BattleError) as error:
            battles.submit_answer(self.player, self.battle, 0, 0)
        self.assertEqual(error.exception.code, "closed")

    def test_questions_advance_in_order_and_completion_is_replay_safe(self):
        battles.join(self.player, self.battle.code)
        first = battles.advance_question(self.host, self.battle.pk)
        self.assertEqual(first["index"], 0)
        with self.assertRaises(battles.BattleError) as error:
            battles.advance_question(self.host, self.battle.pk)
        self.assertEqual(error.exception.code, "awaiting_reveal")

        battles.reveal_current_answer(self.host, self.battle.pk)
        second = battles.advance_question(self.host, self.battle.pk)
        self.assertEqual(second["index"], 1)
        self.assertEqual(second["question"], QUESTIONS[1]["question"])

        battles.reveal_current_answer(self.host, self.battle.pk)
        self.assertIsNone(battles.advance_question(self.host, self.battle.pk))
        self.battle.refresh_from_db()
        self.assertEqual(self.battle.status, "completed")
        battles.end_battle(self.host, self.battle.pk)

        first_finish = battles.finish_for_user(self.player, self.battle)
        second_finish = battles.finish_for_user(self.player, self.battle)
        self.assertEqual(first_finish, second_finish)
        self.assertEqual(
            LearningEvent.objects.filter(
                user=self.player,
                activity=ActivityType.BRAIN_BATTLE_COMPLETED,
                resource_id=str(self.battle.pk),
            ).count(),
            1,
        )

    def test_non_host_cannot_advance_or_end_battle(self):
        with self.assertRaises(battles.BattleError) as error:
            battles.advance_question(self.player, self.battle.pk)
        self.assertEqual(error.exception.code, "forbidden")
        with self.assertRaises(battles.BattleError) as error:
            battles.end_battle(self.player, self.battle.pk)
        self.assertEqual(error.exception.code, "forbidden")
        self.battle.refresh_from_db()
        self.assertEqual(self.battle.status, "scheduled")

    def test_host_end_persists_participant_completion(self):
        battles.join(self.player, self.battle.code)
        battles.advance_question(self.host, self.battle.pk)
        battles.end_battle(self.host, self.battle.pk)

        participant = BattleParticipant.objects.get(battle=self.battle, user=self.player)
        self.assertIsNotNone(participant.finished_at)
        self.assertEqual(
            LearningEvent.objects.filter(
                user=self.player,
                activity=ActivityType.BRAIN_BATTLE_COMPLETED,
                resource_id=str(self.battle.pk),
            ).count(),
            1,
        )

    def test_battle_detail_does_not_leak_questions_to_non_hosts(self):
        request = APIRequestFactory().get("/api/battles/")
        request.user = self.player
        player_data = BrainBattleSerializer(
            self.battle, context={"request": request}
        ).data
        self.assertEqual(player_data["questions"], [])
        self.assertEqual(player_data["question_count"], len(QUESTIONS))

        request.user = self.host
        host_data = BrainBattleSerializer(
            self.battle, context={"request": request}
        ).data
        self.assertEqual(host_data["questions"], QUESTIONS)


class BattleReconnectTests(TransactionTestCase):
    def setUp(self):
        school = School.objects.create(name="Reconnect school")
        self.group = ClassGroup.objects.create(
            school=school, set_name="Year 2", code="812346"
        )
        self.host = self.user("reconnect-host")
        self.player = self.user("reconnect-player")
        self.battle = BrainBattle.objects.create(
            title="Reconnect battle",
            host=self.host,
            class_group=self.group,
            status="scheduled",
            questions=QUESTIONS,
            time_per_question=20,
        )
        BattleParticipant.objects.create(battle=self.battle, user=self.player)

    def user(self, username):
        user = User.objects.create_user(username)
        user.profile.class_group = self.group
        user.profile.save(update_fields=["class_group"])
        return user

    async def connect(self, user):
        app = ApplicationCommunicator(BattleConsumer.as_asgi(), {
            "type": "websocket",
            "path": f"/ws/battle/{self.battle.pk}/",
            "url_route": {"kwargs": {"battle_id": str(self.battle.pk)}},
            "query_string": b"",
            "user": user,
        })
        await app.send_input({"type": "websocket.connect"})
        response = await app.receive_output(timeout=5)
        self.assertEqual(response["type"], "websocket.accept")
        state = json.loads((await app.receive_output(timeout=5))["text"])
        return app, state

    async def disconnect(self, app):
        await app.send_input({"type": "websocket.disconnect", "code": 1000})
        await app.wait(timeout=5)

    def test_host_reconnect_restores_active_question_and_server_timer(self):
        battles.advance_question(self.host, self.battle.pk)
        started_at = timezone.now() - timedelta(seconds=5)
        BrainBattle.objects.filter(pk=self.battle.pk).update(
            current_question_started_at=started_at
        )

        async def scenario():
            first, initial = await self.connect(self.host)
            state = initial["state"]
            self.assertEqual(state["status"], "active")
            self.assertEqual(state["current_question_index"], 0)
            self.assertEqual(state["current_question"]["question"], QUESTIONS[0]["question"])
            self.assertNotIn("correct_index", state["current_question"])
            self.assertGreater(state["remaining_ms"], 14000)
            self.assertLessEqual(state["remaining_ms"], 15000)
            await self.disconnect(first)

            status = await database_sync_to_async(
                lambda: BrainBattle.objects.values_list("status", flat=True).get(
                    pk=self.battle.pk
                )
            )()
            self.assertEqual(status, "active")
            second, resumed = await self.connect(self.host)
            self.assertEqual(resumed["state"]["current_question_index"], 0)
            self.assertNotIn("correct_index", resumed["state"]["current_question"])
            await self.disconnect(second)

        async_to_sync(scenario)()

    def test_player_reconnect_and_completed_replay_restore_persisted_results(self):
        battles.advance_question(self.host, self.battle.pk)

        async def scenario():
            first, initial = await self.connect(self.player)
            self.assertEqual(initial["state"]["status"], "active")
            await first.send_input({
                "type": "websocket.receive",
                "text": json.dumps({
                    "type": "submit_answer",
                    "question_index": 0,
                    "answer_index": 0,
                    "time_left_ms": 20000,
                }),
            })
            answer_result = json.loads((await first.receive_output(timeout=5))["text"])
            self.assertEqual(answer_result["type"], "answer_result")
            await self.disconnect(first)

            resumed, state_message = await self.connect(self.player)
            self.assertTrue(state_message["state"]["has_answered"])
            self.assertEqual(state_message["state"]["selected_answer"], 0)
            await self.disconnect(resumed)

            host = await database_sync_to_async(User.objects.get)(pk=self.host.pk)
            await database_sync_to_async(battles.end_battle)(host, self.battle.pk)
            replay, final_message = await self.connect(self.player)
            self.assertEqual(final_message["state"]["status"], "completed")
            self.assertEqual(final_message["participants"][0]["score"], answer_result["points_earned"])
            await self.disconnect(replay)

        async_to_sync(scenario)()


@skipUnless(connection.vendor == "postgresql", "PostgreSQL row locks required")
class BattleAnswerConcurrencyTests(TransactionTestCase):
    def setUp(self):
        school = School.objects.create(name="Concurrent battle school")
        group = ClassGroup.objects.create(
            school=school, set_name="Year 3", code="812347"
        )
        self.host = User.objects.create_user("concurrent-battle-host")
        self.player = User.objects.create_user("concurrent-battle-player")
        self.player.profile.class_group = group
        self.player.profile.save(update_fields=["class_group"])
        self.battle = BrainBattle.objects.create(
            title="Concurrent battle",
            host=self.host,
            class_group=group,
            questions=QUESTIONS[:1],
            time_per_question=20,
        )
        battles.join(self.player, self.battle.code)
        battles.advance_question(self.host, self.battle.pk)

    def test_simultaneous_answer_replays_only_one_persisted_score(self):
        barrier = Barrier(2)

        def submit_answer():
            close_old_connections()
            try:
                player = User.objects.get(pk=self.player.pk)
                battle = BrainBattle.objects.get(pk=self.battle.pk)
                barrier.wait(timeout=10)
                return battles.submit_answer(player, battle, 0, 0)
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: submit_answer(), range(2)))

        participant = BattleParticipant.objects.get(
            battle=self.battle, user=self.player
        )
        self.assertEqual(sum(not result["replayed"] for result in results), 1)
        self.assertEqual(results[0]["points"], results[1]["points"])
        self.assertGreater(participant.score, 0)
        self.assertLessEqual(participant.score, 1000)
        self.assertEqual(participant.score, results[0]["points"])
        self.assertEqual(participant.answered_count, 1)
        self.assertEqual(
            BattleAnswer.objects.filter(
                participant=participant, question_index=0
            ).count(),
            1,
        )
