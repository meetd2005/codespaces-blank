from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from django.db import transaction as db_transaction
from django.contrib import messages
from .models import Deposit, Withdrawal, Transaction


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("wallet", "kind_badge", "amount", "balance_after", "description", "created_at")
    list_filter = ("kind",)
    search_fields = ("wallet__user__username", "description")
    readonly_fields = ("wallet", "kind", "amount", "balance_after", "description", "created_at")
    ordering = ("-created_at",)

    @admin.display(description="Type")
    def kind_badge(self, obj):
        colour = "green" if obj.kind == Transaction.CREDIT else "red"
        return format_html(
            '<b style="color:{}">{}</b>', colour, obj.get_kind_display()
        )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Deposit)
class DepositAdmin(admin.ModelAdmin):
    list_display = (
        "short_ref", "user", "rupee_amount", "coins",
        "upi_ref", "status_badge", "screenshot_link", "requested_at"
    )
    list_filter = ("status",)
    search_fields = ("user__username", "upi_ref", "ref")
    readonly_fields = (
        "ref", "user", "rupee_amount", "coins",
        "upi_ref", "screenshot_preview", "requested_at"
    )
    actions = ["confirm_deposits", "reject_deposits"]

    fieldsets = (
        ("Request", {"fields": ("ref", "user", "rupee_amount", "coins", "requested_at")}),
        ("Payment Proof", {"fields": ("upi_ref", "screenshot_preview")}),
        ("Admin", {"fields": ("status", "admin_note", "confirmed_by", "confirmed_at")}),
    )

    @admin.display(description="Ref")
    def short_ref(self, obj):
        return obj.short_ref

    @admin.display(description="Status")
    def status_badge(self, obj):
        colours = {
            Deposit.PENDING: "orange",
            Deposit.UNDER_REVIEW: "blue",
            Deposit.CONFIRMED: "green",
            Deposit.REJECTED: "red",
        }
        return format_html(
            '<span style="color:{};font-weight:bold">{}</span>',
            colours.get(obj.status, "grey"),
            obj.get_status_display(),
        )

    @admin.display(description="Screenshot")
    def screenshot_link(self, obj):
        if obj.screenshot:
            return format_html('<a href="{}" target="_blank">View</a>', obj.screenshot.url)
        return "—"

    @admin.display(description="Screenshot")
    def screenshot_preview(self, obj):
        if obj.screenshot:
            return format_html(
                '<img src="{}" style="max-height:300px;max-width:500px" />',
                obj.screenshot.url
            )
        return "No screenshot"

    @admin.action(description="✅ Confirm selected deposits (credit coins)")
    def confirm_deposits(self, request, queryset):
        for dep in queryset.filter(status__in=[Deposit.PENDING, Deposit.UNDER_REVIEW]):
            try:
                with db_transaction.atomic():
                    wallet = dep.user.wallet.__class__.objects.select_for_update().get(user=dep.user)
                    wallet.credit(dep.coins, description=f"Deposit #{dep.short_ref} confirmed")
                    dep.status = Deposit.CONFIRMED
                    dep.confirmed_at = timezone.now()
                    dep.confirmed_by = request.user
                    dep.save()
                self.message_user(
                    request,
                    f"Deposit #{dep.short_ref} confirmed — {dep.coins} coins credited to {dep.user.username}",
                    level=messages.SUCCESS,
                )
            except Exception as e:
                self.message_user(request, f"Error: {e}", level=messages.ERROR)

    @admin.action(description="❌ Reject selected deposits")
    def reject_deposits(self, request, queryset):
        updated = queryset.filter(
            status__in=[Deposit.PENDING, Deposit.UNDER_REVIEW]
        ).update(status=Deposit.REJECTED)
        self.message_user(request, f"{updated} deposit(s) rejected.", level=messages.WARNING)


@admin.register(Withdrawal)
class WithdrawalAdmin(admin.ModelAdmin):
    list_display = (
        "short_ref", "user", "coins", "rupee_amount",
        "upi_id", "status_badge", "upi_ref_paid", "requested_at"
    )
    list_filter = ("status",)
    search_fields = ("user__username", "upi_id", "ref", "upi_ref_paid")
    readonly_fields = ("ref", "user", "coins", "rupee_amount", "upi_id", "requested_at")
    actions = ["approve_withdrawals", "mark_paid", "reject_withdrawals"]

    fieldsets = (
        ("Request", {"fields": ("ref", "user", "coins", "rupee_amount", "upi_id", "requested_at")}),
        ("Processing", {"fields": ("status", "admin_note", "upi_ref_paid", "processed_by", "processed_at")}),
    )

    @admin.display(description="Ref")
    def short_ref(self, obj):
        return obj.short_ref

    @admin.display(description="Status")
    def status_badge(self, obj):
        colours = {
            Withdrawal.PENDING: "orange",
            Withdrawal.APPROVED: "blue",
            Withdrawal.PAID: "green",
            Withdrawal.REJECTED: "red",
        }
        return format_html(
            '<span style="color:{};font-weight:bold">{}</span>',
            colours.get(obj.status, "grey"),
            obj.get_status_display(),
        )

    @admin.action(description="Approve selected withdrawals (deduct coins)")
    def approve_withdrawals(self, request, queryset):
        for wd in queryset.filter(status=Withdrawal.PENDING):
            try:
                with db_transaction.atomic():
                    wallet = wd.user.wallet.__class__.objects.select_for_update().get(user=wd.user)
                    wallet.debit(wd.coins, description=f"Withdrawal #{wd.short_ref} approved")
                    wd.status = Withdrawal.APPROVED
                    wd.processed_by = request.user
                    wd.processed_at = timezone.now()
                    wd.save()
                self.message_user(
                    request,
                    f"Withdrawal #{wd.short_ref} approved — {wd.coins} coins deducted from {wd.user.username}",
                    level=messages.SUCCESS,
                )
            except ValueError as e:
                self.message_user(request, f"Error for {wd.user.username}: {e}", level=messages.ERROR)

    @admin.action(description="Mark selected withdrawals as PAID (UPI sent)")
    def mark_paid(self, request, queryset):
        updated = queryset.filter(status=Withdrawal.APPROVED).update(
            status=Withdrawal.PAID,
            processed_at=timezone.now(),
            processed_by=request.user,
        )
        self.message_user(request, f"{updated} withdrawal(s) marked paid.", level=messages.SUCCESS)

    @admin.action(description="Reject & refund selected withdrawals")
    def reject_withdrawals(self, request, queryset):
        for wd in queryset.filter(status=Withdrawal.PENDING):
            wd.status = Withdrawal.REJECTED
            wd.save()
        self.message_user(request, "Selected withdrawals rejected.", level=messages.WARNING)
