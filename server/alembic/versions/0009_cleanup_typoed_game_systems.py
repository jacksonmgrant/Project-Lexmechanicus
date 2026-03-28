"""clean up typoed game systems

Revision ID: 0009_cleanup_typoed_game_systems
Revises: 0008_seed_common_game_systems
Create Date: 2026-03-26 01:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0009_cleanup_typoed_game_systems"
down_revision = "0008_seed_common_game_systems"
branch_labels = None
depends_on = None


TYPO_NORMALIZED_NAME = "warhammer 40k 10th edtion"
CORRECT_NAME = "Warhammer 40,000 10th Edition"
CORRECT_NORMALIZED_NAME = "warhammer 40,000 10th edition"


def upgrade() -> None:
    connection = op.get_bind()

    typo_ruleset_id = connection.execute(
        sa.text("SELECT id FROM rulesets WHERE normalized_name = :normalized_name"),
        {"normalized_name": TYPO_NORMALIZED_NAME},
    ).scalar()
    if typo_ruleset_id is None:
        return

    correct_ruleset_id = connection.execute(
        sa.text("SELECT id FROM rulesets WHERE normalized_name = :normalized_name"),
        {"normalized_name": CORRECT_NORMALIZED_NAME},
    ).scalar()

    if correct_ruleset_id is None:
        connection.execute(
            sa.text(
                """
                INSERT INTO rulesets (name, normalized_name, slug, kind, parent_id, edition_label)
                VALUES (:name, :normalized_name, 'warhammer-40-000-10th-edition', 'general', NULL, NULL)
                ON CONFLICT (normalized_name) DO NOTHING
                """
            ),
            {
                "name": CORRECT_NAME,
                "normalized_name": CORRECT_NORMALIZED_NAME,
            },
        )
        correct_ruleset_id = connection.execute(
            sa.text("SELECT id FROM rulesets WHERE normalized_name = :normalized_name"),
            {"normalized_name": CORRECT_NORMALIZED_NAME},
        ).scalar()

    if correct_ruleset_id is None:
        return

    connection.execute(
        sa.text("UPDATE files SET ruleset_id = :correct_ruleset_id WHERE ruleset_id = :typo_ruleset_id"),
        {
            "correct_ruleset_id": correct_ruleset_id,
            "typo_ruleset_id": typo_ruleset_id,
        },
    )
    connection.execute(
        sa.text("UPDATE users SET active_ruleset_id = :correct_ruleset_id WHERE active_ruleset_id = :typo_ruleset_id"),
        {
            "correct_ruleset_id": correct_ruleset_id,
            "typo_ruleset_id": typo_ruleset_id,
        },
    )
    connection.execute(
        sa.text(
            """
            DELETE FROM ruleset_aliases
            WHERE ruleset_id = :typo_ruleset_id
               OR normalized_alias = :typo_normalized_name
            """
        ),
        {
            "typo_ruleset_id": typo_ruleset_id,
            "typo_normalized_name": TYPO_NORMALIZED_NAME,
        },
    )
    connection.execute(
        sa.text("DELETE FROM rulesets WHERE id = :typo_ruleset_id"),
        {"typo_ruleset_id": typo_ruleset_id},
    )


def downgrade() -> None:
    pass
