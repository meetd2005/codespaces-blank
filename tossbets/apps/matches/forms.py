from django import forms
from .models import Bet, Match


class PlaceBetForm(forms.Form):
    side = forms.ChoiceField(
        choices=Match.SIDE_CHOICES,
        widget=forms.RadioSelect(attrs={"class": "form-check-input"}),
        label="Pick your side",
    )
    amount = forms.DecimalField(
        min_value=1,
        max_digits=10,
        decimal_places=2,
        label="Coins to bet",
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "1"}),
    )

    def __init__(self, match, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.match = match
        self.fields["amount"].min_value = match.min_bet
        self.fields["amount"].max_value = match.max_bet
        self.fields["amount"].widget.attrs.update({
            "min": str(match.min_bet),
            "max": str(match.max_bet),
            "placeholder": f"{match.min_bet} – {match.max_bet}",
        })
