"""add canonical rulesets and aliases

Revision ID: 0006_rulesets_and_aliases
Revises: 0005_tags_and_active_game_system
Create Date: 2026-03-26 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_rulesets_and_aliases"
down_revision = "0005_tags_and_active_game_system"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rulesets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("normalized_name", sa.String(length=160), nullable=False),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("rulesets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("edition_label", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("normalized_name", name="uq_rulesets_normalized_name"),
        sa.UniqueConstraint("slug", name="uq_rulesets_slug"),
    )
    op.create_index("ix_rulesets_parent_id", "rulesets", ["parent_id"])

    op.create_table(
        "ruleset_aliases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ruleset_id", sa.Integer(), sa.ForeignKey("rulesets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("alias", sa.String(length=160), nullable=False),
        sa.Column("normalized_alias", sa.String(length=160), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("normalized_alias", name="uq_ruleset_aliases_normalized_alias"),
    )
    op.create_index("ix_ruleset_aliases_ruleset_id", "ruleset_aliases", ["ruleset_id"])

    op.add_column("files", sa.Column("ruleset_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_files_ruleset_id",
        "files",
        "rulesets",
        ["ruleset_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_files_ruleset_id", "files", ["ruleset_id"])

    op.add_column("users", sa.Column("active_ruleset_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_users_active_ruleset_id",
        "users",
        "rulesets",
        ["active_ruleset_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.execute(
        """
        INSERT INTO rulesets (name, normalized_name, slug, kind)
        VALUES ('All Systems', 'all systems', 'all-systems', 'general')
        ON CONFLICT (normalized_name) DO NOTHING
        """
    )

    op.execute(
        """
        INSERT INTO rulesets (name, normalized_name, slug, kind)
        SELECT
            t.name,
            lower(trim(t.name)),
            CASE WHEN t.slug = 'general-rules' THEN 'all-systems' ELSE t.slug END,
            CASE WHEN t.slug = 'general-rules' THEN 'general' ELSE 'general' END
        FROM tags t
        WHERE t.kind = 'game_system'
        ON CONFLICT (normalized_name) DO UPDATE SET name = EXCLUDED.name
        """
    )

    op.execute(
        """
        INSERT INTO ruleset_aliases (ruleset_id, alias, normalized_alias)
        SELECT
            r.id,
            r.name,
            r.normalized_name
        FROM rulesets r
        ON CONFLICT (normalized_alias) DO NOTHING
        """
    )

    op.execute(
        """
        UPDATE files f
        SET ruleset_id = r.id
        FROM tags t
        JOIN rulesets r ON r.normalized_name = lower(trim(t.name))
        WHERE f.game_system_tag_id = t.id
        """
    )
    op.execute(
        """
        UPDATE files
        SET ruleset_id = (SELECT id FROM rulesets WHERE slug = 'all-systems')
        WHERE ruleset_id IS NULL
        """
    )
    op.alter_column("files", "ruleset_id", existing_type=sa.Integer(), nullable=False)

    op.execute(
        """
        UPDATE users u
        SET active_ruleset_id = r.id
        FROM tags t
        JOIN rulesets r ON r.normalized_name = lower(trim(t.name))
        WHERE u.active_game_system_tag_id = t.id
        """
    )
    op.execute(
        """
        UPDATE users
        SET active_ruleset_id = (SELECT id FROM rulesets WHERE slug = 'all-systems')
        WHERE active_ruleset_id IS NULL
        """
    )


def downgrade() -> None:
    op.drop_constraint("fk_users_active_ruleset_id", "users", type_="foreignkey")
    op.drop_column("users", "active_ruleset_id")

    op.drop_index("ix_files_ruleset_id", table_name="files")
    op.drop_constraint("fk_files_ruleset_id", "files", type_="foreignkey")
    op.drop_column("files", "ruleset_id")

    op.drop_index("ix_ruleset_aliases_ruleset_id", table_name="ruleset_aliases")
    op.drop_table("ruleset_aliases")

    op.drop_index("ix_rulesets_parent_id", table_name="rulesets")
    op.drop_table("rulesets")
