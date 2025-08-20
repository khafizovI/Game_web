from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from .models import Quiz, Question, Answer
from game.models import Game, GamePlayer
from django.db.models import Sum, Avg, Count
import json
import re
from quizgame.moderation import check_and_flag_content, is_ip_blocked

# Import AI libraries
import torch
from transformers import T5ForConditionalGeneration, T5Tokenizer

from .utils.ai_quiz_generator import generate_quiz_from_topic
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta

# Quiz Management Views
@login_required
def browse_quizzes(request):
    """View for browsing all quizzes - Teachers only"""
    # Redirect students to join game page
    if not request.user.profile.is_teacher:
        return redirect('game:join')
    
    # Get search query if provided
    search_query = request.GET.get('search', '').strip()
    
    # Base queryset with annotations
    quizzes = Quiz.objects.annotate(
        total_points=Sum('questions__points'),
        question_count=Count('questions')
    ).select_related('created_by__profile')
    
    # Apply search filter if provided
    if search_query:
        quizzes = quizzes.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(created_by__username__icontains=search_query)
        )
    
    # Order by creation date (newest first)
    quizzes = quizzes.order_by('-created_at')
    
    # Get statistics for the teacher
    total_quizzes = Quiz.objects.count()
    user_quizzes = Quiz.objects.filter(created_by=request.user).count()
    recent_quizzes = Quiz.objects.filter(created_at__gte=timezone.now() - timedelta(days=7)).count()

    context = {
        'quizzes': quizzes,
        'search_query': search_query,
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

            messages.success(request, 'AI-generated quiz created successfully! You can now edit it.')
            return redirect('quiz:edit', quiz_id=quiz.id)

        # This branch handles the old form-based AI generation (can be deprecated)
        elif 'generate_with_ai' in request.POST:
            title = request.POST.get('title')
            description = request.POST.get('description', '')
            topic = request.POST.get('topic')
            num_questions = int(request.POST.get('num_questions', 5))
            num_options = int(request.POST.get('num_options', 4))

            # Moderation check
            is_suspicious, response = check_and_flag_content(request, f"{title} {description} {topic}")
            if is_suspicious:
                return response

            if not title or not topic:
                messages.error(request, "Quiz title and a topic for AI generation are required.")
                return render(request, 'quiz/create.html')

            try:
                generated_data = generate_quiz_from_topic(topic, num_questions, num_options)
                if not generated_data or 'questions' not in generated_data:
                    raise ValueError("AI failed to generate valid quiz data.")
                
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
                messages.error(request, f"Could not generate quiz: {e}")
                return render(request, 'quiz/create.html')

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
                return render(request, 'quiz/create.html')

            quiz = Quiz.objects.create(
                title=title,
                description=description,
                created_by=request.user
            )
            messages.success(request, 'Quiz created successfully! You can now add questions.')
            return redirect('quiz:edit', quiz_id=quiz.id)

    return render(request, 'quiz/create.html')

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
    
    context = {
        'quiz': quiz,
        'questions': questions
    }
    return render(request, 'quiz/edit.html', context)

@login_required
def quiz_detail(request, quiz_id):
    """View for viewing a quiz's details"""
    quiz = get_object_or_404(Quiz, id=quiz_id)

    questions = Question.objects.filter(quiz=quiz).order_by('order')
    
    # Calculate quiz stats
    stats = questions.aggregate(
        total_points=Sum('points'),
        avg_time=Avg('time_limit')
    )
    
    # Get leaderboard data (top 5 players)
    leaderboard_entries = GamePlayer.objects.filter(
        game__quiz=quiz, 
        game__is_completed=True
    ).order_by('-score')[:5]
    
    context = {
        'quiz': quiz,
        'questions': questions,
        'can_edit': quiz.created_by == request.user,
        'total_points': stats.get('total_points'),
        'avg_time': round(stats.get('avg_time', 0)),
        'leaderboard_entries': leaderboard_entries
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
        'quizzes': quizzes
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
            # Update the question
            question.text = text
            question.time_limit = time_limit
            question.points = points
            question.save()
            
            # First, delete all existing answers
            question.answers.all().delete()
            
            # Then create the new answers
            for i, answer_text in enumerate(answer_texts):
                if answer_text:  # Only create if there's text
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
        'answers': answers
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
