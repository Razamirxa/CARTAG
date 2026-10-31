from alembic import command

from tests.conftest import alembic_config


def test_migrations_match_the_models():
    """Fails when someone changes models.py without writing a migration for it."""
    command.check(alembic_config())
