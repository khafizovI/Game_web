from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from .models import Profile
from quiz.models import Quiz
from game.models import Game, GamePlayer, PlayerAnswer
from .forms import CustomUserCreationForm, LoginForm  # Make sure LoginForm is imported
from django.contrib.auth import authenticate, login


# This view should now work correctly with your updated register.html
def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            username = form.cleaned_data.get('username')
            role = form.cleaned_data.get('role', 'student')

            # Ensure profile is created and role is set
            profile, created = Profile.objects.get_or_create(user=user)
            profile.role = role
            profile.save()

            # Log the user in automatically
            login(request, user)

            messages.success(request,
                             f'Welcome, {username}! You are now logged in as a {profile.get_role_display()}.')
            return redirect('home')
    else:
        form = CustomUserCreationForm()
    return render(request, 'accounts/register.html', {'form': form})


# This is the new, corrected login view
def login_view(request):
    """Custom login view that preserves data on error."""
    if request.method == 'POST':
        # Bind data to the form
        form = LoginForm(data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')

            user = authenticate(request, username=username, password=password)

            if user is not None:
                login(request, user)
                next_page = request.POST.get('next')
                if next_page:
                    return redirect(next_page)
                return redirect('home')
            else:
                # This error is for invalid username/password
                form.add_error(None, 'Invalid username or password.')
    else:
        # For GET requests, create a new, empty form
        form = LoginForm()

    # For GET requests or failed POST requests, render the page with the form object
    return render(request, 'accounts/login.html', {
        'form': form,
        'next': request.GET.get('next', '')
    })


@login_required
def edit_profile(request):
    if request.method == 'POST':
        user = request.user
        profile = user.profile

        profile.bio = request.POST.get('bio', '')

        role = request.POST.get('role')
        if role and role in [choice[0] for choice in Profile.ROLE_CHOICES]:
            profile.role = role

        if 'avatar' in request.FILES:
            profile.avatar = request.FILES['avatar']

        profile.save()

        user.first_name = request.POST.get('first_name', '')
        user.last_name = request.POST.get('last_name', '')
        user.email = request.POST.get('email', '')
        user.save()

        messages.success(request, 'Your profile has been updated!')
        return redirect('accounts:profile')

    context = {}
    return render(request, 'accounts/edit_profile.html', context)


@login_required
def profile(request):
    user = request.user
    profile = user.profile

    created_quizzes = Quiz.objects.filter(created_by=user)
    hosted_games = Game.objects.filter(host=user, is_completed=False)
    played_games = GamePlayer.objects.filter(user=user).select_related('game')

    top_position = "N/A"
    if profile.is_student():
        player_games = GamePlayer.objects.filter(user=user, game__is_completed=True)
        if player_games.exists():
            for player_game in player_games:
                game = player_game.game
                position = list(game.players.order_by('-score')).index(player_game) + 1
                if top_position == "N/A" or position < int(top_position):
                    top_position = str(position)

    context = {
        'profile': profile,
        'created_quizzes': created_quizzes,
        'hosted_games': hosted_games,
        'played_games': played_games,
        'top_position': top_position,
    }
    return render(request, 'accounts/dashboard.html', context)


@login_required
def hosted_history(request):
    if not request.user.profile.is_teacher:
        return redirect('home')

    hosted_games_history = []
    completed_games = Game.objects.filter(host=request.user, is_completed=True).prefetch_related('quiz__questions', 'players__user')

    for game in completed_games:
        game_data = {
            'quiz_title': game.quiz.title,
            'players_stats': []
        }
        total_questions = game.quiz.questions.count()

        if total_questions > 0:
            for player in game.players.all():
                correct_answers_count = PlayerAnswer.objects.filter(
                    player=player,
                    answer__is_correct=True
                ).count()

                correct_percentage = round((correct_answers_count / total_questions) * 100)

                game_data['players_stats'].append({
                    'username': player.user.username,
                    'correct_percentage': correct_percentage
                })
        
        if game_data['players_stats']:
            hosted_games_history.append(game_data)

    context = {
        'hosted_games_history': hosted_games_history,
    }
    return render(request, 'accounts/history.html', context)