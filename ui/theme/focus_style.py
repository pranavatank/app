"""Suppress Fusion's inner focus rectangle; QSS paints rounded outer borders."""

from PySide6.QtWidgets import QProxyStyle, QStyle, QStyleFactory


class FocusRingStyle(QProxyStyle):
    """Keep Fusion behavior while suppressing its inner focus rectangle.

    The application stylesheet paints the accessible, rounded outer focus
    border for each control; this proxy prevents Fusion from drawing a second
    square ring inside it.
    """

    def drawPrimitive(self, element, option, painter, widget=None):
        if element != QStyle.PrimitiveElement.PE_FrameFocusRect:
            return super().drawPrimitive(element, option, painter, widget)

        # The app stylesheet supplies rounded, control-specific focus borders.
        # Suppress Fusion's inset focus rectangle so it cannot draw a second
        # square/dark ring inside those controls.
        return


def install_focus_ring_style(app):
    """Install once, preserving Fusion as the wrapped base style."""
    # QApplication.style() becomes QStyleSheetStyle after a global stylesheet
    # is set. Never wrap that transient wrapper (or our own proxy) on a later
    # theme switch; build one proxy around a fresh owned Fusion style instead.
    if app.property("_focus_ring_style_installed"):
        return app.style()
    base = QStyleFactory.create("Fusion")
    style = FocusRingStyle(base)
    app.setStyle(style)
    app.setProperty("_focus_ring_style_installed", True)
    return style
