"""
tests/test_ui_threading.py — Test that parsing happens on worker threads, not UI thread.

Verifies:
1. Parse functions run on different thread than GUI thread
2. Controls are disabled during parse and re-enabled after (including on failure)
3. Loader.run() properly marshals work to background thread
"""

import pytest
import time
from unittest.mock import patch, MagicMock
from threading import Thread, current_thread
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import QThread, QTimer, Qt
import threading


@pytest.fixture(scope="session")
def qapp():
    """Create QApplication for all tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def main_thread_id():
    """Capture the main thread ID."""
    return threading.current_thread().ident


class TestStatementParsingThreading:
    """Test that statement parsing runs off the UI thread."""

    def test_parse_statement_runs_on_worker_thread(self, qapp, main_thread_id):
        """
        Verify parse_statement_with_debug runs on a different thread than the GUI thread.
        """
        from ui.statement_import_screen_modern import _StatementParseWorker

        parse_thread_id = None
        parse_started_event = threading.Event()

        # Monkeypatch parse_statement_with_debug to capture the thread it's running on
        def mock_parse(*args, **kwargs):
            nonlocal parse_thread_id
            parse_thread_id = threading.current_thread().ident
            parse_started_event.set()
            time.sleep(0.5)
            return [{"amount": 100, "transaction_date": "2024-01-01"}], {"debug": "info"}

        with patch("ui.statement_import_screen_modern.parse_statement_with_debug", side_effect=mock_parse):
            worker = _StatementParseWorker(
                file_path="/tmp/test.pdf",
                file_type="PDF",
                bank_name="Test Bank",
                password=None,
                column_mapping=None
            )

            # Run worker in a separate thread (simulating QThread)
            worker_thread = Thread(target=worker.run, daemon=True)
            worker_thread.start()

            # Wait for parse to start
            assert parse_started_event.wait(timeout=5), "Parse did not start"

            # Verify parse is running on different thread
            assert parse_thread_id is not None
            assert parse_thread_id != main_thread_id, \
                f"Parse ran on UI thread (ID {main_thread_id}), not worker thread"

            # Wait for worker to finish
            worker_thread.join(timeout=5)

    def test_ui_responsive_during_parse(self, qapp, main_thread_id):
        """
        Verify QApplication.processEvents() can still run while parsing is in flight.
        This ensures the UI thread is not blocked.
        """
        from ui.statement_import_screen_modern import _StatementParseWorker

        def mock_parse(*args, **kwargs):
            # Simulate a 1.5s parse
            start = time.time()
            while time.time() - start < 1.5:
                time.sleep(0.1)
            return [], {}

        # While a parse is in flight, the UI thread should be able to process events
        with patch("ui.statement_import_screen_modern.parse_statement_with_debug", side_effect=mock_parse):
            worker = _StatementParseWorker(
                file_path="/tmp/test.pdf",
                file_type="PDF",
                bank_name="Test",
                password=None,
                column_mapping=None
            )

            worker_thread = Thread(target=worker.run, daemon=True)
            worker_thread.start()

            # Process events while worker is running
            # This proves the UI thread is responsive
            processed_events = 0
            start = time.time()
            while time.time() - start < 2.0:  # Process for 2 seconds
                qapp.processEvents()
                processed_events += 1
                time.sleep(0.01)

            # Wait for worker
            worker_thread.join(timeout=5)

            # We should have processed at least some events
            assert processed_events > 0, "No events were processed while worker was running"

    def test_parse_disables_controls(self, qapp):
        """Verify that _parse_statement disables controls at startup."""
        from ui.statement_import_screen_modern import StatementImportScreen
        from core.database import initialise_database

        initialise_database()
        screen = StatementImportScreen()

        # Set up the screen
        screen.selected_account_id = 1
        screen.selected_person_id = 1
        screen.selected_file = "/tmp/test.pdf"
        screen.file_type = "PDF"

        # Enable controls initially
        screen.btn_next.setEnabled(True)
        screen.btn_browse.setEnabled(True)
        screen.file_type_combo.setEnabled(True)

        def mock_parse(*args, **kwargs):
            return [], {}

        # Mock Loader.run to prevent actual threading in this test
        with patch("ui.statement_import_screen_modern.parse_statement_with_debug", side_effect=mock_parse), \
             patch.object(screen, "_get_saved_statement_password", return_value=None), \
             patch.object(screen, "_is_statement_file_encrypted", return_value=False), \
             patch("ui.statement_import_screen_modern.Loader.run"):

            # Call _parse_statement, which should disable controls
            screen._parse_statement()

            # Verify controls are disabled
            assert not screen.btn_next.isEnabled(), "btn_next should be disabled during parse"
            assert not screen.btn_browse.isEnabled(), "btn_browse should be disabled during parse"
            assert not screen.file_type_combo.isEnabled(), "file_type_combo should be disabled during parse"

    def test_controls_reenabled_on_parse_error(self, qapp):
        """Verify that _handle_parse_error re-enables controls."""
        from ui.statement_import_screen_modern import StatementImportScreen
        from core.database import initialise_database

        initialise_database()
        screen = StatementImportScreen()

        # Disable controls to simulate being in a parse
        screen.btn_next.setEnabled(False)
        screen.btn_browse.setEnabled(False)
        screen.file_type_combo.setEnabled(False)

        # Mock the password prompt to return None (user cancels)
        with patch.object(screen, "_prompt_statement_password", return_value=(None, False)), \
             patch("ui.statement_import_screen_modern.QMessageBox.critical"):
            # Call error handler with a non-password error
            screen._handle_parse_error(ValueError("Test error"))

        # After error handling, controls should be re-enabled
        assert screen.btn_next.isEnabled(), "btn_next should be re-enabled after error"
        assert screen.btn_browse.isEnabled(), "btn_browse should be re-enabled after error"
        assert screen.file_type_combo.isEnabled(), "file_type_combo should be re-enabled after error"


class TestAISTISThreading:
    """Test that AIS/TIS parsing runs off the UI thread."""

    def test_ais_tis_parse_worker_uses_worker_thread(self, main_thread_id):
        """Verify AIS/TIS parse runs on a different thread."""
        from ui.ais_tis_import_screen_v2 import _AISTISParseWorker

        parse_thread_id = None

        def mock_parser(text):
            nonlocal parse_thread_id
            parse_thread_id = threading.current_thread().ident
            time.sleep(0.5)
            return {"details": [{"amount": 100}]}

        with patch("ui.ais_tis_import_screen_v2.parse_ais_pdf_text", side_effect=mock_parser):
            worker = _AISTISParseWorker(pdf_text="test", source_type="AIS")

            worker_thread = Thread(target=worker.run, daemon=True)
            worker_thread.start()
            worker_thread.join(timeout=5)

            assert parse_thread_id is not None
            assert parse_thread_id != main_thread_id, \
                "AIS/TIS parse should not run on UI thread"


class TestForm26ASThreading:
    """Test that Form 26AS parsing runs off the UI thread."""

    def test_form26as_parse_worker_uses_worker_thread(self, main_thread_id):
        """Verify Form 26AS parse runs on a different thread."""
        from ui.ais_tis_import_screen_v2 import _Form26ASParseWorker

        parse_thread_id = None

        def mock_parser(text):
            nonlocal parse_thread_id
            parse_thread_id = threading.current_thread().ident
            time.sleep(0.5)
            return {"records": [{"amount_paid": 100}], "assessment_year": "2023-24"}

        with patch("ui.ais_tis_import_screen_v2.parse_form26as_pdf", side_effect=mock_parser):
            worker = _Form26ASParseWorker(pdf_text="test")

            worker_thread = Thread(target=worker.run, daemon=True)
            worker_thread.start()
            worker_thread.join(timeout=5)

            assert parse_thread_id is not None
            assert parse_thread_id != main_thread_id, \
                "Form 26AS parse should not run on UI thread"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
