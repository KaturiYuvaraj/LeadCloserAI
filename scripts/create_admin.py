"""
CLI Utility to create or update an Account and Admin/Owner User (Phase 0).

Usage:
    python scripts/create_admin.py admin@spassociates.com SecretPass123 --role admin --account "S P Associates"
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "telugu-ai-caller"
VENV_SITE = APP_DIR / "venv" / "Lib" / "site-packages"
for _p in (str(APP_DIR), str(VENV_SITE), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core.auth import hash_password
from core.db import Base, SessionLocal, engine
from models import Account, User


def create_or_update_admin(
    email: str,
    password: str,
    role: str = "admin",
    account_name: str = "S P Associates Software Company",
) -> dict:
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        account = session.query(Account).filter(Account.name == account_name).first()
        if not account:
            account = session.query(Account).filter_by(id=1).first()
        if not account:
            account = Account(
                name=account_name,
                default_language="te-IN",
                calling_approved=True,
                rate_per_min=5.00,
            )
            session.add(account)
            session.flush()

        user = session.query(User).filter(User.email.ilike(email.strip())).first()
        pw_hash = hash_password(password)
        if user:
            user.password_hash = pw_hash
            user.role = role
            user.account_id = account.id
        else:
            user = User(
                account_id=account.id,
                email=email.strip().lower(),
                password_hash=pw_hash,
                role=role,
            )
            session.add(user)
        session.commit()
        session.refresh(user)
        return {
            "user_id": user.id,
            "email": user.email,
            "role": user.role,
            "account_id": account.id,
            "account_name": account.name,
        }
    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(description="Create or update a LeadCloser AI admin/owner user.")
    parser.add_argument("email", help="User email address")
    parser.add_argument("password", help="Plaintext password (min 6 chars)")
    parser.add_argument("--role", default="admin", choices=["owner", "admin", "member"], help="User role")
    parser.add_argument("--account", default="S P Associates Software Company", help="Account/Company name")
    args = parser.parse_args()

    res = create_or_update_admin(args.email, args.password, role=args.role, account_name=args.account)
    print(f"Ready: user #{res['user_id']} ({res['email']}, role={res['role']}) in account '{res['account_name']}' (#{res['account_id']}).")


if __name__ == "__main__":
    main()

