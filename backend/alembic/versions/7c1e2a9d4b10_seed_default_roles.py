"""seed default farmer and admin roles

Revision ID: 7c1e2a9d4b10
Revises: eb7fa9c41df9
Create Date: 2026-11-22 01:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "7c1e2a9d4b10"
down_revision: str | Sequence[str] | None = "eb7fa9c41df9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEFAULT_ROLES = ("farmer", "admin")


def upgrade() -> None:
    """Insert the roles registration depends on. Safe to run on a database
    where the roles were already created by hand."""
    connection = op.get_bind()

    for role_name in DEFAULT_ROLES:
        connection.execute(
            sa.text(
                "INSERT INTO roles (name) "
                "SELECT :name "
                "WHERE NOT EXISTS (SELECT 1 FROM roles WHERE name = :name)"
            ),
            {"name": role_name},
        )


def downgrade() -> None:
    # Roles may already be referenced by users, so they are left in place.
    pass
