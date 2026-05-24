# TokenVault — Referral System & Distribution to Inviters

> **Scope:** This document explains exactly how the two-level referral network works, how rewards are distributed to inviters at Level 1 and Level 2, and what rules govern when a referral counts as "qualified."

---

## 1. The Two-Level Referral Tree

TokenVault supports a **two-level referral graph**:

| Level | Who they are | Stored as |
|-------|-------------|-----------|
| **L1 (Direct)** | Someone who registered using **your** invite code | `Referral(level=1)` |
| **L2 (Indirect)** | Someone who registered using **your L1's** invite code | `Referral(level=2)` |

Every user receives a unique 8-character `referral_code` at registration. The graph is stored in the `referrals.Referral` table with a unique constraint on `(inviter, invited_user, level)` — the same person cannot be counted twice at the same level.

**Example tree:**

```
Alice (you)
├── Bob   ← L1 of Alice (used Alice's code)
│   ├── Dave  ← L2 of Alice / L1 of Bob (used Bob's code)
│   └── Eve   ← L2 of Alice / L1 of Bob
└── Carol ← L1 of Alice
    └── Frank ← L2 of Alice / L1 of Carol
```

---

## 2. Referral Statuses

Not all referrals are equal. There are four progression statuses:

| Status | Condition |
|--------|-----------|
| `registered` | The invited user has a `Referral` row — they signed up |
| `verified` | + Their email is verified (`is_email_verified = True`) |
| `first_deposit_completed` | + They have at least one completed USDT deposit |
| `qualified` | + The referral is Level 1 (only direct invites can be "qualified") |

> **Anti-fake-account rule:** Only L1 referrals whose invited user has completed at least one deposit count toward milestone rewards and the reward-cycle activation guard. Signups alone earn nothing for the inviter.

The `Referral.objects.qualified_for(user)` queryset joins through to the `Transaction` table to check for a `deposit, status=completed` row. This is the only way a referral becomes qualified.

---

## 3. Two Ways to Earn from Referrals

### 3.1 Milestone Rewards (Flat Bonus)

Every **5 qualified L1 referrals** pays the inviter a flat **+1 H Coin** bonus.

| Config knob | Default |
|-------------|---------|
| `REFERRAL_MILESTONE_SIZE` | 5 |
| `REFERRAL_MILESTONE_REWARD_HCOIN` | 1 H Coin |

#### When it triggers:

1. **At registration** — `pay_referral_milestones(inviter)` runs immediately after a new L1 referral is created. Since the new user hasn't deposited yet, this pays nothing in practice — it runs defensively.
2. **At first deposit** — `on_deposit_completed(invited_user)` finds the L1 inviter and calls `pay_referral_milestones(inviter)`. **This is the real qualifying event.**

#### Idempotency:

The `ReferralMilestoneReward` table has `UniqueConstraint(user, milestone)`. Even under concurrent registrations, the same milestone cannot be paid twice. A database `IntegrityError` is caught silently.

#### What happens when milestone N is reached:

| Action | Effect |
|--------|--------|
| Balance credit | `h_coin_balance += 1 H` |
| Transaction row | `type=referral_milestone, status=completed` |
| WebSocket event | `referral_milestone` + `balance_update` |
| Push notification | "You hit N referrals and earned 1 H Coins." |

---

### 3.2 Commission from Reward Claims (Percentage Cut)

When an invited user **claims their 15-day reward cycle**, the platform's `distribute_commission(user, profit)` function runs **inside the same atomic database transaction** and pays:

| Level | Who receives | Rate |
|-------|-------------|------|
| **L1 commission** | The direct inviter (1 level up) | **5%** of the claimed reward |
| **L2 commission** | The grand-inviter (2 levels up) | **3%** of the claimed reward |

> **Key point:** The commission is NOT deducted from the claiming user's wallet. It is new H Coin credit minted by the platform. The invitee keeps 100% of their reward.

#### Config knobs:

```
REFERRAL_L1_COMMISSION_PCT=5
REFERRAL_L2_COMMISSION_PCT=3
```

#### What each commission creates:

- A `Transaction(type=commission, commission_level=1 or 2, commission_rate=5% or 3%, commission_from_user=<claiming user>)` row.
- `Referral.total_commission_earned_hcoin` is incremented on the referral row for lifetime stats.
- A `commission_received` WebSocket event and a `commission` push notification are sent to the inviter.

---

## 4. Exact Flow: Who Gets What When

### Scenario A — Bob (L1 of Alice) claims a 100 H reward

```
Bob claims 100 H reward
│
├── Bob's wallet: +100 H  (reward)
│
└── distribute_commission(Bob, 100)
    ├── Alice (Bob's L1 inviter): +5 H  [5% × 100]  → commission level 1
    └── (no L2 — Alice has no inviter above her)
```

### Scenario B — Dave (L2 of Alice, L1 of Bob) claims a 200 H reward

```
Dave claims 200 H reward
│
├── Dave's wallet: +200 H  (reward)
│
└── distribute_commission(Dave, 200)
    ├── Bob (Dave's direct L1 inviter): +10 H  [5% × 200]  → commission level 1
    └── Alice (Dave's L2 grand-inviter): +6 H   [3% × 200]  → commission level 2
```

Both commissions fire atomically — either both succeed or neither does.

---

## 5. Reward Cycle Activation Guard (why you need referrals to earn rewards)

Before a user can activate a 15-day reward cycle, **both** of the following must be true:

1. `h_coin_balance > 0`
2. The user has **≥ 1 qualified L1 referral** (an L1 who has completed at least one deposit)

If either condition fails, `POST /api/v1/reward/cycle/activate/` returns `400` with a `reasons[]` array. The UI disables the button before the user even clicks it (sourced from the `ineligibilityReasons` field in `GET /api/v1/reward/cycle/`).

This means: **to unlock the 15-day reward cycle, you must first invite at least one person who actually deposits.**

---

## 6. Stats Endpoint

`GET /api/v1/referrals/stats/` returns a complete picture:

```json
{
  "l1Count": 12,
  "l2Count": 4,
  "qualifiedCount": 7,
  "pendingDepositCount": 5,
  "milestone": {
    "size": 5,
    "rewardHcoin": "1",
    "milestonesPaid": 1,
    "totalRewardEarnedHcoin": "1",
    "nextMilestoneAt": 10,
    "qualifiedUntilNext": 3,
    "progressPercent": 40.0,
    "qualifyingRule": "Only invited users with at least one completed deposit count toward milestone rewards."
  }
}
```

---

## 7. Full Earnings Summary

| Trigger | Who earns | Amount | Transaction type |
|---------|-----------|--------|-----------------|
| 5th, 10th, 15th… qualified L1 deposits | Inviter | +1 H Coin flat | `referral_milestone` |
| Any L1 claims a reward | Their direct inviter (L1 parent) | +5% of claimed H | `commission` (level 1) |
| Any L2 claims a reward | Their grand-inviter (L2 parent) | +3% of claimed H | `commission` (level 2) |

> **Important:** L2 referrals do NOT count toward the inviter's milestone counter. Milestones only count qualified L1s. L2s only generate commission income when they claim rewards.

---

## 8. Where the Code Lives

| Concern | File |
|---------|------|
| Referral graph & statuses | `backend/referrals/models.py` |
| Qualification queryset | `backend/referrals/models.py::ReferralQuerySet` |
| Commission distribution | `backend/referrals/services.py::distribute_commission` |
| Milestone payments | `backend/referrals/services.py::pay_referral_milestones` |
| First-deposit trigger | `backend/referrals/services.py::on_deposit_completed` |
| Reward cycle claim (triggers commissions) | `backend/rewards/views.py` |
| Configuration knobs | `backend/core/settings/base.py` |

---

*Last updated: May 2026 — TokenVault codebase.*
