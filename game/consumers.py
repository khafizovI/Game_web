import json
import asyncio
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from game.models import Game, GamePlayer, Question, Answer, PlayerAnswer
from accounts.models import Profile


logger = logging.getLogger(__name__)


class GameConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.question_timer_task = None
        self.is_showing_results = False
        try:
            self.game_code = self.scope['url_route']['kwargs']['game_code']
            self.game_group_name = f'game_{self.game_code}'
            self.user = self.scope['user']

            await self.channel_layer.group_add(
                self.game_group_name,
                self.channel_name
            )

            await self.accept()

            if not self.user.is_authenticated:
                await self.close()
                return

            # 1. Add the current user to the game.
            new_player_data = await self.add_player_to_game(self.user)

            # 2. Get the full, updated list of players.
            all_players = await self.get_all_players_in_game()

            # 3. Send the complete state to the user who just connected.
            await self.send(text_data=json.dumps({
                'type': 'lobby_state',
                'players': all_players
            }))

            # 4. Notify everyone else that a new player has joined.
            await self.channel_layer.group_send(
                self.game_group_name,
                {
                    'type': 'player_joined',
                    'player': new_player_data,
                    'sender_channel_name': self.channel_name
                }
            )

            game_state = await self.get_game_state()
            if game_state and game_state['is_active'] and not game_state['is_completed']:
                await asyncio.sleep(0.1)  # Add a small delay to prevent race conditions
                current_question = await self.get_current_question()
                if current_question:
                    await self.send(text_data=json.dumps({
                        'type': 'game_started',
                        'question_text': current_question['question_text'],
                        'answers': current_question['answers'],
                        'time_limit': current_question['time_limit'],
                        'current_question': current_question['current_question'],
                        'total_questions': current_question['total_questions']
                    }))
        except Exception as e:
            logger.error(f"Error in GameConsumer connect for game {self.game_code}: {e}", exc_info=True)
            await self.close(code=4000) # Use a custom code to indicate an application error

    async def disconnect(self, close_code):
        # TODO: Handle player leaving
        await self.channel_layer.group_discard(
            self.game_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type')

        if message_type == 'start_game' and await self.is_user_host():
            await self.start_game()
        elif message_type == 'submit_answer':
            await self.submit_answer(data)

    async def start_game(self):
        # Broadcast that the game is about to start
        await self.channel_layer.group_send(self.game_group_name, {
            'type': 'broadcast_game_starting'
        })

        # Wait for the countdown to finish on the client side
        await asyncio.sleep(4)  # 3s for countdown, 1s buffer

        await self.set_game_active(True)
        await self.send_next_question()

    async def submit_answer(self, data):
        player = await self.get_player()
        answer_id = data.get('answer_id')
        question_id = data.get('question_id')

        if not player or not answer_id or not question_id:
            return

        answer, question = await self.save_player_answer(player, answer_id, question_id)

        # Check if all players have answered
        game = await self.get_game()
        all_players_count = await self.get_game_players_count(game)
        answered_players_count = await self.get_player_answers_count_for_question(question)

        if answered_players_count >= all_players_count:
            if self.question_timer_task:
                self.question_timer_task.cancel()
            await self.show_results(question)

    async def send_next_question(self):
        self.is_showing_results = False
        game = await self.get_game()
        
        question_data = await self.get_current_question()
        if not question_data:
            await self.end_game()
            return

        # Broadcast the new question to everyone
        await self.channel_layer.group_send(self.game_group_name, {
            'type': 'broadcast_question',
            'question_data': question_data
        })

        # Start server-side timer
        if self.question_timer_task:
            self.question_timer_task.cancel()
        self.question_timer_task = asyncio.create_task(self.question_timeout(question_data['time_limit'], question_data))

    async def question_timeout(self, delay, question_data):
        try:
            await asyncio.sleep(delay)
            # Pass the question data to show_results
            await self.show_results(question_data)
        except asyncio.CancelledError:
            # Timer was cancelled because all players answered
            pass

    async def show_results(self, question):
        if self.is_showing_results:
            return
        self.is_showing_results = True

        is_timeout = isinstance(question, dict)
        db_question = None

        if is_timeout:
            # Timeout: 'question' is a dict of data. We need the model instance.
            db_question = await self.get_question_by_id(question.get('id'))
        else:
            # All answered: 'question' is already a Question model instance.
            db_question = question

        if not db_question:
            logger.error(f"[Game {self.game_code}] Could not find question in show_results.")
            # Attempt to recover by moving to the next question
            await self.increment_question_number()
            await self.send_next_question()
            return

        if is_timeout:
            await self.record_unanswered_as_incorrect(db_question)

        scores = await self.get_scores()
        answer_stats = await self.get_answer_stats(db_question)

        await self.channel_layer.group_send(
            self.game_group_name,
            {
                'type': 'broadcast_results',
                'results': {
                    'scores': scores,
                    'answer_stats': answer_stats,
                    'correct_answer_id': answer_stats['correct_answer_id']
                }
            }
        )

        # Wait a few seconds before showing the next question
        await asyncio.sleep(5)

        # Proceed to the next question or end the game
        await self.increment_question_number()
        await self.send_next_question()

    async def end_game(self):
        await self.set_game_completed()
        final_scores = await self.get_final_scores()
        await self.channel_layer.group_send(self.game_group_name, {
            'type': 'broadcast_game_end',
            'scores': final_scores
        })

    # --- Broadcasting Helpers ---
    async def broadcast_game_starting(self, event):
        await self.send(text_data=json.dumps({
            'type': 'game_starting'
        }))

    async def broadcast_question(self, event):
        await self.send(text_data=json.dumps({
            'type': 'next_question_sent',
            **event['question_data']
        }))

    async def broadcast_results(self, event):
        await self.send(text_data=json.dumps({
            'type': 'question_results',
            **event['results']
        }))

    async def broadcast_game_end(self, event):
        await self.send(text_data=json.dumps({
            'type': 'game_ended',
            'scores': event['scores']
        }))

    async def player_joined(self, event):
        # Only send to other clients
        if self.channel_name != event.get('sender_channel_name'):
            await self.send(text_data=json.dumps({
                'type': 'player_joined',
                'player': event['player']
            }))

    # --- Database Helpers (must be @database_sync_to_async) ---
    @database_sync_to_async
    def get_game(self):
        return Game.objects.select_related('quiz', 'host').get(code=self.game_code)

    @database_sync_to_async
    def get_player(self):
        try:
            return GamePlayer.objects.filter(game__code=self.game_code, user=self.user).first()
        except GamePlayer.DoesNotExist:
            return None

    @database_sync_to_async
    def set_game_active(self, status):
        Game.objects.filter(code=self.game_code).update(is_active=status)

    @database_sync_to_async
    def get_current_db_question(self):
        game = Game.objects.get(code=self.game_code)
        return game.quiz.questions.all().order_by('order').get(order=game.current_question_number)

    @database_sync_to_async
    def save_player_answer(self, player, answer_id, question_id):
        answer = Answer.objects.get(id=answer_id)
        question = Question.objects.get(id=question_id)
        points = 100 if answer.is_correct else 0
        player_answer, created = PlayerAnswer.objects.update_or_create(
            player=player, question=question,
            defaults={'answer': answer, 'points_awarded': points}
        )
        if not created:
            player.score -= player_answer.points_awarded # Adjust score if answer is changed
        player.score += points
        player.save()
        return answer, question

    @database_sync_to_async
    def get_game_players_count(self, game):
        return GamePlayer.objects.filter(game=game).count()

    @database_sync_to_async
    def get_player_answers_count_for_question(self, question):
        return PlayerAnswer.objects.filter(question=question).count()

    @database_sync_to_async
    def check_all_players_answered(self):
        game = Game.objects.get(code=self.game_code)
        question = game.quiz.questions.all().order_by('order')[game.current_question_number]
        player_count = game.players.count()
        answer_count = PlayerAnswer.objects.filter(question=question).count()
        return player_count == answer_count

    @database_sync_to_async
    def get_scores(self):
        game = Game.objects.get(code=self.game_code)
        players = GamePlayer.objects.filter(game=game).order_by('-score')
        return [{'username': p.user.username, 'score': p.score} for p in players]

    @database_sync_to_async
    def get_answer_stats(self, question):
        correct_answer_id = question.answers.get(is_correct=True).id
        answer_counts = {}
        for answer in question.answers.all():
            answer_counts[answer.id] = PlayerAnswer.objects.filter(question=question, answer=answer).count()
        return {
            'correct_answer_id': correct_answer_id,
            'answer_counts': answer_counts
        }

    @database_sync_to_async
    def increment_question_number(self):
        game = Game.objects.get(code=self.game_code)
        game.current_question_number += 1
        game.save()

    @database_sync_to_async
    def set_game_completed(self):
        Game.objects.filter(code=self.game_code).update(is_completed=True)

    @database_sync_to_async
    def get_final_scores(self):
        players = GamePlayer.objects.filter(game__code=self.game_code).order_by('-score')
        return [{'username': p.user.username, 'score': p.score} for p in players]

    @database_sync_to_async
    def get_current_question(self):
        game = Game.objects.get(code=self.game_code)
        question_count = game.quiz.questions.count()

        if game.current_question_number >= question_count:
            return None

        question = game.quiz.questions.all().order_by('order')[game.current_question_number]
        answers = list(question.answers.all().values('id', 'text'))

        return {
            'id': question.id,  # Include the question ID
            'question_text': question.text,
            'answers': answers,
            'time_limit': question.time_limit,
            'current_question': game.current_question_number + 1,
            'total_questions': question_count
        }

    @database_sync_to_async
    def is_user_host(self):
        game = Game.objects.get(code=self.game_code)
        return game.host.id == self.user.id

    @database_sync_to_async
    def add_player_to_game(self, user):
        game = Game.objects.get(code=self.game_code)
        player, created = GamePlayer.objects.get_or_create(game=game, user=user)

        # Temporarily disabled for debugging
        avatar_url = None

        return {
            'username': user.username,
            'score': player.score,
            'avatar_url': avatar_url
        }

    @database_sync_to_async
    def get_all_players_in_game(self):
        game = Game.objects.get(code=self.game_code)
        players = GamePlayer.objects.filter(game=game).select_related('user')
        player_list = []
        for p in players:
            # Temporarily disabled for debugging
            avatar_url = None

            player_list.append({
                'username': p.user.username,
                'score': p.score,
                'avatar_url': avatar_url
            })
        return player_list

    @database_sync_to_async
    def get_game_state(self):
        """
        Fetches the current state of the game.
        """
        try:
            game = Game.objects.get(code=self.game_code)
            return {
                'is_active': game.is_active,
                'is_completed': game.is_completed,
                'current_question': game.current_question_number
            }
        except Game.DoesNotExist:
            return None

    @database_sync_to_async
    def get_db_question_by_text(self, question_text):
        try:
            return Question.objects.get(text=question_text, quiz__games__code=self.game_code)
        except Question.DoesNotExist:
            return None

    @database_sync_to_async
    def get_question_by_id(self, question_id):
        if not question_id:
            return None
        try:
            return Question.objects.get(id=question_id)
        except Question.DoesNotExist:
            return None

    @database_sync_to_async
    def record_unanswered_as_incorrect(self, question):
        game = Game.objects.get(code=self.game_code)
        players_in_game = GamePlayer.objects.filter(game=game)
        players_who_answered = PlayerAnswer.objects.filter(
            question=question,
            player__in=players_in_game
        ).values_list('player_id', flat=True)

        unanswered_players = players_in_game.exclude(id__in=players_who_answered)

        for player in unanswered_players:
            PlayerAnswer.objects.create(
                player=player,
                question=question,
                answer=None,  # No answer was chosen
                is_correct=False, # Explicitly mark as incorrect
                points_awarded=0
            )