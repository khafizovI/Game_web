from django.shortcuts import render, redirect
from quiz.models import Quiz
from django.utils import translation
from django.conf import settings
from django.http import HttpResponseRedirect
import logging

# Setup logger
logger = logging.getLogger(__name__)

def home(request):
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
    
    featured_quizzes = Quiz.objects.filter(is_public=True).order_by('-created_at')[:5]
    
    context = {
        'featured_quizzes': featured_quizzes
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
