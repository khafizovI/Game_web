import json
import asyncio
import logging
import random
import time

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from game.models import Game, GamePlayer, Question, Answer, PlayerAnswer
from accounts.models import Profile
from quiz.models import Quiz, Question, Answer
import random

logger = logging.getLogger(__name__)

class GameConsumer(AsyncWebsocketConsumer):
    player_channels = {}
    current_question_context = {}

    async def connect(self):
        self.room_code = self.scope['url_route']['kwargs']['room_code']
        self.game_group_name = f'game_{self.room_code}'
        self.user = self.scope['user']

        try:
            # Add player to the group first to ensure they receive all broadcasts.
            await self.channel_layer.group_add(
                self.game_group_name,
                self.channel_name
            )
            await self.accept()

            # Handle unauthenticated users as guests
            if not self.user.is_authenticated:
                all_players = await self.get_all_players_in_game()
                await self.send(text_data=json.dumps({
                    'type': 'lobby_state',
                    'players': all_players,
                    'is_guest': True
                }))
                return

            # Add the user to the game and get updated player list.
            game, player = await self.get_or_create_player()
            if not player:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': "Could not identify player."
                }))
                await self.close()
                return

            self.player = player

            # Prepare player data in a sync-safe way before sending
            player_data = await self.get_player_data_as_dict(player)

            # Send current lobby state to the new player
            all_players = await self.get_all_players_in_game()
            await self.send(text_data=json.dumps({
                'type': 'lobby_state',
                'players': all_players
            }))

            # Notify other players that a new player has joined
            await self.channel_layer.group_send(
                self.game_group_name,
                {
                    'type': 'player_joined',
                    'player': player_data,
                    'sender_channel_name': self.channel_name
                }
            )

            # If game is active, send the current question
            game = await self.get_game()
            if game.is_active and not game.is_completed:
                current_question = await self.get_current_question(re_send=True)
                if current_question:
                    await self.send(text_data=json.dumps({
                        'type': 'show_question',
                        'question_id': current_question['id'],
                        'question_text': current_question['question_text'],
                        'answers': current_question['answers'],
                        'time_limit': current_question['time_limit'],
                        'current_question': current_question['current_question'],
                        'total_questions': current_question['total_questions']
                    }))

        except Exception as e:
            logger.error(f"Error in GameConsumer connect for game {self.room_code}: {e}", exc_info=True)
            await self.close(code=4000)

    async def disconnect(self, close_code):
        player_left_data = await self.remove_player_from_game(self.user)

        if player_left_data:
            # Notify the group that a player has left
            await self.channel_layer.group_send(
                self.game_group_name,
                {
                    'type': 'player_left',
                    'player': player_left_data,
                    'sender_channel_name': self.channel_name
                }
            )

            # If the host (teacher) disconnects, end the game and kick all students
            if player_left_data.get('was_host'):
                await self.handle_host_disconnect()

        await self.channel_layer.group_discard(
            self.game_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type')

        if message_type == 'start_game' and await self.is_user_host():
            await self.start_game()
        elif message_type == 'player_ready':
            await self.player_ready()
        elif message_type == 'submit_answer':
            await self.submit_answer(data)
        elif message_type == 'next_question' and await self.is_user_host():
            await self.proceed_to_next_question()

    async def start_game(self):
        # Set the game to active and broadcast the starting event.
        # The host's 'player_ready' message on the next screen will trigger the first question.
        await self.set_game_active(True)
        await self.channel_layer.group_send(self.game_group_name, {
            'type': 'broadcast_game_starting'
        })

    async def player_ready(self):
        """
        Handles a player connecting to the play screen.
        If the user is the host and the game is just beginning,
        this triggers the first question for everyone.
        """
        game = await self.get_game()
        # The host sending 'player_ready' for the first question kicks off the game.
        if game.is_active and self.user.id == game.host_id and game.current_question_number == 0:
            self.player_id = await self.get_player_id()
            if self.player_id not in self.player_channels:
                self.player_channels[self.player_id] = self.channel_name

            # If this is the first player to be ready, start the game loop
            if len(self.player_channels) == 1:
                asyncio.create_task(self.game_loop())

    async def submit_answer(self, data):
        """Handles answer submission from a player."""
        answer_id = data['answer_id']
        time_taken = time.time() - self.current_question_context.get('start_time', 0)
        time_limit = self.current_question_context.get('time_limit', 10)
        question_id = self.current_question_context.get('question_id')

        if not question_id:
            return # Ignore submission if no question is active

        is_correct, score_to_add = await self.calculate_score(answer_id, time_taken, time_limit)
        await self.save_player_answer(self.player, question_id, answer_id, is_correct, score_to_add)

        # Send immediate feedback to the student
        correct_answer = await self.get_correct_answer(question_id)
        await self.send(text_data=json.dumps({
            'type': 'immediate_feedback',
            'is_correct': is_correct,
            'correct_answer_id': correct_answer.id if correct_answer else None,
            'score_earned': score_to_add,
            'selected_answer_id': answer_id
        }))

    async def game_loop(self):
        """The main loop that controls the game flow."""
        while True:
            question_data = await self.get_current_question()
            if not question_data:
                await self.end_game()
                break

            # Store question context for scoring
            self.current_question_context = {
                'start_time': time.time(),
                'time_limit': question_data['time_limit'],
                'question_id': question_data['id']
            }

            # Send the question to all players
            await self.channel_layer.group_send(
                self.game_group_name,
                {
                    'type': 'show_question',
                    'question_data': question_data
                }
            )

            # Wait for the question's time limit
            await asyncio.sleep(question_data['time_limit'])

            # Get and send feedback to students, and leaderboard to teacher
            feedback_data = await self.get_feedback_data(self.current_question_context['question_id'])
            
            # Send feedback to students
            for player_id, channel_name in self.player_channels.items():
                player_result = next((p for p in feedback_data['player_results'] if p['id'] == player_id), None)
                
                if not player_result:
                    player_result = {
                        'id': player_id,
                        'username': 'Unknown',
                        'score': 0,
                        'is_correct': False,
                        'score_earned': 0,
                        'answered': False
                    }

                await self.channel_layer.send(
                    channel_name,
                    {
                        'type': 'send_feedback_to_client',
                        'correct_answer_id': feedback_data['correct_answer_id'],
                        'player_result': player_result,
                        'player_results': feedback_data['player_results']
                    }
                )
            
            # Send leaderboard to teacher
            teacher_channel = await self.get_teacher_channel()
            if teacher_channel:
                await self.channel_layer.send(teacher_channel, {
                    'type': 'send_teacher_leaderboard',
                    'player_results': feedback_data['player_results'],
                    'current_question': await self.get_current_question_number(),
                    'total_questions': await self.get_total_questions()
                })
            
            # Wait for teacher to click "Next" - the loop will continue when proceed_to_next_question is called
            return

    async def send_teacher_leaderboard(self, event):
        """Sends leaderboard data to the teacher."""
        await self.send(text_data=json.dumps({
            'type': 'teacher_leaderboard',
            'player_results': event['player_results'],
            'current_question': event['current_question'],
            'total_questions': event['total_questions']
        }))

    async def proceed_to_next_question(self):
        game = await self.get_game()
        if game.is_active and not game.is_completed:
            await self.increment_question_number()
            # Continue the game loop by calling it again
            await self.game_loop()

    async def end_game(self):
        game = await self.get_game()
        if game:
            game.is_completed = True
            await self.save_game(game)

            final_scores = await self.get_final_scores()
            await self.channel_layer.group_send(
                self.game_group_name,
                {
                    'type': 'game_over',
                    'scores': final_scores
                }
            )

    async def broadcast_game_starting(self, event):
        # This method is called on each consumer when the group receives a message with type 'broadcast_game_starting'
        await self.send(text_data=json.dumps({
            'type': 'game_starting'
        }))

    async def broadcast_question(self, event):
        question_data = event['question_data']
        await self.send(text_data=json.dumps({
            'type': 'show_question',
            'question_id': question_data['id'],
            'question_text': question_data['question_text'],
            'answers': question_data['answers'],
            'time_limit': question_data['time_limit'],
            'current_question': question_data['current_question'],
            'total_questions': question_data['total_questions'],
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

    async def player_left(self, event):
        if self.channel_name != event.get('sender_channel_name'):
            await self.send(text_data=json.dumps({
                'type': 'player_left',
                'player': event['player']
            }))

    async def send_feedback_to_client(self, event):
        """Sends feedback data to a specific client."""
        await self.send(text_data=json.dumps({
            'type': 'show_feedback',
            'correct_answer_id': event['correct_answer_id'],
            'player_result': event['player_result'],
            'player_results': event['player_results']
        }))

    async def game_over(self, event):
        """Sends the final game results to the client."""
        await self.send(text_data=json.dumps({
            'type': 'game_over',
            'scores': event['scores']
        }))

    async def show_question(self, event):
        """Sends question data to the client after being broadcast to the group."""
        question_data = event['question_data']
        await self.send(text_data=json.dumps({
            'type': 'show_question',
            'question_id': question_data['id'],
            'question_text': question_data['question_text'],
            'answers': question_data['answers'],
            'time_limit': question_data['time_limit'],
            'current_question': question_data['current_question'],
            'total_questions': question_data['total_questions'],
        }))

    async def handle_host_disconnect(self):
        """Handle teacher disconnection by ending the game and kicking all students."""
        try:
            # Mark the game as completed
            await self.set_game_completed()
            
            # Get final scores for the game summary
            final_scores = await self.get_final_scores()
            
            # Notify all remaining players that the game has ended due to host disconnect
            await self.channel_layer.group_send(
                self.game_group_name,
                {
                    'type': 'host_disconnected',
                    'message': 'The teacher has left the game. The test has been ended.',
                    'scores': final_scores
                }
            )
            
            # Send final game results to all players
            await self.channel_layer.group_send(
                self.game_group_name,
                {
                    'type': 'game_over',
                    'scores': final_scores,
                    'reason': 'host_disconnect'
                }
            )
            
        except Exception as e:
            logger.error(f"Error handling host disconnect for game {self.room_code}: {e}")

    async def host_disconnected(self, event):
        """Handle host disconnection event - notify client and redirect."""
        await self.send(text_data=json.dumps({
            'type': 'host_disconnected',
            'message': event['message'],
            'scores': event.get('scores', []),
            'redirect': True
        }))

    # --- Database Helpers (must be @database_sync_to_async) ---
    @database_sync_to_async
    def get_feedback_data(self, question_id):
        game = Game.objects.select_related('quiz').get(code=self.room_code)
        question = Question.objects.get(id=question_id)

        correct_answer_id = question.answers.get(is_correct=True).id
        player_answers = PlayerAnswer.objects.filter(question_id=question_id, player__game=game)

        player_results_data = []
        for p in game.players.all().order_by('-score'):
            player_answer = player_answers.filter(player=p).first()
            player_results_data.append({
                'id': p.id,
                'username': p.user.username,
                'score': p.score, # This is the new total score
                'is_correct': player_answer.is_correct if player_answer else False,
                'score_earned': player_answer.score_earned if player_answer else 0,
                'answered': True if player_answer else False
            })
        
        return {
            'correct_answer_id': correct_answer_id,
            'player_results': player_results_data
        }

    @database_sync_to_async
    def save_game(self, game):
        game.save()

    @database_sync_to_async
    def get_final_scores(self):
        game = Game.objects.get(code=self.room_code)
        return sorted(
            [{'username': p.user.username, 'score': p.score} for p in game.players.all()],
            key=lambda x: x['score'],
            reverse=True
        )

    @database_sync_to_async
    def get_game(self):
        try:
            return Game.objects.select_related('quiz', 'host').get(code=self.room_code)
        except Game.DoesNotExist:
            return None

    @database_sync_to_async
    def get_player(self):
        try:
            return GamePlayer.objects.filter(game__code=self.room_code, user=self.user).first()
        except GamePlayer.DoesNotExist:
            return None

    @database_sync_to_async
    def set_game_active(self, status):
        Game.objects.filter(code=self.room_code).update(is_active=status)

    @database_sync_to_async
    def get_current_db_question(self):
        game = Game.objects.get(code=self.room_code)
        return game.quiz.questions.all().order_by('order')[game.current_question_number - 1]

    @database_sync_to_async
    def save_player_answer(self, player, question_id, answer_id, is_correct, score_earned):
        player.score += score_earned
        player.save()

        answer = Answer.objects.get(id=answer_id)
        PlayerAnswer.objects.create(
            player=player,
            question_id=question_id,
            answer=answer,
            is_correct=is_correct,
            score_earned=score_earned
        )

    @database_sync_to_async
    def get_game_players_count(self, game):
        return GamePlayer.objects.filter(game=game).count()

    @database_sync_to_async
    def get_player_answers_count_for_question(self, question):
        return PlayerAnswer.objects.filter(question=question).count()

    @database_sync_to_async
    def check_all_players_answered(self):
        game = Game.objects.get(code=self.room_code)
        question = game.quiz.questions.all().order_by('order')[game.current_question_number - 1]
        player_count = game.players.count()
        answer_count = PlayerAnswer.objects.filter(question=question).count()
        return player_count == answer_count

    @database_sync_to_async
    def get_scores(self):
        game = Game.objects.get(code=self.room_code)
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
        game = Game.objects.get(code=self.room_code)
        game.current_question_number += 1
        game.save()
        return game

    @database_sync_to_async
    def get_current_question_number(self):
        """Gets the current question number without incrementing it."""
        game = Game.objects.get(code=self.room_code)
        return game.current_question_number

    @database_sync_to_async
    def set_game_completed(self):
        Game.objects.filter(code=self.room_code).update(is_completed=True)

    @database_sync_to_async
    def get_current_question(self, re_send=False):
        """Gets the next question for the game.""" 
        try:
            game = Game.objects.get(code=self.room_code)

            if not re_send:
                game.current_question_number += 1
                game.save()

            if game.current_question_number <= 0:
                return None

            questions = list(Question.objects.filter(quiz=game.quiz).order_by('order'))
            
            if not questions or game.current_question_number > len(questions):
                return None

            question = questions[game.current_question_number - 1]

            answers = list(question.answers.all())
            if not answers:
                logger.error(f"Question {question.id} has no answers")
                return None
                
            random.shuffle(answers)

            return {
                'id': question.id,
                'question_text': question.text,
                'answers': [{'id': a.id, 'text': a.text} for a in answers],
                'time_limit': question.time_limit,
                'current_question': game.current_question_number,
                'total_questions': len(questions)
            }
        except (Game.DoesNotExist, IndexError, Question.DoesNotExist) as e:
            logger.error(f"Could not retrieve question for game {self.room_code}: {e}")
            return None

    @database_sync_to_async
    def is_user_host(self):
        game = Game.objects.get(code=self.room_code)
        return game.host.id == self.user.id

    @database_sync_to_async
    def get_or_create_player(self):
        game = Game.objects.get(code=self.room_code)
        player, created = GamePlayer.objects.get_or_create(game=game, user=self.user)
        # Use select_related to pre-fetch the user and avoid lazy loading in async context
        return game, GamePlayer.objects.select_related('user').get(id=player.id)

    @database_sync_to_async
    def get_all_players_in_game(self):
        game = Game.objects.get(code=self.room_code)
        players = GamePlayer.objects.filter(game=game).select_related('user')
        player_list = []
        for p in players:
            # Temporarily disabled for debugging
            avatar_url = None

            player_list.append({
                'id': p.id, 
                'username': p.user.username,
                'score': p.score,
                'is_host': game.host == p.user, 
                'avatar_url': avatar_url
            })
        return player_list

    @database_sync_to_async
    def get_game_state(self):
        """
        Fetches the current state of the game.
        """
        try:
            game = Game.objects.get(code=self.room_code)
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
            return Question.objects.get(text=question_text, quiz__games__code=self.room_code)
        except Question.DoesNotExist:
            return None

    @database_sync_to_async
    def get_question_by_id(self, question_id):
        return Question.objects.filter(id=question_id).first()

    @database_sync_to_async
    def record_unanswered_as_incorrect(self, question):
        game = Game.objects.get(code=self.room_code)
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
                is_correct=False,  # Explicitly mark as incorrect
                points_awarded=0
            )

    @database_sync_to_async
    def remove_player_from_game(self, user):
        try:
            player = GamePlayer.objects.get(game__code=self.room_code, user=user)
            game = player.game
            is_host = game.host == user

            player_data = {
                'id': player.id,
                'username': user.username,
                'was_host': is_host
            }
            player.delete()
            return player_data
        except GamePlayer.DoesNotExist:
            return None

    @database_sync_to_async
    def game_exists(self):
        return Game.objects.filter(code=self.room_code).exists()

    @database_sync_to_async
    def get_player_id(self):
        try:
            return GamePlayer.objects.get(game__code=self.room_code, user=self.user).id
        except GamePlayer.DoesNotExist:
            return None

    @database_sync_to_async
    def calculate_score(self, answer_id, time_taken, time_limit):
        try:
            answer = Answer.objects.get(id=answer_id)
            if not answer.is_correct:
                return False, 0

            # Score calculation: 1000 base points, scaled by time remaining
            # Max score: 1000, Min score: 500 (for answering at the last moment)
            time_ratio = 1 - (time_taken / time_limit)
            score = 500 + (500 * time_ratio)
            return True, int(score)
        except Answer.DoesNotExist:
            return False, 0

    @database_sync_to_async
    def get_player_data_as_dict(self, player):
        game = Game.objects.get(code=self.room_code)
        return {
            'id': player.id,
            'username': player.user.username,
            'score': player.score,
            'is_host': game.host == player.user,
            'avatar_url': None  # Placeholder
        }

    @database_sync_to_async
    def get_correct_answer(self, question_id):
        try:
            return Answer.objects.get(question_id=question_id, is_correct=True)
        except Answer.DoesNotExist:
            return None

    @database_sync_to_async
    def get_total_questions(self):
        game = Game.objects.get(code=self.room_code)
        return game.quiz.questions.count()

    @database_sync_to_async
    def get_player_by_id(self, player_id):
        try:
            return GamePlayer.objects.get(id=player_id)
        except GamePlayer.DoesNotExist:
            return None

    @database_sync_to_async
    def get_teacher_channel(self):
        game = Game.objects.get(code=self.room_code)
        teacher_player = GamePlayer.objects.get(game=game, user=game.host)
        return self.player_channels.get(teacher_player.id)