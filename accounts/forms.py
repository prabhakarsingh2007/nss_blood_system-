import re
from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from donors.models import DonorProfile

class UserRegisterForm(forms.Form):
    name = forms.CharField(
        max_length=120,
        required=True,
        label="Full Name",
        widget=forms.TextInput(attrs={
            "placeholder": "Enter your full name",
            "autofocus": True,
        })
    )
    email = forms.EmailField(
        required=True,
        label="Email Address",
        widget=forms.EmailInput(attrs={
            "placeholder": "Enter your email address",
        })
    )
    phone = forms.CharField(
        max_length=10,
        min_length=10,
        required=True,
        label="Phone Number",
        widget=forms.TextInput(attrs={
            "placeholder": "10-digit mobile number",
        })
    )
    blood_group = forms.ChoiceField(
        choices=DonorProfile.BLOOD_GROUP_CHOICES,
        required=True,
        label="Blood Group"
    )
    gender = forms.ChoiceField(
        choices=DonorProfile.GENDER_CHOICES,
        required=True,
        label="Gender"
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
    age = forms.IntegerField(
        min_value=18,
        max_value=65,
        required=True,
        label="Age",
        widget=forms.NumberInput(attrs={
            "placeholder": "Age (18-65)",
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "placeholder": "Minimum 8 characters (letters + numbers)",
        }),
        required=True,
        label="Password"
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "placeholder": "Confirm your password",
        }),
        required=True,
        label="Confirm Password"
    )

    def clean_name(self):
        name = self.cleaned_data.get("name")
        if name:
            name = name.strip()
            if not re.match(r"^[a-zA-Z\s]+$", name):
                raise forms.ValidationError("Name must contain letters only.")
        return name

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if email:
            email = email.lower().strip()
            if User.objects.filter(username=email).exists() or User.objects.filter(email=email).exists():
                raise forms.ValidationError("A user with this email already exists.")
        return email

    def clean_phone(self):
        phone = self.cleaned_data.get("phone")
        if phone:
            phone = phone.strip()
            if not phone.isdigit() or len(phone) != 10:
                raise forms.ValidationError("Phone number must be exactly 10 digits.")
        return phone

    def clean_age(self):
        age = self.cleaned_data.get("age")
        if age is not None:
            if age < 18 or age > 65:
                raise forms.ValidationError("Age must be between 18 and 65.")
        return age

    def clean_password(self):
        password = self.cleaned_data.get("password")
        if password:
            if len(password) < 8:
                raise forms.ValidationError("Password must be at least 8 characters.")
            if not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
                raise forms.ValidationError("Password must contain both letters and numbers.")
        return password

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")
        if password and confirm_password and password != confirm_password:
            self.add_error("confirm_password", "Confirm password must match password.")
        return cleaned_data

    def save(self):
        email = self.cleaned_data["email"]
        password = self.cleaned_data["password"]
        name = self.cleaned_data["name"]
        
        name_parts = name.split(maxsplit=1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )

        DonorProfile.objects.create(
            user=user,
            full_name=name,
            blood_group=self.cleaned_data["blood_group"],
            gender=self.cleaned_data["gender"],
            age=self.cleaned_data["age"],
            phone=self.cleaned_data["phone"],
            city=self.cleaned_data["city"],
            otp_verified=True,
            verification_status="PENDING",
            available=True
        )
        return user


class UserLoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={"autofocus": True}))
