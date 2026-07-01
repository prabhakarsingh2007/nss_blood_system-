import os
from django import forms
from .models import BloodRequest, Hospital, BloodBank

class BloodRequestForm(forms.ModelForm):
    prescription = forms.FileField(
        required=True,
        label="Doctor's Prescription (JPG, JPEG, PNG, PDF)",
        help_text="Upload a valid doctor's prescription (Max 5 MB)."
    )
    blood_group = forms.ChoiceField(
        choices=BloodRequest.BLOOD_GROUP_CHOICES,
        widget=forms.HiddenInput(),
        required=True
    )
    hospital_name = forms.ModelChoiceField(
        queryset=Hospital.objects.filter(is_active=True),
        required=True,
        label="Deliver to Hospital",
        to_field_name="name",
        empty_label="Select Hospital"
    )
    city = forms.CharField(
        widget=forms.HiddenInput(),
        required=True
    )
    priority = forms.ChoiceField(
        choices=BloodRequest.PRIORITY_CHOICES,
        required=True,
        label="Emergency Priority"
    )

    def __init__(self, *args, **kwargs):
        city_val = kwargs.get('initial', {}).get('city')
        if not city_val and kwargs.get('data'):
            city_val = kwargs.get('data', {}).get('city')
            
        super().__init__(*args, **kwargs)
        
        if city_val:
            city_val = city_val.strip()
            self.fields["hospital_name"].queryset = Hospital.objects.filter(is_active=True, city__iexact=city_val)
        else:
            self.fields["hospital_name"].queryset = Hospital.objects.filter(is_active=True)


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
            "priority",
            "prescription",
        ]

    def clean_contact_number(self):
        number = self.cleaned_data.get("contact_number")
        if number:
            number = number.strip()
            if not number.isdigit() or len(number) < 10 or len(number) > 12:
                raise forms.ValidationError("Enter a valid 10 to 12 digit contact number.")
        return number

    def clean_units(self):
        units = self.cleaned_data.get("units")
        if units is not None and (units < 1 or units > 10):
            raise forms.ValidationError("Units requested must be between 1 and 10.")
        return units

    def clean_prescription(self):
        file = self.cleaned_data.get("prescription")
        if file:
            if file.size > 5 * 1024 * 1024:
                raise forms.ValidationError("File size must be under 5 MB.")
            ext = os.path.splitext(file.name)[1].lower()
            if ext not in ['.jpg', '.jpeg', '.png', '.pdf']:
                raise forms.ValidationError("Only JPG, JPEG, PNG, and PDF files are allowed.")
        return file


class HospitalForm(forms.ModelForm):
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
        model = Hospital
        fields = ["name", "city", "address", "is_active"]


class BloodBankForm(forms.ModelForm):
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
        model = BloodBank
        fields = ["name", "city", "address", "is_active"]


