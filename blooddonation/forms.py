from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import BloodCamp, BloodRequest, BroadcastMessage, DonorProfile


class UserRegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email", "password1", "password2")


class DonorProfileForm(forms.ModelForm):
    class Meta:
        model = DonorProfile
        fields = [
            "full_name",
            "blood_group",
            "age",
            "phone",
            "city",
            "last_donation_date",
            "available",
        ]
        widgets = {
            "last_donation_date": forms.DateInput(attrs={"type": "date"}),
        }


class BloodRequestForm(forms.ModelForm):
    class Meta:
        model = BloodRequest
        fields = [
            "requester_name",
            "blood_group",
            "units",
            "hospital_name",
            "city",
            "contact_number",
            "reason",
            "is_emergency",
        ]


class UserLoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={"autofocus": True}))


class OtpVerifyForm(forms.Form):
    otp = forms.CharField(max_length=6, min_length=6)


class BroadcastMessageForm(forms.ModelForm):
    class Meta:
        model = BroadcastMessage
        fields = ["message", "is_active"]


class BloodCampForm(forms.ModelForm):
    class Meta:
        model = BloodCamp
        fields = ["title", "description", "date", "location"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
        }