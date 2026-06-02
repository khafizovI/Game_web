from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from .models import (
    Profile,
    EmailVerification,
    PasswordResetCode,
    ShopItem,
    UserPurchase,
    InventoryItem,
    UserInventoryItem,
    Pet,
    UserPet,
    Achievement,
    UserAchievement,
    DailyTask,
    UserDailyTask,
)
from quiz.models import Quiz
from game.models import Game, GamePlayer, PlayerAnswer
from .forms import (
    CustomUserCreationForm,
    LoginForm,
    EmailVerificationForm,
    PasswordResetEmailForm,
    PasswordResetCodeForm,
    SetNewPasswordForm,
    append_css_class,
)
from django.contrib.auth import authenticate, login, logout
from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse
from django.http import JsonResponse
from django.db.models import Count, Q
from django.db import transaction
from django.utils import timezone
from django.template.loader import render_to_string
from datetime import timedelta
from django.views.decorators.csrf import csrf_exempt
from functools import wraps
import random
from django.views.decorators.http import require_http_methods
from django.utils.translation import gettext as _
import json
import logging
from quizgame.translation_utils import translate_text, translate_text_for_request


DEFAULT_DAILY_TASKS = [
    {
        'name': 'Game Starter',
        'description': 'Play 1 game today',
        'task_type': 'play_games',
        'target_value': 1,
        'reward_coins': 10,
        'reward_points': 25,
        'icon': 'fas fa-gamepad',
    },
    {
        'name': 'Game Marathon',
        'description': 'Play 3 games today',
        'task_type': 'play_games',
        'target_value': 3,
        'reward_coins': 25,
        'reward_points': 60,
        'icon': 'fas fa-fire',
    },
    {
        'name': 'Sharp Mind',
        'description': 'Answer 5 questions correctly',
        'task_type': 'answer_correctly',
        'target_value': 5,
        'reward_coins': 20,
        'reward_points': 50,
        'icon': 'fas fa-brain',
    },
    {
        'name': 'Perfect Run',
        'description': 'Answer 10 questions correctly',
        'task_type': 'answer_correctly',
        'target_value': 10,
        'reward_coins': 35,
        'reward_points': 85,
        'icon': 'fas fa-bullseye',
    },
    {
        'name': 'Point Collector',
        'description': 'Earn 10 points from games',
        'task_type': 'earn_points',
        'target_value': 10,
        'reward_coins': 15,
        'reward_points': 35,
        'icon': 'fas fa-star',
    },
    {
        'name': 'Quiz Finisher',
        'description': 'Finish 2 full games today',
        'task_type': 'complete_quiz',
        'target_value': 2,
        'reward_coins': 30,
        'reward_points': 75,
        'icon': 'fas fa-flag-checkered',
    },
]

COSMETIC_BOXES = {
    'common': {
        'name': 'Common Box',
        'price': 60,
        'icon': 'fa-box',
        'rarity_weights': {'common': 72, 'rare': 22, 'epic': 6, 'legendary': 0},
    },
    'rare': {
        'name': 'Rare Box',
        'price': 130,
        'icon': 'fa-gem',
        'rarity_weights': {'common': 38, 'rare': 42, 'epic': 17, 'legendary': 3},
    },
    'epic': {
        'name': 'Epic Box',
        'price': 260,
        'icon': 'fa-wand-magic-sparkles',
        'rarity_weights': {'common': 16, 'rare': 34, 'epic': 40, 'legendary': 10},
    },
    'legendary': {
        'name': 'Legendary Box',
        'price': 520,
        'icon': 'fa-crown',
        'rarity_weights': {'common': 4, 'rare': 18, 'epic': 42, 'legendary': 36},
    },
}

PET_BOX = {
    'name': 'Pet Box',
    'price': 300,
    'icon': 'fa-paw',
}

AVATAR_BOXES = {
    'girls': {
        'name': 'Girls Box',
        'price': 100,
        'icon': 'fa-venus',
        'accent': 'girls',
    },
    'boys': {
        'name': 'Boys Box',
        'price': 120,
        'icon': 'fa-mars',
        'accent': 'boys',
    },
}

DEFAULT_INVENTORY_ITEMS = [
    ('Neon Rookie', 'avatar', 'common', 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128"%3E%3Crect width="128" height="128" rx="64" fill="%2314b8a6"/%3E%3Ccircle cx="46" cy="54" r="10" fill="white"/%3E%3Ccircle cx="82" cy="54" r="10" fill="white"/%3E%3Cpath d="M42 84c15 12 35 12 50 0" stroke="white" stroke-width="8" fill="none" stroke-linecap="round"/%3E%3C/svg%3E', 'avatar-neon-rookie'),
    ('Quiz Spark', 'avatar', 'rare', 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128"%3E%3Crect width="128" height="128" rx="64" fill="%233b82f6"/%3E%3Cpath d="M68 12 34 72h26l-8 44 42-66H68z" fill="%23facc15"/%3E%3C/svg%3E', 'avatar-quiz-spark'),
    ('Arcane Mind', 'avatar', 'epic', 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128"%3E%3Crect width="128" height="128" rx="64" fill="%237c3aed"/%3E%3Ccircle cx="64" cy="64" r="34" fill="%23f0abfc"/%3E%3Cpath d="M34 64h60M64 34v60M42 42l44 44M86 42 42 86" stroke="%23fff" stroke-width="6" stroke-linecap="round"/%3E%3C/svg%3E', 'avatar-arcane-mind'),
    ('Crown Solver', 'avatar', 'legendary', 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128"%3E%3Crect width="128" height="128" rx="64" fill="%23111827"/%3E%3Cpath d="m24 52 22 18 18-34 18 34 22-18-8 44H32z" fill="%23facc15"/%3E%3Ccircle cx="64" cy="78" r="12" fill="%23fff7ed"/%3E%3C/svg%3E', 'avatar-crown-solver'),
    ('Aqua Ring', 'border', 'common', 'Aqua', 'aqua-border'),
    ('Solar Ring', 'border', 'rare', 'Solar', 'solar-border'),
    ('Plasma Ring', 'border', 'epic', 'Plasma', 'plasma-border'),
    ('Royal Crown Ring', 'border', 'legendary', 'Royal', 'royal-crown-border'),
    ('Fresh Start Banner', 'banner', 'common', 'Fresh Start', 'fresh-banner'),
    ('Night League Banner', 'banner', 'rare', 'Night League', 'night-banner'),
    ('Victory Pulse Banner', 'banner', 'epic', 'Victory Pulse', 'victory-banner'),
    ('Champion Aurora Banner', 'banner', 'legendary', 'Champion Aurora', 'aurora-banner'),
    ('Fast Thinker', 'title', 'common', 'Fast Thinker', 'title-fast-thinker'),
    ('Quiz Hunter', 'title', 'rare', 'Quiz Hunter', 'title-quiz-hunter'),
    ('Brainstormer', 'title', 'epic', 'Brainstormer', 'title-brainstormer'),
    ('Legend of Logic', 'title', 'legendary', 'Legend of Logic', 'title-legend-logic'),
]

DEFAULT_AVATAR_ITEMS = [
    ('Girls Avatar 1', 'avatar', 'common', '/static/avatars/girls.png', 'avatar-girls-1', 'girls'),
    ('Girls Avatar 2', 'avatar', 'rare', '/static/avatars/girls2.png', 'avatar-girls-2', 'girls'),
    ('Girls Avatar 3', 'avatar', 'epic', '/static/avatars/girls3.png', 'avatar-girls-3', 'girls'),
    ('Girls Avatar 4', 'avatar', 'legendary', '/static/avatars/girls4.png', 'avatar-girls-4', 'girls'),
    ('Boys Avatar 1', 'avatar', 'common', '/static/avatars/boys.png', 'avatar-boys-1', 'boys'),
    ('Boys Avatar 2', 'avatar', 'rare', '/static/avatars/boys2.png', 'avatar-boys-2', 'boys'),
    ('Boys Avatar 3', 'avatar', 'epic', '/static/avatars/boys3.png', 'avatar-boys-3', 'boys'),
    ('Boys Avatar 4', 'avatar', 'legendary', '/static/avatars/boys4.png', 'avatar-boys-4', 'boys'),
]

DEFAULT_PETS = [
    ('Cat', '😸', 'common', 28),
    ('Dog', '🐶', 'common', 28),
    ('Cow', '🐮', 'common', 20),
    ('Fox', '🦊', 'rare', 14),
    ('Panda', '🐼', 'rare', 11),
    ('Owl', '🦉', 'epic', 7),
    ('Penguin', '🐧', 'epic', 6),
    ('Robot', '🤖', 'legendary', 2),
]

DEFAULT_PETS = [
    ('Cat', '/static/pets/cat/default.png', 'common', 28),
    ('Robot', '/static/pets/cat/robot/default.png', 'legendary', 2),
]


def ensure_shop_catalog():
    for name, item_type, rarity, preview_value, css_class in DEFAULT_INVENTORY_ITEMS:
        InventoryItem.objects.update_or_create(
            name=name,
            item_type=item_type,
            defaults={
                'description': f'{rarity.title()} {InventoryItem(item_type=item_type).get_item_type_display()} cosmetic.',
                'rarity': rarity,
                'preview_value': preview_value,
                'css_class': css_class,
                'is_active': True,
            },
        )

    for name, item_type, rarity, preview_value, css_class, group in DEFAULT_AVATAR_ITEMS:
        InventoryItem.objects.update_or_create(
            name=name,
            item_type=item_type,
            defaults={
                'description': f'{group.title()} avatar from the {group.title()} Box.',
                'rarity': rarity,
                'preview_value': preview_value,
                'css_class': css_class,
                'is_active': True,
            },
        )

    active_pet_names = [name for name, _, _, _ in DEFAULT_PETS]
    Pet.objects.exclude(name__in=active_pet_names).update(is_active=False)
    Profile.objects.filter(selected_pet__pet__is_active=False).update(selected_pet=None)

    for name, image, rarity, weight in DEFAULT_PETS:
        Pet.objects.update_or_create(
            name=name,
            defaults={'image': image, 'rarity': rarity, 'weight': weight, 'is_active': True},
        )


def choose_weighted_key(weights):
    entries = [(key, weight) for key, weight in weights.items() if weight > 0]
    return random.choices([key for key, _ in entries], weights=[weight for _, weight in entries], k=1)[0]


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

            try:
                verification = EmailVerification.generate_code(user)
                send_verification_email(user, verification.code, request.LANGUAGE_CODE)
            except Exception:
                messages.error(
                    request,
                    translate_text_for_request(
                        request,
                        "We could not send the verification email right now. Please try again later."
                    ),
                )
                user.delete()
                return render(request, 'accounts/register.html', {'form': form})

            # Store user ID in session for verification
            request.session['pending_user_id'] = user.id
            
            messages.info(
                request,
                translate_text_for_request(
                    request,
                    "Welcome, {username}! Please check your email ({email}) for a verification code.",
                    username=username,
                    email=email,
                ),
            )
            return redirect('accounts:verify_email')
        # If form is not valid, it will be rendered again with errors and preserved data
    else:
        form = CustomUserCreationForm()
    return render(request, 'accounts/register.html', {'form': form})


def send_verification_email(user, code, language_code='en'):
    subject = translate_text('Verify Your Email - Quiz Game', language_code)
    message = "\n".join([
        translate_text('Hi {username},', language_code, username=user.username),
        "",
        translate_text(
            'Welcome to Quiz Game! Please use the following verification code to complete your registration:',
            language_code,
        ),
        "",
        translate_text('Verification Code: {code}', language_code, code=code),
        "",
        translate_text('This code will expire in 10 minutes.', language_code),
        "",
        translate_text("If you didn't create an account, please ignore this email.", language_code),
        "",
        translate_text('Best regards,', language_code),
        translate_text('Quiz Game Team', language_code),
    ])

    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
    except Exception:
        logging.getLogger(__name__).exception("Failed to send verification email to %s", user.email)
        raise


def send_password_reset_email(user, code, language_code='en'):
    subject = translate_text('Reset Your QuizBattle Password', language_code)
    text_message = "\n".join([
        translate_text('Hi {username},', language_code, username=user.username),
        "",
        translate_text('Use this code to reset your QuizBattle password:', language_code),
        "",
        code,
        "",
        translate_text('This code will expire in 10 minutes.', language_code),
        translate_text("If you didn't request a password reset, you can ignore this email.", language_code),
    ])
    html_message = render_to_string('accounts/emails/password_reset_code.html', {
        'user': user,
        'code': code,
    })

    try:
        send_mail(
            subject,
            text_message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
            html_message=html_message,
        )
    except Exception:
        logging.getLogger(__name__).exception("Failed to send password reset email to %s", user.email)
        raise


def verify_email(request):
    user_id = request.session.get('pending_user_id')
    if not user_id:
        messages.error(request, translate_text_for_request(request, 'No pending registration found.'))
        return redirect('accounts:register')
    
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        messages.error(request, translate_text_for_request(request, 'Invalid registration session.'))
        return redirect('accounts:register')
    
    if request.method == 'POST':
        if 'resend_code' in request.POST:
            try:
                verification = EmailVerification.generate_code(user)
                send_verification_email(user, verification.code, request.LANGUAGE_CODE)
                messages.success(request, translate_text_for_request(request, 'New verification code sent to your email.'))
            except Exception:
                messages.error(
                    request,
                    translate_text_for_request(
                        request,
                        'We could not send the verification email right now. Please try again later.'
                    ),
                )
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
                    
                    messages.success(
                        request,
                        translate_text_for_request(
                            request,
                            'Email verified successfully! Welcome, {username}!',
                            username=user.username,
                        ),
                    )
                    return redirect('home')
                else:
                    form.add_error('code', _('Verification code has expired. Please request a new one.'))
            except EmailVerification.DoesNotExist:
                form.add_error('code', _('Invalid verification code.'))
        # If form is not valid, it will be rendered again with errors
    else:
        form = EmailVerificationForm(user=user)
    
    return render(request, 'accounts/verify_email.html', {'form': form, 'user': user})


def forgot_password(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = PasswordResetEmailForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email'].strip()
            user = User.objects.filter(email__iexact=email).first()
            if not user:
                form.add_error('email', _('No account was found with this email address.'))
            else:
                reset_code = PasswordResetCode.generate_code(user)
                try:
                    send_password_reset_email(user, reset_code.code, request.LANGUAGE_CODE)
                except Exception:
                    messages.error(
                        request,
                        translate_text_for_request(
                            request,
                            'We could not send the reset email right now. Please try again later.'
                        ),
                    )
                    return render(request, 'accounts/forgot_password.html', {'form': form})

                request.session['password_reset_user_id'] = user.id
                request.session.pop('password_reset_verified', None)
                messages.info(request, translate_text_for_request(request, 'A reset code has been sent to your email.'))
                return redirect('accounts:forgot_password_code')
    else:
        form = PasswordResetEmailForm()

    return render(request, 'accounts/forgot_password.html', {'form': form})


def forgot_password_code(request):
    user_id = request.session.get('password_reset_user_id')
    if not user_id:
        return redirect('accounts:forgot_password')

    user = get_object_or_404(User, id=user_id)

    if request.method == 'POST':
        if 'resend_code' in request.POST:
            reset_code = PasswordResetCode.generate_code(user)
            try:
                send_password_reset_email(user, reset_code.code, request.LANGUAGE_CODE)
                messages.success(request, translate_text_for_request(request, 'New reset code sent to your email.'))
            except Exception:
                messages.error(
                    request,
                    translate_text_for_request(
                        request,
                        'We could not send the reset email right now. Please try again later.'
                    ),
                )
            return render(request, 'accounts/forgot_password_code.html', {'form': PasswordResetCodeForm(), 'user': user})

        form = PasswordResetCodeForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data['code']
            reset_code = PasswordResetCode.objects.filter(user=user, code=code, is_used=False).order_by('-created_at').first()
            if not reset_code:
                form.add_error('code', _('Invalid reset code.'))
            elif reset_code.is_expired():
                form.add_error('code', _('Reset code has expired. Please request a new one.'))
            else:
                request.session['password_reset_verified'] = True
                request.session['password_reset_code_id'] = reset_code.id
                return redirect('accounts:reset_password')
    else:
        form = PasswordResetCodeForm()

    return render(request, 'accounts/forgot_password_code.html', {'form': form, 'user': user})


def reset_password(request):
    user_id = request.session.get('password_reset_user_id')
    verified = request.session.get('password_reset_verified')
    code_id = request.session.get('password_reset_code_id')
    if not user_id or not verified or not code_id:
        return redirect('accounts:forgot_password')

    user = get_object_or_404(User, id=user_id)
    reset_code = PasswordResetCode.objects.filter(id=code_id, user=user, is_used=False).first()
    if not reset_code or reset_code.is_expired():
        messages.error(request, translate_text_for_request(request, 'Reset session expired. Please request a new code.'))
        request.session.pop('password_reset_verified', None)
        request.session.pop('password_reset_code_id', None)
        return redirect('accounts:forgot_password')

    if request.method == 'POST':
        form = SetNewPasswordForm(request.POST)
        if form.is_valid():
            user.set_password(form.cleaned_data['password1'])
            user.save()
            reset_code.is_used = True
            reset_code.save(update_fields=['is_used'])
            request.session.pop('password_reset_user_id', None)
            request.session.pop('password_reset_verified', None)
            request.session.pop('password_reset_code_id', None)
            messages.success(request, translate_text_for_request(request, 'Your password has been updated. You can log in now.'))
            return redirect('accounts:login')
    else:
        form = SetNewPasswordForm()

    return render(request, 'accounts/reset_password.html', {'form': form})


# This is the corrected login view that preserves data on error
def login_view(request):
    """Custom login view that preserves data on error."""
    if request.method == 'POST':
        # Bind data to the form
        form = LoginForm(data=request.POST)
        if form.is_valid():
            username_or_email = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')

            auth_username = username_or_email
            if username_or_email and '@' in username_or_email:
                email_user = User.objects.filter(email__iexact=username_or_email, is_active=True).order_by('id').first()
                if email_user:
                    auth_username = email_user.username

            user = authenticate(request, username=auth_username, password=password)

            if user is not None:
                # Check if email is verified
                if hasattr(user, 'profile') and not user.profile.email_verified:
                    try:
                        verification = EmailVerification.generate_code(user)
                        send_verification_email(user, verification.code, request.LANGUAGE_CODE)
                        request.session['pending_user_id'] = user.id
                        messages.warning(
                            request,
                            translate_text_for_request(
                                request,
                                'Please verify your email before logging in. A new verification code has been sent.'
                            ),
                        )
                        return redirect('accounts:verify_email')
                    except Exception:
                        messages.error(
                            request,
                            translate_text_for_request(
                                request,
                                'We could not send the verification email right now. Please try again later.'
                            ),
                        )
                        return render(request, 'accounts/login.html', {
                            'form': form,
                            'next': request.POST.get('next') or request.GET.get('next', '')
                        })
                
                login(request, user)
                next_page = request.POST.get('next')
                if next_page:
                    return redirect(next_page)
                return redirect('home')
            else:
                # This error is for invalid username/password
                form.add_error(None, _('Invalid username/email or password.'))
                append_css_class(form.fields['username'].widget, 'is-invalid')
                append_css_class(form.fields['password'].widget, 'is-invalid')
        # If form is not valid, it will be rendered again with errors and preserved data
    else:
        # For GET requests, create a new, empty form
        form = LoginForm()

    # For GET requests or failed POST requests, render the page with the form object
    return render(request, 'accounts/login.html', {
        'form': form,
        'next': request.POST.get('next') or request.GET.get('next', '')
    })


@require_http_methods(["GET", "POST"])
def logout_view(request):
    logout(request)
    messages.info(
        request,
        translate_text_for_request(request, 'You have been logged out successfully.'),
    )
    return redirect('home')


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
            try:
                profile.set_avatar_upload(request.FILES['avatar'])
            except ValueError as exc:
                messages.error(request, str(exc))
                return redirect('accounts:edit_profile')

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
    if profile.is_teacher():
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
    
    if not request.user.profile.is_teacher():
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
            try:
                profile.set_avatar_upload(request.FILES['avatar'])
            except ValueError as exc:
                messages.error(request, str(exc))
                return redirect('accounts:student_dashboard')
        
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
    
    ensure_shop_catalog()
    profile = request.user.profile
    recent_items = UserInventoryItem.objects.filter(user=request.user).select_related('item')[:8]
    recent_pets = UserPet.objects.filter(user=request.user, pet__is_active=True).select_related('pet')[:8]
    owned_item_ids = set(UserInventoryItem.objects.filter(user=request.user).values_list('item_id', flat=True))
    avatar_boxes = {}

    for key, box in AVATAR_BOXES.items():
        group_prefix = 'Girls Avatar' if key == 'girls' else 'Boys Avatar'
        pool_ids = list(InventoryItem.objects.filter(
            item_type='avatar',
            name__startswith=group_prefix,
            is_active=True,
        ).values_list('id', flat=True))
        box_data = box.copy()
        box_data['total_items'] = len(pool_ids)
        box_data['owned_items'] = len([item_id for item_id in pool_ids if item_id in owned_item_ids])
        box_data['is_complete'] = bool(pool_ids) and box_data['owned_items'] >= box_data['total_items']
        avatar_boxes[key] = box_data

    context = {
        'profile': profile,
        'cosmetic_boxes': COSMETIC_BOXES,
        'avatar_boxes': avatar_boxes,
        'pet_box': PET_BOX,
        'recent_items': recent_items,
        'recent_pets': recent_pets,
    }
    
    return render(request, 'accounts/shop.html', context)


@login_required
@require_http_methods(["POST"])
def open_cosmetic_box(request, box_key):
    if not request.user.profile.is_student():
        return JsonResponse({'success': False, 'message': 'Access denied'}, status=403)

    ensure_shop_catalog()
    box = COSMETIC_BOXES.get(box_key)
    if not box:
        return JsonResponse({'success': False, 'message': 'Box not found'}, status=404)

    with transaction.atomic():
        profile = Profile.objects.select_for_update().get(user=request.user)
        if profile.coins < box['price']:
            return JsonResponse({'success': False, 'message': 'Not enough coins'}, status=400)

        rarity = choose_weighted_key(box['rarity_weights'])
        pool = list(InventoryItem.objects.filter(rarity=rarity, is_active=True))
        if not pool:
            pool = list(InventoryItem.objects.filter(is_active=True))
        if not pool:
            return JsonResponse({'success': False, 'message': 'No cosmetic items are available'}, status=500)

        owned_ids = set(UserInventoryItem.objects.filter(user=request.user).values_list('item_id', flat=True))
        unowned_pool = [item for item in pool if item.id not in owned_ids]
        if not unowned_pool:
            return JsonResponse({'success': False, 'message': 'This case is closed'}, status=400)

        item = random.choice(unowned_pool)
        is_duplicate = False

        profile.coins -= box['price']
        profile.save(update_fields=['coins'])
        if not is_duplicate:
            UserInventoryItem.objects.create(user=request.user, item=item)

    return JsonResponse({
        'success': True,
        'message': 'Box opened!',
        'new_coin_balance': profile.coins,
        'duplicate': is_duplicate,
        'item': {
            'name': item.name,
            'type': item.item_type,
            'type_label': item.get_item_type_display(),
            'rarity': item.rarity,
            'rarity_label': item.get_rarity_display(),
            'preview': item.preview_value,
            'css_class': item.css_class,
        },
    })


@login_required
@require_http_methods(["POST"])
def open_avatar_box(request, box_key):
    if not request.user.profile.is_student():
        return JsonResponse({'success': False, 'message': 'Access denied'}, status=403)

    ensure_shop_catalog()
    box = AVATAR_BOXES.get(box_key)
    if not box:
        return JsonResponse({'success': False, 'message': 'Box not found'}, status=404)

    group_prefix = 'Girls Avatar' if box_key == 'girls' else 'Boys Avatar'
    with transaction.atomic():
        profile = Profile.objects.select_for_update().get(user=request.user)
        if profile.coins < box['price']:
            return JsonResponse({'success': False, 'message': 'Not enough coins'}, status=400)

        pool = list(InventoryItem.objects.filter(item_type='avatar', name__startswith=group_prefix, is_active=True))
        if not pool:
            return JsonResponse({'success': False, 'message': 'No avatars are available'}, status=500)

        owned_ids = set(UserInventoryItem.objects.filter(user=request.user).values_list('item_id', flat=True))
        unowned_pool = [item for item in pool if item.id not in owned_ids]
        if not unowned_pool:
            return JsonResponse({'success': False, 'message': 'This case is closed'}, status=400)

        item = random.choice(unowned_pool)
        is_duplicate = False

        profile.coins -= box['price']
        profile.save(update_fields=['coins'])
        if not is_duplicate:
            UserInventoryItem.objects.create(user=request.user, item=item)

    return JsonResponse({
        'success': True,
        'message': 'Box opened!',
        'new_coin_balance': profile.coins,
        'duplicate': is_duplicate,
        'item': {
            'name': item.name,
            'type': item.item_type,
            'type_label': item.get_item_type_display(),
            'rarity': item.rarity,
            'rarity_label': item.get_rarity_display(),
            'preview': item.preview_value,
            'css_class': item.css_class,
        },
    })


@login_required
@require_http_methods(["POST"])
def open_pet_box(request):
    if not request.user.profile.is_student():
        return JsonResponse({'success': False, 'message': 'Access denied'}, status=403)

    ensure_shop_catalog()
    with transaction.atomic():
        profile = Profile.objects.select_for_update().get(user=request.user)
        if profile.coins < PET_BOX['price']:
            return JsonResponse({'success': False, 'message': 'Not enough coins'}, status=400)

        pets = list(Pet.objects.filter(is_active=True))
        if not pets:
            return JsonResponse({'success': False, 'message': 'No pets are available'}, status=500)

        owned_ids = set(UserPet.objects.filter(user=request.user).values_list('pet_id', flat=True))
        unowned_pets = [pet for pet in pets if pet.id not in owned_ids]
        weighted_pool = unowned_pets or pets
        pet = random.choices(weighted_pool, weights=[entry.weight for entry in weighted_pool], k=1)[0]
        is_duplicate = pet.id in owned_ids

        profile.coins -= PET_BOX['price']
        profile.save(update_fields=['coins'])
        if not is_duplicate:
            user_pet = UserPet.objects.create(user=request.user, pet=pet)
        else:
            user_pet = UserPet.objects.get(user=request.user, pet=pet)

    return JsonResponse({
        'success': True,
        'message': 'Pet unlocked!',
        'new_coin_balance': profile.coins,
        'duplicate': is_duplicate,
        'pet': {
            'id': user_pet.id,
            'name': pet.name,
            'image': pet.image,
            'rarity': pet.rarity,
            'rarity_label': pet.get_rarity_display(),
            'unlocked_at': user_pet.unlocked_at.strftime('%Y-%m-%d %H:%M'),
        },
    })


@login_required
def inventory(request):
    if not request.user.profile.is_student():
        messages.error(request, "Access denied. Students only.")
        return redirect('home')

    ensure_shop_catalog()
    owned_items = UserInventoryItem.objects.filter(user=request.user).select_related('item')
    owned_pets = UserPet.objects.filter(user=request.user, pet__is_active=True).select_related('pet')
    grouped_items = {
        'avatar': owned_items.filter(item__item_type='avatar'),
        'border': owned_items.filter(item__item_type='border'),
        'banner': owned_items.filter(item__item_type='banner'),
        'title': owned_items.filter(item__item_type='title'),
    }
    return render(request, 'accounts/inventory.html', {
        'profile': request.user.profile,
        'grouped_items': grouped_items,
        'owned_pets': owned_pets,
    })


@login_required
@require_http_methods(["POST"])
def equip_inventory_item(request, user_item_id):
    profile = request.user.profile
    user_item = get_object_or_404(UserInventoryItem.objects.select_related('item'), id=user_item_id, user=request.user)
    field_by_type = {
        'avatar': 'selected_avatar',
        'border': 'selected_border',
        'banner': 'selected_banner',
        'title': 'selected_title',
    }
    field = field_by_type[user_item.item.item_type]
    setattr(profile, field, user_item.item)
    if user_item.item.item_type == 'border':
        matching_frame = ShopItem.objects.filter(css_class=user_item.item.css_class, item_type='frame').first()
        if matching_frame:
            profile.selected_frame = matching_frame
    profile.save()
    return JsonResponse({'success': True, 'message': f'Equipped {user_item.item.name}', 'item_type': user_item.item.item_type})


@login_required
@require_http_methods(["POST"])
def unequip_inventory_type(request, item_type):
    field_by_type = {
        'avatar': 'selected_avatar',
        'border': 'selected_border',
        'banner': 'selected_banner',
        'title': 'selected_title',
        'pet': 'selected_pet',
    }
    field = field_by_type.get(item_type)
    if not field:
        return JsonResponse({'success': False, 'message': 'Invalid item type'}, status=400)

    profile = request.user.profile
    setattr(profile, field, None)
    if item_type == 'border':
        profile.selected_frame = None
    profile.save()
    return JsonResponse({'success': True, 'message': 'Unequipped', 'item_type': item_type})


@login_required
@require_http_methods(["POST"])
def equip_pet(request, user_pet_id):
    profile = request.user.profile
    user_pet = get_object_or_404(UserPet.objects.select_related('pet'), id=user_pet_id, user=request.user)
    profile.selected_pet = user_pet
    profile.save(update_fields=['selected_pet'])
    return JsonResponse({'success': True, 'message': f'Equipped {user_pet.pet.name}', 'pet_name': user_pet.pet.name})


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
        'message': translate_text_for_request(
            request,
            'Successfully purchased {item_name}!',
            item_name=item.name,
        ),
        'new_coin_balance': profile.coins,
        'item_type': item.item_type,
        'item_name': item.name,
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
            'message': translate_text_for_request(
                request,
                'Equipped {item_name}!',
                item_name=item.name,
            ),
            'item_id': item_id,
            'item_name': item.name,
            'css_class': item.css_class,
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
            'message': translate_text_for_request(
                request,
                'Equipped {item_name}!',
                item_name=item.name,
            ),
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
                'message': translate_text_for_request(
                    request,
                    'Task completed! Earned {coins} coins and {points} points!',
                    coins=user_task.task.reward_coins,
                    points=user_task.task.reward_points,
                ),
                'coins_earned': user_task.task.reward_coins,
                'points_earned': user_task.task.reward_points
            })
        else:
            return JsonResponse({'success': False, 'message': 'Failed to complete task'}, status=500)
            
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error: {str(e)}'}, status=500)


@require_http_methods(["POST"])
def submit_rating(request):
    """Submit user rating for the platform"""
    
    # Check if user is authenticated
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'message': 'Authentication required'}, status=401)
    
    # Check if user has profile
    if not hasattr(request.user, 'profile'):
        return JsonResponse({'success': False, 'message': 'Profile not found'}, status=400)
    
    # Check if user is a student
    if not request.user.profile.is_student():
        return JsonResponse({'success': False, 'message': 'Access denied - students only'}, status=403)
    
    try:
        # Try to get rating from POST data or JSON body
        rating = None
        if request.content_type == 'application/json':
            try:
                data = json.loads(request.body)
                rating = int(data.get('rating', 0))
            except (json.JSONDecodeError, ValueError):
                return JsonResponse({'success': False, 'message': 'Invalid JSON data'}, status=400)
        else:
            rating = int(request.POST.get('rating', 0))
        
        if rating < 1 or rating > 5:
            return JsonResponse({'success': False, 'message': 'Rating must be between 1 and 5'}, status=400)
        
        # Update user's rating
        profile = request.user.profile
        profile.user_rating = rating
        profile.save()
        
        return JsonResponse({'success': True, 'message': 'Rating submitted successfully!'})
    except (ValueError, TypeError) as e:
        return JsonResponse({'success': False, 'message': f'Invalid rating value: {str(e)}'}, status=400)
    except Exception as e:
        # Log the error for debugging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in submit_rating: {str(e)}", exc_info=True)
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


def ensure_default_daily_tasks():
    """Create a baseline set of daily tasks when the table is empty or incomplete."""
    existing_names = set(DailyTask.objects.values_list('name', flat=True))

    for task_data in DEFAULT_DAILY_TASKS:
        if task_data['name'] in existing_names:
            continue

        DailyTask.objects.create(**task_data)


def award_game_points(user, correct_answers, total_questions):
    """Award points and coins to a student after a game."""
    profile = user.profile

    if total_questions > 0:
        percentage = (correct_answers / total_questions) * 100
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
        elif correct_answers > 0:
            points = max(1, int(percentage / 20))  # Minimum 1 point
        else:
            points = 0
    else:
        points = 0

    coins_earned = min(correct_answers, 10) if correct_answers > 0 else 0

    profile.total_points += points
    profile.coins += coins_earned
    profile.games_played += 1
    profile.save()

    update_task_progress(user, 'play_games', 1)
    update_task_progress(user, 'complete_quiz', 1)
    if points > 0:
        update_task_progress(user, 'earn_points', points)
    if correct_answers > 0:
        update_task_progress(user, 'answer_correctly', correct_answers)

    check_achievements(user)

    return {
        'points_earned': points,
        'coins_earned': coins_earned,
        'correct_answers': correct_answers,
    }


def get_or_create_daily_tasks(user):
    """Get or create daily tasks for a user for today"""
    ensure_default_daily_tasks()
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
