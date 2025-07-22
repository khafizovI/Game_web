from django.db import models
from django.conf import settings

class BlockedIP(models.Model):
    ip_address = models.GenericIPAddressField(unique=True)
    reason = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.ip_address

    class Meta:
        verbose_name = "Blocked IP"
        verbose_name_plural = "Blocked IPs"

class ModerationLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    ip_address = models.GenericIPAddressField()
    timestamp = models.DateTimeField(auto_now_add=True)
    content = models.TextField()
    is_suspicious = models.BooleanField(default=False)

    def __str__(self):
        return f"Log for {self.user or self.ip_address} at {self.timestamp}"

    class Meta:
        ordering = ['-timestamp']
