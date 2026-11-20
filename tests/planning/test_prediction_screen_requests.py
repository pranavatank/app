"""Deterministic request lifecycle coverage for the income prediction screen."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

import ui.income_prediction_screen as screen_module


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    return QApplication.instance() or QApplication([])


def _make_screen(monkeypatch, people=None):
    requests = []

    class Overlay:
        hidden = False

        def hide(self):
            self.hidden = True

    def queue(parent, fn, message, on_done, on_error):
        overlay = Overlay()
        requests.append({"fn": fn, "done": on_done, "error": on_error, "overlay": overlay})
        return overlay

    monkeypatch.setattr(screen_module, "Loader", type("FakeLoader", (), {
        "run": staticmethod(queue)
    }))
    monkeypatch.setattr("models.person.get_all_persons", lambda: people or [])
    monkeypatch.setattr("engines.prediction_engine._current_fy_or_default", lambda fy: fy or "2026-27")
    monkeypatch.setattr(screen_module.IncomePredictionScreen, "_refresh_all_sections", lambda self: None)
    monkeypatch.setattr(screen_module.session, "selected_person_id", 71)
    monkeypatch.setattr(screen_module.session, "selected_fy", "2026-27")
    monkeypatch.setattr(screen_module.session, "privacy_mode", False)
    screen = screen_module.IncomePredictionScreen()
    return screen, requests


def test_latest_generation_wins_even_when_callbacks_complete_in_reverse(monkeypatch):
    screen, requests = _make_screen(monkeypatch)
    screen.refresh()
    older, newer = requests
    assert older["overlay"].hidden
    newer["done"]({"tag": "new"})
    older["done"]({"tag": "old"})
    older["error"](RuntimeError("Stale result"))
    assert screen._prediction_data["tag"] == "new"
    assert screen.status_label.text() == "Prediction ready"


def test_request_freezes_person_fy_and_as_of_before_worker_runs(monkeypatch):
    screen, requests = _make_screen(monkeypatch)
    captured = []
    monkeypatch.setattr("engines.prediction_engine.get_prediction_summary",
                        lambda person_id, financial_year, as_of:
                        captured.append((person_id, financial_year, as_of)) or {"ok": True})
    queued = requests[0]
    snapshot = screen._request_context.copy()
    screen_module.session.selected_person_id = 99
    screen_module.session.selected_fy = "2025-26"
    queued["fn"]()
    assert captured == [(71, "2026-27", snapshot["as_of"])]


def test_person_deselection_invalidates_pending_result_and_clears_data(monkeypatch):
    screen, requests = _make_screen(monkeypatch)
    screen._prediction_data = {"secret": "old context"}
    screen_module.session.selected_person_id = None
    monkeypatch.setattr("models.person.get_all_persons", lambda: [{"person_id": 1}, {"person_id": 2}])
    screen.refresh()
    assert screen._prediction_data == {}
    assert "Select one person" in screen.status_label.text()
    requests[0]["done"]({"secret": "late"})
    assert screen._prediction_data == {}


def test_empty_success_and_worker_error_show_generic_unavailable_status(monkeypatch):
    screen, requests = _make_screen(monkeypatch)
    requests[0]["done"]({})
    assert "unavailable" in screen.status_label.text().lower()
    screen.refresh()
    requests[-1]["error"](RuntimeError("private detail"))
    assert "unavailable" in screen.status_label.text().lower()
    assert "private detail" not in screen.status_label.text()


def test_synthetic_timeline_chart_uses_engine_projection_series(qt_app, monkeypatch):
    screen, _ = _make_screen(monkeypatch)
    screen._prediction_data = {"timeline": {"months": [
        {"month_name": "Apr", "monthly_projected": 120, "cumulative_projected": 120},
        {"month_name": "May", "monthly_projected": 80, "cumulative_projected": 200},
    ]}}
    section = screen._build_timeline_section()
    call = screen.timeline_chart._last_call
    assert call[0] == "plot_line"
    assert call[2]["x_data"] == ["Apr", "May"]
    assert call[2]["y_data"] == [120, 200]
    section.deleteLater()


def test_refresh_retains_focus_in_the_original_section(qt_app, monkeypatch):
    monkeypatch.setattr(screen_module.IncomePredictionScreen, "load_data", lambda self: None)
    screen = screen_module.IncomePredictionScreen()
    screen._prediction_data = {"financial_year": "2026-27"}
    screen._refresh_all_sections()
    screen.show()
    screen.activateWindow()
    timeline = screen._sections["timeline"]
    timeline._header.setFocus()
    qt_app.processEvents()
    assert qt_app.focusWidget() is timeline._header
    screen._refresh_all_sections()
    assert qt_app.focusWidget() is screen._sections["timeline"]._header
    screen.close()


def test_privacy_mode_discards_pending_prediction_and_skips_dispatch(monkeypatch):
    screen, requests = _make_screen(monkeypatch)
    screen_module.session.set_privacy_mode(True)
    requests[0]["done"]({"amount": 12000})
    assert screen._prediction_data == {}
    assert "privacy mode" in screen.status_label.text()
    screen.refresh()
    assert len(requests) == 1
