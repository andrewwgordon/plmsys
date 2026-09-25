"""managed file uploads

Revision ID: 8394654f0db5
Revises: eb8e40076f38
Create Date: 2026-09-25 10:35:00.145694

Replaces ``managed_file.storage_path`` (a free-text path/URL) with ``file``
(the FAB-managed filename) and adds a SHA-256 ``checksum``. The managed bytes
live under ``UPLOAD_FOLDER`` outside the web-served static tree.
"""

import os

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '8394654f0db5'
down_revision = 'eb8e40076f38'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('managed_file', schema=None) as batch_op:
        batch_op.add_column(sa.Column('file', sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column('checksum', sa.String(length=64), nullable=True)
        )

    # Backfill the managed filename from the old storage_path (basename).
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, storage_path FROM managed_file "
            "WHERE storage_path IS NOT NULL"
        )
    ).fetchall()
    for row_id, storage_path in rows:
        filename = os.path.basename(storage_path or "")
        if filename:
            bind.execute(
                sa.text("UPDATE managed_file SET file = :f WHERE id = :i"),
                {"f": filename, "i": row_id},
            )

    with op.batch_alter_table('managed_file', schema=None) as batch_op:
        batch_op.drop_column('storage_path')


def downgrade():
    with op.batch_alter_table('managed_file', schema=None) as batch_op:
        batch_op.add_column(sa.Column('storage_path', sa.Text(), nullable=True))

    # Reconstruct the old public path from the managed filename.
    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT id, file FROM managed_file WHERE file IS NOT NULL")
    ).fetchall()
    for row_id, filename in rows:
        if filename:
            bind.execute(
                sa.text(
                    "UPDATE managed_file SET storage_path = :p WHERE id = :i"
                ),
                {"p": "/static/uploads/" + filename, "i": row_id},
            )

    with op.batch_alter_table('managed_file', schema=None) as batch_op:
        batch_op.drop_column('checksum')
        batch_op.drop_column('file')