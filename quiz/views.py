from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from .models import Quiz, Question, Answer
from django.db.models import Sum, Avg, Count
import json
import re
from quizgame.moderation import check_and_flag_content, is_ip_blocked

from .utils.ai_quiz_generator import generate_quiz_from_topic
from .constants import MIN_QUIZ_QUESTIONS
from .validators import get_quiz_host_status, validate_question_answers
from django.utils import timezone
from datetime import timedelta
from quizgame.translation_utils import translate_text_for_request
from accounts.subscription_utils import (
    check_ai_generation_allowed,
    get_ai_quota_status,
    record_ai_generation,
)

# Quiz Management Views
@login_required
def browse_quizzes(request):
    """View for browsing all quizzes - Teachers only"""
    # Redirect students to join game page
    if not request.user.profile.is_teacher():
        return redirect('game:join')
    
    # Base queryset with annotations
    quizzes = Quiz.objects.annotate(
        total_points=Sum('questions__points'),
        question_count=Count('questions'),
        games_played=Count('games'),
    ).select_related('created_by__profile')
    
    # Order by creation date (newest first)
    quizzes = quizzes.order_by('-created_at')
    
    # Get statistics for the teacher
    total_quizzes = Quiz.objects.count()
    user_quizzes = Quiz.objects.filter(created_by=request.user).count()
    recent_quizzes = Quiz.objects.filter(created_at__gte=timezone.now() - timedelta(days=7)).count()

    context = {
        'quizzes': quizzes,
        'total_quizzes': total_quizzes,
        'user_quizzes': user_quizzes,
        'recent_quizzes': recent_quizzes,
    }
    return render(request, 'quiz/browse.html', context)

@login_required
def create_quiz(request):
    """View for creating a new quiz, either manually or with AI."""
    if not request.user.profile.is_teacher():
        messages.error(request, "Only teachers can create quizzes.")
        return redirect('accounts:dashboard')

    if request.method == 'POST':
        # Check if IP is blocked
        if is_ip_blocked(request.META.get('REMOTE_ADDR')):
            messages.error(request, "Your IP has been blocked due to suspicious activity.")
            return redirect('home')

        # This branch handles the submission from the frontend JavaScript after AI generation
        if request.POST.get('source') == 'ai':
            title = request.POST.get('title')
            description = request.POST.get('description', '')
            session_token = request.session.pop('ai_generation_token', None)
            posted_token = request.POST.get('ai_generation_token')

            if not session_token or posted_token != session_token:
                messages.error(
                    request,
                    translate_text_for_request(
                        request,
                        "Daily AI limit reached. Upgrade your plan for more generations.",
                    ),
                )
                return render(
                    request,
                    'quiz/create.html',
                    {'ai_quota': get_ai_quota_status(request.user)},
                )

            # Moderation check
            is_suspicious, response = check_and_flag_content(request, f"{title} {description}")
            if is_suspicious:
                return response

            quiz = Quiz.objects.create(
                title=title,
                description=description,
                created_by=request.user
            )

            # Reconstruct questions from POST data
            questions_data = {}
            for key, value in request.POST.items():
                match = re.match(r'questions\[(\d+)\]\[(text|answer|options)\](?:\_(\d+))?', key)
                if match:
                    q_index, q_key, o_index = match.groups()
                    q_index = int(q_index)
                    if q_index not in questions_data:
                        questions_data[q_index] = {'options': []}
                    
                    if q_key == 'options':
                        questions_data[q_index]['options'].append(value)
                    else:
                        questions_data[q_index][q_key] = value

            for index in sorted(questions_data.keys()):
                q_data = questions_data[index]
                question = Question.objects.create(quiz=quiz, text=q_data['text'])
                for o_text in q_data['options']:
                    Answer.objects.create(
                        question=question,
                        text=o_text,
                        is_correct=(o_text == q_data['answer'])
                    )

            if quiz.questions.count() < MIN_QUIZ_QUESTIONS:
                quiz.delete()
                messages.error(
                    request,
                    translate_text_for_request(
                        request,
                        "A quiz must have at least {count} questions.",
                        count=MIN_QUIZ_QUESTIONS,
                    ),
                )
                return render(
                    request,
                    'quiz/create.html',
                    {'ai_quota': get_ai_quota_status(request.user)},
                )

            messages.success(request, 'AI-generated quiz created successfully! You can now edit it.')
            return redirect('quiz:edit', quiz_id=quiz.id)

        # This branch handles the old form-based AI generation (can be deprecated)
        elif 'generate_with_ai' in request.POST:
            allowed, quota = check_ai_generation_allowed(request.user)
            if not allowed:
                messages.error(
                    request,
                    translate_text_for_request(
                        request,
                        "Daily AI limit reached. Upgrade your plan for more generations.",
                    ),
                )
                return render(request, 'quiz/create.html', {'ai_quota': quota})

            title = request.POST.get('title')
            description = request.POST.get('description', '')
            topic = request.POST.get('topic')
            num_questions = int(request.POST.get('num_questions', 5))
            num_options = 4

            # Moderation check
            is_suspicious, response = check_and_flag_content(request, f"{title} {description} {topic}")
            if is_suspicious:
                return response

            if not title or not topic:
                messages.error(request, "Quiz title and a topic for AI generation are required.")
                return render(request, 'quiz/create.html', {'ai_quota': get_ai_quota_status(request.user)})

            if num_questions < MIN_QUIZ_QUESTIONS:
                messages.error(
                    request,
                    translate_text_for_request(
                        request,
                        "A quiz must have at least {count} questions.",
                        count=MIN_QUIZ_QUESTIONS,
                    ),
                )
                return render(request, 'quiz/create.html', {'ai_quota': get_ai_quota_status(request.user)})

            try:
                generated_data = generate_quiz_from_topic(topic, num_questions, num_options)
                if not generated_data or 'questions' not in generated_data:
                    raise ValueError("AI failed to generate valid quiz data.")

                if len(generated_data['questions']) < MIN_QUIZ_QUESTIONS:
                    raise ValueError(
                        translate_text_for_request(
                            request,
                            "A quiz must have at least {count} questions.",
                            count=MIN_QUIZ_QUESTIONS,
                        )
                    )

                record_ai_generation(request.user)
                # Create the quiz
                quiz = Quiz.objects.create(
                    title=title,
                    description=description,
                    created_by=request.user
                )

                # Create questions and answers
                for q_data in generated_data['questions']:
                    question = Question.objects.create(
                        quiz=quiz,
                        text=q_data['question']
                    )
                    for o_text in q_data['options']:
                        Answer.objects.create(
                            question=question,
                            text=o_text,
                            is_correct=(o_text == q_data['answer'])
                        )
                
                messages.success(request, 'AI-generated quiz created successfully! You can now edit it.')
                return redirect('quiz:edit', quiz_id=quiz.id)

            except Exception as e:
                messages.error(
                    request,
                    translate_text_for_request(request, "Could not generate quiz: {error}", error=str(e)),
                )
                return render(
                    request,
                    'quiz/create.html',
                    {'ai_quota': get_ai_quota_status(request.user)},
                )

        # This branch handles manual quiz creation (no questions added)
        elif 'create_manually' in request.POST:
            title = request.POST.get('title')
            description = request.POST.get('description', '')

            # Moderation check
            is_suspicious, response = check_and_flag_content(request, f"{title} {description}")
            if is_suspicious:
                return response

            if not title:
                messages.error(request, 'Quiz title is required.')
                return render(request, 'quiz/create.html', {'ai_quota': get_ai_quota_status(request.user)})

            quiz = Quiz.objects.create(
                title=title,
                description=description,
                created_by=request.user
            )
            messages.success(request, 'Quiz created successfully! You can now add questions.')
            return redirect('quiz:edit', quiz_id=quiz.id)

    return render(
        request,
        'quiz/create.html',
        {'ai_quota': get_ai_quota_status(request.user)},
    )

@login_required
def edit_quiz(request, quiz_id):
    """View for editing an existing quiz and its questions"""
    quiz = get_object_or_404(Quiz, id=quiz_id)
    
    # Ensure the user is the owner of the quiz
    if quiz.created_by != request.user:
        messages.error(request, "You don't have permission to edit this quiz")
        return redirect('quiz:browse')
    
    # Handle basic quiz info updates
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        
        if not title:
            messages.error(request, 'Quiz title is required')
        else:
            quiz.title = title
            quiz.description = description
            quiz.save()
            messages.success(request, 'Quiz details updated successfully')
    
    # Get all questions for this quiz
    questions = Question.objects.filter(quiz=quiz).order_by('order')
    host_status = get_quiz_host_status(quiz)
    
    context = {
        'quiz': quiz,
        'questions': questions,
        'min_questions': MIN_QUIZ_QUESTIONS,
        'can_host': host_status['can_host'],
        'host_status': host_status,
        'delete_confirm_message': translate_text_for_request(
            request,
            "Are you sure you want to delete this quiz? This action cannot be undone.",
        ),
    }
    return render(request, 'quiz/edit.html', context)

@login_required
def delete_quiz(request, quiz_id):
    """Delete a quiz and all related questions."""
    quiz = get_object_or_404(Quiz, id=quiz_id)

    if quiz.created_by != request.user:
        messages.error(request, "You don't have permission to delete this quiz")
        return redirect('quiz:browse')

    if request.method == 'POST':
        quiz_title = quiz.title
        quiz.delete()
        messages.success(
            request,
            translate_text_for_request(
                request,
                'Quiz "{title}" deleted successfully.',
                title=quiz_title,
            ),
        )
        return redirect('quiz:browse')

    return redirect('quiz:edit', quiz_id=quiz_id)

@login_required
def quiz_detail(request, quiz_id):
    """View for viewing a quiz's details"""
    quiz = get_object_or_404(Quiz, id=quiz_id)

    questions = Question.objects.filter(quiz=quiz).prefetch_related('answers').order_by('order')
    
    # Calculate quiz stats
    stats = questions.aggregate(
        total_points=Sum('points'),
        avg_time=Avg('time_limit')
    )
    host_status = get_quiz_host_status(quiz)
    
    context = {
        'quiz': quiz,
        'questions': questions,
        'can_edit': quiz.created_by == request.user,
        'total_points': stats.get('total_points'),
        'avg_time': round(stats.get('avg_time', 0)),
        'min_questions': MIN_QUIZ_QUESTIONS,
        'can_host': host_status['can_host'],
    }
    return render(request, 'quiz/detail.html', context)

@login_required
def manage_quizzes(request):
    """View for managing all quizzes created by a user"""
    # Check if user is a teacher
    if not request.user.profile.is_teacher():
        messages.error(request, "Only teachers can manage quizzes.")
        return redirect('accounts:dashboard')
    
    # Get all quizzes created by the user
    quizzes = Quiz.objects.filter(created_by=request.user).order_by('-created_at')
    
    context = {
        'quizzes': quizzes,
        'delete_confirm_message': translate_text_for_request(
            request,
            "Are you sure you want to delete this quiz? This action cannot be undone.",
        ),
    }
    return render(request, 'quiz/manage.html', context)


# Question Management Views
@login_required
def add_question(request, quiz_id):
    """View for adding a new question to a quiz"""
    quiz = get_object_or_404(Quiz, id=quiz_id)
    
    # Ensure the user is the owner of the quiz
    if quiz.created_by != request.user:
        messages.error(request, "You don't have permission to edit this quiz")
        return redirect('quiz:browse')
    
    if request.method == 'POST':
        text = request.POST.get('text')
        time_limit = request.POST.get('time_limit', 20)
        points = request.POST.get('points', 100)
        
        # Get the answers
        answer_texts = request.POST.getlist('answer_text')
        is_correct_list = request.POST.getlist('is_correct')
        
        if not text:
            messages.error(request, 'Question text is required')
            return redirect('quiz:add_question', quiz_id=quiz.id)

        is_valid, error_key = validate_question_answers(answer_texts, is_correct_list)
        if not is_valid:
            if error_key == "min_answers":
                messages.error(request, "Each question must have at least 2 answers.")
            else:
                messages.error(request, "Please select at least one correct answer.")
            return redirect('quiz:add_question', quiz_id=quiz.id)
        
        # Create the question
        order = Question.objects.filter(quiz=quiz).count()
        question = Question.objects.create(
            quiz=quiz,
            text=text,
            time_limit=time_limit,
            points=points,
            order=order
        )
        
        # Create the answers
        for i, answer_text in enumerate(answer_texts):
            if answer_text:  # Only create if there's text
                is_correct = str(i) in is_correct_list
                Answer.objects.create(
                    question=question,
                    text=answer_text,
                    is_correct=is_correct
                )
        
        messages.success(request, 'Question added successfully')
        return redirect('quiz:edit', quiz_id=quiz.id)
    
    return render(request, 'quiz/add_question.html', {'quiz': quiz})

@login_required
def edit_question(request, question_id):
    """View for editing an existing question"""
    question = get_object_or_404(Question, id=question_id)
    quiz = question.quiz
    
    # Ensure the user is the owner of the quiz
    if quiz.created_by != request.user:
        messages.error(request, "You don't have permission to edit this question")
        return redirect('quiz:browse')
    
    if request.method == 'POST':
        text = request.POST.get('text')
        time_limit = request.POST.get('time_limit', 20)
        points = request.POST.get('points', 100)
        
        # Get the answers
        answer_ids = request.POST.getlist('answer_id')
        answer_texts = request.POST.getlist('answer_text')
        is_correct_list = request.POST.getlist('is_correct')
        
        if not text:
            messages.error(request, 'Question text is required')
        else:
            is_valid, error_key = validate_question_answers(answer_texts, is_correct_list)
            if not is_valid:
                if error_key == "min_answers":
                    messages.error(request, "Each question must have at least 2 answers.")
                else:
                    messages.error(request, "Please select at least one correct answer.")
            else:
                question.text = text
                question.time_limit = time_limit
                question.points = points
                question.save()

                question.answers.all().delete()

                for i, answer_text in enumerate(answer_texts):
                    if answer_text:
                        is_correct = str(i) in is_correct_list
                        Answer.objects.create(
                            question=question,
                            text=answer_text,
                            is_correct=is_correct
                        )

                messages.success(request, 'Question updated successfully')
                return redirect('quiz:edit', quiz_id=quiz.id)
    
    answers = Answer.objects.filter(question=question)
    
    context = {
        'quiz': quiz,
        'question': question,
        'answers': answers,
    }
    return render(request, 'quiz/edit_question.html', context)

@login_required
def delete_question(request, question_id):
    """View for deleting a question"""
    question = get_object_or_404(Question, id=question_id)
    quiz = question.quiz
    
    # Ensure the user is the owner of the quiz
    if quiz.created_by != request.user:
        messages.error(request, "You don't have permission to delete this question")
        return redirect('quiz:browse')
    
    if request.method == 'POST':
        quiz_id = quiz.id
        question.delete()
        
        # Reorder remaining questions
        for i, q in enumerate(Question.objects.filter(quiz=quiz).order_by('order')):
            q.order = i
            q.save()
        
        messages.success(request, 'Question deleted successfully')
        return redirect('quiz:edit', quiz_id=quiz_id)
    
    context = {
        'quiz': quiz,
        'question': question
    }
    return render(request, 'quiz/delete_question.html', context)
