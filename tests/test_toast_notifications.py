from PySide6.QtCore import Qt, QPoint, QPointF, QEvent
from PySide6.QtGui import QEnterEvent
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QWidget, QMessageBox, QDialog
import pytest
import shiboken6

from ui.widgets.toast import Toast, ToastContainer


@pytest.fixture(autouse=True)
def isolate_toast_manager(qapp):
    """Keep manager queues and callbacks from one test out of the next."""
    from PySide6.QtCore import QCoreApplication, QEvent
    from ui.widgets import toast_utils

    def reset():
        containers = list({id(entry[1]): entry[1] for entry in toast_utils._containers.values()}.values())
        for container in containers:
            if not container or not shiboken6.isValid(container):
                continue
            container.drain_requests()
            container.deleteLater()
        toast_utils._containers.clear()
        toast_utils._orphaned.clear()
        toast_utils._toast_container = None
        toast_utils._default_host = None
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        qapp.processEvents()

    initial_top_levels = {id(widget) for widget in qapp.topLevelWidgets()}
    reset()
    yield
    reset()
    created = [widget for widget in qapp.topLevelWidgets() if id(widget) not in initial_top_levels]
    for widget in created:
        if shiboken6.isValid(widget):
            widget.close()
            widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qapp.processEvents()
    reset()


def test_toast_stack_is_top_right_and_resize_tracks_host(qapp):
    host = QWidget(); host.resize(900, 600); host.show()
    overlay = ToastContainer(host); overlay.setGeometry(host.rect())
    overlay.show_toast("first", "success", 0)
    overlay.show_toast("second", "warning", 0)
    qapp.processEvents()
    first, second = overlay.toasts
    assert first.geometry().top() < second.geometry().top()
    assert first.geometry().right() == host.width() - 20
    host.resize(700, 500); qapp.processEvents()
    assert overlay.size() == host.size()
    assert first.geometry().right() == host.width() - 20
    overlay.close(); host.close()


def test_toast_persistent_and_hover_pause(qapp):
    persistent = Toast("keep", duration_ms=0)
    assert persistent.duration_ms == 0
    persistent.show_toast()
    assert not persistent.timer.isActive()
    transient = Toast("pause", duration_ms=5000)
    transient.show_toast(); transient.enterEvent(QEnterEvent(QPointF(), QPointF(), QPointF()))
    assert not transient.timer.isActive()
    transient.leaveEvent(QEvent(QEvent.Type.Leave))
    assert transient.timer.isActive()
    transient.dismiss(); persistent.dismiss()


def test_fifo_overflow_does_not_start_hidden_timers(qapp):
    host = QWidget(); host.resize(400, 240); host.show()
    overlay = ToastContainer(host); overlay.setGeometry(host.rect())
    for i in range(6): overlay.show_toast(f"notice {i}", duration_ms=5000)
    qapp.processEvents()
    assert [t.message for t in overlay.toasts] == [f"notice {i}" for i in range(6)]
    shown = [t for t in overlay.toasts if not t.isHidden()]
    waiting = [t for t in overlay.toasts if t.isHidden()]
    assert shown and waiting
    assert all(t.timer.isActive() for t in shown)
    assert all(not t.timer.isActive() for t in waiting)
    first = shown[0]; first.dismiss(); qapp.processEvents()
    assert not waiting[0].isHidden() and waiting[0].timer.isActive()
    assert overlay.toasts[0].message == "notice 1"
    overlay.close(); host.close()


def test_card_that_exceeds_remaining_stack_space_waits_at_full_height(qapp):
    host = QWidget(); host.resize(400, 500); host.show()
    try:
        overlay = ToastContainer(host); overlay.setGeometry(host.rect())
        overlay.show_toast("first notice", duration_ms=5000)
        overlay.show_toast("second notice", duration_ms=5000)
        qapp.processEvents()
        first, second = overlay.toasts
        first_height = first.measure_height(376)
        natural_height = second.measure_height(376)
        host.resize(400, first_height + 65)  # Leaves 25px after first card and stack gap.
        qapp.processEvents()
        assert not first.isHidden()
        assert second.isHidden()
        assert not second.timer.isActive()
        first.dismiss(); qapp.processEvents()
        assert not second.isHidden()
        assert second.height() == natural_height
        assert second.timer.isActive()
    finally:
        host.close()


def test_overlay_mask_keeps_outside_clicks_uncovered_and_small_host_fits(qapp):
    host = QWidget(); host.resize(150, 150); host.show()
    overlay = ToastContainer(host); overlay.setGeometry(host.rect())
    overlay.show_toast("A very long diagnostic message. " * 50, "danger", 0)
    qapp.processEvents()
    card = overlay.toasts[0]
    assert card.width() <= host.width()
    assert overlay.mask().contains(card.geometry().center())
    assert not overlay.mask().contains(QPoint(2, host.height()-2))
    overlay.close(); host.close()


def test_short_toasts_stay_compact_and_long_toasts_scroll(qapp):
    host = QWidget(); host.resize(640, 620); host.show()
    overlay = ToastContainer(host); overlay.setGeometry(host.rect())
    overlay.show_toast("Saved.", duration_ms=0)
    overlay.show_toast("Long detail. " * 400, "danger", 0)
    qapp.processEvents()
    short, long = overlay.toasts
    assert short.height() < 100
    assert long._message_area.maximumHeight() == 120
    assert long.height() <= 160
    overlay.close(); host.close()


def test_short_danger_toast_with_title_and_copy_fits_body(qapp):
    host = QWidget(); host.resize(700, 300); host.show()
    try:
        overlay = ToastContainer(host); overlay.setGeometry(host.rect())
        overlay.show_toast("The file could not be imported. Review it and retry.", "danger", 0, "Import failed")
        qapp.processEvents()
        card = overlay.toasts[0]
        viewport_width = card._message_area.viewport().width()
        required_height = card.message_label.heightForWidth(viewport_width)
        assert required_height <= 120
        assert card.message_label.height() >= required_height
        assert card._message_area.verticalScrollBar().maximum() == 0
    finally:
        host.close()


@pytest.mark.parametrize("theme_name", ["Aurora", "Nova"])
def test_themed_short_danger_toast_uses_settled_viewport(qapp, theme_name):
    from ui.theme.theme_manager import ThemeManager

    old_font = qapp.font()
    ThemeManager.apply(theme_name, save=False, notify=False)
    qapp.setFont(QFont("Segoe UI", 10))
    host = QWidget(); host.resize(700, 300); host.show()
    try:
        overlay = ToastContainer(host); overlay.setGeometry(host.rect())
        overlay.show_toast("The file could not be imported. Review it and retry.", "danger", 0, "Import failed")
        qapp.processEvents()
        card = overlay.toasts[0]
        viewport = card._message_area.viewport()
        required_height = card.message_label.heightForWidth(viewport.width())
        assert required_height < 120
        assert viewport.height() >= required_height
        assert card._message_area.verticalScrollBar().maximum() == 0
    finally:
        host.close()
        qapp.setFont(old_font)
        ThemeManager.apply("Aurora", save=False, notify=False)


def test_modal_success_rehomes_to_parent_on_close(qapp):
    from ui.widgets import toast_utils
    from ui.widgets.toast_utils import show_success
    parent = QWidget(); parent.resize(600, 400); parent.show()
    dialog = QDialog(parent); dialog.setModal(True); dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True); dialog.show()
    qapp.processEvents()
    show_success("survives modal close", 4000, "Saved", parent=dialog)
    qapp.processEvents()
    modal_overlay = toast_utils._containers[id(dialog)][1]
    assert [card.message for card in modal_overlay.toasts] == ["survives modal close"]
    dialog.accept()
    qapp.processEvents()
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete); qapp.processEvents()
    moved = toast_utils._containers[id(parent)][1]
    assert [card.message for card in moved.toasts] == ["survives modal close"]
    parent.close()


def test_destroyed_host_is_removed_from_manager(qapp):
    from ui.widgets import toast_utils
    survivor = QWidget(); survivor.resize(500, 300); survivor.show()
    host = QWidget(); host.resize(500, 300); host.show()
    qapp.setActiveWindow(survivor)
    toast_utils._get_dispatcher().show_for("cleanup survives", "info", 0, None, host)
    qapp.processEvents()
    key = id(host)
    assert key in toast_utils._containers
    host.deleteLater(); qapp.processEvents()
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete); qapp.processEvents()
    assert key not in toast_utils._containers
    moved = toast_utils._containers[id(survivor)][1]
    assert [card.message for card in moved.toasts] == ["cleanup survives"]
    survivor.close()


def test_hidden_default_host_does_not_receive_fallback_toast(qapp):
    from ui.widgets import toast_utils
    hidden = QWidget(); hidden.resize(500, 300)
    toast_utils.init_toast_container(hidden)
    survivor = QWidget(); survivor.resize(500, 300); survivor.show()
    qapp.setActiveWindow(survivor)
    dispatcher = toast_utils._get_dispatcher()
    dispatcher.show_for("visible survivor", "info", 0, None, None)
    qapp.processEvents()
    assert [card.message for card in toast_utils._containers[id(survivor)][1].toasts] == ["visible survivor"]
    hidden.close(); survivor.close()


def test_single_ok_notice_routed_and_questions_preserved(monkeypatch):
    import ui.messagebox_utils as utils
    calls = []
    monkeypatch.setattr(utils, "show_danger", lambda text, title=None, parent=None: calls.append((text, title)))
    original = QMessageBox.critical
    original_warning = QMessageBox.warning
    original_information = QMessageBox.information
    utils.install_copyable_error_dialogs()
    try:
        assert QMessageBox.critical(None, "Import failed", "Bad row") == QMessageBox.StandardButton.Ok
        assert calls == [("Bad row", "Import failed")]
        assert QMessageBox.question is not None
        assert QMessageBox.critical is not original
        sentinel = object()
        monkeypatch.setitem(utils._ORIGINALS, "critical", lambda *args: sentinel)
        assert QMessageBox.critical(None, "Replace?", "Continue?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) is sentinel
    finally:
        QMessageBox.critical = original
        QMessageBox.warning = original_warning
        QMessageBox.information = original_information
        utils._ORIGINALS.clear()
