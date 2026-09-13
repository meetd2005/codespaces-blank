import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from apps.accounts.models import User, Wallet


class Transaction(models.Model):
    """Immutable ledger entry for every wallet movement."""
    CREDIT = "credit"
    DEBIT = "debit"
    KIND_CHOICES = [(CREDIT, "Credit"), (DEBIT, "Debit")]

    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name="transactions")
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "transaction"
        verbose_name_plural = "transactions"

    def __str__(self):
        return f"{self.kind.upper()} {self.amount} → {self.wallet.user.username}"


class Deposit(models.Model):
    """
    Coin deposit request via QR scan.
    Flow: user requests → QR shown → user pays via UPI → admin confirms.
    """
    PENDING = "pending"      # Waiting for payment
    UNDER_REVIEW = "review"  # User marked paid, awaiting admin verify
    CONFIRMED = "confirmed"  # Admin confirmed, coins credited
    REJECTED = "rejected"    # Admin rejected (fake screenshot etc.)

    STATUS_CHOICES = [
        (PENDING, "Pending Payment"),
        (UNDER_REVIEW, "Under Review"),
        (CONFIRMED, "Confirmed"),
        (REJECTED, "Rejected"),
    ]

    ref = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="deposits")
    # Rupee amount paid (coins = rupee_amount * COIN_RUPEE_RATE)
    rupee_amount = models.DecimalField(max_digits=10, decimal_places=2)
    coins = models.DecimalField(max_digits=10, decimal_places=2)
    upi_ref = models.CharField(max_length=100, blank=True, help_text="UTR / UPI transaction ID")
    # User uploads payment screenshot
    screenshot = models.ImageField(upload_to="deposits/screenshots/", null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    admin_note = models.TextField(blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    confirmed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="confirmed_deposits"
    )

    class Meta:
        ordering = ["-requested_at"]
        verbose_name = "deposit"
        verbose_name_plural = "deposits"

    def __str__(self):
        return f"Deposit #{str(self.ref)[:8]} – {self.user.username} – ₹{self.rupee_amount}"

    @property
    def short_ref(self):
        return str(self.ref)[:8].upper()

    @classmethod
    def calculate_coins(cls, rupee_amount):
        rate = getattr(settings, "COIN_RUPEE_RATE", 1)
        return Decimal(str(rupee_amount)) * Decimal(str(rate))


class Withdrawal(models.Model):
    """
    Coin withdrawal request.
    User requests → admin manually processes and transfers via UPI → marks paid.
    """
    PENDING = "pending"
    APPROVED = "approved"   # Admin approved, will process
    PAID = "paid"           # Real money transferred
    REJECTED = "rejected"

    STATUS_CHOICES = [
        (PENDING, "Pending"),
        (APPROVED, "Approved"),
        (PAID, "Paid"),
        (REJECTED, "Rejected"),
    ]

    ref = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="withdrawals")
    coins = models.DecimalField(max_digits=10, decimal_places=2)
    rupee_amount = models.DecimalField(max_digits=10, decimal_places=2)
    upi_id = models.CharField(max_length=100, help_text="UPI ID to pay to")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    admin_note = models.TextField(blank=True)
    upi_ref_paid = models.CharField(max_length=100, blank=True, help_text="UTR after payment")
    requested_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    processed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="processed_withdrawals"
    )

    class Meta:
        ordering = ["-requested_at"]
        verbose_name = "withdrawal"
        verbose_name_plural = "withdrawals"

    def __str__(self):
        return f"Withdrawal #{str(self.ref)[:8]} – {self.user.username} – {self.coins} coins"

    @property
    def short_ref(self):
        return str(self.ref)[:8].upper()
