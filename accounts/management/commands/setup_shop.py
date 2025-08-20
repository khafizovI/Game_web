from django.core.management.base import BaseCommand
from accounts.models import ShopItem, Achievement


class Command(BaseCommand):
    help = 'Create initial shop items and achievements'

    def handle(self, *args, **options):
        self.stdout.write('Setting up shop items and achievements...')
        
        # Create Profile Frames
        frames_data = [
            {
                'name': 'Golden Frame',
                'description': 'A luxurious golden frame that shows your premium status',
                'item_type': 'frame',
                'price': 500,
                'css_class': 'golden-frame'
            },
            {
                'name': 'Silver Frame',
                'description': 'An elegant silver frame for distinguished players',
                'item_type': 'frame',
                'price': 300,
                'css_class': 'silver-frame'
            },
            {
                'name': 'Rainbow Frame',
                'description': 'A vibrant rainbow frame that changes colors',
                'item_type': 'frame',
                'price': 750,
                'css_class': 'rainbow-frame'
            },
            {
                'name': 'Diamond Frame',
                'description': 'A sparkling diamond frame for elite players',
                'item_type': 'frame',
                'price': 1000,
                'css_class': 'diamond-frame'
            },
            {
                'name': 'Fire Frame',
                'description': 'A blazing fire frame for hot streaks',
                'item_type': 'frame',
                'price': 600,
                'css_class': 'fire-frame'
            }
        ]
        
        for frame_data in frames_data:
            frame, created = ShopItem.objects.get_or_create(
                name=frame_data['name'],
                defaults=frame_data
            )
            if created:
                self.stdout.write(f'Created frame: {frame.name}')
            else:
                self.stdout.write(f'Frame already exists: {frame.name}')
        
        # Create Badges
        badges_data = [
            {
                'name': 'Quiz Master Badge',
                'description': 'Awarded to players who excel in quiz games',
                'item_type': 'badge',
                'price': 200,
                'css_class': 'quiz-master-badge'
            },
            {
                'name': 'Speed Demon Badge',
                'description': 'For the fastest quiz solvers',
                'item_type': 'badge',
                'price': 250,
                'css_class': 'speed-demon-badge'
            },
            {
                'name': 'Knowledge Seeker Badge',
                'description': 'For dedicated learners and quiz enthusiasts',
                'item_type': 'badge',
                'price': 150,
                'css_class': 'knowledge-seeker-badge'
            }
        ]
        
        for badge_data in badges_data:
            badge, created = ShopItem.objects.get_or_create(
                name=badge_data['name'],
                defaults=badge_data
            )
            if created:
                self.stdout.write(f'Created badge: {badge.name}')
            else:
                self.stdout.write(f'Badge already exists: {badge.name}')
        
        # Create Themes
        themes_data = [
            {
                'name': 'Dark Theme',
                'description': 'A sleek dark theme for your dashboard',
                'item_type': 'theme',
                'price': 400,
                'css_class': 'dark-theme'
            },
            {
                'name': 'Ocean Theme',
                'description': 'A calming ocean-inspired theme',
                'item_type': 'theme',
                'price': 350,
                'css_class': 'ocean-theme'
            },
            {
                'name': 'Sunset Theme',
                'description': 'A warm sunset theme with beautiful gradients',
                'item_type': 'theme',
                'price': 450,
                'css_class': 'sunset-theme'
            }
        ]
        
        for theme_data in themes_data:
            theme, created = ShopItem.objects.get_or_create(
                name=theme_data['name'],
                defaults=theme_data
            )
            if created:
                self.stdout.write(f'Created theme: {theme.name}')
            else:
                self.stdout.write(f'Theme already exists: {theme.name}')
        
        # Create Achievements
        achievements_data = [
            {
                'name': 'First Steps',
                'description': 'Play your first quiz game',
                'icon': 'fas fa-baby',
                'points_required': 0,
                'games_required': 1
            },
            {
                'name': 'Getting Started',
                'description': 'Play 5 quiz games',
                'icon': 'fas fa-play',
                'points_required': 0,
                'games_required': 5
            },
            {
                'name': 'Quiz Enthusiast',
                'description': 'Play 25 quiz games',
                'icon': 'fas fa-heart',
                'points_required': 0,
                'games_required': 25
            },
            {
                'name': 'Quiz Master',
                'description': 'Play 100 quiz games',
                'icon': 'fas fa-crown',
                'points_required': 0,
                'games_required': 100
            },
            {
                'name': 'Point Collector',
                'description': 'Earn 100 points',
                'icon': 'fas fa-star',
                'points_required': 100,
                'games_required': 0
            },
            {
                'name': 'Rising Star',
                'description': 'Earn 500 points',
                'icon': 'fas fa-star-half-alt',
                'points_required': 500,
                'games_required': 0
            },
            {
                'name': 'Point Master',
                'description': 'Earn 1000 points',
                'icon': 'fas fa-medal',
                'points_required': 1000,
                'games_required': 0
            },
            {
                'name': 'Legend',
                'description': 'Earn 5000 points',
                'icon': 'fas fa-trophy',
                'points_required': 5000,
                'games_required': 0
            },
            {
                'name': 'Perfect Score',
                'description': 'Get a perfect score in any quiz',
                'icon': 'fas fa-bullseye',
                'points_required': 0,
                'games_required': 0
            },
            {
                'name': 'Speed Runner',
                'description': 'Complete a quiz in record time',
                'icon': 'fas fa-bolt',
                'points_required': 0,
                'games_required': 0
            }
        ]
        
        for achievement_data in achievements_data:
            achievement, created = Achievement.objects.get_or_create(
                name=achievement_data['name'],
                defaults=achievement_data
            )
            if created:
                self.stdout.write(f'Created achievement: {achievement.name}')
            else:
                self.stdout.write(f'Achievement already exists: {achievement.name}')
        
        self.stdout.write(self.style.SUCCESS('Successfully set up shop items and achievements!'))
