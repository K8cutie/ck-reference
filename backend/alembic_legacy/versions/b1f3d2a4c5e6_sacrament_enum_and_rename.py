"""Rename sacrament_type → type and convert to ENUM.

Revision ID: b1f3d2a4c5e6
Revises: 88a6d17ecac8
Create Date: 2025-08-08 10:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "b1f3d2a4c5e6"
down_revision = "88a6d17ecac8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) Create the ENUM type (idempotent)
    sacrament_enum = postgresql.ENUM(
        "BAPTISM",
        "CONFIRMATION",
        "MARRIAGE",
        "DEATH",
        "FIRST_COMMUNION",
        "ANOINTING",
        name="sacramenttype",
    )
    sacrament_enum.create(op.get_bind(), checkfirst=True)

    # 2) Normalize existing string values so they cast cleanly
    #    - Handle lowercase and snake_case inputs
    #    - Map 'funeral' (if any) to canonical enum 'DEATH'
    op.execute(
        """
        UPDATE sacraments
        SET sacrament_type = CASE
            WHEN lower(sacrament_type) IN ('funeral','death') THEN 'DEATH'
            WHEN lower(sacrament_type) = 'anointing' THEN 'ANOINTING'
            WHEN lower(sacrament_type) = 'first_communion' THEN 'FIRST_COMMUNION'
            WHEN lower(sacrament_type) = 'confirmation' THEN 'CONFIRMATION'
            WHEN lower(sacrament_type) = 'baptism' THEN 'BAPTISM'
            WHEN lower(sacrament_type) = 'marriage' THEN 'MARRIAGE'
            ELSE upper(sacrament_type)
        END
        """
    )

    # 3) Rename column sacrament_type → type (still VARCHAR at this point)
    op.alter_column(
        "sacraments",
        "sacrament_type",
        new_column_name="type",
        existing_type=sa.String(length=32),
    )

    # 4) Convert VARCHAR → ENUM using a cast
    op.alter_column(
        "sacraments",
        "type",
        type_=sacrament_enum,
        postgresql_using="type::sacramenttype",
    )


def downgrade() -> None:
    # Revert ENUM back to VARCHAR and rename column back
    sacrament_enum = postgresql.ENUM(
        "BAPTISM",
        "CONFIRMATION",
        "MARRIAGE",
        "DEATH",
        "FIRST_COMMUNION",
        "ANOINTING",
        name="sacramenttype",
    )

    # 1) Cast enum back to text
    op.alter_column(
        "sacraments",
        "type",
        type_=sa.String(length=32),
        postgresql_using="type::text",
    )

    # 2) Rename column back to sacrament_type
    op.alter_column(
        "sacraments",
        "type",
        new_column_name="sacrament_type",
        existing_type=sa.String(length=32),
    )

    # 3) Drop the ENUM type
    sacrament_enum.drop(op.get_bind(), checkfirst=True)
