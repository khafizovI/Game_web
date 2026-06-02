from django.shortcuts import render, redirect
from quiz.models import Quiz, Question
from game.models import Game, GamePlayer
from accounts.models import Profile
from django.contrib.auth.models import User
from django.utils import translation
from django.conf import settings
from django.http import HttpResponseRedirect, JsonResponse
from django.db.utils import OperationalError, ProgrammingError
from django.db.models import Count, Avg
from .translation_utils import normalize_language_code, switch_language_url
import logging

# Setup logger
logger = logging.getLogger(__name__)

def home(request):
    """Render the homepage with real statistics."""
    # Handle language selection from query parameter
    lang = request.GET.get('lang')
    if lang and lang in [code for code, name in settings.LANGUAGES]:
        # Set language in session and cookie
        translation.activate(lang)
        request.session[settings.LANGUAGE_SESSION_KEY] = lang
        
        # Redirect to the same page without the query parameter
        response = HttpResponseRedirect(request.path)
        response.set_cookie(settings.LANGUAGE_COOKIE_NAME, lang, max_age=365*24*60*60)
        
        return response
    
    try:
        # Get the 3 most recent public quizzes
        quizzes = Quiz.objects.filter(is_public=True).order_by('-created_at')[:3]

        # Calculate real statistics
        stats = {
            'active_players': User.objects.filter(is_active=True).count(),
            'quiz_questions': Question.objects.count(),
            'games_played': Game.objects.filter(is_completed=True).count(),
            'user_rating': 4.8,  # Replace with a real aggregate when ratings are modeled separately.
        }
    except (OperationalError, ProgrammingError):
        # Allow the homepage to render before the first migrate has been run.
        quizzes = Quiz.objects.none()
        stats = {
            'active_players': 0,
            'quiz_questions': 0,
            'games_played': 0,
            'user_rating': 4.8,
        }
    
    context = {
        'quizzes': quizzes,
        'stats': stats
    }
    
    return render(request, 'home.html', context)

def set_language(request):
    """
    Custom view to handle language switching
    """
    if request.method == 'POST':
        language = normalize_language_code(request.POST.get('language', None))
        next_url = request.POST.get('next', '/')
        
        logger.info(f"Language change requested: {language}, Next URL: {next_url}")
        
        if language and language in [lang[0] for lang in settings.LANGUAGES]:
            # Activate the language
            translation.activate(language)
            
            # Set language in session
            request.session[settings.LANGUAGE_SESSION_KEY] = language
            
            # Create response with redirect
            response = HttpResponseRedirect(switch_language_url(next_url, language))
            
            # Set language cookie
            response.set_cookie(
                settings.LANGUAGE_COOKIE_NAME,
                language,
                max_age=365*24*60*60,  # One year
                path=settings.LANGUAGE_COOKIE_PATH
            )
            
            return response
    
    # If something goes wrong, redirect to home
    return redirect('home')

def def_chrome_devtools_json(request):
    return JsonResponse({})


def bad_request(request, exception):
    return render(request, '400.html', status=400)


def permission_denied(request, exception):
    return render(request, '403.html', status=403)


def csrf_failure(request, reason=""):
    return render(request, '403.html', status=403)


def page_not_found(request, exception):
    return render(request, '404.html', status=404)


def server_error(request):
    return render(request, '500.html', status=500)
