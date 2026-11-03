"""
Phase 2 Alembic Migrations Verification Tests.
Tests Alembic configuration, script directory, and initial migration revision.
"""
from pathlib import Path
from alembic.config import Config
from alembic.script import ScriptDirectory

from app.core.config import get_settings


def test_alembic_configuration():
    """Verify that alembic.ini and migration scripts directory exist and load properly."""
    settings = get_settings()
    ini_path = Path(__file__).parent.parent / "alembic.ini"
    assert ini_path.exists(), f"Alembic ini file not found at {ini_path}"

    alembic_cfg = Config(str(ini_path))
    script_dir = ScriptDirectory.from_config(alembic_cfg)

    # Verify migration revisions
    revisions = list(script_dir.walk_revisions())
    assert len(revisions) >= 1, "Expected at least one migration revision"

    initial_rev = revisions[-1]
    assert initial_rev.revision == "001_initial_schema"
    assert "initial schema" in initial_rev.doc.lower()


def test_migration_functions_defined():
    """Verify that upgrade() and downgrade() functions are properly defined in 001_initial_schema."""
    ini_path = Path(__file__).parent.parent / "alembic.ini"
    alembic_cfg = Config(str(ini_path))
    script_dir = ScriptDirectory.from_config(alembic_cfg)
    rev = script_dir.get_revision("001_initial_schema")
    module = rev.module

    assert hasattr(module, "upgrade"), "Migration module missing upgrade() function"
    assert hasattr(module, "downgrade"), "Migration module missing downgrade() function"
    assert callable(module.upgrade)
    assert callable(module.downgrade)
