import json
import secrets
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from quizgame.translation_utils import translate_text_for_request
from accounts.subscription_utils import (
    check_ai_generation_allowed,
    get_ai_quota_status,
    record_ai_generation,
)
from .constants import MIN_QUIZ_QUESTIONS
from .utils.ai_quiz_generator import generate_quiz_from_topic


@login_required
def generate_quiz_ai_endpoint(request):
    """API endpoint to generate quiz questions using AI and return as JSON."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST requests are allowed.'}, status=405)

    if not request.user.profile.is_teacher():
        return JsonResponse(
            {'error': translate_text_for_request(request, "Only teachers can create quizzes.")},
            status=403,
        )

    allowed, quota = check_ai_generation_allowed(request.user)
    if not allowed:
        return JsonResponse(
            {
                'error': translate_text_for_request(
                    request,
                    "Daily AI limit reached. Upgrade your plan for more generations.",
                ),
                'quota': quota,
            },
            status=429,
        )

    try:
        data = json.loads(request.body)
        topic = data.get('topic')
        num_questions = int(data.get('num_questions', 5))
        num_options = 4

        if not topic:
            return JsonResponse({'error': 'A topic for AI generation is required.'}, status=400)

        if num_questions < MIN_QUIZ_QUESTIONS:
            return JsonResponse(
                {
                    'error': translate_text_for_request(
                        request,
                        "A quiz must have at least {count} questions.",
                        count=MIN_QUIZ_QUESTIONS,
                    )
                },
                status=400,
            )

        generated_data = generate_quiz_from_topic(topic, num_questions, num_options)
        if not generated_data or 'questions' not in generated_data:
            return JsonResponse({'error': 'AI failed to generate valid quiz data.'}, status=500)

        record_ai_generation(request.user)
        quota = get_ai_quota_status(request.user)
        generation_token = secrets.token_hex(16)
        request.session['ai_generation_token'] = generation_token
        request.session.modified = True

        return JsonResponse({
            **generated_data,
            'quota': quota,
            'generation_token': generation_token,
        })

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON in request body.'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Could not generate quiz: {str(e)}'}, status=500)
