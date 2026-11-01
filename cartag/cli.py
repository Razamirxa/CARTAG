"""Command line tools.

    uv run python -m cartag.cli create-admin --email you@example.com --name "Your Name"

The password is read from the ADMIN_PASSWORD environment variable, or typed at the prompt.
It is never taken from the command line, so it does not end up in shell history.
"""

import argparse
import getpass
import os
import re
import sys

from sqlalchemy import select

from cartag.db import SessionLocal
from cartag.models import Admin
from cartag.security import hash_password
from cartag.services.audit import Actor, audit


def create_admin(email: str, name: str, if_none: bool = False) -> None:
    email = email.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        sys.exit("That does not look like an email address.")
    password = os.environ.get("ADMIN_PASSWORD") or getpass.getpass("Password (min 8 characters): ")
    if len(password) < 8:
        sys.exit("The password must be at least 8 characters.")

    with SessionLocal() as db:
        if if_none and db.scalar(select(Admin.id).limit(1)) is not None:
            print("An admin already exists, nothing changed")
            return
        admin = db.scalar(select(Admin).where(Admin.email == email))
        existed = admin is not None
        if admin is None:
            admin = Admin(email=email, name=name, password_hash=hash_password(password))
            db.add(admin)
            db.flush()
        else:
            admin.password_hash = hash_password(password)
            admin.name = name
            admin.disabled_at = None
        audit(db, Actor.system(), "admin.password_set" if existed else "admin.create", "Admin", admin.id)
        db.commit()
    print(f"{'Updated' if existed else 'Created'} admin {email}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="cartag")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create-admin", help="Create an admin, or reset an admin's password")
    create.add_argument("--email", required=True)
    create.add_argument("--name", default="Admin")
    create.add_argument("--if-none", action="store_true", help="Do nothing when an admin already exists")
    args = parser.parse_args()
    if args.command == "create-admin":
        create_admin(args.email, args.name, args.if_none)


if __name__ == "__main__":
    main()
