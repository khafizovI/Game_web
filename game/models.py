from django.db import models
from django.contrib.auth.models import User
from quiz.models import Quiz, Question, Answer
from django.utils.crypto import get_random_string

def generate_game_code():
    return get_random_string(6, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')

class Game(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='games')
    code = models.CharField(max_length=6, unique=True, default=generate_game_code)
    host = models.ForeignKey(User, on_delete=models.CASCADE, related_name='hosted_games')
    is_active = models.BooleanField(default=False)
    is_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    current_question = models.ForeignKey(Question, on_delete=models.SET_NULL, null=True, blank=True, related_name='active_in_games')
    current_question_number = models.IntegerField(default=0)

    def __str__(self):
        return f"Game {self.code} for {self.quiz.title}"

    class Meta:
        ordering = ['-created_at']

class GamePlayer(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='players')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='game_participations')
    score = models.IntegerField(default=0)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('game', 'user')

    def __str__(self):
        return f"{self.user.username} in game {self.game.code}"
    
    @property
    def is_host(self):
        return self.game.host == self.user

class PlayerAnswer(models.Model):
    player = models.ForeignKey(GamePlayer, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    answer = models.ForeignKey(Answer, on_delete=models.CASCADE, null=True, blank=True)
    is_correct = models.BooleanField(default=False)
    score_earned = models.IntegerField(default=0)
    answered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('player', 'question')

    def __str__(self):
        return f"{self.player.user.username}'s answer to {self.question.text}"
