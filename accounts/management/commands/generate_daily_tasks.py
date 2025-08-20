from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from accounts.models import DailyTask, UserDailyTask, Profile
from django.utils import timezone
import random


class Command(BaseCommand):
    help = 'Generate daily tasks for all students'

    def handle(self, *args, **options):
        today = timezone.now().date()
        
        # Get all students
        students = User.objects.filter(profile__role='student')
        
        # Get all active daily tasks
        available_tasks = list(DailyTask.objects.filter(is_active=True))
        
        if len(available_tasks) < 3:
            self.stdout.write(
                self.style.ERROR('Not enough active daily tasks available. Need at least 3.')
            )
            return
        
        tasks_assigned = 0
        
        for student in students:
            # Check if student already has tasks for today
            existing_tasks = UserDailyTask.objects.filter(
                user=student, 
                assigned_date=today
            ).count()
            
            if existing_tasks >= 3:
                continue  # Student already has tasks for today
            
            # Remove any existing tasks for today (in case of partial assignment)
            UserDailyTask.objects.filter(user=student, assigned_date=today).delete()
            
            # Select 3 random tasks
            selected_tasks = random.sample(available_tasks, 3)
            
            # Assign tasks to student
            for task in selected_tasks:
                UserDailyTask.objects.create(
                    user=student,
                    task=task,
                    assigned_date=today
                )
                tasks_assigned += 1
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully assigned {tasks_assigned} daily tasks to {students.count()} students'
            )
        )
