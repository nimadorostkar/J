# === FILE: backend/users/management/commands/ensure_admin.py ===
"""
Idempotently create or refresh a superuser.

The default credentials match the project's documented admin login:
    email:    admin@admin.com
    password: 123qweQWE

Safe to run repeatedly. If the user already exists this command:
  * promotes them to staff + superuser if they aren't already,
  * resets the password to the supplied value,
  * marks their email as verified.

Usage:
    docker compose exec django python manage.py ensure_admin
    docker compose exec django python manage.py ensure_admin --email foo@bar.com --password secret
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction


DEFAULT_EMAIL = "admin@admin.com"
DEFAULT_PASSWORD = "123qweQWE"


class Command(BaseCommand):
    help = "Create or refresh a superuser (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument("--email", default=DEFAULT_EMAIL)
        parser.add_argument("--password", default=DEFAULT_PASSWORD)
        parser.add_argument(
            "--first-name",
            default="Admin",
            help="First name for newly-created superusers.",
        )
        parser.add_argument(
            "--last-name",
            default="User",
            help="Last name for newly-created superusers.",
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        User = get_user_model()
        email = User.objects.normalize_email(opts["email"]).lower()
        password = opts["password"]

        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            user = User.objects.create_superuser(
                email=email,
                password=password,
                first_name=opts["first_name"],
                last_name=opts["last_name"],
            )
            self.stdout.write(self.style.SUCCESS(f"Created superuser {email}."))
            return

        # Already exists — make sure it's a fully-privileged, password-known
        # account so re-running this command is enough to "reset" the admin.
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.is_email_verified = True
        user.set_password(password)
        user.save(
            update_fields=[
                "is_staff",
                "is_superuser",
                "is_active",
                "is_email_verified",
                "password",
            ]
        )
        self.stdout.write(self.style.SUCCESS(f"Refreshed superuser {email} (password reset)."))
