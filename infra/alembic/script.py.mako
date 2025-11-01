"""Generic Alembic revision script."""

from alembic import op
import sqlalchemy as sa

${upgrades}

${downgrades}
