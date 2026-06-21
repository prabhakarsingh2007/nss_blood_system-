from django.contrib import admin
from .models import BroadcastMessage

@admin.register(BroadcastMessage)
class BroadcastMessageAdmin(admin.ModelAdmin):
    list_display = ("message", "is_active", "created_by", "created_at")
    list_filter = ("is_active",)
