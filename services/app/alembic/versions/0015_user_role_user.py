"""user_role: the label 'user' (task 15)

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-27

Hand-written (docs/tasks/15-chat-contract-eval.md). The closed beta chat has its own role: a `user`
may call `/chat/*` and nothing of the dashboard. Postgres cannot drop an enum label, so the
downgrade swaps in the old type; it refuses while a `user` account exists, because no old label
fits it (deactivating or deleting the accounts is the operator's decision, not the migration's).
"""

from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None

OLD_LABELS = ("admin", "reviewer")


def upgrade() -> None:
    op.execute("ALTER TYPE user_role ADD VALUE 'user'")


def downgrade() -> None:
    count = op.get_bind().exec_driver_sql("SELECT count(*) FROM app_user WHERE role = 'user'")
    if count.scalar_one():
        raise RuntimeError("cannot downgrade: accounts with the role 'user' exist")
    op.execute("ALTER TYPE user_role RENAME TO user_role_old")
    labels = ", ".join(f"'{label}'" for label in OLD_LABELS)
    op.execute(f"CREATE TYPE user_role AS ENUM ({labels})")
    op.execute("ALTER TABLE app_user ALTER COLUMN role TYPE user_role USING role::text::user_role")
    op.execute("DROP TYPE user_role_old")
