# === FILE: backend/referrals/services.py ===
"""Referral commission engine + milestone rewards.

`distribute_commission(user, profit_hcoin)` MUST be called *inside* the
same atomic block as the original profit credit. It is intentionally
synchronous so inviters are paid (or not paid) atomically with the
event that triggered the payout.

`pay_referral_milestones(user)` is called after a new L1 referral is
created. It is idempotent: every milestone tier the user has reached is
recorded in ReferralMilestoneReward with a unique (user, milestone)
constraint, so duplicate or racing calls can never double-credit.
"""
import logging
from decimal import Decimal

from django.conf import settings
from django.db import IntegrityError, transaction as db_tx

from core.audit import log_audit

logger = logging.getLogger("tokenvault")


def _push_event(user_id, event_type, **payload):
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
        layer = get_channel_layer()
        if not layer:
            return
        async_to_sync(layer.group_send)(
            f"wallet_{user_id}",
            {"type": event_type, **payload},
        )
    except Exception:
        logger.exception("Failed to push commission event")


def distribute_commission(user, profit_hcoin: Decimal):
    """Credit L1 (and L2, if applicable) inviters their share of `profit_hcoin`.

    Must be called from inside an atomic block. Internally we use a
    nested savepoint via `transaction.atomic()` and `select_for_update()`
    on referral rows + wallets to guard against concurrent writes.
    """
    if profit_hcoin is None or profit_hcoin <= 0:
        return

    from referrals.models import Referral
    from transactions.models import Transaction
    from wallet.models import Wallet

    l1_pct = Decimal(settings.REFERRAL_L1_COMMISSION_PCT)
    l2_pct = Decimal(settings.REFERRAL_L2_COMMISSION_PCT)

    with db_tx.atomic():
        # ── Level 1 ──────────────────────────────────────────────
        ref_l1 = (
            Referral.objects.select_for_update()
            .filter(invited_user=user, level=1)
            .select_related("inviter")
            .first()
        )
        if ref_l1:
            l1_amount = (profit_hcoin * l1_pct / Decimal(100)).quantize(Decimal("0.00000001"))
            if l1_amount > 0:
                inviter = ref_l1.inviter
                inviter_wallet = (
                    Wallet.objects.select_for_update().get(user=inviter)
                )
                inviter_wallet.h_coin_balance = inviter_wallet.h_coin_balance + l1_amount
                inviter_wallet.save(update_fields=["h_coin_balance", "updated_at"])

                Transaction.objects.create(
                    user=inviter,
                    wallet=inviter_wallet,
                    type="commission",
                    network=None,
                    amount_hcoin=l1_amount,
                    status="completed",
                    commission_from_user=user,
                    commission_level=1,
                    commission_rate=l1_pct,
                )
                ref_l1.total_commission_earned_hcoin = (
                    ref_l1.total_commission_earned_hcoin + l1_amount
                )
                ref_l1.save(update_fields=["total_commission_earned_hcoin"])
                log_audit("commission_pay", user=inviter,
                          level=1, amount=str(l1_amount),
                          from_user=str(user.id))

                # Notify (deferred to Celery for the email/notification row)
                from notifications.tasks import send_notification
                send_notification.delay(
                    str(inviter.id),
                    title="Referral commission earned",
                    body=(f"You earned {l1_amount} H Coins commission from "
                          f"{user.first_name or user.email}'s reward."),
                    notification_type="commission",
                )
                _push_event(
                    inviter.id,
                    "commission_received",
                    amount=str(l1_amount),
                    level=1,
                    from_user={"id": str(user.id),
                               "firstName": user.first_name},
                )
                _push_event(
                    inviter.id,
                    "balance_update",
                    h_coins=str(inviter_wallet.h_coin_balance),
                    usdt_balance=str(inviter_wallet.usdt_balance),
                )

        # ── Level 2 ──────────────────────────────────────────────
        ref_l2 = (
            Referral.objects.select_for_update()
            .filter(invited_user=user, level=2)
            .select_related("inviter")
            .first()
        )
        if ref_l2:
            l2_amount = (profit_hcoin * l2_pct / Decimal(100)).quantize(Decimal("0.00000001"))
            if l2_amount > 0:
                inviter = ref_l2.inviter
                inviter_wallet = (
                    Wallet.objects.select_for_update().get(user=inviter)
                )
                inviter_wallet.h_coin_balance = inviter_wallet.h_coin_balance + l2_amount
                inviter_wallet.save(update_fields=["h_coin_balance", "updated_at"])

                Transaction.objects.create(
                    user=inviter,
                    wallet=inviter_wallet,
                    type="commission",
                    network=None,
                    amount_hcoin=l2_amount,
                    status="completed",
                    commission_from_user=user,
                    commission_level=2,
                    commission_rate=l2_pct,
                )
                ref_l2.total_commission_earned_hcoin = (
                    ref_l2.total_commission_earned_hcoin + l2_amount
                )
                ref_l2.save(update_fields=["total_commission_earned_hcoin"])
                log_audit("commission_pay", user=inviter,
                          level=2, amount=str(l2_amount),
                          from_user=str(user.id))

                from notifications.tasks import send_notification
                send_notification.delay(
                    str(inviter.id),
                    title="Level-2 commission earned",
                    body=(f"You earned {l2_amount} H Coins commission from "
                          f"{user.first_name or user.email}'s reward."),
                    notification_type="commission",
                )
                _push_event(
                    inviter.id,
                    "commission_received",
                    amount=str(l2_amount),
                    level=2,
                    from_user={"id": str(user.id),
                               "firstName": user.first_name},
                )
                _push_event(
                    inviter.id,
                    "balance_update",
                    h_coins=str(inviter_wallet.h_coin_balance),
                    usdt_balance=str(inviter_wallet.usdt_balance),
                )


# ──────────────────────────────────────────────────────────────────────
# Milestone rewards
# ──────────────────────────────────────────────────────────────────────

def pay_referral_milestones(user):
    """
    Award the inviter a flat coin reward for every Nth successful L1
    referral they've earned. Safe to call multiple times — each milestone
    tier is recorded in ReferralMilestoneReward with a unique constraint
    on (user, milestone), so duplicate calls can never double-pay.

    Returns a list of newly-awarded milestone numbers (empty if there was
    nothing to pay). Designed to be called inside the same atomic block
    as the registration that created the L1 referral, but uses a nested
    atomic + IntegrityError catch so a failed milestone insert doesn't
    blow up the outer transaction.

    Race-safety:
      • SELECT FOR UPDATE on the inviter's wallet serializes balance writes.
      • SELECT FOR UPDATE on the milestone rows that already exist for
        this user serializes the "what tier are we at?" computation.
      • The unique constraint is the canonical last line of defense — if
        two transactions somehow both decide to insert milestone 5 at the
        same time, exactly one will succeed and the other rolls back its
        nested savepoint.
    """
    from referrals.models import Referral, ReferralMilestoneReward
    from transactions.models import Transaction
    from wallet.models import Wallet

    size = int(settings.REFERRAL_MILESTONE_SIZE or 0)
    reward_each = Decimal(settings.REFERRAL_MILESTONE_REWARD_HCOIN or 0)
    if size <= 0 or reward_each <= 0:
        return []

    awarded = []

    # Lock the wallet first so balance + milestone insert are serialized.
    try:
        wallet = Wallet.objects.select_for_update().get(user=user)
    except Wallet.DoesNotExist:
        logger.warning("pay_referral_milestones: no wallet for user %s", user.id)
        return []

    # Only QUALIFIED L1 referrals count toward milestones.
    # A referral is qualified once the invited user has completed at least
    # one deposit. Signups without deposits do not count — this prevents
    # farming rewards from inactive / fake accounts.
    referral_count = Referral.objects.qualified_for(user).count()
    earned_tiers = referral_count // size  # e.g. 12 refs / 5 = 2 tiers earned (5, 10)

    if earned_tiers <= 0:
        return []

    # Find which tiers we've already paid for, locked.
    paid_set = set(
        ReferralMilestoneReward.objects.select_for_update()
        .filter(user=user)
        .values_list("milestone", flat=True)
    )

    # Pay any tier we haven't paid yet.
    for i in range(1, earned_tiers + 1):
        milestone = i * size
        if milestone in paid_set:
            continue

        try:
            with db_tx.atomic():
                # Credit the wallet first.
                wallet.h_coin_balance = wallet.h_coin_balance + reward_each
                wallet.save(update_fields=["h_coin_balance", "updated_at"])

                # Audit / history row — Transaction shows up in user's
                # tx feed (TYPE_REFERRAL_MILESTONE).
                tx = Transaction.objects.create(
                    user=user,
                    wallet=wallet,
                    type=Transaction.TYPE_REFERRAL_MILESTONE,
                    network=None,
                    amount_hcoin=reward_each,
                    status=Transaction.STATUS_COMPLETED,
                )

                # The unique constraint on (user, milestone) is the
                # idempotency guarantee. If a parallel transaction beat
                # us to inserting this milestone, IntegrityError fires
                # and we roll the nested atomic back (wallet credit
                # included).
                ReferralMilestoneReward.objects.create(
                    user=user,
                    milestone=milestone,
                    amount_hcoin=reward_each,
                    transaction=tx,
                )

                log_audit(
                    "referral_milestone_pay",
                    user=user,
                    milestone=milestone,
                    amount=str(reward_each),
                    tx_id=str(tx.id),
                )
                awarded.append(milestone)
        except IntegrityError:
            # Already paid concurrently — that's fine, it's the whole
            # point of the unique constraint. Skip silently.
            logger.info(
                "pay_referral_milestones: race on milestone %s for user %s — already paid",
                milestone, user.id,
            )
            continue

    # Notify + push only for milestones we actually paid in this call.
    for milestone in awarded:
        try:
            from notifications.tasks import send_notification
            send_notification.delay(
                str(user.id),
                title="Referral milestone reached!",
                body=(f"You hit {milestone} referrals and earned "
                      f"{reward_each} H Coins. Keep inviting!"),
                notification_type="referral_milestone",
            )
        except Exception:
            logger.exception("send_notification failed for milestone %s", milestone)

        _push_event(
            user.id,
            "referral_milestone",
            milestone=milestone,
            amount=str(reward_each),
        )

    if awarded:
        _push_event(
            user.id,
            "balance_update",
            h_coins=str(wallet.h_coin_balance),
            usdt_balance=str(wallet.usdt_balance),
        )

    return awarded


# ──────────────────────────────────────────────────────────────────────
# Deposit-completion hook
# ──────────────────────────────────────────────────────────────────────

def on_deposit_completed(user):
    """
    Called from `verify_deposit` / `force_complete_deposit` after a
    deposit has been marked completed. If the depositing user has an L1
    inviter, this triggers a milestone recheck for that inviter — because
    one of their (until now non-qualifying) referrals just qualified.

    Always safe: no-op when the user has no L1 inviter, idempotent thanks
    to the (user, milestone) unique constraint in pay_referral_milestones.
    """
    from referrals.models import Referral

    try:
        # Find the L1 inviter (only one — enforced by unique constraint
        # on (inviter, invited_user, level)).
        ref = (
            Referral.objects.filter(invited_user=user, level=1)
            .select_related("inviter")
            .first()
        )
    except Exception:
        logger.exception("on_deposit_completed: failed to look up L1 inviter for %s", user.id)
        return []

    if not ref:
        return []

    # Notify the inviter that their referral just became "qualified".
    # Always fires regardless of whether a milestone was crossed.
    try:
        from notifications.tasks import send_notification
        inviter_name = ref.invited_user.first_name or ref.invited_user.email
        send_notification.delay(
            str(ref.inviter_id),
            title="Referral qualified",
            body=(f"{inviter_name} just made their first deposit — "
                  "they now count toward your milestone rewards."),
            notification_type="referral_qualified",
        )
    except Exception:
        logger.exception("on_deposit_completed: notify inviter failed")

    _push_event(
        ref.inviter_id,
        "referral_qualified",
        invited_user_id=str(ref.invited_user_id),
    )

    try:
        with db_tx.atomic():
            return pay_referral_milestones(ref.inviter)
    except Exception:
        logger.exception(
            "on_deposit_completed: pay_referral_milestones failed for inviter %s",
            ref.inviter_id,
        )
        return []
