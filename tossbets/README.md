# TossBets 🪙

A **coin-based toss betting** platform built with Django — no real money, just coins.
College project. Admin creates matches, users bet Heads or Tails, admin declares
the winner, and coins are distributed automatically.

---

## Quick start (development)

```bash
cd tossbets
pip install -r requirements.txt
python manage.py migrate
# Seed demo data (admin + demo user + 3 sample matches):
python manage.py shell -c "exec(open('scripts/seed.py').read())"
python manage.py runserver
```

Open **http://localhost:8000**  
Admin panel: **http://localhost:8000/admin** → `admin / admin1234`  
Demo user: `demo / demo1234` (500 coins pre-loaded)

---

## Production (Docker)

```bash
cp .env.example .env        # fill in your secrets
docker compose up -d
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

---

## Feature overview

### User side
| Feature | URL |
|---|---|
| Register / login | `/accounts/register/` |
| Open matches + bet form | `/` or `/matches/` |
| Match detail + live pool bars | `/matches/<id>/` |
| My bets history | `/matches/my-bets/` |
| Deposit coins via UPI QR | `/payments/deposit/` |
| Withdrawal request | `/payments/withdraw/` |
| Full transaction ledger | `/payments/transactions/` |
| Profile (UPI ID, phone) | `/accounts/profile/` |

### Admin panel (`/admin/`)
| Section | Key actions |
|---|---|
| **Matches** | Create match, set min/max bet, house edge |
| | `Declare HEADS as winner` action → auto-distributes coins |
| | `Declare TAILS as winner` action |
| | `Lock betting` (close new bets) |
| | `Cancel match + refund all bets` action |
| **Deposits** | View screenshot, UTR → `Confirm deposit` (credits coins) |
| | `Reject deposit` |
| **Withdrawals** | `Approve` (deducts coins) → pay via UPI → `Mark paid` |
| **Bets** | Full audit log |
| **Transactions** | Immutable ledger |
| **Users** | Wallet balance inline, verify/ban users |

---

## Deposit QR flow (step-by-step)

1. User clicks **Deposit Coins** → enters ₹ amount  
2. System creates a `Deposit` record and shows a UPI QR code  
   (deep link: `upi://pay?pa=...&am=...&tn=TossBets <ref>`)  
3. User scans with any UPI app (GPay, PhonePe, Paytm, etc.)  
4. User enters the UTR/transaction-ID + optional screenshot → submits  
5. Admin sees it in `/admin/payments/deposit/` → confirms → coins credited instantly

---

## Settlement math

```
losing_pool = sum of losing bets
house_cut   = losing_pool × house_edge%
prize_pool  = losing_pool − house_cut
each winner gets: their_bet + (their_bet / winning_pool) × prize_pool
```

Example: 100 coins on Heads, 200 on Tails, 5% house edge, Heads wins  
→ prize_pool = 200 − 10 = 190  
→ Heads winner gets 100 + 190 = **290 coins**

---

## Tech stack

| Layer | Tech |
|---|---|
| Backend | Django 4.2 + DRF |
| Database | SQLite (dev) / PostgreSQL (prod) |
| Cache / Queue | Redis + Celery |
| QR codes | `qrcode` library |
| Frontend | Bootstrap 5 (dark theme), no JS framework |
| PDF/static | WhiteNoise |
| Container | Docker Compose |

---

## 7-week roadmap

| Week | Goal |
|---|---|
| 1 | ✅ Core models, auth, wallet, admin panel |
| 2 | ✅ Bet placement, settlement, deposit QR, withdrawal flow |
| 3 | Live pool bar auto-refresh (HTMX/polling), match locking timer |
| 4 | Email notifications (won/lost, deposit confirmed) |
| 5 | Dashboard stats (total coins in circulation, house profit) |
| 6 | Referral system (earn coins for inviting friends) |
| 7 | Cleanup, tests, deploy to VPS |

---

## Server requirements

Your 4 GB RAM / 2 vCPU / 100 GB server is comfortably enough.
- Gunicorn (3 workers)
- PostgreSQL
- Redis
- Nginx as reverse proxy
