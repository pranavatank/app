from types import SimpleNamespace

from PySide6.QtWidgets import QComboBox

from ui.dashboard_screen import _is_reloadable_app_module
from ui.dashboard_screen import DashboardScreen
from core.session import session


def _module_at(path):
    return SimpleNamespace(__spec__=SimpleNamespace(origin=str(path)))


def test_hard_refresh_accepts_first_party_python_modules(tmp_path):
    app_root = tmp_path / "App"
    session_source = app_root / "core" / "session.py"
    ui_source = app_root / "ui" / "widgets" / "section.py"
    config_source = app_root / "config.py"

    assert _is_reloadable_app_module(
        "core.session", _module_at(session_source), app_root
    )
    assert _is_reloadable_app_module(
        "ui.widgets.section", _module_at(ui_source), app_root
    )
    assert _is_reloadable_app_module("config", _module_at(config_source), app_root)


def test_hard_refresh_rejects_venv_and_non_app_modules(tmp_path):
    app_root = tmp_path / "App"
    numpy_source = app_root / ".venv" / "Lib" / "site-packages" / "numpy" / "__init__.py"
    tool_source = app_root / "tools" / "helper.py"

    assert not _is_reloadable_app_module(
        "numpy", _module_at(numpy_source), app_root
    )
    assert not _is_reloadable_app_module(
        "tools.helper", _module_at(tool_source), app_root
    )


def test_hard_refresh_rejects_path_prefix_sibling(tmp_path):
    app_root = tmp_path / "App"
    sibling_source = tmp_path / "App-vendor" / "core" / "session.py"

    assert not _is_reloadable_app_module(
        "core.session", _module_at(sibling_source), app_root
    )


def test_hard_refresh_rejects_native_extensions(tmp_path):
    app_root = tmp_path / "App"
    extension_source = app_root / "ui" / "native_widget.pyd"

    assert not _is_reloadable_app_module(
        "ui.native_widget", _module_at(extension_source), app_root
    )


def _populate_year_selector(qapp, monkeypatch, selected_fy):
    import ui.dashboard_screen as dashboard_module

    monkeypatch.setattr(
        dashboard_module, "get_all_financial_years",
        lambda since_year: ["2025-26", "2026-27"],
    )
    monkeypatch.setattr(
        dashboard_module, "get_current_financial_year", lambda: "2026-27"
    )
    previous_fy = session.selected_fy
    session.selected_fy = selected_fy
    combo = QComboBox()
    screen_stub = SimpleNamespace(
        fy_combo=combo,
        _sync_context_selectors=lambda: None,
    )
    try:
        DashboardScreen._populate_selectors(screen_stub)
        return combo.currentText(), session.selected_fy
    finally:
        session.selected_fy = previous_fy
        combo.deleteLater()


def test_hard_refresh_keeps_selected_fy_when_available(qapp, monkeypatch):
    assert _populate_year_selector(qapp, monkeypatch, "2025-26") == (
        "2025-26", "2025-26"
    )


def test_hard_refresh_falls_back_to_current_fy_when_unavailable(qapp, monkeypatch):
    assert _populate_year_selector(qapp, monkeypatch, "2024-25") == (
        "2026-27", "2026-27"
    )
