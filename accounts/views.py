from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from .models import Profile, EmailVerification, ShopItem, UserPurchase, Achievement, UserAchievement, DailyTask, UserDailyTask
from quiz.models import Quiz
from game.models import Game, GamePlayer, PlayerAnswer
from .forms import CustomUserCreationForm, LoginForm, EmailVerificationForm
from django.contrib.auth import authenticate, login
from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse
from django.http import JsonResponse
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
from django.views.decorators.csrf import csrf_exempt
from functools import wraps
import random


def ajax_login_required(view_func):
    """
    Custom decorator for AJAX views that require authentication.
    Returns JSON response instead of redirecting for AJAX requests.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': 'Authentication required'}, status=401)
            else:
                # For non-AJAX requests, redirect to login
                from django.shortcuts import redirect
                return redirect('accounts:login')
        return view_func(request, *args, **kwargs)
    return wrapper


def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            # Create user but don't log them in yet
            user = form.save()
            username = form.cleaned_data.get('username')
            email = form.cleaned_data.get('email')
            role = form.cleaned_data.get('role', 'student')

            # Ensure profile is created and role is set
            profile, created = Profile.objects.get_or_create(user=user)
            profile.role = role
            profile.save()

            # Generate and send verification code
            verification = EmailVerification.generate_code(user)
            send_verification_email(user, verification.code)

            # Store user ID in session for verification
            request.session['pending_user_id'] = user.id
            
            messages.info(request, f'Welcome, {username}! Please check your email ({email}) for a verification code.')
            return redirect('accounts:verify_email')
        # If form is not valid, it will be rendered again with errors and preserved data
    else:
        form = CustomUserCreationForm()
    return render(request, 'accounts/register.html', {'form': form})


def send_verification_email(user, code):
    # For development: Just print the verification code to console
    print(f"=== EMAIL VERIFICATION CODE FOR {user.username} ===")
    print(f"Verification Code: {code}")
    print(f"Email: {user.email}")
    print("=" * 50)
    
    # Uncomment the code below to actually send emails in production
    """
    subject = 'Verify Your Email - Quiz Game'
    message = f'''
    Hi {user.username},

    Welcome to Quiz Game! Please use the following verification code to complete your registration:

    Verification Code: {code}

    This code will expire in 10 minutes.

    If you didn't create an account, please ignore this email.

    Best regards,
    Quiz Game Team
    '''
    
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
    except Exception as e:
        print(f"Failed to send email: {e}")
    """


def verify_email(request):
    user_id = request.session.get('pending_user_id')
    if not user_id:
        messages.error(request, 'No pending registration found.')
        return redirect('accounts:register')
    
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        messages.error(request, 'Invalid registration session.')
        return redirect('accounts:register')
    
    if request.method == 'POST':
        if 'resend_code' in request.POST:
            # Resend verification code
            verification = EmailVerification.generate_code(user)
            send_verification_email(user, verification.code)
            messages.success(request, 'New verification code sent to your email.')
            return render(request, 'accounts/verify_email.html', {'user': user})
        
        form = EmailVerificationForm(user=user, data=request.POST)
        if form.is_valid():
            code = form.cleaned_data.get('code')
            try:
                verification = EmailVerification.objects.get(
                    user=user,
                    code=code,
                    is_used=False
                )
                if not verification.is_expired():
                    # Mark verification as used
                    verification.is_used = True
                    verification.save()
                    
                    # Mark profile as email verified
                    profile = user.profile
                    profile.email_verified = True
                    profile.save()
                    
                    # Log the user in
                    login(request, user)
                    
                    # Clear session
                    del request.session['pending_user_id']
                    
                    messages.success(request, f'Email verified successfully! Welcome, {user.username}!')
                    return redirect('home')
                else:
                    form.add_error('code', 'Verification code has expired. Please request a new one.')
            except EmailVerification.DoesNotExist:
                form.add_error('code', 'Invalid verification code.')
        # If form is not valid, it will be rendered again with errors
    else:
        form = EmailVerificationForm(user=user)
    
    return render(request, 'accounts/verify_email.html', {'form': form, 'user': user})


# This is the corrected login view that preserves data on error
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
                # Check if email is verified
                if hasattr(user, 'profile') and not user.profile.email_verified:
                    # Generate new verification code and redirect to verification
                    verification = EmailVerification.generate_code(user)
                    send_verification_email(user, verification.code)
                    request.session['pending_user_id'] = user.id
                    messages.warning(request, 'Please verify your email before logging in. A new verification code has been sent.')
                    return redirect('accounts:verify_email')
                
                login(request, user)
                next_page = request.POST.get('next')
                if next_page:
                    return redirect(next_page)
                return redirect('home')
            else:
                # This error is for invalid username/password
                form.add_error(None, 'Invalid username or password.')
        # If form is not valid, it will be rendered again with errors and preserved data
    else:
        # For GET requests, create a new, empty form
        form = LoginForm()

    # For GET requests or failed POST requests, render the page with the form object
    return render(request, 'accounts/login.html', {
        'form': form,
        'next': request.GET.get('next', '')
    })


def edit_profile(request):
    """Edit profile view - redirects students to dashboard, allows teachers to edit profile"""
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'message': 'Authentication required'}, status=401)
    
    profile = request.user.profile
    
    # Redirect students to their dashboard where they can edit profile
    if profile.is_student():
        return redirect('accounts:student_dashboard')

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


def profile(request):
    """Profile view - redirects students to dashboard, shows teacher profile"""
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'message': 'Authentication required'}, status=401)
    
    user = request.user
    profile = user.profile
    
    # Redirect students to their dashboard
    if profile.is_student():
        return redirect('accounts:student_dashboard')

    created_quizzes = Quiz.objects.filter(created_by=user)
    hosted_games = Game.objects.filter(host=user, is_completed=False)
    played_games = GamePlayer.objects.filter(user=user).select_related('game')

    # Additional stats for teacher dashboard
    total_hosted_games = Game.objects.filter(host=user).count()
    completed_games_count = Game.objects.filter(host=user, is_completed=True).count()
    
    # Count unique students taught
    students_taught = 0
    latest_activity = None
    if profile.is_teacher:
        # Get all players from teacher's hosted games
        hosted_game_ids = Game.objects.filter(host=user).values_list('id', flat=True)
        students_taught = GamePlayer.objects.filter(game_id__in=hosted_game_ids).values('user').distinct().count()
        
        # Get latest activity (most recent completed game)
        latest_game = Game.objects.filter(host=user, is_completed=True).order_by('-created_at').first()
        if latest_game:
            latest_activity = latest_game.created_at

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
        'total_hosted_games': total_hosted_games,
        'completed_games_count': completed_games_count,
        'students_taught': students_taught,
        'latest_activity': latest_activity,
    }
    return render(request, 'accounts/dashboard.html', context)


def hosted_history(request):
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'message': 'Authentication required'}, status=401)
    
    if not request.user.profile.is_teacher:
        return redirect('home')

    # Get completed games with detailed information
    completed_games = Game.objects.filter(
        host=request.user, 
        is_completed=True
    ).prefetch_related(
        'quiz__questions', 
        'players__user',
        'players__answers__answer'
    ).order_by('-created_at')

    hosted_games_history = []
    
    for game in completed_games:
        total_questions = game.quiz.questions.count()
        
        if total_questions > 0:
            # Calculate player statistics and rankings
            players_stats = []
            
            for player in game.players.all():
                correct_answers = PlayerAnswer.objects.filter(
                    player=player,
                    answer__is_correct=True
                ).count()
                
                total_answered = PlayerAnswer.objects.filter(player=player).count()
                correct_percentage = round((correct_answers / total_questions) * 100) if total_questions > 0 else 0
                
                players_stats.append({
                    'username': player.user.username,
                    'score': player.score,
                    'correct_answers': correct_answers,
                    'total_questions': total_questions,
                    'correct_percentage': correct_percentage,
                    'total_answered': total_answered
                })
            
            # Sort players by score (descending) to determine rankings
            players_stats.sort(key=lambda x: x['score'], reverse=True)
            
            # Add rank to each player
            for i, player_stat in enumerate(players_stats):
                player_stat['rank'] = i + 1
                
                # Add rank badge class for styling
                if player_stat['rank'] == 1:
                    player_stat['rank_class'] = 'gold'
                elif player_stat['rank'] == 2:
                    player_stat['rank_class'] = 'silver'
                elif player_stat['rank'] == 3:
                    player_stat['rank_class'] = 'bronze'
                else:
                    player_stat['rank_class'] = 'default'
            
            game_data = {
                'id': game.id,
                'quiz_title': game.quiz.title,
                'game_code': game.code,
                'date': game.created_at,
                'total_questions': total_questions,
                'total_players': len(players_stats),
                'players_stats': players_stats,
                'average_score': round(sum(p['score'] for p in players_stats) / len(players_stats)) if players_stats else 0,
                'average_percentage': round(sum(p['correct_percentage'] for p in players_stats) / len(players_stats)) if players_stats else 0
            }
            
            hosted_games_history.append(game_data)

    context = {
        'hosted_games_history': hosted_games_history,
        'total_games': len(hosted_games_history),
        'total_students': sum(game['total_players'] for game in hosted_games_history)
    }
    return render(request, 'accounts/history.html', context)


@login_required
def student_dashboard(request):
    """Comprehensive student dashboard with profile, stats, achievements, and progress"""
    if not request.user.profile.is_student():
        messages.error(request, "Access denied. Students only.")
        return redirect('home')
    
    profile = request.user.profile
    
    # Handle profile update form submission
    if request.method == 'POST':
        # Update user fields
        request.user.first_name = request.POST.get('first_name', '')
        request.user.last_name = request.POST.get('last_name', '')
        request.user.email = request.POST.get('email', '')
        request.user.save()
        
        # Update profile fields
        profile.bio = request.POST.get('bio', '')
        
        # Handle avatar upload
        if 'avatar' in request.FILES:
            profile.avatar = request.FILES['avatar']
        
        profile.save()
        messages.success(request, "Profile updated successfully!")
        return redirect('accounts:student_dashboard')
    
    # Get or create daily tasks for today
    daily_tasks = get_or_create_daily_tasks(request.user)
    completed_tasks_count = daily_tasks.filter(is_completed=True).count()
    
    # Get recent games played
    recent_games = GamePlayer.objects.filter(user=request.user).select_related('game__quiz').order_by('-joined_at')[:5]
    
    # Calculate statistics
    total_games = GamePlayer.objects.filter(user=request.user).count()
    total_score = sum(gp.score for gp in GamePlayer.objects.filter(user=request.user))
    avg_score = round(total_score / total_games) if total_games > 0 else 0
    
    # Get achievements
    user_achievements = UserAchievement.objects.filter(user=request.user).select_related('achievement')
    available_achievements = Achievement.objects.exclude(
        id__in=user_achievements.values_list('achievement_id', flat=True)
    ).filter(is_hidden=False)
    
    # Check for new achievements
    check_achievements(request.user)
    
    # Recent activity (last 7 days)
    week_ago = timezone.now() - timedelta(days=7)
    recent_activity = GamePlayer.objects.filter(
        user=request.user, 
        joined_at__gte=week_ago
    ).count()
    
    # Get user's purchased items
    user_purchases = UserPurchase.objects.filter(user=request.user).select_related('item')
    purchased_frames = user_purchases.filter(item__item_type='frame')
    purchased_badges = user_purchases.filter(item__item_type='badge')
    purchased_themes = user_purchases.filter(item__item_type='theme')
    
    context = {
        'profile': profile,
        'recent_games': recent_games,
        'total_games': total_games,
        'avg_score': avg_score,
        'user_achievements': user_achievements,
        'available_achievements': available_achievements[:6],  # Show 6 next achievements
        'recent_activity': recent_activity,
        'level': profile.get_level(),
        'level_progress': profile.get_level_progress(),
        'purchased_frames': purchased_frames,
        'purchased_badges': purchased_badges,
        'purchased_themes': purchased_themes,
        'daily_tasks': daily_tasks,
        'completed_tasks_count': completed_tasks_count,
    }
    
    return render(request, 'accounts/student_dashboard.html', context)


def shop(request):
    """Shop where students can buy cosmetic items"""
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'message': 'Authentication required'}, status=401)
    
    if not request.user.profile.is_student():
        messages.error(request, "Access denied. Students only.")
        return redirect('home')
    
    profile = request.user.profile
    
    # Get all shop items
    frames = ShopItem.objects.filter(item_type='frame', is_active=True)
    badges = ShopItem.objects.filter(item_type='badge', is_active=True)
    themes = ShopItem.objects.filter(item_type='theme', is_active=True)
    
    # Get user's purchases
    user_purchases = UserPurchase.objects.filter(user=request.user).values_list('item_id', flat=True)
    
    context = {
        'profile': profile,
        'frames': frames,
        'badges': badges,
        'themes': themes,
        'user_purchases': user_purchases,
    }
    
    return render(request, 'accounts/shop.html', context)


def purchase_item(request, item_id):
    """Purchase a shop item"""
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'message': 'Authentication required'}, status=401)
    
    if not request.user.profile.is_student():
        return JsonResponse({'success': False, 'message': 'Access denied'})
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method'})
    
    try:
        item = ShopItem.objects.get(id=item_id, is_active=True)
    except ShopItem.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Item not found'}, status=404)
    
    profile = request.user.profile
    
    # Check if user already owns this item
    if UserPurchase.objects.filter(user=request.user, item=item).exists():
        return JsonResponse({'success': False, 'message': 'You already own this item'})
    
    # Check if user has enough coins
    if profile.coins < item.price:
        return JsonResponse({'success': False, 'message': 'Not enough coins'})
    
    # Make the purchase
    profile.coins -= item.price
    profile.save()
    
    UserPurchase.objects.create(user=request.user, item=item)
    
    return JsonResponse({
        'success': True, 
        'message': f"Successfully purchased {item.name}!",
        'new_coin_balance': profile.coins
    })


def equip_frame(request, item_id):
    """Equip a profile frame"""
    
    # Only allow POST requests
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST method required'}, status=405)
    
    # Check if user is a student
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'message': 'Authentication required'}, status=401)
    
    if not request.user.profile.is_student():
        return JsonResponse({'success': False, 'message': 'Access denied - students only'}, status=403)
    
    try:
        # Get the shop item
        item = ShopItem.objects.get(id=item_id, item_type='frame')
        
        # Check if user owns this item
        if not UserPurchase.objects.filter(user=request.user, item=item).exists():
            return JsonResponse({'success': False, 'message': 'You do not own this item'}, status=400)
        
        # Equip the frame
        profile = request.user.profile
        profile.selected_frame = item
        profile.save()
        
        return JsonResponse({
            'success': True, 
            'message': f"Equipped {item.name}!",
            'item_id': item_id,
            'item_name': item.name
        })
        
    except ShopItem.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Item not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'message': 'An error occurred'}, status=500)


def equip_theme(request, item_id):
    """Equip a profile theme"""
    
    # Only allow POST requests
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST method required'}, status=405)
    
    # Check if user is a student
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'message': 'Authentication required'}, status=401)
    
    if not request.user.profile.is_student():
        return JsonResponse({'success': False, 'message': 'Access denied - students only'}, status=403)
    
    try:
        # Get the shop item
        item = ShopItem.objects.get(id=item_id, item_type='theme')
        
        # Check if user owns this item
        if not UserPurchase.objects.filter(user=request.user, item=item).exists():
            return JsonResponse({'success': False, 'message': 'You do not own this item'}, status=400)
        
        # Equip the theme
        profile = request.user.profile
        profile.selected_theme = item
        profile.save()
        
        return JsonResponse({
            'success': True, 
            'message': f"Equipped {item.name}!",
            'item_id': item_id,
            'item_name': item.name,
            'css_class': item.css_class
        })
        
    except ShopItem.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Item not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'message': 'An error occurred'}, status=500)


def update_task_progress(user, task_type, increment=1):
    """Update progress for user daily tasks of a specific type"""
    today = timezone.now().date()
    
    # Get today's tasks of the specified type
    user_tasks = UserDailyTask.objects.filter(
        user=user,
        assigned_date=today,
        task__task_type=task_type,
        is_completed=False
    )
    
    completed_tasks = []
    total_xp_gained = 0
    leveled_up = False
    
    for user_task in user_tasks:
        result = user_task.update_progress(increment)
        if result['completed']:
            completed_tasks.append(user_task)
            total_xp_gained += result['xp_gained']
            if result['leveled_up']:
                leveled_up = True
    
    return {
        'completed_tasks': completed_tasks,
        'total_xp_gained': total_xp_gained,
        'leveled_up': leveled_up
    }


def complete_daily_task(request, task_id):
    """Mark a daily task as completed (for manual completion)"""
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'message': 'Authentication required'}, status=401)
    
    if not request.user.profile.is_student():
        return JsonResponse({'success': False, 'message': 'Only students can complete tasks'}, status=403)
    
    try:
        user_task = get_object_or_404(UserDailyTask, id=task_id, user=request.user)
        
        if user_task.is_completed:
            return JsonResponse({'success': False, 'message': 'Task already completed'}, status=400)
        
        # Complete the task
        user_task.current_progress = user_task.task.target_value
        completed = user_task.update_progress(0)  # Just trigger completion check
        
        if completed:
            return JsonResponse({
                'success': True, 
                'message': f'Task completed! Earned {user_task.task.reward_coins} coins and {user_task.task.reward_points} points!',
                'coins_earned': user_task.task.reward_coins,
                'points_earned': user_task.task.reward_points
            })
        else:
            return JsonResponse({'success': False, 'message': 'Failed to complete task'}, status=500)
            
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error: {str(e)}'}, status=500)


def submit_rating(request):
    """Submit user rating for the platform"""
    
    # Only allow POST requests
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST method required'}, status=405)
    
    # Check if user is a student
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'message': 'Authentication required'}, status=401)
    
    # Check if user has profile
    if not hasattr(request.user, 'profile'):
        return JsonResponse({'success': False, 'message': 'Profile not found'}, status=400)
    
    # Check if user is a student
    if not request.user.profile.is_student():
        return JsonResponse({'success': False, 'message': 'Access denied - students only'}, status=403)
    
    try:
        rating = int(request.POST.get('rating', 0))
        if rating < 1 or rating > 5:
            return JsonResponse({'success': False, 'message': 'Rating must be between 1 and 5'}, status=400)
        
        # Update user's rating
        profile = request.user.profile
        profile.user_rating = rating
        profile.save()
        
        return JsonResponse({'success': True, 'message': 'Rating submitted successfully!'})
    except (ValueError, TypeError):
        return JsonResponse({'success': False, 'message': 'Invalid rating value'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error: {str(e)}'}, status=500)


def check_achievements(user):
    """Check and award achievements to user"""
    profile = user.profile
    
    # Get all achievements user doesn't have
    earned_achievements = UserAchievement.objects.filter(user=user).values_list('achievement_id', flat=True)
    available_achievements = Achievement.objects.exclude(
        id__in=earned_achievements
    ).filter(is_hidden=False)
    
    for achievement in available_achievements:
        earned = False
        
        # Check points requirement
        if achievement.points_required > 0 and profile.total_points >= achievement.points_required:
            earned = True
        
        # Check games requirement
        if achievement.games_required > 0 and profile.games_played >= achievement.games_required:
            earned = True
        
        if earned:
            # Award achievement
            UserAchievement.objects.create(user=user, achievement=achievement)
            
            # Give coin reward
            profile.coins += achievement.reward_coins
            profile.save()


def award_game_points(user, score, total_possible_score):
    """Award points to user based on game performance"""
    profile = user.profile
    
    # Calculate points (1-10 based on performance)
    if total_possible_score > 0:
        percentage = (score / total_possible_score) * 100
        if percentage >= 90:
            points = 10
        elif percentage >= 80:
            points = 8
        elif percentage >= 70:
            points = 6
        elif percentage >= 60:
            points = 4
        elif percentage >= 50:
            points = 3
        else:
            points = max(1, int(percentage / 20))  # Minimum 1 point
    else:
        points = 1
    
    # Award points and coins
    profile.total_points += points
    profile.coins += points // 2  # Half the points as coins
    profile.games_played += 1
    profile.save()
    
    # Check for new achievements
    check_achievements(user)
    
    return points


def get_or_create_daily_tasks(user):
    """Get or create daily tasks for a user for today"""
    today = timezone.now().date()
    
    # Check if user already has tasks for today
    existing_tasks = UserDailyTask.objects.filter(
        user=user, 
        assigned_date=today
    )
    
    if existing_tasks.count() >= 3:
        return existing_tasks
    
    # If not enough tasks, generate new ones
    existing_tasks.delete()  # Remove partial tasks
    
    # Get all available tasks
    available_tasks = list(DailyTask.objects.filter(is_active=True))
    
    if len(available_tasks) < 3:
        return UserDailyTask.objects.none()  # Return empty queryset if not enough tasks
    
    # Select 3 random tasks
    selected_tasks = random.sample(available_tasks, 3)
    
    # Create user daily tasks
    user_tasks = []
    for task in selected_tasks:
        user_task = UserDailyTask.objects.create(
            user=user,
            task=task,
            assigned_date=today
        )
        user_tasks.append(user_task)
    
    return UserDailyTask.objects.filter(id__in=[task.id for task in user_tasks])