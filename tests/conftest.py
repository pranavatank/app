import os
import sys
import tempfile
import shutil

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """
    Redirect the entire test session to a temporary database.

    This fixture:
    1. Creates a temp directory for the test database
    2. Patches config.DATA_DIR and config.DB_PATH to point to it
    3. Patches core.database.DB_PATH and core.database.DATA_DIR (captured at import time)
    4. Initializes the test database with all tables and seed data
    5. Asserts that we're not using the real financial.db
    6. Cleans up after all tests complete
    """
    # Create temp directory
    temp_dir = tempfile.mkdtemp(prefix="test_db_")

    # Import config and core.database AFTER setting up sys.path
    import config
    import core.database

    # Patch the module-level captures in core.database
    # These were imported from config at module load time, so we must patch them directly
    core.database.DATA_DIR = temp_dir
    core.database.DB_PATH = os.path.join(temp_dir, "test_financial.db")

    # Also patch config in case other modules import from it after this point
    config.DATA_DIR = temp_dir
    config.DB_PATH = os.path.join(temp_dir, "test_financial.db")

    # Verify we're not pointing at the real database
    assert not config.DB_PATH.endswith("data/financial.db"), \
        f"Test database protection failed: config.DB_PATH still points to {config.DB_PATH}"

    # Initialize the test database with all tables and seed data
    core.database.initialise_database()

    yield  # Run all tests

    # Cleanup: remove temp directory
    try:
        shutil.rmtree(temp_dir)
    except OSError:
        # On Windows, files may still be open; ignore cleanup errors
        pass


@pytest.fixture(scope="session")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app
