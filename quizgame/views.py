from django.shortcuts import render, redirect
from quiz.models import Quiz, Question
from game.models import Game, GamePlayer
from accounts.models import Profile
from django.contrib.auth.models import User
from django.utils import translation
from django.conf import settings
from django.http import HttpResponseRedirect, JsonResponse
from django.db.models import Count, Avg
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
    
    # Get the 3 most recent public quizzes
    quizzes = Quiz.objects.filter(is_public=True).order_by('-created_at')[:3]
    
    # Calculate real statistics
    stats = {
        'active_players': User.objects.filter(is_active=True).count(),
        'quiz_questions': Question.objects.count(),
        'games_played': Game.objects.filter(is_completed=True).count(),
        'user_rating': 4.8  # You can calculate this from actual ratings if you have a rating system
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
        language = request.POST.get('language', None)
        next_url = request.POST.get('next', '/')
        
        logger.info(f"Language change requested: {language}, Next URL: {next_url}")
        
        if language and language in [lang[0] for lang in settings.LANGUAGES]:
            # Activate the language
            translation.activate(language)
            
            # Set language in session
            request.session[settings.LANGUAGE_SESSION_KEY] = language
            
            # Create response with redirect
            response = HttpResponseRedirect(next_url)
            
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
