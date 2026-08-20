from django import forms
from django.utils import timezone
from .models import DonorProfile, BloodCamp

class DonorProfileForm(forms.ModelForm):
    city = forms.ChoiceField(
        choices=[(c, c) for c in [
            "Araria", "Arwal", "Aurangabad", "Banka", "Begusarai", "Bhagalpur", "Bhojpur", "Buxar",
            "Darbhanga", "East Champaran", "Gaya", "Gopalganj", "Jamui", "Jehanabad", "Kaimur", "Katihar",
            "Khagaria", "Kishanganj", "Lakhisarai", "Madhepura", "Madhubani", "Munger", "Muzaffarpur",
            "Nalanda", "Nawada", "Patna", "Purnia", "Rohtas", "Saharsa", "Samastipur", "Saran",
            "Sheikhpura", "Sheohar", "Sitamarhi", "Siwan", "Supaul", "Vaishali", "West Champaran",
        ]],
        required=True,
        label="District / City"
    )

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

    def clean_age(self):
        age = self.cleaned_data.get("age")
        if age is not None and (age < 18 or age > 65):
            raise forms.ValidationError("Donors must be between 18 and 65 years old.")
        return age

    def clean_phone(self):
        phone = self.cleaned_data.get("phone")
        if phone:
            phone = phone.strip()
            if not phone.isdigit() or len(phone) < 10 or len(phone) > 12:
                raise forms.ValidationError("Enter a valid 10 to 12 digit phone number.")
            
            qs = DonorProfile.objects.filter(phone=phone)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("A donor with this phone number is already registered.")
        return phone

    def clean_last_donation_date(self):
        last_donation_date = self.cleaned_data.get("last_donation_date")
        if last_donation_date and last_donation_date > timezone.localdate():
            raise forms.ValidationError("Last donation date cannot be in the future.")
        return last_donation_date


class BloodCampForm(forms.ModelForm):
    district = forms.ChoiceField(
        choices=[(c, c) for c in [
            "Araria", "Arwal", "Aurangabad", "Banka", "Begusarai", "Bhagalpur", "Bhojpur", "Buxar",
            "Darbhanga", "East Champaran", "Gaya", "Gopalganj", "Jamui", "Jehanabad", "Kaimur", "Katihar",
            "Khagaria", "Kishanganj", "Lakhisarai", "Madhepura", "Madhubani", "Munger", "Muzaffarpur",
            "Nalanda", "Nawada", "Patna", "Purnia", "Rohtas", "Saharsa", "Samastipur", "Saran",
            "Sheikhpura", "Sheohar", "Sitamarhi", "Siwan", "Supaul", "Vaishali", "West Champaran",
        ]],
        required=True,
        label="District"
    )

    class Meta:
        model = BloodCamp
        fields = [
            "title", "description", "date", "start_time", "end_time", 
            "location", "district", "organizer_name", "organizer_contact", 
            "status", "cover_image", "manual_donation_count"
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
            "organizer_contact": forms.TextInput(attrs={"placeholder": "e.g. +91 98765 43210 (Optional)"}),
        }

    def clean_date(self):
        date = self.cleaned_data.get("date")
        status = self.cleaned_data.get("status")
        # Only check future date if creating a new camp
        if not self.instance.pk and status in {None, "AUTO", "UPCOMING"}:
            if date and date < timezone.localdate():
                raise forms.ValidationError("Blood camp cannot be scheduled in the past.")
        return date



class OtpVerifyForm(forms.Form):
    otp = forms.CharField(max_length=6, min_length=6)
