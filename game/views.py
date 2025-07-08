from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils.crypto import get_random_string
from quiz.models import Quiz, Question, Answer
from .models import Game, GamePlayer
import json

# Create your views here.

@login_required
def host_game(request, quiz_id):
    """View for hosting a new game from a quiz"""
    # Check if user is a teacher
    if not request.user.profile.is_teacher():
        messages.error(request, "Only teachers can host games.")
        return redirect('accounts:dashboard')
        
    quiz = get_object_or_404(Quiz, id=quiz_id)
    
    # Check if quiz has questions
    if quiz.questions.count() == 0:
        messages.error(request, "You can't host a game with a quiz that has no questions.")
        return redirect('quiz:edit', quiz_id=quiz.id)
    
    # Generate a unique 6-character game code
    code = get_random_string(6).upper()
    while Game.objects.filter(code=code).exists():
        code = get_random_string(6).upper()
    
    # Create the game
    game = Game.objects.create(
        quiz=quiz,
        host=request.user,
        code=code
    )
    
    # Add the host as a player
    GamePlayer.objects.create(
        game=game,
        user=request.user
    )
    
    # Redirect to the game lobby
    return redirect('game:lobby', game_code=code)

@login_required
def lobby(request, game_code):
    """View for the game lobby, where players wait for the host to start the game."""
    game = get_object_or_404(Game, code=game_code)
    players = GamePlayer.objects.filter(game=game)
    is_host = (request.user.id == game.host.id)

    context = {
        'game': game,
        'players': players,
        'is_host': is_host,
    }
    return render(request, 'game/lobby.html', context)

@login_required
def join_game(request):
    """View for joining a game using a game code"""
    if request.method == 'POST':
        game_code = request.POST.get('game_code')
        try:
            game = Game.objects.get(code=game_code)
            # Add the player to the game if they are not already in it
            GamePlayer.objects.get_or_create(
                game=game,
                user=request.user
            )
            return redirect('game:lobby', game_code=game.code)
        except Game.DoesNotExist:
            messages.error(request, _('Game with code %(code)s not found.') % {'code': game_code})
            return redirect('game:join')
    return render(request, 'game/join.html')

@login_required
def play_game(request, game_code):
    """View for playing a game"""
    game = get_object_or_404(Game, code=game_code)
    
    # Check if the game is completed
    if game.is_completed:
        return redirect('game:results', game_code=game_code)
    
    # Get or create player
    player, created = GamePlayer.objects.get_or_create(
        game=game,
        user=request.user
    )
    
    context = {
        'game': game,
        'player': player,
        'quiz': game.quiz
    }
    return render(request, 'game/play.html', context)

@login_required
def game_results(request, game_code):
    """View for seeing game results"""
    game = get_object_or_404(Game, code=game_code)
    
    # Mark game as completed if not already
    if not game.is_completed:
        game.is_completed = True
        game.save()
    
    # Get all players sorted by score
    players = GamePlayer.objects.filter(game=game).order_by('-score')
    
    # Calculate player ranks
    for i, player in enumerate(players):
        player.rank = i + 1
    
    context = {
        'game': game,
        'quiz': game.quiz,
        'players': players,
        'is_host': game.host == request.user,
        'player': players.filter(user=request.user).first()
    }
    return render(request, 'game/results.html', context)
