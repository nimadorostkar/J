# === FILE: backend/wallet/admin.py ===
from decimal import Decimal

from django import forms
from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils.html import format_html

from .models import DepositAddress, Wallet
from .services import admin_credit_manual_deposit


@admin.action(description="Reset reward cycle")
def reset_reward_cycle(modeladmin, request, queryset):
    queryset.update(reward_active=False, reward_end_time=None)


class _ManualDepositForm(forms.Form):
    """Admin-only form: pick a user, an amount, optional note."""

    user = forms.ModelChoiceField(
        queryset=None,  # set in __init__ so we can sort by email at request time
        label="Target user",
        help_text="Wallet to credit. Searches by email.",
    )
    amount_usdt = forms.DecimalField(
        max_digits=18,
        decimal_places=8,
        min_value=Decimal("0.00000001"),
        label="Amount (USDT)",
    )
    note = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
        max_length=500,
        label="Internal note",
        help_text="Saved to the audit log only — never shown to the user.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        User = get_user_model()
        self.fields["user"].queryset = User.objects.order_by("email")


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = (
        "user", "h_coin_balance", "usdt_balance",
        "reward_active", "has_completed_deposit", "has_referral",
        "updated_at",
    )
    list_filter = ("reward_active", "has_completed_deposit", "has_referral")
    search_fields = ("user__email",)
    readonly_fields = ("updated_at",)
    actions = [reset_reward_cycle]

    # Adds a "Manual deposit" button at the top of the Wallet changelist.
    change_list_template = "admin/wallet/wallet_changelist.html"

    def get_urls(self):
        urls = super().get_urls()
        extra = [
            path(
                "manual-deposit/",
                self.admin_site.admin_view(self.manual_deposit_view),
                name="wallet_wallet_manual_deposit",
            ),
        ]
        return extra + urls

    def manual_deposit_view(self, request):
        """Admin form for issuing a manual deposit.

        Reuses `admin_credit_manual_deposit` so the audit/notification/WS
        fan-out is identical to what a real on-chain deposit triggers.
        """
        if not request.user.is_staff:
            return redirect("admin:login")

        if request.method == "POST":
            form = _ManualDepositForm(request.POST)
            if form.is_valid():
                target = form.cleaned_data["user"]
                amount = form.cleaned_data["amount_usdt"]
                note = form.cleaned_data["note"]
                try:
                    # Ensure a wallet exists (mirrors the API view's behaviour).
                    Wallet.objects.get_or_create(user=target)
                    tx = admin_credit_manual_deposit(
                        admin_user=request.user,
                        target_user=target,
                        amount_usdt=amount,
                        note=note,
                        ip=request.META.get("REMOTE_ADDR"),
                    )
                    messages.success(
                        request,
                        format_html(
                            "Credited <b>{}</b> USDT to <b>{}</b> (tx <code>{}</code>).",
                            amount, target.email, tx.id,
                        ),
                    )
                    return redirect("admin:wallet_wallet_changelist")
                except Exception as e:  # surface to the form, never 500
                    messages.error(request, f"Failed: {e}")
        else:
            form = _ManualDepositForm()

        context = {
            **self.admin_site.each_context(request),
            "title": "Manual deposit",
            "subtitle": "Credit a user's wallet as a real successful deposit",
            "form": form,
            "opts": Wallet._meta,
            "has_view_permission": True,
            "cancel_url": reverse("admin:wallet_wallet_changelist"),
        }
        return render(request, "admin/wallet/manual_deposit.html", context)


@admin.register(DepositAddress)
class DepositAddressAdmin(admin.ModelAdmin):
    list_display = ("user", "network", "address", "is_active", "created_at")
    list_filter = ("network", "is_active")
    search_fields = ("address", "user__email")
