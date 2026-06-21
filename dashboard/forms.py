from django import forms
from .models import BroadcastMessage

class BroadcastMessageForm(forms.ModelForm):
    class Meta:
        model = BroadcastMessage
        fields = ["message", "is_active"]
