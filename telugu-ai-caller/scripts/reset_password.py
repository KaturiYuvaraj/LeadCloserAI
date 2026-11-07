"""
Sets a new password for a dashboard login, when it has been forgotten. Run it on the server:

    venv\\Scripts\\python.exe scripts\\reset_password.py admin@leadcloser.ai

The password is typed at a hidden prompt (nothing appears while typing), so it never reaches a
chat, a log or the command history. Only its scrambled form is stored.
"""

import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.auth import hash_password  # noqa: E402
from core.db import SessionLocal  # noqa: E402
from models import User  # noqa: E402
from models.audit_log import AuditLog  # noqa: E402

MIN_LENGTH = 8


def set_password(email: str, password: str) -> bool:
    """False if there is no such user."""
    session = SessionLocal()
    try:
        user = session.query(User).filter(User.email.ilike(email.strip())).first()
        if not user:
            return False
        user.password_hash = hash_password(password)
        session.add(AuditLog(account_id=user.account_id, user_id=user.id, action="password_reset_on_server",
                             target=f"user:{user.id}", details={"email": user.email}))
        session.commit()
        return True
    finally:
        session.close()


def main() -> int:
    email = sys.argv[1] if len(sys.argv) > 1 else input("Login email: ")
    password = getpass.getpass(f"New password (at least {MIN_LENGTH} characters, hidden while typing): ")
    if len(password) < MIN_LENGTH:
        print(f"Too short: use at least {MIN_LENGTH} characters. Nothing was changed.")
        return 1
    if password != getpass.getpass("Type it again: "):
        print("The two passwords don't match. Nothing was changed.")
        return 1
    if not set_password(email, password):
        print(f"No login found for {email}. Nothing was changed.")
        return 1
    print(f"Password changed for {email}. You can log in now.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
