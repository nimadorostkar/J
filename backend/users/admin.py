# === FILE: backend/users/admin.py ===
import csv

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.http import HttpResponse

from .models import EmailVerificationToken, PasswordResetToken, User


@admin.action(description="Export selected users to CSV")
def export_users_csv(modeladmin, request, queryset):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = "attachment; filename=users.csv"
    writer = csv.writer(response)
    writer.writerow([
        "id", "email", "first_name", "last_name", "phone", "country",
        "referral_code", "referred_by", "is_email_verified", "created_at",
    ])
    for u in queryset.select_related("referred_by"):
        writer.writerow([
            u.id, u.email, u.first_name, u.last_name, u.phone, u.country,
            u.referral_code,
            (u.referred_by.email if u.referred_by else ""),
            u.is_email_verified, u.created_at,
        ])
    return response


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    actions = [export_users_csv]
    ordering = ("-created_at",)
    list_display = ("email", "first_name", "last_name", "referral_code",
                    "referred_by", "is_email_verified", "is_staff", "created_at")
    list_filter = ("is_email_verified", "is_staff", "is_superuser", "country")
    search_fields = ("email", "first_name", "last_name", "referral_code", "phone")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal", {"fields": ("first_name", "last_name", "phone",
                                  "country_code", "country", "avatar")}),
        ("Referral", {"fields": ("referral_code", "referred_by")}),
        ("Verification", {"fields": ("is_email_verified",)}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser",
                                     "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "created_at")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "password1", "password2", "first_name", "last_name"),
        }),
    )
    readonly_fields = ("referral_code", "created_at")


admin.site.register(EmailVerificationToken)
admin.site.register(PasswordResetToken)
