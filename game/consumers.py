import asyncio
import json
import logging
import random
import time

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.db import transaction
from django.db.models import Count, Q

from game.models import Game, GamePlayer, PlayerAnswer
from quiz.models import Answer, Question

logger = logging.getLogger(__name__)


class GameConsumer(AsyncWebsocketConsumer):
    room_states = {}

    @classmethod
    def get_room_state(cls, room_code):
        return cls.room_states.setdefault(
            room_code,
            {
                "phase": "lobby",
                "player_channels": {},
                "teacher_channel": None,
                "loop_task": None,
                "host_disconnect_task": None,
                "current_question_context": {},
                "last_results": None,
            },
        )

    @classmethod
    def clear_room_task(cls, room_code, task_name, task):
        state = cls.room_states.get(room_code)
        if state and state.get(task_name) is task:
            state[task_name] = None

    @staticmethod
    def guest_session_key(room_code):
        return f"guest_player_{room_code}"

    async def connect(self):
        self.room_code = self.scope["url_route"]["kwargs"]["room_code"]
        self.game_group_name = f"game_{self.room_code}"
        self.user = self.scope["user"]
        self.session = self.scope.get("session")
        self.room_state = self.get_room_state(self.room_code)
        self.player = None
        self.player_id = None

        await self.channel_layer.group_add(self.game_group_name, self.channel_name)
        await self.accept()

        try:
            game, player = await self.get_or_create_player()
            if not game or not player:
                await self.send_json(
                    {
                        "type": "error",
                        "message": "Join the game first before opening the lobby or play screen.",
                    }
                )
                await self.close(code=4004)
                return

            self.player = player
            self.player_id = player.id
            self.room_state["player_channels"][self.player_id] = self.channel_name

            await self.send_lobby_state()

            player_data = await self.get_player_data_as_dict(player.id)
            await self.channel_layer.group_send(
                self.game_group_name,
                {
                    "type": "player_joined",
                    "player": player_data,
                    "sender_channel_name": self.channel_name,
                },
            )

            if game.is_completed:
                await self.send_game_over_message()
            elif game.is_active:
                await self.send_json({"type": "game_started"})

        except Exception as exc:
            logger.error(
                "Error in GameConsumer.connect for room %s: %s",
                self.room_code,
                exc,
                exc_info=True,
            )
            await self.close(code=4000)

    async def disconnect(self, close_code):
        try:
            if self.player_id and self.room_state["player_channels"].get(self.player_id) == self.channel_name:
                self.room_state["player_channels"].pop(self.player_id, None)

            if self.room_state.get("teacher_channel") == self.channel_name:
                self.room_state["teacher_channel"] = None

            game_state = await self.get_game_state()
            if game_state and game_state["is_active"] and not game_state["is_completed"]:
                game = await self.get_game()
                if game and self.player and self.player.is_host:
                    host_disconnect_task = self.room_state.get("host_disconnect_task")
                    if not host_disconnect_task or host_disconnect_task.done():
                        host_disconnect_task = asyncio.create_task(
                            self.handle_host_disconnect_after_grace_period()
                        )
                        self.room_state["host_disconnect_task"] = host_disconnect_task
                        host_disconnect_task.add_done_callback(
                            lambda task, room_code=self.room_code: self.clear_room_task(
                                room_code, "host_disconnect_task", task
                            )
                        )

                await self.channel_layer.group_discard(self.game_group_name, self.channel_name)
                return

            if self.player_id:
                player_left_data = await self.remove_player_from_game(self.player_id)
                if player_left_data:
                    await self.channel_layer.group_send(
                        self.game_group_name,
                        {
                            "type": "player_left",
                            "player": player_left_data,
                            "sender_channel_name": self.channel_name,
                        },
                    )

            await self.channel_layer.group_discard(self.game_group_name, self.channel_name)
        except Exception as exc:
            logger.error(
                "Error in GameConsumer.disconnect for room %s: %s",
                self.room_code,
                exc,
                exc_info=True,
            )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        message_type = data.get("type")

        if message_type == "start_game" and await self.is_user_host():
            await self.start_game()
        elif message_type == "player_ready":
            await self.player_ready()
        elif message_type == "submit_answer":
            await self.submit_answer(data)
        elif message_type == "next_question" and await self.is_user_host():
            await self.proceed_to_next_question()
        elif message_type == "end_game" and await self.is_user_host():
            await self.end_game()
        elif message_type == "kick_player" and await self.is_user_host():
            player_id = data.get("player_id")
            if player_id:
                await self.kick_player(player_id)

    async def send_json(self, payload):
        await self.send(text_data=json.dumps(payload))

    async def send_lobby_state(self):
        players = await self.get_all_players_in_game()
        await self.send_json({"type": "lobby_state", "players": players})

    async def start_game(self):
        game = await self.get_game()
        if not game or game.is_completed:
            return

        await self.mark_game_started()
        self.room_state["phase"] = "countdown"
        self.room_state["current_question_context"] = {}
        self.room_state["last_results"] = None

        await self.channel_layer.group_send(
            self.game_group_name,
            {"type": "broadcast_game_starting"},
        )

    async def player_ready(self):
        game = await self.get_game()
        if not game or not self.player_id:
            return

        self.room_state["player_channels"][self.player_id] = self.channel_name

        if await self.is_user_host():
            self.room_state["teacher_channel"] = self.channel_name
            host_disconnect_task = self.room_state.get("host_disconnect_task")
            if host_disconnect_task and not host_disconnect_task.done():
                host_disconnect_task.cancel()
                self.room_state["host_disconnect_task"] = None

        if game.is_completed:
            await self.send_game_over_message()
            return

        if not game.is_active:
            return

        if self.room_state["phase"] == "question":
            await self.send_current_question_to_self()
            return

        if self.room_state["phase"] == "results":
            await self.send_current_results_to_self()
            return

        if await self.is_user_host() and game.current_question_number == 0:
            await self.launch_question_round()

    async def submit_answer(self, data):
        if not self.player_id or await self.is_user_host():
            return

        if self.room_state.get("phase") != "question":
            return

        answer_id = data.get("answer_id")
        question_context = self.room_state.get("current_question_context", {})
        question_id = question_context.get("question_id")
        if not answer_id or not question_id:
            return

        time_taken = time.time() - question_context.get("start_time", 0)
        time_limit = question_context.get("time_limit", 10)

        is_correct, score_to_add = await self.calculate_score(answer_id, time_taken, time_limit)
        saved, total_score = await self.save_player_answer(
            self.player_id,
            question_id,
            answer_id,
            is_correct,
            score_to_add,
        )
        if not saved:
            return

        correct_answer = await self.get_correct_answer(question_id)
        await self.send_json(
            {
                "type": "immediate_feedback",
                "is_correct": is_correct,
                "correct_answer_id": correct_answer.id if correct_answer else None,
                "score_earned": score_to_add,
                "selected_answer_id": answer_id,
                "total_score": total_score,
            }
        )

    async def proceed_to_next_question(self):
        if self.room_state.get("phase") != "results":
            return
        await self.launch_question_round()

    async def launch_question_round(self):
        loop_task = self.room_state.get("loop_task")
        if loop_task and not loop_task.done():
            return

        loop_task = asyncio.create_task(self.run_question_round())
        self.room_state["loop_task"] = loop_task
        loop_task.add_done_callback(
            lambda task, room_code=self.room_code: self.clear_room_task(room_code, "loop_task", task)
        )

    async def run_question_round(self):
        try:
            question_data = await self.get_next_question_data()
            if not question_data:
                await self.end_game()
                return

            self.room_state["phase"] = "question"
            self.room_state["last_results"] = None
            self.room_state["current_question_context"] = {
                "question_id": question_data["question_id"],
                "question_text": question_data["question_text"],
                "answers": question_data["answers"],
                "time_limit": question_data["time_limit"],
                "start_time": time.time(),
                "current_question": question_data["current_question"],
                "total_questions": question_data["total_questions"],
            }

            await self.channel_layer.group_send(
                self.game_group_name,
                {"type": "show_question_event", "question_data": question_data},
            )

            await asyncio.sleep(question_data["time_limit"])
            await self.finish_question_round()
        except asyncio.CancelledError:
            return

    async def finish_question_round(self):
        question_context = self.room_state.get("current_question_context", {})
        question_id = question_context.get("question_id")
        if not question_id:
            return

        feedback_data = await self.get_feedback_data(question_id)
        teacher_player_id = await self.get_teacher_player_id()
        results_payload = {
            "correct_answer_id": feedback_data["correct_answer_id"],
            "player_results": feedback_data["player_results"],
            "current_question": question_context.get("current_question", 0),
            "total_questions": question_context.get("total_questions", 0),
        }

        self.room_state["phase"] = "results"
        self.room_state["last_results"] = results_payload

        for player_id, channel_name in list(self.room_state["player_channels"].items()):
            if teacher_player_id and player_id == teacher_player_id:
                continue

            player_result = next(
                (item for item in feedback_data["player_results"] if item["id"] == player_id),
                {
                    "id": player_id,
                    "username": "Unknown",
                    "score": 0,
                    "is_correct": False,
                    "score_earned": 0,
                    "answered": False,
                    "selected_answer_id": None,
                },
            )

            await self.channel_layer.send(
                channel_name,
                {
                    "type": "send_feedback_to_client",
                    "correct_answer_id": feedback_data["correct_answer_id"],
                    "player_result": player_result,
                    "player_results": feedback_data["player_results"],
                },
            )

        teacher_channel = self.room_state.get("teacher_channel")
        if teacher_channel:
            await self.channel_layer.send(
                teacher_channel,
                {
                    "type": "send_teacher_leaderboard",
                    "player_results": feedback_data["player_results"],
                    "current_question": question_context.get("current_question", 0),
                    "total_questions": question_context.get("total_questions", 0),
                },
            )

    async def end_game(self):
        self.cancel_round_loop()
        await self.set_game_completed()
        await self.process_game_rewards()
        self.room_state["phase"] = "completed"
        self.room_state["current_question_context"] = {}
        self.room_state["last_results"] = None
        self.room_state["host_disconnect_task"] = None

        scores = await self.get_final_scores()
        await self.channel_layer.group_send(
            self.game_group_name,
            {"type": "game_over_event", "scores": scores},
        )

    async def kick_player(self, player_id):
        try:
            target_player_id = int(player_id)
        except (TypeError, ValueError):
            return

        kicked_player = await self.remove_player_by_id(target_player_id)
        if not kicked_player:
            return

        target_channel = self.room_state["player_channels"].pop(target_player_id, None)
        if target_channel and target_channel != self.channel_name:
            await self.channel_layer.send(
                target_channel,
                {
                    "type": "kicked_from_game",
                    "message": "Teacher sizni o'yindan chiqardi.",
                },
            )

        await self.channel_layer.group_send(
            self.game_group_name,
            {
                "type": "player_left",
                "player": kicked_player,
            },
        )

    async def send_current_question_to_self(self):
        payload = await self.get_current_question_for_resend()
        if payload:
            await self.send_json(payload)

    async def send_current_results_to_self(self):
        results = self.room_state.get("last_results")
        if not results:
            return

        if await self.is_user_host():
            await self.send_json(
                {
                    "type": "teacher_leaderboard",
                    "player_results": results["player_results"],
                    "current_question": results["current_question"],
                    "total_questions": results["total_questions"],
                }
            )
            return

        player_result = next(
            (item for item in results["player_results"] if item["id"] == self.player_id),
            {
                "id": self.player_id,
                "username": self.player.name if self.player else "Guest",
                "score": 0,
                "is_correct": False,
                "score_earned": 0,
                "answered": False,
                "selected_answer_id": None,
            },
        )
        await self.send_json(
            {
                "type": "show_feedback",
                "correct_answer_id": results["correct_answer_id"],
                "player_result": player_result,
                "player_results": results["player_results"],
            }
        )

    async def send_game_over_message(self):
        scores = await self.get_final_scores()
        await self.send_json({"type": "game_over", "scores": scores})

    async def handle_host_disconnect_after_grace_period(self):
        try:
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            return

        if not self.room_state.get("teacher_channel"):
            await self.handle_host_disconnect()

    async def handle_host_disconnect(self):
        try:
            self.cancel_round_loop()
            await self.set_game_completed()
            await self.process_game_rewards()
            self.room_state["phase"] = "completed"
            self.room_state["current_question_context"] = {}
            self.room_state["last_results"] = None

            scores = await self.get_final_scores()
            await self.channel_layer.group_send(
                self.game_group_name,
                {
                    "type": "host_disconnected",
                    "message": "The teacher left the game. The session has ended.",
                    "scores": scores,
                },
            )
            await self.channel_layer.group_send(
                self.game_group_name,
                {"type": "game_over_event", "scores": scores},
            )
        except Exception as exc:
            logger.error(
                "Error handling host disconnect for room %s: %s",
                self.room_code,
                exc,
                exc_info=True,
            )

    async def broadcast_game_starting(self, event):
        await self.send_json({"type": "game_starting"})

    async def player_joined(self, event):
        if self.channel_name == event.get("sender_channel_name"):
            return
        await self.send_json({"type": "player_joined", "player": event["player"]})

    async def player_left(self, event):
        if self.channel_name == event.get("sender_channel_name"):
            return
        await self.send_json({"type": "player_left", "player": event["player"]})

    async def show_question_event(self, event):
        await self.send_json(
            {
                "type": "show_question",
                "question_id": event["question_data"]["question_id"],
                "question_text": event["question_data"]["question_text"],
                "answers": event["question_data"]["answers"],
                "time_limit": event["question_data"]["time_limit"],
                "current_question": event["question_data"]["current_question"],
                "total_questions": event["question_data"]["total_questions"],
            }
        )

    async def send_feedback_to_client(self, event):
        await self.send_json(
            {
                "type": "show_feedback",
                "correct_answer_id": event["correct_answer_id"],
                "player_result": event["player_result"],
                "player_results": event["player_results"],
            }
        )

    async def send_teacher_leaderboard(self, event):
        await self.send_json(
            {
                "type": "teacher_leaderboard",
                "player_results": event["player_results"],
                "current_question": event["current_question"],
                "total_questions": event["total_questions"],
            }
        )

    async def game_over_event(self, event):
        await self.send_json({"type": "game_over", "scores": event["scores"]})

    async def host_disconnected(self, event):
        await self.send_json(
            {
                "type": "host_disconnected",
                "message": event["message"],
                "scores": event.get("scores", []),
                "redirect": True,
            }
        )

    async def kicked_from_game(self, event):
        await self.send_json(
            {
                "type": "kicked_from_game",
                "message": event.get("message", "You were removed from the game."),
            }
        )
        await self.close(code=4003)

    def cancel_round_loop(self):
        loop_task = self.room_state.get("loop_task")
        current_task = asyncio.current_task()
        if loop_task and not loop_task.done() and loop_task is not current_task:
            loop_task.cancel()
        self.room_state["loop_task"] = None

    @database_sync_to_async
    def get_game(self):
        return Game.objects.select_related("quiz", "host").filter(code=self.room_code).first()

    @database_sync_to_async
    def get_game_state(self):
        game = Game.objects.filter(code=self.room_code).first()
        if not game:
            return None
        return {
            "is_active": game.is_active,
            "is_completed": game.is_completed,
            "current_question_number": game.current_question_number,
        }

    @database_sync_to_async
    def process_game_rewards(self):
        from accounts.views import award_game_points

        with transaction.atomic():
            game = Game.objects.select_for_update().select_related("quiz").filter(code=self.room_code).first()
            if not game or game.rewards_processed:
                return

            total_questions = game.quiz.questions.count()
            student_players = GamePlayer.objects.filter(
                game=game,
                user__profile__role='student',
            ).select_related("user", "user__profile").annotate(
                correct_answers=Count("answers", filter=Q(answers__is_correct=True))
            )

            for player in student_players:
                award_game_points(player.user, player.correct_answers, total_questions)

            game.rewards_processed = True
            game.save(update_fields=["rewards_processed"])

    @database_sync_to_async
    def mark_game_started(self):
        game = Game.objects.get(code=self.room_code)
        game.is_active = True
        game.is_completed = False
        game.current_question_number = 0
        game.current_question = None
        game.save(
            update_fields=[
                "is_active",
                "is_completed",
                "current_question_number",
                "current_question",
            ]
        )

    @database_sync_to_async
    def set_game_completed(self):
        Game.objects.filter(code=self.room_code).update(is_completed=True, is_active=False)

    @database_sync_to_async
    def get_or_create_player(self):
        game = Game.objects.filter(code=self.room_code).first()
        if not game:
            return None, None

        if self.user.is_authenticated:
            profile = getattr(self.user, "profile", None)
            if profile and profile.is_teacher() and self.user.id != game.host_id:
                return game, None

            player, _ = GamePlayer.objects.get_or_create(
                game=game,
                user=self.user,
                defaults={"display_name": self.user.username},
            )
            if not player.display_name.strip():
                player.display_name = self.user.username
                player.save(update_fields=["display_name"])
        else:
            player_id = None
            if self.session is not None:
                player_id = self.session.get(self.guest_session_key(self.room_code))
            if not player_id:
                return game, None

            player = (
                GamePlayer.objects.filter(
                    game=game,
                    id=player_id,
                    user__isnull=True,
                )
                .first()
            )
            if not player:
                return game, None

        player = GamePlayer.objects.select_related(
            "user",
            "user__profile",
            "user__profile__selected_frame",
            "game__host",
        ).get(id=player.id)
        return game, player

    @database_sync_to_async
    def remove_player_from_game(self, player_id):
        player = (
            GamePlayer.objects.select_related("game", "user")
            .filter(game__code=self.room_code, id=player_id)
            .first()
        )
        if not player:
            return None
        payload = {
            "id": player.id,
            "username": player.name,
            "was_host": player.is_host,
        }
        player.delete()
        return payload

    @database_sync_to_async
    def remove_player_by_id(self, player_id):
        player = (
            GamePlayer.objects.select_related("game", "user")
            .filter(game__code=self.room_code, id=player_id)
            .first()
        )
        if not player or player.is_host:
            return None

        payload = {
            "id": player.id,
            "username": player.name,
            "was_host": False,
        }
        player.delete()
        return payload

    @database_sync_to_async
    def is_user_host(self):
        game = Game.objects.filter(code=self.room_code).first()
        return bool(game and self.user.is_authenticated and game.host_id == self.user.id)

    @database_sync_to_async
    def get_host_id(self):
        game = Game.objects.filter(code=self.room_code).first()
        return game.host_id if game else None

    @database_sync_to_async
    def get_teacher_player_id(self):
        game = Game.objects.filter(code=self.room_code).first()
        if not game:
            return None
        player = GamePlayer.objects.filter(game=game, user_id=game.host_id).first()
        return player.id if player else None

    @database_sync_to_async
    def get_next_question_data(self):
        game = Game.objects.select_related("quiz").filter(code=self.room_code).first()
        if not game:
            return None

        questions = list(Question.objects.filter(quiz=game.quiz).order_by("order"))
        next_number = game.current_question_number + 1
        if next_number > len(questions):
            return None

        question = questions[next_number - 1]
        answers = list(question.answers.all())
        if not answers:
            return None

        random.shuffle(answers)

        game.current_question_number = next_number
        game.current_question = question
        game.save(update_fields=["current_question_number", "current_question"])

        return {
            "question_id": question.id,
            "question_text": question.text,
            "answers": [{"id": answer.id, "text": answer.text} for answer in answers],
            "time_limit": question.time_limit,
            "current_question": next_number,
            "total_questions": len(questions),
        }

    async def get_current_question_for_resend(self):
        context = self.room_state.get("current_question_context", {})
        if not context:
            return None

        elapsed = max(0, int(time.time() - context["start_time"]))
        remaining = max(1, context["time_limit"] - elapsed)
        return {
            "type": "show_question",
            "question_id": context["question_id"],
            "question_text": context["question_text"],
            "answers": context["answers"],
            "time_limit": remaining,
            "current_question": context["current_question"],
            "total_questions": context["total_questions"],
        }

    @database_sync_to_async
    def save_player_answer(self, player_id, question_id, answer_id, is_correct, score_earned):
        with transaction.atomic():
            player = GamePlayer.objects.select_for_update().filter(id=player_id).first()
            if not player:
                return False, 0

            existing = PlayerAnswer.objects.filter(player=player, question_id=question_id).first()
            if existing:
                return False, player.score

            answer = Answer.objects.filter(id=answer_id, question_id=question_id).first()
            if not answer:
                return False, player.score

            player.score += score_earned
            player.save(update_fields=["score"])

            PlayerAnswer.objects.create(
                player=player,
                question_id=question_id,
                answer=answer,
                is_correct=is_correct,
                score_earned=score_earned,
            )
            return True, player.score

    @database_sync_to_async
    def get_feedback_data(self, question_id):
        game = Game.objects.select_related("host").filter(code=self.room_code).first()
        question = Question.objects.filter(id=question_id).first()
        if not game or not question:
            return {"correct_answer_id": None, "player_results": []}

        correct_answer = question.answers.filter(is_correct=True).first()
        correct_answer_id = correct_answer.id if correct_answer else None

        answers = PlayerAnswer.objects.filter(
            question_id=question_id,
            player__game=game,
        ).select_related("player__user", "answer")
        answers_by_player = {item.player_id: item for item in answers}

        players = (
            GamePlayer.objects.filter(game=game)
            .exclude(user_id=game.host_id)
            .select_related("user")
            .order_by("-score", "joined_at")
        )

        player_results = []
        for player in players:
            player_answer = answers_by_player.get(player.id)
            player_results.append(
                {
                    "id": player.id,
                    "username": player.name,
                    "score": player.score,
                    "is_correct": player_answer.is_correct if player_answer else False,
                    "score_earned": player_answer.score_earned if player_answer else 0,
                    "answered": bool(player_answer),
                    "selected_answer_id": player_answer.answer_id if player_answer else None,
                }
            )

        return {
            "correct_answer_id": correct_answer_id,
            "player_results": player_results,
        }

    @database_sync_to_async
    def get_final_scores(self):
        game = Game.objects.select_related("host").filter(code=self.room_code).first()
        if not game:
            return []

        players = (
            GamePlayer.objects.filter(game=game)
            .exclude(user_id=game.host_id)
            .select_related("user")
            .annotate(correct_answers=Count("answers", filter=Q(answers__is_correct=True)))
            .order_by("-score", "joined_at")
        )
        return [
            {
                "id": player.id,
                "username": player.name,
                "score": player.score,
                "correct_answers": player.correct_answers,
                "coins_earned": min(player.correct_answers, 10) if player.correct_answers > 0 else 0,
            }
            for player in players
        ]

    @database_sync_to_async
    def calculate_score(self, answer_id, time_taken, time_limit):
        answer = Answer.objects.filter(id=answer_id).first()
        if not answer or not answer.is_correct:
            return False, 0

        if time_limit <= 0:
            return True, 500

        time_ratio = max(0.0, min(1.0, 1 - (time_taken / time_limit)))
        score = 500 + int(500 * time_ratio)
        return True, score

    @database_sync_to_async
    def get_correct_answer(self, question_id):
        return Answer.objects.filter(question_id=question_id, is_correct=True).first()

    @database_sync_to_async
    def get_all_players_in_game(self):
        game = Game.objects.select_related("host").filter(code=self.room_code).first()
        if not game:
            return []

        players = (
            GamePlayer.objects.filter(game=game)
            .select_related("user", "user__profile", "user__profile__selected_frame")
            .order_by("joined_at")
        )

        payload = []
        for player in players:
            selected_frame = {"css_class": player.selected_frame_css_class} if player.selected_frame_css_class else None
            payload.append(
                {
                    "id": player.id,
                    "username": player.name,
                    "score": player.score,
                    "is_host": player.is_host,
                    "user": {
                        "username": player.name,
                        "profile": {
                            "avatar": {"url": player.avatar_url} if player.avatar_url else None,
                            "selected_frame": selected_frame,
                            "total_points": player.profile.total_points if player.profile else 0,
                            "games_played": player.profile.games_played if player.profile else 0,
                            "level": player.level,
                        },
                    },
                }
            )
        return payload

    @database_sync_to_async
    def get_player_data_as_dict(self, player_id):
        player = (
            GamePlayer.objects.select_related(
                "user",
                "user__profile",
                "user__profile__selected_frame",
                "game__host",
            )
            .filter(id=player_id)
            .first()
        )
        if not player:
            return None

        selected_frame = {"css_class": player.selected_frame_css_class} if player.selected_frame_css_class else None
        return {
            "id": player.id,
            "username": player.name,
            "score": player.score,
            "is_host": player.is_host,
            "user": {
                "username": player.name,
                "profile": {
                    "avatar": {"url": player.avatar_url} if player.avatar_url else None,
                    "selected_frame": selected_frame,
                    "total_points": player.profile.total_points if player.profile else 0,
                    "games_played": player.profile.games_played if player.profile else 0,
                    "level": player.level,
                },
            },
        }
