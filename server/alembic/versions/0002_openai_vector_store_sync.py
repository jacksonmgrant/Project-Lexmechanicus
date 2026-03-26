from alembic import op
import sqlalchemy as sa


revision = "0002_openai_vector_store_sync"
down_revision = "0001_init"


def upgrade():
    op.add_column("files", sa.Column("openai_file_id", sa.String(128), nullable=True))
    op.add_column("files", sa.Column("openai_vector_store_file_id", sa.String(128), nullable=True))
    op.add_column("files", sa.Column("openai_vector_store_status", sa.String(32), nullable=True))
    op.add_column("files", sa.Column("openai_last_error", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("files", "openai_last_error")
    op.drop_column("files", "openai_vector_store_status")
    op.drop_column("files", "openai_vector_store_file_id")
    op.drop_column("files", "openai_file_id")
