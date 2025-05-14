from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from .models import Profile
from quiz.models import Quiz
from game.models import Game, GamePlayer

# Create your views here.
def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f'Account created for {username}! You can now log in.')
            return redirect('accounts:login')
    else:
        form = UserCreationForm()
    return render(request, 'accounts/register.html', {'form': form})

@login_required
def profile(request):
    user = request.user
    created_quizzes = Quiz.objects.filter(created_by=user)
    hosted_games = Game.objects.filter(host=user)
    
    # Get games where the user was a player
    played_games = GamePlayer.objects.filter(user=user).select_related('game')
    
    context = {
        'profile': user.profile,
        'created_quizzes': created_quizzes,
        'hosted_games': hosted_games,
        'played_games': played_games,
    }
    return render(request, 'accounts/profile.html', context)

@login_required
def edit_profile(request):
    if request.method == 'POST':
        # Update profile information
        user = request.user
        profile = user.profile
        
        # Update profile fields
        profile.bio = request.POST.get('bio', '')
        profile.save()
        
        # Update user fields
        user.first_name = request.POST.get('first_name', '')
        user.last_name = request.POST.get('last_name', '')
        user.email = request.POST.get('email', '')
        user.save()
        
        messages.success(request, 'Your profile has been updated!')
        return redirect('accounts:profile')
    
    return render(request, 'accounts/edit_profile.html')
