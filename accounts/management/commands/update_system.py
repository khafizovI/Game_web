from django.core.management.base import BaseCommand
from accounts.models import DailyTask, ShopItem, UserPurchase
from django.db import transaction


class Command(BaseCommand):
    help = 'Update system: Add new daily tasks, remove themes/badges, add new frames'

    def handle(self, *args, **options):
        with transaction.atomic():
            # Remove themes and badges
            self.stdout.write('Removing themes and badges...')
            ShopItem.objects.filter(item_type__in=['theme', 'badge']).delete()
            UserPurchase.objects.filter(item__item_type__in=['theme', 'badge']).delete()
            
            # Add new daily tasks
            self.stdout.write('Adding new daily tasks...')
            new_tasks = [
                {
                    'name': 'Speed Runner',
                    'description': 'Complete 3 quizzes in under 2 minutes each',
                    'task_type': 'complete_quiz',
                    'target_value': 3,
                    'reward_coins': 45,
                    'reward_points': 100
                },
                {
                    'name': 'Perfectionist',
                    'description': 'Get 100% accuracy on 2 quizzes',
                    'task_type': 'answer_correctly',
                    'target_value': 2,
                    'reward_coins': 60,
                    'reward_points': 150
                },
                {
                    'name': 'Marathon Player',
                    'description': 'Play 10 games in a single day',
                    'task_type': 'play_games',
                    'target_value': 10,
                    'reward_coins': 80,
                    'reward_points': 200
                },
                {
                    'name': 'Point Hunter',
                    'description': 'Earn 1000 points in total',
                    'task_type': 'earn_points',
                    'target_value': 1000,
                    'reward_coins': 50,
                    'reward_points': 120
                },
                {
                    'name': 'Consistency King',
                    'description': 'Login for 7 consecutive days',
                    'task_type': 'login_streak',
                    'target_value': 7,
                    'reward_coins': 100,
                    'reward_points': 300
                },
                {
                    'name': 'Big Spender',
                    'description': 'Spend 200 coins in the shop',
                    'task_type': 'spend_coins',
                    'target_value': 200,
                    'reward_coins': 40,
                    'reward_points': 80
                },
                {
                    'name': 'Quiz Novice',
                    'description': 'Complete your first quiz',
                    'task_type': 'complete_quiz',
                    'target_value': 1,
                    'reward_coins': 15,
                    'reward_points': 30
                },
                {
                    'name': 'Social Gamer',
                    'description': 'Play 5 multiplayer games',
                    'task_type': 'play_games',
                    'target_value': 5,
                    'reward_coins': 35,
                    'reward_points': 75
                },
                {
                    'name': 'Knowledge Seeker',
                    'description': 'Answer 50 questions correctly',
                    'task_type': 'answer_correctly',
                    'target_value': 50,
                    'reward_coins': 70,
                    'reward_points': 180
                },
                {
                    'name': 'Daily Warrior',
                    'description': 'Complete 3 daily tasks',
                    'task_type': 'complete_quiz',  # We'll track this separately
                    'target_value': 3,
                    'reward_coins': 90,
                    'reward_points': 250
                }
            ]
            
            for task_data in new_tasks:
                task, created = DailyTask.objects.get_or_create(
                    name=task_data['name'],
                    defaults={
                        'description': task_data['description'],
                        'task_type': task_data['task_type'],
                        'target_value': task_data['target_value'],
                        'reward_coins': task_data['reward_coins'],
                        'reward_points': task_data['reward_points'],
                    }
                )
                if created:
                    self.stdout.write(f"Created task: {task.name}")
                else:
                    self.stdout.write(f'Task already exists: {task.name}')
            
            # Add new frames
            self.stdout.write('Adding new frames...')
            new_frames = [
                {
                    'name': 'Cosmic Frame',
                    'description': 'A mystical cosmic frame with swirling galaxies',
                    'item_type': 'frame',
                    'price': 350,
                    'css_class': 'cosmic-frame'
                },
                {
                    'name': 'Dragon Frame',
                    'description': 'A fierce dragon-themed frame with fire effects',
                    'item_type': 'frame',
                    'price': 450,
                    'css_class': 'dragon-frame'
                },
                {
                    'name': 'Crystal Frame',
                    'description': 'A sparkling crystal frame that shimmers',
                    'item_type': 'frame',
                    'price': 300,
                    'css_class': 'crystal-frame'
                },
                {
                    'name': 'Neon Frame',
                    'description': 'A vibrant neon frame with electric glow',
                    'item_type': 'frame',
                    'price': 400,
                    'css_class': 'neon-frame'
                },
                {
                    'name': 'Royal Frame',
                    'description': 'An elegant royal frame fit for a king',
                    'item_type': 'frame',
                    'price': 500,
                    'css_class': 'royal-frame'
                },
                {
                    'name': 'Ocean Frame',
                    'description': 'A flowing ocean frame with wave effects',
                    'item_type': 'frame',
                    'price': 320,
                    'css_class': 'ocean-frame'
                },
                {
                    'name': 'Flame Frame',
                    'description': 'A blazing flame frame with fire animation',
                    'item_type': 'frame',
                    'price': 380,
                    'css_class': 'flame-frame'
                },
                {
                    'name': 'Shadow Frame',
                    'description': 'A mysterious shadow frame with dark energy',
                    'item_type': 'frame',
                    'price': 420,
                    'css_class': 'shadow-frame'
                }
            ]
            
            for frame_data in new_frames:
                frame, created = ShopItem.objects.get_or_create(
                    name=frame_data['name'],
                    defaults={
                        'description': frame_data['description'],
                        'item_type': frame_data['item_type'],
                        'price': frame_data['price'],
                        'css_class': frame_data['css_class'],
                    }
                )
                if created:
                    self.stdout.write(f"Created frame: {frame.name}")
                else:
                    self.stdout.write(f'Frame already exists: {frame.name}')
            
            self.stdout.write(self.style.SUCCESS('Successfully updated system!'))
