from django.db import models
from django.contrib.auth.models import User
from quiz.models import Quiz, Question, Answer
import random
import string

# Create your models here.

def generate_unique_code():
    """Generate a random 6-character game code"""
    length = 6
    while True:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
        if not Game.objects.filter(code=code).exists():
            return code

class Game(models.Model):
    code = models.CharField(max_length=6, unique=True, default=generate_unique_code)
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='games')
    host = models.ForeignKey(User, on_delete=models.CASCADE, related_name='hosted_games')
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=False)
    is_completed = models.BooleanField(default=False)
    current_question = models.IntegerField(default=0)
    
    def __str__(self):
        return f"Game {self.code} - {self.quiz.title}"
    
    class Meta:
        ordering = ['-created_at']

class GamePlayer(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='players')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='played_games', null=True, blank=True)
    username = models.CharField(max_length=50)  # For guest players without accounts
    score = models.IntegerField(default=0)
    joined_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.username} in game {self.game.code}"
    
    class Meta:
        unique_together = ('game', 'username')
        ordering = ['-score']

class PlayerAnswer(models.Model):
    player = models.ForeignKey(GamePlayer, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    answer = models.ForeignKey(Answer, on_delete=models.CASCADE, null=True, blank=True)
    is_correct = models.BooleanField(default=False)
    points_earned = models.IntegerField(default=0)
    response_time = models.FloatField(default=0.0)  # Time taken to answer in seconds
    submitted_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.player.username}'s answer to {self.question.text[:20]}..."
