from django.contrib import admin
from .models import ModerationLog, BlockedIP

@admin.register(BlockedIP)
class BlockedIPAdmin(admin.ModelAdmin):
    list_display = ('ip_address', 'reason', 'timestamp')
    search_fields = ('ip_address', 'reason')

@admin.register(ModerationLog)
class ModerationLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user', 'ip_address', 'is_suspicious')
    list_filter = ('is_suspicious', 'timestamp')
    search_fields = ('user__username', 'ip_address', 'content')
    readonly_fields = ('timestamp', 'user', 'ip_address', 'content', 'is_suspicious')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
