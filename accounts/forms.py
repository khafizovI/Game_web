from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Profile, EmailVerification
from django.core.exceptions import ValidationError
import re


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    role = forms.ChoiceField(
        choices=Profile.ROLE_CHOICES,
        required=True,
        widget=forms.RadioSelect,
        initial='student'
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + ('email',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'class': 'form-control', 'autofocus': True})
        self.fields['email'].widget.attrs.update({'class': 'form-control'})
        self.fields['password1'].widget.attrs.update({'class': 'form-control'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control'})
        
        # Update help text for password fields
        self.fields['password1'].help_text = (
            "Your password should be secure and not too simple. "
            "Avoid using common passwords or personal information."
        )
        self.fields['password2'].help_text = "Enter the same password as before, for verification."

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("A user with this username already exists. Please choose a different username.")
        
        # Additional username validation
        if len(username) < 3:
            raise forms.ValidationError("Username must be at least 3 characters long.")
        
        if not re.match("^[a-zA-Z0-9_]+$", username):
            raise forms.ValidationError("Username can only contain letters, numbers, and underscores.")
        
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email

    def clean_password1(self):
        password1 = self.cleaned_data.get('password1')
        
        if not password1:
            raise forms.ValidationError("Password is required.")
        
        # Minimum length check (reduced from Django's default 8)
        if len(password1) < 4:
            raise forms.ValidationError("Password must be at least 4 characters long.")
        
        # Check if password is too simple
        simple_passwords = [
            '1234', '12345', '123456', '1234567', '12345678',
            'password', 'pass', 'admin', 'user', 'test',
            'qwerty', 'abc123', '111111', '000000'
        ]
        
        if password1.lower() in simple_passwords:
            raise forms.ValidationError("Password is too simple. Please choose a more secure password.")
        
        # Check if password is same as username
        username = self.cleaned_data.get('username')
        if username and password1.lower() == username.lower():
            raise forms.ValidationError("Password cannot be the same as your username.")
        
        # Check if password contains only numbers
        if password1.isdigit():
            raise forms.ValidationError("Password cannot contain only numbers.")
        
        return password1

    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("The two password fields didn't match.")
        
        return password2


class LoginForm(forms.Form):
    username = forms.CharField(
        label="Username",
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'autofocus': True})
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=True
    )


class EmailVerificationForm(forms.Form):
    code = forms.CharField(
        label="Verification Code",
        max_length=6,
        min_length=6,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control text-center',
            'placeholder': '000000',
            'style': 'letter-spacing: 0.5em; font-size: 1.5em;'
        })
    )

    def __init__(self, user=None, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_code(self):
        code = self.cleaned_data.get('code')
        if self.user:
            try:
                verification = EmailVerification.objects.get(
                    user=self.user,
                    code=code,
                    is_used=False
                )
                if verification.is_expired():
                    raise forms.ValidationError("Verification code has expired. Please request a new one.")
            except EmailVerification.DoesNotExist:
                raise forms.ValidationError("Invalid verification code.")
        return code