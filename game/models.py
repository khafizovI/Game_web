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
    rewards_processed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    current_question = models.ForeignKey(Question, on_delete=models.SET_NULL, null=True, blank=True, related_name='active_in_games')
    current_question_number = models.IntegerField(default=0)

    def __str__(self):
        return f"Game {self.code} for {self.quiz.title}"

    class Meta:
        ordering = ['-created_at']

class GamePlayer(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='players')
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='game_participations',
        null=True,
        blank=True,
    )
    display_name = models.CharField(max_length=40, blank=True)
    score = models.IntegerField(default=0)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('game', 'user')

    def __str__(self):
        return f"{self.name} in game {self.game.code}"

    @property
    def is_host(self):
        return self.user_id == self.game.host_id

    @property
    def is_guest(self):
        return self.user_id is None

    @property
    def name(self):
        if self.display_name.strip():
            return self.display_name.strip()
        if self.user_id:
            return self.user.username
        return "Guest"

    @property
    def username(self):
        return self.name

    @property
    def profile(self):
        if not self.user_id:
            return None
        return getattr(self.user, "profile", None)

    @property
    def avatar_url(self):
        profile = self.profile
        return profile.avatar_url if profile else None

    @property
    def selected_frame_css_class(self):
        profile = self.profile
        if profile and profile.selected_border:
            return profile.selected_border.css_class
        if profile and profile.selected_frame:
            return profile.selected_frame.css_class
        return ""

    @property
    def level(self):
        profile = self.profile
        return profile.level if profile else 1

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
        return f"{self.player.name}'s answer to {self.question.text}"
