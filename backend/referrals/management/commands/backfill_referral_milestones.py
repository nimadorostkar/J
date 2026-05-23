# === FILE: backend/referrals/management/commands/backfill_referral_milestones.py ===
"""
One-shot backfill that walks every user with at least one L1 referral and
pays any milestone rewards they should have received but never did.

Safe to run repeatedly — `pay_referral_milestones()` is idempotent via the
unique constraint on (user, milestone). Re-running it on an already-paid
user is a no-op.

Usage:
    docker compose exec django python manage.py backfill_referral_milestones
    docker compose exec django python manage.py backfill_referral_milestones --user=admin@admin.com
    docker compose exec django python manage.py backfill_referral_milestones --dry-run
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction as db_tx

from referrals.models import Referral
from referrals.services import pay_referral_milestones

User = get_user_model()


class Command(BaseCommand):
    help = "Pay any unpaid referral milestone rewards for existing users."

    def add_arguments(self, parser):
        parser.add_argument(
            "--user",
            help="Only backfill for the user with this email "
                 "(otherwise: all users with ≥1 L1 referral).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would be paid without actually crediting wallets.",
        )

    def handle(self, *args, **opts):
        email = opts.get("user")
        dry_run = opts.get("dry_run", False)

        if email:
            qs = User.objects.filter(email__iexact=email)
        else:
            # Every user who has invited at least one L1 referral.
            inviter_ids = (
                Referral.objects.filter(level=1)
                .values_list("inviter_id", flat=True)
                .distinct()
            )
            qs = User.objects.filter(id__in=list(inviter_ids))

        total_users = qs.count()
        self.stdout.write(
            f"Found {total_users} candidate user(s)"
            + (" (dry-run)" if dry_run else "")
        )

        total_awarded = 0
        for user in qs.iterator():
            l1_count = Referral.objects.filter(inviter=user, level=1).count()
            if dry_run:
                # Show what *would* be paid: count of milestone tiers that
                # don't yet have a ReferralMilestoneReward row.
                from referrals.models import ReferralMilestoneReward
                from django.conf import settings
                size = int(settings.REFERRAL_MILESTONE_SIZE or 1)
                tiers_earned = l1_count // size if size > 0 else 0
                paid = set(
                    ReferralMilestoneReward.objects.filter(user=user)
                    .values_list("milestone", flat=True)
                )
                missing = [
                    i * size for i in range(1, tiers_earned + 1)
                    if i * size not in paid
                ]
                if missing:
                    self.stdout.write(
                        self.style.WARNING(
                            f"  WOULD PAY {user.email}: "
                            f"L1={l1_count}, missing milestones={missing}"
                        )
                    )
                continue

            with db_tx.atomic():
                awarded = pay_referral_milestones(user)
            if awarded:
                total_awarded += len(awarded)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  {user.email}: L1={l1_count}, paid milestones={awarded}"
                    )
                )

        if dry_run:
            self.stdout.write("(dry-run complete — no wallets credited)")
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Backfill complete. Paid {total_awarded} milestone(s) "
                    f"across {total_users} candidate user(s)."
                )
            )
