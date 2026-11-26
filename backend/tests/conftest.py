"""Point every test at the test database before the app is imported.

Tests create and delete rows, so they must never touch the dev database. This
refuses to run unless TEST_DATABASE_URL is set AND names a different database.
"""
import os

from sqlalchemy.engine import make_url

from app.config import get_settings

SETUP_HELP = (
    "Create it once as the postgres superuser:\n"
    "    CREATE DATABASE projectflow_test OWNER projectflow;\n"
    "then set TEST_DATABASE_URL=.../projectflow_test in backend/.env and run\n"
    "    DATABASE_URL=<that url> uv run alembic upgrade head"
)

_settings = get_settings()
if not _settings.test_database_url:
    raise RuntimeError(f"TEST_DATABASE_URL is not set; refusing to run tests.\n{SETUP_HELP}")

_dev, _test = make_url(_settings.database_url), make_url(_settings.test_database_url)
if (_dev.host, _dev.port, _dev.database) == (_test.host, _test.port, _test.database):
    raise RuntimeError(
        f"TEST_DATABASE_URL points at the dev database '{_dev.database}'; refusing to run tests.\n{SETUP_HELP}"
    )

os.environ["DATABASE_URL"] = _settings.test_database_url
get_settings.cache_clear()
