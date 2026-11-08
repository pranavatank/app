from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QCheckBox, QComboBox, QPushButton

from tools.real_ui_tests.rebuild_common import _combo_arrow_local_point, _os_click_local_point


def test_wide_checkbox_uses_its_indicator_as_os_click_target(qapp):
    checkbox = QCheckBox("Mask financial amounts")
    checkbox.setFixedSize(620, 36)
    checkbox.show()
    qapp.processEvents()

    center = checkbox.rect().center()
    assert not checkbox.hitButton(center)
    QTest.mouseClick(checkbox, Qt.MouseButton.LeftButton, pos=center)
    assert not checkbox.isChecked()

    indicator_center = _os_click_local_point(checkbox)
    assert checkbox.hitButton(indicator_center)
    QTest.mouseClick(checkbox, Qt.MouseButton.LeftButton, pos=QPoint(indicator_center))
    assert checkbox.isChecked()
    checkbox.close()


def test_narrow_checkbox_and_regular_button_keep_center_click(qapp):
    checkbox = QCheckBox("Privacy")
    checkbox.setFixedSize(100, 32)
    checkbox.show()
    qapp.processEvents()
    indicator_center = _os_click_local_point(checkbox)
    assert checkbox.hitButton(indicator_center)
    QTest.mouseClick(checkbox, Qt.MouseButton.LeftButton, pos=QPoint(indicator_center))
    assert checkbox.isChecked()
    checkbox.close()

    button = QPushButton("Save")
    button.setFixedSize(120, 36)
    button.show()
    qapp.processEvents()
    point = _os_click_local_point(button)
    assert point == button.rect().center()
    clicked = []
    button.clicked.connect(lambda: clicked.append(True))
    QTest.mouseClick(button, Qt.MouseButton.LeftButton, pos=point)
    assert clicked == [True]
    button.close()


def test_editable_combo_opens_from_arrow_and_selects_existing_item_data(qapp):
    combo = QComboBox()
    combo.setEditable(True)
    combo.setFixedSize(420, 40)
    combo.addItem("-- Select or Type New Bank --", userData=None)
    combo.addItem("Jana (Jana Small Finance Bank)", userData="Jana Small Finance Bank")
    combo.show()
    qapp.processEvents()

    QTest.mouseClick(combo, Qt.MouseButton.LeftButton, pos=combo.rect().center())
    qapp.processEvents()
    assert not combo.view().isVisible()

    arrow_point = _combo_arrow_local_point(combo)
    QTest.mouseClick(combo, Qt.MouseButton.LeftButton, pos=arrow_point)
    qapp.processEvents()
    assert combo.view().isVisible()

    count_before = combo.count()
    index = combo.model().index(1, 0)
    QTest.keyClick(combo.view(), Qt.Key.Key_Down)
    QTest.keyClick(combo.view(), Qt.Key.Key_Enter)
    qapp.processEvents()
    assert combo.currentText() == "Jana (Jana Small Finance Bank)"
    assert combo.currentData() == "Jana Small Finance Bank"
    assert combo.count() == count_before
    combo.close()
