import random
import string
import base64

from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from datetime import datetime, timedelta
from django.utils import timezone

# Create your models here.

class Profile(models.Model):
    ROLE_CHOICES = (
        ('student', 'Student'),
        ('teacher', 'Teacher'),
    )
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    bio = models.TextField(max_length=500, blank=True)
    games_hosted = models.IntegerField(default=0)
    games_played = models.IntegerField(default=0)
    total_points = models.IntegerField(default=0)
    coins = models.IntegerField(default=100)  # Shop currency
    experience_points = models.IntegerField(default=0)  # XP for leveling up
    level = models.IntegerField(default=1)  # Current level
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='student')
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    avatar_data = models.BinaryField(blank=True, null=True)
    avatar_content_type = models.CharField(max_length=100, blank=True)
    avatar_filename = models.CharField(max_length=255, blank=True)
    email_verified = models.BooleanField(default=False)
    selected_frame = models.ForeignKey('ShopItem', on_delete=models.SET_NULL, null=True, blank=True, related_name='users_using')
    selected_theme = models.ForeignKey('ShopItem', on_delete=models.SET_NULL, null=True, blank=True, related_name='users_using_theme')
    user_rating = models.IntegerField(null=True, blank=True, help_text="User's rating of the platform (1-5 stars)")
    
    def __str__(self):
        return f"{self.user.username}'s profile"
    
    def is_teacher(self):
        return self.role == 'teacher'
    
    def is_student(self):
        return self.role == 'student'
    
    def get_xp_for_level(self, level):
        """Calculate XP required for a specific level"""
        return level * 100 + (level - 1) * 50  # Progressive XP requirement
    
    def get_current_level_xp(self):
        """Get XP required for current level"""
        return self.get_xp_for_level(self.level)
    
    def get_next_level_xp(self):
        """Get XP required for next level"""
        return self.get_xp_for_level(self.level + 1)
    
    def get_level_progress(self):
        """Get progress to next level (0-100)"""
        current_level_xp = self.get_current_level_xp()
        next_level_xp = self.get_next_level_xp()
        if self.experience_points < current_level_xp:
            return 0
        progress_xp = self.experience_points - current_level_xp
        required_xp = next_level_xp - current_level_xp
        return min((progress_xp / required_xp) * 100, 100)
    
    def add_experience(self, xp_amount):
        """Add XP and check for level up"""
        self.experience_points += xp_amount
        old_level = self.level
        
        # Check for level up
        while self.experience_points >= self.get_next_level_xp() and self.level < 100:  # Max level 100
            self.level += 1
        
        self.save()
        
        # Return True if leveled up
        return self.level > old_level
    
    def get_level(self):
        """Calculate user level based on XP (for backward compatibility)"""
        return self.level

    def set_avatar_upload(self, uploaded_file):
        """Persist avatar bytes in the database instead of the media filesystem."""
        if not uploaded_file:
            return

        content_type = getattr(uploaded_file, "content_type", "") or ""
        if not content_type.startswith("image/"):
            raise ValueError("Avatar upload must be an image.")

        self.avatar_data = uploaded_file.read()
        self.avatar_content_type = content_type
        self.avatar_filename = getattr(uploaded_file, "name", "") or ""

        if self.avatar:
            self.avatar.delete(save=False)
        self.avatar = None

    @property
    def avatar_url(self):
        if self.avatar_data and self.avatar_content_type:
            encoded_bytes = base64.b64encode(self.avatar_data).decode("ascii")
            return f"data:{self.avatar_content_type};base64,{encoded_bytes}"

        if self.avatar:
            try:
                return self.avatar.url
            except (ValueError, OSError):
                return None

        return None


class ShopItem(models.Model):
    ITEM_TYPES = (
        ('frame', 'Profile Frame'),
        ('badge', 'Achievement Badge'),
        ('theme', 'Dashboard Theme'),
    )
    
    name = models.CharField(max_length=100)
    description = models.TextField()
    item_type = models.CharField(max_length=20, choices=ITEM_TYPES)
    price = models.IntegerField()
    image = models.ImageField(upload_to='shop_items/', blank=True, null=True)
    css_class = models.CharField(max_length=50, blank=True)  # For styling
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name} ({self.get_item_type_display()})"
    
    class Meta:
        ordering = ['item_type', 'price']


class UserPurchase(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='purchases')
    item = models.ForeignKey(ShopItem, on_delete=models.CASCADE)
    purchased_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user', 'item')
    
    def __str__(self):
        return f"{self.user.username} owns {self.item.name}"


class Achievement(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    icon = models.CharField(max_length=50, default='fas fa-trophy')  # Font Awesome icon
    points_required = models.IntegerField(default=0)
    games_required = models.IntegerField(default=0)
    is_hidden = models.BooleanField(default=False)
    reward_coins = models.IntegerField(default=10)
    
    def __str__(self):
        return self.name


class UserAchievement(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='achievements')
    achievement = models.ForeignKey(Achievement, on_delete=models.CASCADE)
    earned_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user', 'achievement')
    
    def __str__(self):
        return f"{self.user.username} earned {self.achievement.name}"


class EmailVerification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)
    
    def __str__(self):
        return f"Verification for {self.user.username}"
    
    def is_expired(self):
        """Check if the verification code has expired (10 minutes)"""
        return timezone.now() > self.created_at + timedelta(minutes=10)
    
    @classmethod
    def generate_code(cls, user):
        """Generate a new 6-digit verification code for the user"""
        # Delete any existing codes for this user
        cls.objects.filter(user=user).delete()
        
        # Generate new code
        code = ''.join(random.choices(string.digits, k=6))
        verification = cls.objects.create(user=user, code=code)
        return verification


class DailyTask(models.Model):
    TASK_TYPES = (
        ('play_games', 'Play Games'),
        ('earn_points', 'Earn Points'),
        ('answer_correctly', 'Answer Correctly'),
        ('complete_quiz', 'Complete Quiz'),
        ('login_streak', 'Login Streak'),
        ('spend_coins', 'Spend Coins'),
    )
    
    name = models.CharField(max_length=100)
    description = models.TextField()
    task_type = models.CharField(max_length=20, choices=TASK_TYPES)
    target_value = models.IntegerField()  # Target number to achieve
    reward_coins = models.IntegerField(default=10)
    reward_points = models.IntegerField(default=50)
    icon = models.CharField(max_length=50, default='fas fa-tasks')
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.name} - {self.target_value}"
    
    class Meta:
        ordering = ['task_type', 'target_value']


class UserDailyTask(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='daily_tasks')
    task = models.ForeignKey(DailyTask, on_delete=models.CASCADE)
    assigned_date = models.DateField(auto_now_add=True)
    current_progress = models.IntegerField(default=0)
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.task.name} ({self.assigned_date})"
    
    def get_progress_percentage(self):
        """Get progress as percentage (0-100)"""
        if self.task.target_value == 0:
            return 100 if self.is_completed else 0
        return min((self.current_progress / self.task.target_value) * 100, 100)
    
    def update_progress(self, increment=1):
        """Update task progress and check for completion"""
        self.current_progress += increment
        if self.current_progress >= self.task.target_value and not self.is_completed:
            self.is_completed = True
            self.completed_at = timezone.now()
            # Award rewards
            profile = self.user.profile
            profile.coins += self.task.reward_coins
            profile.total_points += self.task.reward_points
            
            # Award XP based on task difficulty and rewards
            xp_reward = self.task.reward_points // 2 + 25  # Base 25 XP + bonus based on points
            leveled_up = profile.add_experience(xp_reward)
            
            # Save profile (add_experience already saves, but let's be explicit)
            profile.save()
            
            # Return completion status and level up info
            return {'completed': True, 'leveled_up': leveled_up, 'xp_gained': xp_reward}
        
        self.save()
        return {'completed': False, 'leveled_up': False, 'xp_gained': 0}
    
    class Meta:
        unique_together = ('user', 'task', 'assigned_date')
        ordering = ['-assigned_date', 'is_completed']


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()
