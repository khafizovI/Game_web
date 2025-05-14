import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
# from game.models import Game, GamePlayer
# from quiz.models import Quiz, Question, Answer


class GameConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.game_code = self.scope['url_route']['kwargs']['game_code']
        self.game_group_name = f'game_{self.game_code}'

        # Join game group
        await self.channel_layer.group_add(
            self.game_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Leave game group
        await self.channel_layer.group_discard(
            self.game_group_name,
            self.channel_name
        )

    # Receive message from WebSocket
    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type', data.get('action'))

        if message_type == 'join_game':
            username = data.get('username')
            await self.add_player_to_game(username)
            await self.channel_layer.group_send(
                self.game_group_name,
                {
                    'type': 'player_joined',
                    'username': username
                }
            )
        elif message_type == 'start_game':
            await self.start_game()
        elif message_type == 'submit_answer':
            username = data.get('username')
            answer_id = data.get('answer_id')
            await self.submit_answer(username, answer_id)
        elif message_type == 'next_question':
            await self.next_question()
        elif message_type == 'fetch_answers':
            question_id = data.get('question_id')
            await self.fetch_answers(question_id)

    # Event handlers
    async def player_joined(self, event):
        username = event['username']
        await self.send(text_data=json.dumps({
            'type': 'player_joined',
            'player': {'username': username, 'score': 0}
        }))

    async def game_started(self, event):
        question = event['question']
        answers = event['answers']

        await self.send(text_data=json.dumps({
            'type': 'start_game',
            'question': question,
            'answers': answers,
            'time_limit': event['time_limit']
        }))

    async def answer_result(self, event):
        await self.send(text_data=json.dumps({
            'type': 'answer_result',
            'is_correct': event['is_correct'],
            'username': event['username'],
            'points': event['points']
        }))

    async def next_question_sent(self, event):
        question = event['question']
        answers = event['answers']

        await self.send(text_data=json.dumps({
            'type': 'show_question',
            'question': event['question_id'],
            'question_text': question,
            'answers': answers,
            'time_limit': event['time_limit'],
            'current_question': event['current_question'],
            'total_questions': event['total_questions']
        }))

    async def game_ended(self, event):
        await self.send(text_data=json.dumps({
            'type': 'end_game',
            'scores': event['scores']
        }))

    async def answers_fetched(self, event):
        await self.send(text_data=json.dumps({
            'type': 'answers_fetched',
            'question_id': event['question_id'],
            'answers': event['answers']
        }))

    # Helper methods
    @database_sync_to_async
    def add_player_to_game(self, username):
        from game.models import Game, GamePlayer
        game = Game.objects.get(code=self.game_code)
        GamePlayer.objects.create(game=game, username=username, score=0)

    @database_sync_to_async
    def start_game(self):
        from game.models import Game
        game = Game.objects.get(code=self.game_code)
        quiz = game.quiz
        game.is_active = True
        game.current_question = 0
        game.save()

        # Get first question
        questions = list(quiz.questions.all())
        if questions:
            question = questions[0]
            answers = list(question.answers.all().values('id', 'text'))

            # Broadcast to group
            self.channel_layer.group_send(
                self.game_group_name,
                {
                    'type': 'game_started',
                    'question': question.text,
                    'answers': answers,
                    'time_limit': question.time_limit
                }
            )

    @database_sync_to_async
    def submit_answer(self, username, answer_id):
        from quiz.models import  Answer
        from game.models import Game,GamePlayer
        game = Game.objects.get(code=self.game_code)
        player = GamePlayer.objects.get(game=game, username=username)

        questions = list(game.quiz.questions.all())
        current_question = questions[game.current_question]

        answer = Answer.objects.get(id=answer_id)
        is_correct = answer.is_correct

        points = 0
        if is_correct:
            points = 100  # Basic points for correct answer
            player.score += points
            player.save()

        # Broadcast result
        self.channel_layer.group_send(
            self.game_group_name,
            {
                'type': 'answer_result',
                'is_correct': is_correct,
                'username': username,
                'points': points
            }
        )

    @database_sync_to_async
    def next_question(self):
        from game.models import Game,GamePlayer
        game = Game.objects.get(code=self.game_code)
        game.current_question += 1
        game.save()

        questions = list(game.quiz.questions.all())
        if game.current_question < len(questions):
            question = questions[game.current_question]
            answers = list(question.answers.all().values('id', 'text'))

            # Broadcast next question
            self.channel_layer.group_send(
                self.game_group_name,
                {
                    'type': 'next_question_sent',
                    'question_id': question.id,
                    'question': question.text,
                    'answers': answers,
                    'time_limit': question.time_limit,
                    'current_question': game.current_question + 1,
                    'total_questions': len(questions)
                }
            )
        else:
            # Game ended
            players = GamePlayer.objects.filter(game=game).order_by('-score')
            scores = [{'username': player.username, 'score': player.score} for player in players]

            self.channel_layer.group_send(
                self.game_group_name,
                {
                    'type': 'game_ended',
                    'scores': scores
                }
            )

    @database_sync_to_async
    def fetch_answers(self, question_id):
        from quiz.models import Quiz, Question
        try:
            question = Question.objects.get(id=question_id)
            answers = list(question.answers.all().values('id', 'text'))

            # Send answers to the requester
            self.channel_layer.group_send(
                self.game_group_name,
                {
                    'type': 'answers_fetched',
                    'question_id': question_id,
                    'answers': answers
                }
            )
        except Question.DoesNotExist:
            pass
