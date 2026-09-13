"""
Seed script — creates demo admin + sample open match.
Run with:  python manage.py shell < scripts/seed.py
"""
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tossbets.settings")
django.setup()

from apps.accounts.models import User, Wallet
from apps.matches.models import Match
from django.utils import timezone
from datetime import timedelta

# ── Admin ──────────────────────────────────────────────────────────────────
if not User.objects.filter(username="admin").exists():
    admin = User.objects.create_superuser(
        username="admin",
        email="admin@tossbets.local",
        password="admin1234",
        is_verified=True,
    )
    Wallet.objects.get_or_create(user=admin)
    print("✓ Superuser created: admin / admin1234")
else:
    admin = User.objects.get(username="admin")
    print("• Superuser already exists")

# ── Demo user ──────────────────────────────────────────────────────────────
if not User.objects.filter(username="demo").exists():
    demo = User.objects.create_user(
        username="demo",
        email="demo@tossbets.local",
        password="demo1234",
        is_verified=True,
    )
    wallet, _ = Wallet.objects.get_or_create(user=demo)
    wallet.credit(500, description="Welcome bonus")
    print("✓ Demo user created: demo / demo1234  (500 coins)")
else:
    print("• Demo user already exists")

# ── Sample Matches ─────────────────────────────────────────────────────────
for title, min_b, max_b in [
    ("IPL Final: Toss", 10, 5000),
    ("Weekend Special", 50, 2000),
    ("Quick Round #1", 10, 500),
]:
    if not Match.objects.filter(title=title).exists():
        Match.objects.create(
            title=title,
            description="Pick Heads or Tails and win big coins!",
            min_bet=min_b,
            max_bet=max_b,
            house_edge=5,
            created_by=admin,
            starts_at=timezone.now(),
            betting_closes_at=timezone.now() + timedelta(hours=2),
        )
        print(f"✓ Match created: {title}")

print("\nDone! Visit http://localhost:8000")
print("Admin panel: http://localhost:8000/admin  (admin/admin1234)")
