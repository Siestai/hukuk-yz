"""Pinned conversations and short titles (docs/tasks/22-sidebar.md).

Adds `chat_conversation.pinned_at` (nullable; set while the conversation is pinned). Titles
longer than 48 characters are cut at a word boundary by the same rule as
`hukuk_models.chat.clamp_title` (the rule is copied here so that the migration stays fixed when
the function changes).

The shortening is one-way: `downgrade()` drops the column but cannot restore the long titles.
"""

import sqlalchemy as sa

from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None

TITLE_MAX = 48


def clamp(title: str) -> str:
    title = " ".join(title.split())
    if len(title) <= TITLE_MAX:
        return title
    head = title[: TITLE_MAX + 1]
    return (head.rsplit(" ", 1)[0] if " " in head else head[:TITLE_MAX]).rstrip(" ,;:-–.")[
        :TITLE_MAX
    ]


def upgrade() -> None:
    op.add_column(
        "chat_conversation", sa.Column("pinned_at", sa.DateTime(timezone=True), nullable=True)
    )
    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT id, title FROM chat_conversation WHERE char_length(title) > :n"),
        {"n": TITLE_MAX},
    ).all()
    for id, title in rows:
        conn.execute(
            sa.text("UPDATE chat_conversation SET title = :title WHERE id = :id"),
            {"title": clamp(title), "id": id},
        )


def downgrade() -> None:
    op.drop_column("chat_conversation", "pinned_at")
