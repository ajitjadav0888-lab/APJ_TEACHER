#!/usr/bin/env python3
"""Create and password-provision the marked development test teacher.

This utility intentionally does not expose an HTTP recovery or registration
route. It is limited to the local development SQLite database and never
writes the password to disk or prints a credential/hash.
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "apj_build" / "backend"
TEST_TEACHER_NAME = "APJ Temporary Development Teacher"
DEFAULT_SCHOOL_ID = 1


def load_backend():
    if os.getenv("APJ_ENV", "").lower() != "development":
        raise SystemExit(
            "Refusing to run: set APJ_ENV=development explicitly. "
            "This utility cannot run in production."
        )

    database_url = os.getenv("APJ_DATABASE_URL", "")
    if database_url and not database_url.lower().startswith("sqlite"):
        raise SystemExit(
            "Refusing to run: this utility only supports the development SQLite database."
        )

    os.chdir(BACKEND_DIR)
    sys.path.insert(0, str(BACKEND_DIR))
    from app import School, SessionLocal, User  # noqa: PLC0415
    from auth import AuthCredential, CredentialIn, set_credential  # noqa: PLC0415

    return School, SessionLocal, User, AuthCredential, CredentialIn, set_credential


def create_account(school_id: int) -> None:
    School, SessionLocal, User, *_ = load_backend()
    session = SessionLocal()
    try:
        school = session.get(School, school_id)
        if school is None:
            raise SystemExit(f"Development school {school_id} does not exist.")

        existing = (
            session.query(User)
            .filter_by(
                name=TEST_TEACHER_NAME,
                role="TEACHER",
                school_id=school_id,
            )
            .order_by(User.id)
            .first()
        )
        if existing is not None:
            print(f"Development test teacher already exists. Login user_id: {existing.id}")
            print("No password or credential data was changed.")
            return

        account = User(
            school_id=school_id,
            name=TEST_TEACHER_NAME,
            role="TEACHER",
        )
        session.add(account)
        session.commit()
        session.refresh(account)
        print(f"Created development test teacher. Login user_id: {account.id}")
        print("No password was created. Set one with the set-password command.")
    finally:
        session.close()


def set_password(user_id: int) -> None:
    School, SessionLocal, User, AuthCredential, CredentialIn, provision = load_backend()
    session = SessionLocal()
    try:
        account = session.get(User, user_id)
        if (
            account is None
            or account.name != TEST_TEACHER_NAME
            or account.role != "TEACHER"
        ):
            raise SystemExit(
                "Refusing to change credentials: user_id is not the marked "
                "development test teacher."
            )

        password = getpass.getpass("New test password (hidden): ")
        confirmation = getpass.getpass("Confirm test password (hidden): ")
        if len(password) < 8:
            raise SystemExit("Password must contain at least 8 characters.")
        if password != confirmation:
            raise SystemExit("Passwords do not match.")

        provision(
            CredentialIn(user_id=user_id, password=password),
            session,
        )
        print(f"Password set for development test teacher user_id {user_id}.")
        print("The password was not displayed or stored by this utility.")
    finally:
        session.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Manage the marked APJ development test teacher."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create", help="create the test teacher")
    create_parser.add_argument(
        "--school-id",
        type=int,
        default=DEFAULT_SCHOOL_ID,
        help=f"development school ID (default: {DEFAULT_SCHOOL_ID})",
    )

    password_parser = subparsers.add_parser(
        "set-password",
        help="set its password using hidden interactive input",
    )
    password_parser.add_argument("user_id", type=int)

    args = parser.parse_args()
    if args.command == "create":
        create_account(args.school_id)
    else:
        set_password(args.user_id)


if __name__ == "__main__":
    main()