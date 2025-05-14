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
    
    # Redirect to the host control page
    return redirect('game:host_control', game_code=code)

@login_required
def host_control(request, game_code):
    """View for controlling a hosted game"""
    game = get_object_or_404(Game, code=game_code)
    
    # Ensure the user is the host of the game
    if game.host != request.user:
        messages.error(request, "You are not the host of this game.")
        return redirect('home')
    
    # Check if the game is already completed
    if game.is_completed:
        return redirect('game:results', game_code=game_code)
    
    # Get questions for this quiz
    questions = Question.objects.filter(quiz=game.quiz).order_by('order')
    # Print for debugging
    print(f"Found {questions.count()} questions for quiz {game.quiz.title}")
    
    context = {
        'game': game,
        'quiz': game.quiz,
        'players': GamePlayer.objects.filter(game=game).order_by('-score'),
        'questions': questions
    }
    return render(request, 'game/host_control.html', context)

@login_required
def join_game(request):
    """View for joining a game using a game code"""
    if request.method == 'POST':
        code = request.POST.get('game_code', '').strip().upper()
        
        if not code:
            messages.error(request, "Please enter a game code.")
            return redirect('game:join')
        
        # Try to find the game
        try:
            game = Game.objects.get(code=code)
            
            # Check if game is already completed
            if game.is_completed:
                messages.error(request, "This game has already ended.")
                return redirect('game:join')
            
            # Check if player already exists for this user and game
            player, created = GamePlayer.objects.get_or_create(
                game=game,
                user=request.user,
                defaults={'username': request.user.username}
            )
            
            # Redirect to the game play page
            return redirect('game:play', game_code=code)
            
        except Game.DoesNotExist:
            messages.error(request, f"No game found with code {code}.")
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
        user=request.user,
        defaults={'username': request.user.username}
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
