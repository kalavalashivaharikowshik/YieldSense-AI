"""Create an admin account, or promote an existing user to admin.

Usage (from the backend folder, with the same environment as the API):

    python -m scripts.create_admin --email admin@example.com --name "Admin"

The password is asked for interactively, or read from the
ADMIN_PASSWORD environment variable for automated setups.
"""

import argparse
import getpass
import os
import sys

from pydantic import ValidationError

from app.core.security import hash_password
from app.db.database import SessionLocal
from app.models import agriculture, crop_recommendation, farm, prediction  # noqa: F401
from app.models.user import Role, User
from app.schemas.auth import normalize_full_name, validate_password_strength


def read_password() -> str:
    password = os.environ.get("ADMIN_PASSWORD")

    if password:
        return password

    password = getpass.getpass("Admin password: ")
    confirmation = getpass.getpass("Repeat password: ")

    if password != confirmation:
        sys.exit("Passwords do not match.")

    return password


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", default="YieldSense Admin")
    arguments = parser.parse_args()

    email = arguments.email.strip().lower()

    session = SessionLocal()

    try:
        admin_role = session.query(Role).filter(Role.name == "admin").first()

        if admin_role is None:
            sys.exit(
                "The 'admin' role does not exist. Run 'alembic upgrade head' first."
            )

        user = session.query(User).filter(User.email == email).first()

        if user is not None:
            user.role_id = admin_role.id
            user.is_active = True
            user.is_verified = True
            session.commit()
            print(f"Promoted existing user {email} to admin.")
            return

        try:
            full_name = normalize_full_name(arguments.name)
            password = validate_password_strength(read_password())
        except (ValueError, ValidationError) as error:
            sys.exit(str(error))

        session.add(
            User(
                full_name=full_name,
                email=email,
                hashed_password=hash_password(password),
                role_id=admin_role.id,
                is_active=True,
                is_verified=True,
            )
        )
        session.commit()
        print(f"Created admin account {email}.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
