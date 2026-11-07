"""
Tests for theme QSS stylesheet validity and accessibility features.
Validates that focus rings and press behaviors meet accessibility standards.
"""

import re
import pytest
from ui.theme.theme import Theme
from ui.theme.theme_manager import ThemeManager


class TestThemeFocusRings:
    """Verify that all themes have proper focus ring styling."""

    def test_all_themes_have_focus_rules(self):
        """Each registered theme's stylesheet must contain focus rules with FOCUS_RING."""
        for theme_name in ThemeManager.theme_names():
            # Apply the theme to get its colors
            ThemeManager.apply(theme_name, save=False, notify=False)

            # Get the generated stylesheet
            qss = Theme.get_stylesheet()

            # Focus states use each control's high-contrast brand border/fill.
            assert ":focus" in qss, f"Theme {theme_name} missing :focus rules"
            assert Theme.PRIMARY in qss, f"Theme {theme_name} focus color not in stylesheet"

            # Count focus rules to ensure multiple interactive elements have focus styling
            focus_count = qss.count(":focus")
            assert focus_count >= 8, (
                f"Theme {theme_name} has only {focus_count} focus rules; "
                "expected at least 8 for QPushButton, QLineEdit, QComboBox, QSpinBox, "
                "QDateEdit, QCheckBox, QRadioButton, QTabBar::tab"
            )

    def test_pressed_rules_no_padding_margin(self):
        """No :pressed rule should change padding or margin."""
        for theme_name in ThemeManager.theme_names():
            ThemeManager.apply(theme_name, save=False, notify=False)
            qss = Theme.get_stylesheet()

            # Parse complete selector blocks so single-line rules cannot
            # accidentally absorb declarations from a later unrelated block.
            for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", qss, re.DOTALL):
                selector, declarations = match.groups()
                if ":pressed" not in selector:
                    continue
                layout_change = re.search(
                    r"(?:^|;)\s*(?:padding|margin)(?:-[\w-]+)?\s*:",
                    declarations,
                    re.IGNORECASE,
                )
                assert layout_change is None, (
                    f"Theme {theme_name} has :pressed rule with padding/margin: "
                    f"{selector.strip()} {{{declarations}}}"
                )

    def test_focus_ring_covers_major_widgets(self):
        """Verify focus ring styling exists for major interactive widgets."""
        ThemeManager.apply("Aurora", save=False, notify=False)
        qss = Theme.get_stylesheet()

        required_widgets = [
            "QPushButton:focus",
            "QLineEdit:focus",
            "QComboBox:focus",
            "QSpinBox:focus",
            "QDateEdit:focus",
            "QCheckBox:focus",
            "QRadioButton:focus",
            "QTabBar::tab:focus",
        ]

        for widget in required_widgets:
            assert widget in qss, (
                f"Missing focus rule for {widget}"
            )

    def test_focus_ring_contrast(self):
        """Verify FOCUS_RING token exists and is defined for all themes."""
        for theme_name in ThemeManager.theme_names():
            ThemeManager.apply(theme_name, save=False, notify=False)

            # FOCUS_RING should be a valid color
            focus_ring = Theme.FOCUS_RING
            assert focus_ring is not None, (
                f"Theme {theme_name} has FOCUS_RING = None"
            )

            # It should be a string (hex color)
            assert isinstance(focus_ring, str), (
                f"Theme {theme_name} FOCUS_RING is not a string: {type(focus_ring)}"
            )

            # Basic format check (hex color)
            assert focus_ring.startswith("#") or focus_ring.startswith("rgb"), (
                f"Theme {theme_name} FOCUS_RING has invalid format: {focus_ring}"
            )

    def test_focus_proxy_paints_ring_without_changing_control_geometry(self, qapp):
        """A focused, QSS-styled button renders the ring and remains keyboard active."""
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QImage
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QLineEdit, QVBoxLayout, QWidget
        from ui.theme.focus_style import install_focus_ring_style

        ThemeManager.apply("Aurora", save=False, notify=False)
        install_focus_ring_style(qapp)
        parent = QWidget()
        layout = QVBoxLayout(parent)
        field = QLineEdit()
        button = Theme.btn("Continue", variant="secondary", height=44, min_width=140)
        button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        layout.addWidget(field)
        layout.addWidget(button)
        parent.show()
        field.setFocus()
        QTest.keyClick(field, Qt.Key.Key_Tab)
        qapp.processEvents()
        assert button.hasFocus(), "Tab did not move focus to the button"
        before = button.geometry()

        image = QImage(button.size(), QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        button.render(image)
        focus_border = Theme.PRIMARY.lower()
        expected = tuple(int(focus_border[i:i + 2], 16) for i in (1, 3, 5))
        assert any(
            all(abs(image.pixelColor(x, y).getRgb()[c] - expected[c]) <= 4 for c in range(3))
            for x in range(image.width()) for y in range(image.height())
        ), "Focused button render did not contain its rounded brand border"
        assert button.geometry() == before

        activated = []
        button.clicked.connect(lambda: activated.append(True))
        QTest.keyClick(button, Qt.Key.Key_Space)
        assert activated == [True]

        # Theme refreshes must leave the installed proxy in place instead of
        # recursively wrapping QStyleSheetStyle and crashing during teardown.
        ThemeManager.apply("Nova", save=False, notify=False)
        ThemeManager.apply("Aurora", save=False, notify=False)
        assert qapp.property("_focus_ring_style_installed")
        assert button.geometry() == before
        parent.close()

    def test_toolbutton_has_keyboard_focus_border_and_space_activation(self, qapp):
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QImage
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QLineEdit, QToolButton, QVBoxLayout, QWidget

        ThemeManager.apply("Aurora", save=False, notify=False)
        parent = QWidget()
        layout = QVBoxLayout(parent)
        field = QLineEdit()
        button = QToolButton()
        button.setText("Previous")
        button.setCheckable(True)
        button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        layout.addWidget(field)
        layout.addWidget(button)
        parent.show()
        field.setFocus()
        QTest.keyClick(field, Qt.Key.Key_Tab)
        qapp.processEvents()
        assert button.hasFocus()
        geometry = button.geometry()

        image = QImage(button.size(), QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        button.render(image)
        primary = Theme.PRIMARY.lower()
        expected = tuple(int(primary[i:i + 2], 16) for i in (1, 3, 5))
        assert any(
            all(abs(image.pixelColor(x, y).getRgb()[c] - expected[c]) <= 4 for c in range(3))
            for x in range(image.width()) for y in range(image.height())
        ), "Focused toolbutton render did not contain its brand border"
        assert button.geometry() == geometry

        QTest.keyClick(button, Qt.Key.Key_Space)
        assert button.isChecked(), "Space did not activate the focused toolbutton"
        qss = Theme.get_stylesheet()
        assert "QCheckBox:focus::indicator:checked" in qss
        assert "QRadioButton:focus::indicator:checked" in qss
        parent.close()

    def test_selected_tab_keyboard_focus_is_distinct_in_light_and_dark(self, qapp):
        """Keyboard focus on the selected tab stays visible in both themes."""
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QImage
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

        for theme_name in ("Aurora", "Nova"):
            ThemeManager.apply(theme_name, save=False, notify=False)
            parent = QWidget()
            layout = QVBoxLayout(parent)
            tabs = QTabWidget()
            tabs.addTab(QWidget(), "Overview")
            tabs.addTab(QWidget(), "Details")
            layout.addWidget(tabs)
            parent.show()
            bar = tabs.tabBar()
            bar.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            bar.setFocus()
            QTest.keyClick(bar, Qt.Key.Key_Right)
            qapp.processEvents()

            assert bar.hasFocus()
            assert tabs.currentIndex() == 1
            geometry = bar.tabRect(1)
            image = QImage(bar.size(), QImage.Format.Format_ARGB32_Premultiplied)
            image.fill(Qt.GlobalColor.transparent)
            bar.render(image)
            focus = Theme.TEXT_ON_PRIMARY.lower()
            expected = tuple(int(focus[i:i + 2], 16) for i in (1, 3, 5))
            assert any(
                all(abs(image.pixelColor(x, y).getRgb()[c] - expected[c]) <= 4 for c in range(3))
                for x in range(image.width()) for y in range(image.height())
            ), f"{theme_name}: selected focused tab did not render its contrasting focus border"
            assert bar.tabRect(1) == geometry
            parent.close()


class TestThemeScrollbars:
    """Verify scrollbars meet size requirements."""

    def test_scrollbar_size(self):
        """Scrollbars should be slim (8-10px) to avoid visual overlap."""
        ThemeManager.apply("Aurora", save=False, notify=False)
        qss = Theme.get_stylesheet()

        # Check vertical scrollbar
        assert "width: 10px" in qss or "width:10px" in qss, (
            "Vertical scrollbar track should be 10px wide (8px handle + 1px padding each side)"
        )

        # Check horizontal scrollbar
        assert "height: 10px" in qss or "height:10px" in qss, (
            "Horizontal scrollbar track should be 10px tall (8px handle + 1px padding each side)"
        )

        # Check handle sizes
        assert "min-height: 28px" in qss or "min-height:28px" in qss, (
            "Vertical scrollbar handle should have min-height: 28px"
        )
        assert "min-width: 8px" in qss or "min-width:8px" in qss, (
            "Vertical scrollbar handle should have min-width: 8px"
        )
        assert "min-height: 8px" in qss or "min-height:8px" in qss, (
            "Horizontal scrollbar handle should have min-height: 8px"
        )


class TestThemeSpinbox:
    """Verify spinbox buttons meet size requirements."""

    def test_spinbox_button_size(self):
        """Spinbox up/down buttons should be sized appropriately."""
        ThemeManager.apply("Aurora", save=False, notify=False)
        qss = Theme.get_stylesheet()

        # Spinbox buttons should be 24px wide and 12px tall each
        assert "width: 24px" in qss or "width:24px" in qss, (
            "Spinbox buttons should have width: 24px"
        )
        assert "height: 12px" in qss or "height:12px" in qss, (
            "Spinbox buttons should have height: 12px"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
