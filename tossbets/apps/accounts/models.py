from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import F


class User(AbstractUser):
    """Extended user with phone and referral tracking."""
    phone = models.CharField(max_length=15, blank=True)
    upi_id = models.CharField(max_length=100, blank=True, help_text="UPI ID for withdrawals")
    is_verified = models.BooleanField(default=False, help_text="Admin-verified account")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_joined"]
        verbose_name = "user"
        verbose_name_plural = "users"

    def __str__(self):
        return f"{self.username} ({self.email})"

    @property
    def wallet_balance(self):
        try:
            return self.wallet.balance
        except Wallet.DoesNotExist:
            return 0


class Wallet(models.Model):
    """
    Coin wallet for each user.
    All operations go through credit/debit helpers which use
    select_for_update() to prevent race conditions.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="wallet")
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_deposited = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_withdrawn = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Wallet({self.user.username}) = {self.balance} coins"

    def credit(self, amount, description="Credit"):
        """Add coins to wallet (call inside an atomic block)."""
        from apps.payments.models import Transaction
        Wallet.objects.filter(pk=self.pk).update(
            balance=F("balance") + amount,
            total_deposited=F("total_deposited") + amount,
        )
        self.refresh_from_db()
        Transaction.objects.create(
            wallet=self,
            amount=amount,
            kind=Transaction.CREDIT,
            description=description,
            balance_after=self.balance,
        )

    def debit(self, amount, description="Debit"):
        """Remove coins from wallet (call inside an atomic block, after checking balance)."""
        from apps.payments.models import Transaction
        if self.balance < amount:
            raise ValueError("Insufficient coins")
        Wallet.objects.filter(pk=self.pk).update(
            balance=F("balance") - amount,
            total_withdrawn=F("total_withdrawn") + amount,
        )
        self.refresh_from_db()
        Transaction.objects.create(
            wallet=self,
            amount=amount,
            kind=Transaction.DEBIT,
            description=description,
            balance_after=self.balance,
        )
