from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.utils.html import format_html
from .models import Profile, ShopItem, UserPurchase, Achievement, UserAchievement

# Register your models here.

class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'Profile'
    fields = ('bio', 'role', 'games_hosted', 'games_played', 'total_points', 'coins', 'avatar', 'selected_frame')
    readonly_fields = ('games_hosted', 'games_played')

class UserAdmin(BaseUserAdmin):
    inlines = (ProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'get_role', 'get_coins', 'get_points', 'is_staff', 'give_coins_link')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'profile__role')
    search_fields = ('username', 'first_name', 'last_name', 'email')
    
    def get_role(self, obj):
        return obj.profile.get_role_display() if hasattr(obj, 'profile') else 'No Profile'
    get_role.short_description = 'Role'
    
    def get_coins(self, obj):
        return obj.profile.coins if hasattr(obj, 'profile') else 0
    get_coins.short_description = 'Coins'
    
    def get_points(self, obj):
        return obj.profile.total_points if hasattr(obj, 'profile') else 0
    get_points.short_description = 'Points'
    
    def give_coins_link(self, obj):
        if hasattr(obj, 'profile') and obj.profile.is_student():
            return format_html(
                '<a class="button" href="{}">Give Coins</a>',
                reverse('admin:give_coins', args=[obj.pk])
            )
        return '-'
    give_coins_link.short_description = 'Actions'
    give_coins_link.allow_tags = True
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('give-coins/<int:user_id>/', self.admin_site.admin_view(self.give_coins_view), name='give_coins'),
        ]
        return custom_urls + urls
    
    def give_coins_view(self, request, user_id):
        user = User.objects.get(pk=user_id)
        
        if request.method == 'POST':
            coins_to_give = int(request.POST.get('coins', 0))
            reason = request.POST.get('reason', '')
            
            if coins_to_give > 0:
                user.profile.coins += coins_to_give
                user.profile.save()
                
                messages.success(
                    request, 
                    f'Successfully gave {coins_to_give} coins to {user.username}. '
                    f'New balance: {user.profile.coins} coins.'
                )
                
                # Log the action
                self.log_addition(request, user.profile, f'Gave {coins_to_give} coins. Reason: {reason}')
            else:
                messages.error(request, 'Please enter a valid number of coins.')
            
            return HttpResponseRedirect(reverse('admin:auth_user_changelist'))
        
        context = {
            'user': user,
            'current_coins': user.profile.coins,
            'title': f'Give Coins to {user.username}',
        }
        
        return render(request, 'admin/give_coins.html', context)

# Unregister the default User admin and register our custom one
admin.site.unregister(User)
admin.site.register(User, UserAdmin)

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'games_hosted', 'games_played', 'total_points', 'coins')
    list_filter = ('role',)
    search_fields = ('user__username', 'user__first_name', 'user__last_name')
    readonly_fields = ('games_hosted', 'games_played')
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')

@admin.register(ShopItem)
class ShopItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'item_type', 'price', 'is_active', 'created_at')
    list_filter = ('item_type', 'is_active')
    search_fields = ('name', 'description')
    list_editable = ('price', 'is_active')

@admin.register(UserPurchase)
class UserPurchaseAdmin(admin.ModelAdmin):
    list_display = ('user', 'item', 'purchased_at')
    list_filter = ('item__item_type', 'purchased_at')
    search_fields = ('user__username', 'item__name')
    readonly_fields = ('purchased_at',)

@admin.register(Achievement)
class AchievementAdmin(admin.ModelAdmin):
    list_display = ('name', 'points_required', 'games_required', 'reward_coins', 'is_hidden')
    list_filter = ('is_hidden',)
    search_fields = ('name', 'description')
    list_editable = ('points_required', 'games_required', 'reward_coins', 'is_hidden')

@admin.register(UserAchievement)
class UserAchievementAdmin(admin.ModelAdmin):
    list_display = ('user', 'achievement', 'earned_at')
    list_filter = ('achievement', 'earned_at')
    search_fields = ('user__username', 'achievement__name')
    readonly_fields = ('earned_at',)
