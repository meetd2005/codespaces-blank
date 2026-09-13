from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from .models import Match, Bet
from .forms import PlaceBetForm


def lobby(request):
    """Public-facing list of open matches."""
    open_matches = Match.objects.filter(status=Match.PENDING).order_by("-created_at")
    recent_settled = Match.objects.filter(status=Match.SETTLED).order_by("-settled_at")[:5]
    return render(request, "matches/lobby.html", {
        "open_matches": open_matches,
        "recent_settled": recent_settled,
    })


def match_detail(request, pk):
    match = get_object_or_404(Match, pk=pk)
    user_bet = None
    form = None

    if request.user.is_authenticated:
        user_bet = Bet.objects.filter(user=request.user, match=match).first()
        if match.status == Match.PENDING and not user_bet:
            form = PlaceBetForm(match)

    bets = Bet.objects.filter(match=match).select_related("user").order_by("-placed_at")

    return render(request, "matches/detail.html", {
        "match": match,
        "user_bet": user_bet,
        "form": form,
        "bets": bets,
    })


@login_required
def place_bet(request, pk):
    match = get_object_or_404(Match, pk=pk)
    if request.method != "POST":
        return redirect("matches:detail", pk=pk)

    if match.status != Match.PENDING:
        messages.error(request, "Betting is closed for this match.")
        return redirect("matches:detail", pk=pk)

    form = PlaceBetForm(match, request.POST)
    if not form.is_valid():
        for err in form.errors.values():
            messages.error(request, err.as_text())
        return redirect("matches:detail", pk=pk)

    side = form.cleaned_data["side"]
    amount = form.cleaned_data["amount"]

    try:
        Bet.place(request.user, match, side, amount)
        messages.success(
            request,
            f"Bet placed! {amount} coins on {side.upper()} for '{match.title}'."
        )
    except ValueError as e:
        messages.error(request, str(e))

    return redirect("matches:detail", pk=pk)


@login_required
def my_bets(request):
    qs = Bet.objects.filter(user=request.user).select_related("match").order_by("-placed_at")
    paginator = Paginator(qs, 15)
    page = paginator.get_page(request.GET.get("page"))
    return render(request, "matches/my_bets.html", {"page": page})
