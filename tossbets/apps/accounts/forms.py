from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)
    phone = forms.CharField(max_length=15, required=False, label="Phone (optional)")

    class Meta:
        model = User
        fields = ("username", "email", "phone", "password1", "password2")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.phone = self.cleaned_data.get("phone", "")
        if commit:
            user.save()
            from apps.accounts.models import Wallet
            Wallet.objects.get_or_create(user=user)
        return user


class LoginForm(AuthenticationForm):
    username = forms.CharField(label="Username")


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "phone", "upi_id")
        labels = {"upi_id": "UPI ID (for withdrawals)"}
        widgets = {
            "upi_id": forms.TextInput(attrs={"placeholder": "yourname@upi"}),
        }
