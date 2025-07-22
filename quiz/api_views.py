import json
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .utils.ai_quiz_generator import generate_quiz_from_topic

@login_required
def generate_quiz_ai_endpoint(request):
    """API endpoint to generate quiz questions using AI and return as JSON."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            topic = data.get('topic')
            num_questions = int(data.get('num_questions', 5))
            num_options = int(data.get('num_options', 4))

            if not topic:
                return JsonResponse({'error': 'A topic for AI generation is required.'}, status=400)

            generated_data = generate_quiz_from_topic(topic, num_questions, num_options)
            if not generated_data or 'questions' not in generated_data:
                return JsonResponse({'error': 'AI failed to generate valid quiz data.'}, status=500)

            return JsonResponse(generated_data)

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON in request body.'}, status=400)
        except Exception as e:
            return JsonResponse({'error': f'Could not generate quiz: {str(e)}'}, status=500)

    return JsonResponse({'error': 'Only POST requests are allowed.'}, status=405)
