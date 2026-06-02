from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.urls import reverse
from django.utils.crypto import get_random_string
from django.utils.translation import gettext as _
from quiz.models import Quiz, Question, Answer
from .models import Game, GamePlayer, PlayerAnswer
from accounts.views import award_game_points, check_achievements
from quizgame.translation_utils import translate_text_for_request
import json
import logging

logger = logging.getLogger('game.views')

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
    player_id = request.GET.get('player') or request.session.get(_guest_player_session_key(game.code))
    if not player_id:
        return None

    player = (
        GamePlayer.objects.select_related("game", "game__host")
        .filter(id=player_id, game=game, user__isnull=True)
        .first()
    )
    if player:
        _remember_guest_player(request, game.code, player)
    return player


def _get_request_player(request, game):
    if request.user.is_authenticated:
        return _get_authenticated_player(game, request.user)
    return _get_guest_player(request, game)


def _remember_guest_player(request, game_code, player):
    request.session[_guest_player_session_key(game_code)] = player.id
    request.session["guest_player_name"] = player.name
    request.session.modified = True


def _serialize_game_player(player):
    selected_frame = {"css_class": player.selected_frame_css_class} if player.selected_frame_css_class else None
    profile = player.profile
    return {
        'id': player.id,
        'username': player.name,
        'avatar_url': player.avatar_url,
        'score': player.score,
        'is_host': player.is_host,
        'user': {
            'username': player.name,
            'profile': {
                'avatar': {'url': player.avatar_url} if player.avatar_url else None,
                'selected_frame': selected_frame,
                'total_points': profile.total_points if profile else 0,
                'games_played': profile.games_played if profile else 0,
                'level': player.level,
            },
        },
    }

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
    logger.info(
        'lobby_view game=%s player=%s query_player=%s ua=%s',
        game_code,
        getattr(current_player, 'id', None),
        request.GET.get('player'),
        request.META.get('HTTP_USER_AGENT', '')[:180],
    )
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

            if request.user.is_authenticated:
                return redirect('game:lobby', game_code=game.code)

            lobby_url = reverse('game:lobby', kwargs={'game_code': game.code})
            return redirect(f'{lobby_url}?player={guest_player.id}')
        except Game.DoesNotExist:
            messages.error(
                request,
                translate_text_for_request(request, 'Game with code {code} not found.', code=game_code),
            )
            return redirect('game:join')
    initial_display_name = request.user.username if request.user.is_authenticated else ''
    return render(request, 'game/join.html', {'initial_display_name': initial_display_name})

def play_game(request, game_code):
    """View for playing a game"""
    game = get_object_or_404(Game, code=game_code)
    player = _get_request_player(request, game)
    logger.info(
        'play_view game=%s active=%s qnum=%s player=%s query_player=%s ua=%s',
        game_code,
        game.is_active,
        game.current_question_number,
        getattr(player, 'id', None),
        request.GET.get('player'),
        request.META.get('HTTP_USER_AGENT', '')[:180],
    )
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

def game_status(request, game_code):
    """Lightweight status endpoint so clients can recover if websocket events are missed."""
    game = get_object_or_404(Game, code=game_code)
    player = _get_request_player(request, game)
    logger.info(
        'status_view game=%s active=%s qnum=%s player=%s query_player=%s ua=%s',
        game_code,
        game.is_active,
        game.current_question_number,
        getattr(player, 'id', None),
        request.GET.get('player'),
        request.META.get('HTTP_USER_AGENT', '')[:180],
    )
    if not player:
        return JsonResponse({'detail': 'Join the game first.'}, status=403)

    return JsonResponse(
        {
            'is_active': game.is_active,
            'is_completed': game.is_completed,
            'current_question_number': game.current_question_number,
        }
    )


def lobby_state(request, game_code):
    """Return the latest lobby player list for clients that missed websocket updates."""
    game = get_object_or_404(Game, code=game_code)
    player = _get_request_player(request, game)
    logger.info(
        'lobby_state game=%s players=%s player=%s query_player=%s ua=%s',
        game_code,
        GamePlayer.objects.filter(game=game).count(),
        getattr(player, 'id', None),
        request.GET.get('player'),
        request.META.get('HTTP_USER_AGENT', '')[:180],
    )
    if not player:
        return JsonResponse({'detail': 'Join the game first.'}, status=403)

    players = (
        GamePlayer.objects.filter(game=game)
        .select_related('user', 'user__profile', 'user__profile__selected_frame')
        .order_by('joined_at')
    )
    return JsonResponse({'players': [_serialize_game_player(item) for item in players]})

@login_required
def game_results(request, game_code):
    """Legacy results URL now points to the in-game final leaderboard."""
    return redirect('game:play', game_code=game_code)
