from django.urls import path
from . import views, api_views

app_name = 'quiz'

urlpatterns = [
    path('browse/', views.browse_quizzes, name='browse'),
    path('create/', views.create_quiz, name='create'),
    path('ai-generate/', api_views.generate_quiz_ai_endpoint, name='ai_generate'),
    path('<int:quiz_id>/edit/', views.edit_quiz, name='edit'),
    path('<int:quiz_id>/', views.quiz_detail, name='detail'),
    path('question/add/<int:quiz_id>/', views.add_question, name='add_question'),
    path('question/edit/<int:question_id>/', views.edit_question, name='edit_question'),
    path('question/delete/<int:question_id>/', views.delete_question, name='delete_question'),
    path('manage/', views.manage_quizzes, name='manage'),
]
