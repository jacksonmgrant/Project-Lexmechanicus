"""flatten rulesets into standalone game systems

Revision ID: 0007_flatten_game_systems
Revises: 0006_rulesets_and_aliases
Create Date: 2026-03-26 00:30:00.000000
"""

from alembic import op


revision = "0007_flatten_game_systems"
down_revision = "0006_rulesets_and_aliases"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE rulesets
        SET kind = 'general',
            parent_id = NULL,
            edition_label = NULL
        """
    )


def downgrade() -> None:
    pass
