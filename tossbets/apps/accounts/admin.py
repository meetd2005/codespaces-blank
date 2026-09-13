from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import User, Wallet


class WalletInline(admin.StackedInline):
    model = Wallet
    can_delete = False
    readonly_fields = ("balance", "total_deposited", "total_withdrawn", "updated_at")
    verbose_name = "Coin Wallet"


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = [WalletInline]
    list_display = (
        "username", "email", "phone", "coin_balance", "is_verified",
        "is_active", "date_joined"
    )
    list_filter = ("is_verified", "is_active", "is_staff")
    search_fields = ("username", "email", "phone")
    list_editable = ("is_verified", "is_active")
    fieldsets = BaseUserAdmin.fieldsets + (
        ("TossBets", {"fields": ("phone", "upi_id", "is_verified")}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("TossBets", {"fields": ("phone", "upi_id", "email")}),
    )

    @admin.display(description="Coins")
    def coin_balance(self, obj):
        try:
            bal = obj.wallet.balance
        except Wallet.DoesNotExist:
            bal = 0
        color = "green" if bal > 0 else "grey"
        return format_html('<b style="color:{}">{}</b>', color, bal)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        Wallet.objects.get_or_create(user=obj)


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ("user", "balance", "total_deposited", "total_withdrawn", "updated_at")
    readonly_fields = ("balance", "total_deposited", "total_withdrawn", "updated_at")
    search_fields = ("user__username", "user__email")
    ordering = ("-balance",)

    def has_add_permission(self, request):
        return False
