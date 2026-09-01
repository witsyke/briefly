"""baseline extractions, images, briefs, brief_config

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None


def upgrade() -> None:
    op.create_table(
        "extractions",
        sa.Column("path", sa.String, primary_key=True),
        sa.Column("title", sa.String, nullable=True),
        sa.Column("authors", sa.String, nullable=True),
        sa.Column("markdown", sa.String, nullable=True),
        sa.Column("image_json", sa.String, nullable=True),
        sa.Column("error", sa.String, nullable=True),
        sa.Column("retryable", sa.Boolean, nullable=False),
    )

    op.create_table(
        "images",
        sa.Column("path", sa.String, primary_key=True),
        sa.Column("order", sa.Integer, primary_key=True),
        sa.Column("page", sa.Integer, nullable=False),
        sa.Column("file_path", sa.String, nullable=False),
    )

    op.create_table(
        "briefs",
        sa.Column("path", sa.String, primary_key=True),
        sa.Column("fields_json", sa.String, nullable=True),
        sa.Column("error", sa.String, nullable=True),
        sa.Column("retryable", sa.Boolean, nullable=False),
    )

    op.create_table(
        "brief_config",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("config_hash", sa.String, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("brief_config")
    op.drop_table("briefs")
    op.drop_table("images")
    op.drop_table("extractions")
