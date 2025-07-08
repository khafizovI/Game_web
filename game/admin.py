from django.contrib import admin
from .models import Game, GamePlayer, PlayerAnswer

# Register your models here.

class GamePlayerInline(admin.TabularInline):
    model = GamePlayer
    extra = 0

@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ('code', 'quiz', 'host', 'created_at', 'is_active', 'is_completed')
    list_filter = ('is_active', 'is_completed', 'created_at')
    search_fields = ('code', 'quiz__title', 'host__username')
    inlines = [GamePlayerInline]

@admin.register(GamePlayer)
class GamePlayerAdmin(admin.ModelAdmin):
    list_display = ('user', 'game', 'score', 'joined_at')
    list_filter = ('game',)
    search_fields = ('user__username', 'game__code')

@admin.register(PlayerAnswer)
class PlayerAnswerAdmin(admin.ModelAdmin):
    list_display = ('player', 'question', 'answer', 'points_awarded', 'answered_at')
    list_filter = ('player__game', 'question')
    search_fields = ('player__user__username', 'question__text')
