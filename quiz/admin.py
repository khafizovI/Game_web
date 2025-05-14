from django.contrib import admin
from .models import Quiz, Question, Answer

# Register your models here.

class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 4
    max_num = 4

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('text', 'quiz', 'time_limit', 'points')
    list_filter = ('quiz',)
    search_fields = ('text',)
    inlines = [AnswerInline]

@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ('title', 'created_by', 'created_at', 'is_public')
    list_filter = ('is_public', 'created_at')
    search_fields = ('title', 'description')
