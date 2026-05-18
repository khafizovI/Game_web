from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils.crypto import get_random_string
from django.utils.translation import gettext as _
from quiz.models import Quiz, Question, Answer
from .models import Game, GamePlayer, PlayerAnswer
from accounts.views import award_game_points, check_achievements
from quizgame.translation_utils import translate_text_for_request
import json

# Create your views here.


def _guest_player_session_key(game_code):
    return f"guest_player_{game_code}"


def _clean_display_name(raw_value):
    return " ".join((raw_value or "").split())[:40]


def _get_authenticated_player(game, user):
    if not user.is_authenticated:
        return None

    if user.profile.is_teacher() and user.id != game.host_id:
        return None

    player, _ = GamePlayer.objects.get_or_create(
        game=game,
        user=user,
        defaults={"display_name": user.username},
    )
    if not player.display_name.strip():
        player.display_name = user.username
        player.save(update_fields=["display_name"])
    return player


def _get_guest_player(request, game):
    player_id = request.session.get(_guest_player_session_key(game.code))
    if not player_id:
        return None

    return (
        GamePlayer.objects.select_related("game", "game__host")
        .filter(id=player_id, game=game, user__isnull=True)
        .first()
    )


def _get_request_player(request, game):
    if request.user.is_authenticated:
        return _get_authenticated_player(game, request.user)
    return _get_guest_player(request, game)


def _remember_guest_player(request, game_code, player):
    request.session[_guest_player_session_key(game_code)] = player.id
    request.session["guest_player_name"] = player.name
    request.session.modified = True

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

def lobby(request, game_code):
    """View for the game lobby, where players wait for the host to start the game."""
    game = get_object_or_404(Game, code=game_code)
    current_player = _get_request_player(request, game)
    if not current_player:
        messages.error(
            request,
            translate_text_for_request(request, 'Join the game first to enter the lobby.'),
        )
        return redirect('game:join')

    players = (
        GamePlayer.objects.filter(game=game)
        .select_related('user', 'user__profile', 'user__profile__selected_frame')
        .order_by('joined_at')
    )
    is_host = bool(request.user.is_authenticated and request.user.id == game.host.id)

    context = {
        'game': game,
        'players': players,
        'is_host': is_host,
        'player': current_player,
    }
    return render(request, 'game/lobby.html', context)

def join_game(request):
    """View for joining a game using a game code"""
    if request.user.is_authenticated and request.user.profile.is_teacher():
        messages.warning(request, translate_text_for_request(request, 'Teachers can only host games.'))
        return redirect('quiz:browse')

    if request.method == 'POST':
        game_code = (request.POST.get('game_code') or '').strip().upper()
        display_name = _clean_display_name(request.POST.get('display_name'))

        if not game_code:
            messages.error(
                request,
                translate_text_for_request(request, 'Please enter a valid game code.'),
            )
            return redirect('game:join')

        try:
            game = Game.objects.get(code=game_code)

            if request.user.is_authenticated:
                _get_authenticated_player(game, request.user)
            else:
                if len(display_name) < 2:
                    messages.error(
                        request,
                        translate_text_for_request(request, 'Please enter your name before joining.'),
                    )
                    return redirect('game:join')

                guest_player = _get_guest_player(request, game)
                if guest_player:
                    if guest_player.display_name != display_name:
                        guest_player.display_name = display_name
                        guest_player.save(update_fields=['display_name'])
                else:
                    guest_player = GamePlayer.objects.create(
                        game=game,
                        display_name=display_name,
                    )
                _remember_guest_player(request, game.code, guest_player)

            return redirect('game:lobby', game_code=game.code)
        except Game.DoesNotExist:
            messages.error(
                request,
                translate_text_for_request(request, 'Game with code {code} not found.', code=game_code),
            )
            return redirect('game:join')
    initial_display_name = (
        request.user.username
        if request.user.is_authenticated
        else request.session.get('guest_player_name', '')
    )
    return render(request, 'game/join.html', {'initial_display_name': initial_display_name})

def play_game(request, game_code):
    """View for playing a game"""
    game = get_object_or_404(Game, code=game_code)
    player = _get_request_player(request, game)
    if not player:
        messages.error(
            request,
            translate_text_for_request(request, 'Join the game first to start playing.'),
        )
        return redirect('game:join')

    context = {
        'game': game,
        'player': player,
        'quiz': game.quiz
    }
    return render(request, 'game/play.html', context)

@login_required
def game_results(request, game_code):
    """Legacy results URL now points to the in-game final leaderboard."""
    return redirect('game:play', game_code=game_code)
