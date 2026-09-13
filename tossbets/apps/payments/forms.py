from decimal import Decimal
from django import forms
from .models import Deposit, Withdrawal


class DepositRequestForm(forms.Form):
    rupee_amount = forms.DecimalField(
        min_value=10,
        max_digits=10,
        decimal_places=2,
        label="Amount to deposit (₹)",
        widget=forms.NumberInput(attrs={
            "class": "form-control form-control-lg",
            "placeholder": "e.g. 100",
            "step": "10",
            "min": "10",
        }),
    )


class DepositConfirmForm(forms.ModelForm):
    """User submits UTR and optional screenshot after paying."""
    class Meta:
        model = Deposit
        fields = ("upi_ref", "screenshot")
        labels = {
            "upi_ref": "UPI Transaction ID / UTR Number",
            "screenshot": "Payment Screenshot (optional but recommended)",
        }
        widgets = {
            "upi_ref": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "e.g. 123456789012",
            }),
        }

    def clean_upi_ref(self):
        val = self.cleaned_data.get("upi_ref", "").strip()
        if not val:
            raise forms.ValidationError("Please enter the UTR/transaction ID.")
        return val


class WithdrawalForm(forms.Form):
    coins = forms.DecimalField(
        min_value=10,
        max_digits=10,
        decimal_places=2,
        label="Coins to withdraw",
        widget=forms.NumberInput(attrs={
            "class": "form-control form-control-lg",
            "placeholder": "e.g. 100",
            "step": "10",
            "min": "10",
        }),
    )
    upi_id = forms.CharField(
        max_length=100,
        label="Your UPI ID",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "yourname@upi",
        }),
    )

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        # Pre-fill UPI ID from profile
        if user.upi_id and not self.data.get("upi_id"):
            self.fields["upi_id"].initial = user.upi_id

    def clean_coins(self):
        coins = self.cleaned_data["coins"]
        try:
            wallet = self.user.wallet
        except Exception:
            raise forms.ValidationError("Wallet not found.")
        if wallet.balance < coins:
            raise forms.ValidationError(
                f"You only have {wallet.balance} coins. Cannot withdraw {coins}."
            )
        return coins
