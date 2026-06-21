from django import forms
from .models import BloodRequest

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
