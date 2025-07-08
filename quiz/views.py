from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from .models import Quiz, Question, Answer
from game.models import Game, GamePlayer
from django.db.models import Sum, Avg
import json

# Quiz Management Views
def browse_quizzes(request):
    """View for browsing public quizzes"""
    public_quizzes = Quiz.objects.filter(is_public=True).annotate(
        total_points=Sum('questions__points')
    ).order_by('-created_at')
    
    # Include user's private quizzes if logged in
    if request.user.is_authenticated:
        private_quizzes = Quiz.objects.filter(created_by=request.user, is_public=False).annotate(
            total_points=Sum('questions__points')
        )
        user_quizzes = private_quizzes
    else:
        user_quizzes = None
    
    context = {
        'public_quizzes': public_quizzes,
        'user_quizzes': user_quizzes
    }
    return render(request, 'quiz/browse.html', context)

@login_required
def create_quiz(request):
    """View for creating a new quiz"""
    # Check if user is a teacher
    if not request.user.profile.is_teacher():
        messages.error(request, "Only teachers can create quizzes.")
        return redirect('accounts:dashboard')
        
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        is_public = request.POST.get('is_public') == 'on'
        
        if not title:
            messages.error(request, 'Quiz title is required')
            return redirect('quiz:create')
        
        quiz = Quiz.objects.create(
            title=title,
            description=description,
            created_by=request.user,
            is_public=is_public
        )
        
        messages.success(request, f'Quiz "{title}" has been created! Now add some questions.')
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
        is_public = request.POST.get('is_public') == 'on'
        
        if not title:
            messages.error(request, 'Quiz title is required')
        else:
            quiz.title = title
            quiz.description = description
            quiz.is_public = is_public
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
    
    # Only allow the owner or public quizzes to be viewed
    if not quiz.is_public and quiz.created_by != request.user:
        messages.error(request, "You don't have permission to view this quiz")
        return redirect('quiz:browse')
    
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
