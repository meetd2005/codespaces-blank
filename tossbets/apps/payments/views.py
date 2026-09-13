"""
Payments views — deposit (QR-based) and withdrawal flows.
"""
import io
import urllib.parse
from decimal import Decimal

import qrcode
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from .forms import DepositConfirmForm, DepositRequestForm, WithdrawalForm
from .models import Deposit, Transaction, Withdrawal


# ──────────────────────────────────────────────────────────────────────────────
# QR image helper
# ──────────────────────────────────────────────────────────────────────────────

def _upi_qr_png(upi_id: str, name: str, amount: Decimal, ref: str) -> bytes:
    """Generate a UPI deep-link QR code and return PNG bytes."""
    params = {
        "pa": upi_id,          # payee address
        "pn": name,             # payee name
        "am": str(amount),      # amount
        "tn": f"TossBets deposit {ref}",  # transaction note
        "cu": "INR",
    }
    upi_url = "upi://pay?" + urllib.parse.urlencode(params)
    img = qrcode.make(upi_url, box_size=8, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ──────────────────────────────────────────────────────────────────────────────
# Deposit
# ──────────────────────────────────────────────────────────────────────────────

@login_required
def deposit_request(request):
    """Step 1: user enters rupee amount → creates pending Deposit → shows QR."""
    if request.method == "POST":
        form = DepositRequestForm(request.POST)
        if form.is_valid():
            rupee_amount = form.cleaned_data["rupee_amount"]
            coins = Deposit.calculate_coins(rupee_amount)
            dep = Deposit.objects.create(
                user=request.user,
                rupee_amount=rupee_amount,
                coins=coins,
            )
            return redirect("payments:deposit_pay", pk=dep.pk)
    else:
        form = DepositRequestForm()
    return render(request, "payments/deposit_request.html", {"form": form})


@login_required
def deposit_pay(request, pk):
    """Step 2: show QR + let user submit UTR proof."""
    dep = get_object_or_404(Deposit, pk=pk, user=request.user)

    if dep.status in (Deposit.CONFIRMED, Deposit.REJECTED):
        return redirect("payments:deposit_list")

    if request.method == "POST" and dep.status == Deposit.PENDING:
        form = DepositConfirmForm(request.POST, request.FILES, instance=dep)
        if form.is_valid():
            dep = form.save(commit=False)
            dep.status = Deposit.UNDER_REVIEW
            dep.save()
            messages.success(
                request,
                "Payment submitted for review. Coins will be credited once admin verifies."
            )
            return redirect("payments:deposit_list")
    else:
        form = DepositConfirmForm(instance=dep)

    return render(request, "payments/deposit_pay.html", {"dep": dep, "form": form})


@login_required
def deposit_qr_image(request, pk):
    """Serve a fresh UPI QR PNG for a deposit."""
    dep = get_object_or_404(Deposit, pk=pk, user=request.user)
    png = _upi_qr_png(
        upi_id=settings.UPI_ID,
        name=settings.UPI_NAME,
        amount=dep.rupee_amount,
        ref=dep.short_ref,
    )
    return HttpResponse(png, content_type="image/png")


@login_required
def deposit_list(request):
    deps = Deposit.objects.filter(user=request.user).order_by("-requested_at")
    paginator = Paginator(deps, 15)
    page = paginator.get_page(request.GET.get("page"))
    return render(request, "payments/deposit_list.html", {"page": page})


# ──────────────────────────────────────────────────────────────────────────────
# Withdrawal
# ──────────────────────────────────────────────────────────────────────────────

@login_required
def withdrawal_request(request):
    if request.method == "POST":
        form = WithdrawalForm(request.user, request.POST)
        if form.is_valid():
            coins = form.cleaned_data["coins"]
            upi_id = form.cleaned_data["upi_id"]
            rate = getattr(settings, "COIN_RUPEE_RATE", 1)
            rupee_amount = coins / Decimal(str(rate))
            Withdrawal.objects.create(
                user=request.user,
                coins=coins,
                rupee_amount=rupee_amount,
                upi_id=upi_id,
            )
            messages.success(
                request,
                f"Withdrawal of {coins} coins requested. "
                "Admin will process within 24 hours."
            )
            return redirect("payments:withdrawal_list")
    else:
        form = WithdrawalForm(request.user)
    return render(request, "payments/withdrawal_request.html", {"form": form})


@login_required
def withdrawal_list(request):
    wds = Withdrawal.objects.filter(user=request.user).order_by("-requested_at")
    paginator = Paginator(wds, 15)
    page = paginator.get_page(request.GET.get("page"))
    return render(request, "payments/withdrawal_list.html", {"page": page})


# ──────────────────────────────────────────────────────────────────────────────
# Transaction history
# ──────────────────────────────────────────────────────────────────────────────

@login_required
def transaction_history(request):
    txns = Transaction.objects.filter(
        wallet__user=request.user
    ).order_by("-created_at")
    paginator = Paginator(txns, 20)
    page = paginator.get_page(request.GET.get("page"))
    return render(request, "payments/transactions.html", {"page": page})
