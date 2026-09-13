import random
from decimal import Decimal
from django.db import models, transaction
from django.utils import timezone
from apps.accounts.models import User


class Match(models.Model):
    """A single toss match that users bet on."""
    PENDING = "pending"       # Created, accepting bets
    LOCKED = "locked"         # Betting closed, waiting for result
    SETTLED = "settled"       # Winner declared, coins distributed
    CANCELLED = "cancelled"   # Refunded

    STATUS_CHOICES = [
        (PENDING, "Open for Bets"),
        (LOCKED, "Betting Closed"),
        (SETTLED, "Settled"),
        (CANCELLED, "Cancelled"),
    ]

    HEADS = "heads"
    TAILS = "tails"
    SIDE_CHOICES = [(HEADS, "Heads"), (TAILS, "Tails")]

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    min_bet = models.DecimalField(max_digits=10, decimal_places=2, default=10)
    max_bet = models.DecimalField(max_digits=10, decimal_places=2, default=10000)
    # House edge as percentage (e.g. 5 = 5%)
    house_edge = models.DecimalField(max_digits=5, decimal_places=2, default=5)
    # Winning side: null until declared
    winning_side = models.CharField(max_length=10, choices=SIDE_CHOICES, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="created_matches"
    )
    starts_at = models.DateTimeField(default=timezone.now)
    betting_closes_at = models.DateTimeField(null=True, blank=True)
    settled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "match"
        verbose_name_plural = "matches"

    def __str__(self):
        return f"{self.title} [{self.get_status_display()}]"

    @property
    def total_pool(self):
        return self.bets.filter(status=Bet.WON).aggregate(
            total=models.Sum("amount")
        )["total"] or Decimal("0")

    @property
    def heads_pool(self):
        return self.bets.filter(
            side=self.HEADS, status__in=[Bet.PENDING, Bet.WON, Bet.LOST]
        ).aggregate(total=models.Sum("amount"))["total"] or Decimal("0")

    @property
    def tails_pool(self):
        return self.bets.filter(
            side=self.TAILS, status__in=[Bet.PENDING, Bet.WON, Bet.LOST]
        ).aggregate(total=models.Sum("amount"))["total"] or Decimal("0")

    def settle(self, winning_side):
        """
        Declare winner, credit winning bettors proportionally from the
        losing pool (minus house edge), and mark match settled.
        Must be called inside an atomic block.
        """
        if self.status == self.SETTLED:
            raise ValueError("Match already settled")
        if winning_side not in (self.HEADS, self.TAILS):
            raise ValueError("Invalid winning side")

        losing_side = self.TAILS if winning_side == self.HEADS else self.HEADS

        winning_bets = list(
            self.bets.select_for_update().filter(
                side=winning_side, status=Bet.PENDING
            )
        )
        losing_bets = list(
            self.bets.select_for_update().filter(
                side=losing_side, status=Bet.PENDING
            )
        )

        total_winning_pool = sum(b.amount for b in winning_bets)
        total_losing_pool = sum(b.amount for b in losing_bets)

        # House takes edge % from the losing pool
        house_cut = total_losing_pool * (self.house_edge / Decimal("100"))
        prize_pool = total_losing_pool - house_cut

        # Each winner gets their stake back + share of prize pool
        for bet in winning_bets:
            if total_winning_pool > 0:
                share = (bet.amount / total_winning_pool) * prize_pool
            else:
                share = Decimal("0")
            payout = bet.amount + share
            bet.payout = payout
            bet.status = Bet.WON
            bet.save()

            wallet = bet.user.wallet
            wallet.credit(
                payout,
                description=f"Won bet on '{self.title}' ({winning_side})"
            )

        for bet in losing_bets:
            bet.status = Bet.LOST
            bet.payout = Decimal("0")
            bet.save()

        self.winning_side = winning_side
        self.status = self.SETTLED
        self.settled_at = timezone.now()
        self.save()

    def cancel(self):
        """Refund all pending bets and cancel the match."""
        pending = self.bets.select_for_update().filter(status=Bet.PENDING)
        for bet in pending:
            bet.status = Bet.REFUNDED
            bet.save()
            bet.user.wallet.credit(
                bet.amount,
                description=f"Refund for cancelled match '{self.title}'"
            )
        self.status = self.CANCELLED
        self.save()


class Bet(models.Model):
    PENDING = "pending"
    WON = "won"
    LOST = "lost"
    REFUNDED = "refunded"

    STATUS_CHOICES = [
        (PENDING, "Pending"),
        (WON, "Won"),
        (LOST, "Lost"),
        (REFUNDED, "Refunded"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="bets")
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name="bets")
    side = models.CharField(max_length=10, choices=Match.SIDE_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payout = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    placed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-placed_at"]
        # One bet per user per match
        unique_together = ("user", "match")
        verbose_name = "bet"
        verbose_name_plural = "bets"

    def __str__(self):
        return f"{self.user.username} → {self.match.title} [{self.side}] {self.amount}"

    @classmethod
    def place(cls, user, match, side, amount):
        """
        Deduct coins and create a bet in one atomic transaction.
        Raises ValueError on any validation failure.
        """
        with transaction.atomic():
            wallet = user.wallet.__class__.objects.select_for_update().get(user=user)
            if match.status != Match.PENDING:
                raise ValueError("Betting is closed for this match")
            if amount < match.min_bet:
                raise ValueError(f"Minimum bet is {match.min_bet} coins")
            if amount > match.max_bet:
                raise ValueError(f"Maximum bet is {match.max_bet} coins")
            if wallet.balance < amount:
                raise ValueError("Insufficient coins in your wallet")
            if cls.objects.filter(user=user, match=match).exists():
                raise ValueError("You have already placed a bet on this match")

            wallet.debit(amount, description=f"Bet on '{match.title}' ({side})")
            return cls.objects.create(
                user=user, match=match, side=side, amount=amount
            )
