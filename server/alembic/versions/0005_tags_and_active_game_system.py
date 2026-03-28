"""add unified tags and active game system preferences

Revision ID: 0005_tags_and_active_game_system
Revises: 0004_file_meta
Create Date: 2026-03-25 00:00:02.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_tags_and_active_game_system"
down_revision = "0004_file_meta"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("slug", name="uq_tags_slug"),
    )
    op.create_index("ix_tags_kind_name", "tags", ["kind", "name"])

    op.create_table(
        "file_tags",
        sa.Column("file_id", sa.Integer(), sa.ForeignKey("files.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tag_id", sa.Integer(), sa.ForeignKey("tags.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("file_id", "tag_id", name="pk_file_tags"),
    )
    op.create_index("ix_file_tags_tag_id", "file_tags", ["tag_id"])

    op.add_column("files", sa.Column("game_system_tag_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_files_game_system_tag_id",
        "files",
        "tags",
        ["game_system_tag_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_files_game_system_tag_id", "files", ["game_system_tag_id"])

    op.add_column("users", sa.Column("active_game_system_tag_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_users_active_game_system_tag_id",
        "users",
        "tags",
        ["active_game_system_tag_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.execute(
        """
        INSERT INTO tags (name, slug, kind)
        VALUES ('All Systems', 'general-rules', 'game_system')
        ON CONFLICT (slug) DO NOTHING
        """
    )
    op.execute(
        """
        UPDATE tags
        SET name = 'All Systems', kind = 'game_system'
        WHERE slug = 'general-rules'
        """
    )
    op.execute(
        """
        INSERT INTO tags (name, slug, kind)
        SELECT gs.name, gs.slug, 'game_system'
        FROM game_systems gs
        ON CONFLICT (slug) DO NOTHING
        """
    )
    op.execute(
        """
        UPDATE files f
        SET game_system_tag_id = tags.id
        FROM folders fo
        JOIN game_systems gs ON gs.id = fo.game_system_id
        JOIN tags ON tags.slug = gs.slug
        WHERE fo.id = f.folder_id
        """
    )
    op.execute(
        """
        UPDATE files
        SET game_system_tag_id = (SELECT id FROM tags WHERE slug = 'general-rules')
        WHERE game_system_tag_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE users
        SET active_game_system_tag_id = (SELECT id FROM tags WHERE slug = 'general-rules')
        WHERE active_game_system_tag_id IS NULL
        """
    )
    op.alter_column("files", "game_system_tag_id", existing_type=sa.Integer(), nullable=False)


def downgrade() -> None:
    op.drop_constraint("fk_users_active_game_system_tag_id", "users", type_="foreignkey")
    op.drop_column("users", "active_game_system_tag_id")

    op.drop_index("ix_files_game_system_tag_id", table_name="files")
    op.drop_constraint("fk_files_game_system_tag_id", "files", type_="foreignkey")
    op.drop_column("files", "game_system_tag_id")

    op.drop_index("ix_file_tags_tag_id", table_name="file_tags")
    op.drop_table("file_tags")

    op.drop_index("ix_tags_kind_name", table_name="tags")
    op.drop_table("tags")
