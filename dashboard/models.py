from django.conf import settings
from django.db import models

class BroadcastMessage(models.Model):
    message = models.CharField(max_length=240)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        db_table = 'blooddonation_broadcastmessage'

    def __str__(self) -> str:
        return self.message
