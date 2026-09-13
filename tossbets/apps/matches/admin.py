from django.contrib import admin
from django.utils.html import format_html
from django.db import transaction
from django.contrib import messages
from .models import Match, Bet


class BetInline(admin.TabularInline):
    model = Bet
    extra = 0
    readonly_fields = ("user", "side", "amount", "payout", "status", "placed_at")
    can_delete = False


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = (
        "title", "status_badge", "heads_pool", "tails_pool",
        "bet_count", "winning_side", "starts_at", "created_by"
    )
    list_filter = ("status",)
    search_fields = ("title",)
    readonly_fields = ("settled_at", "created_at")
    inlines = [BetInline]
    actions = ["declare_heads", "declare_tails", "cancel_matches", "lock_betting"]

    fieldsets = (
        (None, {"fields": ("title", "description", "status", "winning_side")}),
        ("Betting Rules", {"fields": ("min_bet", "max_bet", "house_edge")}),
        ("Schedule", {"fields": ("starts_at", "betting_closes_at", "settled_at")}),
        ("Meta", {"fields": ("created_by", "created_at")}),
    )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    @admin.display(description="Status")
    def status_badge(self, obj):
        colours = {
            Match.PENDING: "green",
            Match.LOCKED: "orange",
            Match.SETTLED: "blue",
            Match.CANCELLED: "red",
        }
        colour = colours.get(obj.status, "grey")
        return format_html(
            '<span style="color:{}; font-weight:bold">{}</span>',
            colour, obj.get_status_display()
        )

    @admin.display(description="# Bets")
    def bet_count(self, obj):
        return obj.bets.count()

    @admin.action(description="Declare HEADS as winner")
    def declare_heads(self, request, queryset):
        self._settle(request, queryset, Match.HEADS)

    @admin.action(description="Declare TAILS as winner")
    def declare_tails(self, request, queryset):
        self._settle(request, queryset, Match.TAILS)

    def _settle(self, request, queryset, side):
        for match in queryset:
            if match.status != Match.PENDING:
                self.message_user(
                    request,
                    f"'{match.title}' is already {match.status}, skipped.",
                    level=messages.WARNING,
                )
                continue
            try:
                with transaction.atomic():
                    match.settle(side)
                self.message_user(
                    request,
                    f"'{match.title}' settled → {side.upper()} wins. Coins distributed.",
                    level=messages.SUCCESS,
                )
            except Exception as e:
                self.message_user(request, f"Error settling '{match.title}': {e}", level=messages.ERROR)

    @admin.action(description="Cancel selected matches (refund all bets)")
    def cancel_matches(self, request, queryset):
        for match in queryset:
            if match.status == Match.SETTLED:
                self.message_user(
                    request,
                    f"'{match.title}' already settled, cannot cancel.",
                    level=messages.WARNING,
                )
                continue
            try:
                with transaction.atomic():
                    match.cancel()
                self.message_user(
                    request,
                    f"'{match.title}' cancelled. All bets refunded.",
                    level=messages.SUCCESS,
                )
            except Exception as e:
                self.message_user(request, f"Error: {e}", level=messages.ERROR)

    @admin.action(description="Lock betting (no new bets accepted)")
    def lock_betting(self, request, queryset):
        updated = queryset.filter(status=Match.PENDING).update(status=Match.LOCKED)
        self.message_user(request, f"{updated} match(es) locked.", level=messages.SUCCESS)


@admin.register(Bet)
class BetAdmin(admin.ModelAdmin):
    list_display = ("user", "match", "side", "amount", "payout", "status", "placed_at")
    list_filter = ("status", "side")
    search_fields = ("user__username", "match__title")
    readonly_fields = ("user", "match", "side", "amount", "payout", "placed_at")
    ordering = ("-placed_at",)

    def has_add_permission(self, request):
        return False
