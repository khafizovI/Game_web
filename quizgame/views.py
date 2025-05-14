from django.shortcuts import render
from quiz.models import Quiz

def home(request):
    """
    View for the home page of the application.
    Shows featured quizzes and main navigation options.
    """
    # Get a few featured quizzes to display on the home page
    featured_quizzes = Quiz.objects.filter(is_public=True).order_by('-created_at')[:5]
    
    context = {
        'featured_quizzes': featured_quizzes
    }
    
    return render(request, 'home.html', context)
