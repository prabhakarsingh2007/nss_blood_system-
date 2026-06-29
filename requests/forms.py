from django import forms
from .models import BloodRequest, Hospital

class BloodRequestForm(forms.ModelForm):
    hospital_name = forms.ModelChoiceField(
        queryset=Hospital.objects.filter(is_active=True),
        required=True,
        label="Hospital Name",
        to_field_name="name",
        empty_label="Select Hospital"
    )
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
    priority = forms.ChoiceField(
        choices=BloodRequest.PRIORITY_CHOICES,
        required=True,
        label="Emergency Priority"
    )

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
