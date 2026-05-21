# TokenVault

A production-ready React frontend for a token reward / referral mini-app. Built with **Vite + React 18 + Tailwind + Framer Motion + lucide-react**.

## Stack
- **Vite** for dev server / production bundling
- **React 18** with React Router 6
- **Tailwind CSS** (custom space/teal/gold tokens) for layout
- **Framer Motion** for transitions and micro-interactions
- **lucide-react** for icons
- **Google Fonts**: Outfit (UI) + Space Mono (numerics)
- Pure-CSS animated star field (box-shadow technique, no canvas)
- Mock auth + wallet state persisted to `localStorage`

## Getting started

```bash
cd tokenvault
npm install
npm run dev
```

Vite will open `http://localhost:5173` automatically.

Build:
```bash
npm run build
npm run preview
```

## App structure

```
src/
├── App.jsx                     # Router + route transitions
├── main.jsx                    # Providers (Auth / Wallet / Toast)
├── index.css                   # Tailwind + Google Fonts + star field CSS
├── components/
│   ├── BottomNav.jsx           # 4-tab navigator with shared layoutId indicator
│   ├── BottomSheet.jsx         # Generic bottom-sheet modal
│   ├── Countdown.jsx           # DD:HH:MM:SS animated digit cards
│   ├── CountUp.jsx             # Animated number roll-up
│   ├── DepositModal.jsx        # Deposit USDT bottom sheet
│   ├── Field.jsx               # Themed input with inline errors
│   ├── NodePopup.jsx           # Network node detail popover
│   ├── Skeleton.jsx            # Shimmer skeletons
│   ├── StarField.jsx           # Drifting CSS star field
│   └── WithdrawModal.jsx       # Withdraw bottom sheet
├── context/
│   ├── AuthContext.jsx         # Mock auth (login/register/updateUser)
│   ├── ToastContext.jsx        # Top-center toasts (success/error/info)
│   └── WalletContext.jsx       # Balance + transactions + reward cycle
├── data/
│   └── network.js              # L1/L2 mock referral nodes + country list
└── pages/
    ├── Home.jsx                # 30-day countdown over star field
    ├── Login.jsx               # Mock sign in (≥6-char password)
    ├── Network.jsx             # Animated SVG orbital network
    ├── Profile.jsx             # Editable profile + invite + password
    ├── Register.jsx            # Multi-field signup with inline validation
    └── Wallet.jsx              # Balance, reward cycle, transactions
```

## Mock auth
- Any email and a password of 6+ characters logs in.
- The mock `user` and `wallet` are persisted in `localStorage` under `tokenvault.user` / `tokenvault.wallet`.
- Use the **Sign Out** button on the Profile tab to clear the session.

## Design notes
- Designed mobile-first for a 390px iPhone width, centered inside a `max-w-[480px]` container on larger viewports — the star field extends full-width as background.
- Accent palette: teal (`#2DD4BF`) for primary, gold (`#FBBF24`) for reward states.
- All long-running animations use CSS keyframes (drift, blink, spin) so they keep running off the JS thread.
- The Network tab uses an SVG-based orbital diagram with two oppositely-rotating groups and animated dashed connectors.

## What's mocked vs. wired
- Auth, wallet balances, transactions, reward timer, referral network, deposit/withdraw flows — all mocked client-side.
- Replace `context/AuthContext.jsx`, `context/WalletContext.jsx`, and the deposit/withdraw modals' submit handlers to plug in a real API.
