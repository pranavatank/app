"""
ui/widgets/chart_widget.py — Matplotlib chart widget with theme-matched colors.
FIX: Removed session.get_theme() dependency; always uses Theme colors directly.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt
import numpy as np

from ui.theme import Theme

try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    import matplotlib
    matplotlib.use("QtAgg")
    _MPL_AVAILABLE = True
except Exception:
    _MPL_AVAILABLE = False


class ChartWidget(QWidget):
    """Embeddable matplotlib chart widget styled with app theme colors."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        if not _MPL_AVAILABLE:
            lbl = QLabel("Charts unavailable\n(pip install matplotlib)")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color: {Theme.TEXT_MUTED}; font-size: 12px;")
            layout.addWidget(lbl)
            self._canvas = None
            return

        self._fig = Figure(figsize=(8, 4.5), facecolor=Theme.SURFACE)
        self._fig.subplots_adjust(left=0.12, right=0.97, top=0.88, bottom=0.15)
        self._canvas = FigureCanvas(self._fig)
        self._canvas.setStyleSheet("background: transparent;")
        layout.addWidget(self._canvas)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _ax(self):
        self._fig.clear()
        ax = self._fig.add_subplot(111)
        ax.set_facecolor(Theme.SURFACE_ALT)
        ax.tick_params(colors=Theme.TEXT_SECONDARY, labelsize=10)
        for spine in ax.spines.values():
            spine.set_edgecolor(Theme.BORDER)
        ax.grid(True, color=Theme.BORDER, alpha=0.6, linewidth=0.7, linestyle="--")
        return ax

    def _finish(self, ax, title, xlabel="", ylabel=""):
        ax.set_title(title, color=Theme.TEXT_PRIMARY, fontsize=12,
                     fontweight="bold", pad=10)
        if xlabel:
            ax.set_xlabel(xlabel, color=Theme.TEXT_SECONDARY, fontsize=10)
        if ylabel:
            ax.set_ylabel(ylabel, color=Theme.TEXT_SECONDARY, fontsize=10)
        self._fig.patch.set_facecolor(Theme.SURFACE)
        self._canvas.draw()

    def clear(self):
        if self._canvas:
            self._fig.clear()
            self._canvas.draw()

    # ── Chart types ───────────────────────────────────────────────────────────

    def plot_bar(self, categories, values, title="", xlabel="", ylabel="", color=None):
        if not self._canvas: return
        ax = self._ax()
        color = color or Theme.PRIMARY
        bars = ax.bar(categories, values, color=color, alpha=0.85,
                      edgecolor="white", linewidth=0.8, width=0.55)
        # Value labels on bars
        for bar, val in zip(bars, values):
            if val > 0:
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() * 1.01,
                        f"₹{val:,.0f}", ha="center", va="bottom",
                        fontsize=9, color=Theme.TEXT_SECONDARY)
        if len(categories) > 5:
            ax.tick_params(axis="x", rotation=30)
        ax.yaxis.grid(True, color=Theme.BORDER, alpha=0.6)
        ax.set_axisbelow(True)
        self._finish(ax, title, xlabel, ylabel)

    def plot_pie(self, labels, values, title=""):
        if not self._canvas: return
        ax = self._ax()
        ax.set_facecolor(Theme.SURFACE)
        colors = Theme.CHART_COLORS
        wedges, texts, autotexts = ax.pie(
            values, labels=labels,
            autopct="%1.1f%%",
            colors=colors[:len(labels)],
            startangle=90,
            pctdistance=0.8,
            wedgeprops={"linewidth": 1.5, "edgecolor": "white"},
        )
        for t in texts:
            t.set_color(Theme.TEXT_PRIMARY)
            t.set_fontsize(10)
        for at in autotexts:
            at.set_color("white")
            at.set_fontweight("bold")
            at.set_fontsize(9)
        self._finish(ax, title)

    def plot_line(self, x_data, y_data, title="", xlabel="", ylabel="", color=None):
        if not self._canvas: return
        ax = self._ax()
        color = color or Theme.PRIMARY
        ax.plot(x_data, y_data, color=color, linewidth=2.5,
                marker="o", markersize=5, markerfacecolor="white",
                markeredgecolor=color, markeredgewidth=2)
        ax.fill_between(range(len(y_data)), y_data,
                        alpha=0.1, color=color)
        if len(x_data) > 5:
            ax.tick_params(axis="x", rotation=30)
        self._finish(ax, title, xlabel, ylabel)

    def plot_comparison(self, categories, values1, values2,
                        label1="", label2="",
                        title="", xlabel="", ylabel=""):
        if not self._canvas: return
        ax = self._ax()
        x = np.arange(len(categories))
        w = 0.38

        bars1 = ax.bar(x - w / 2, values1, w, label=label1,
                       color=Theme.PRIMARY,  alpha=0.85,
                       edgecolor="white", linewidth=0.8)
        bars2 = ax.bar(x + w / 2, values2, w, label=label2,
                       color=Theme.DANGER,   alpha=0.85,
                       edgecolor="white", linewidth=0.8)

        ax.set_xticks(x)
        ax.set_xticklabels(categories, rotation=30 if len(categories) > 5 else 0)
        ax.legend(
            facecolor=Theme.SURFACE,
            edgecolor=Theme.BORDER,
            labelcolor=Theme.TEXT_PRIMARY,
            fontsize=10,
        )
        ax.yaxis.grid(True, color=Theme.BORDER, alpha=0.5)
        ax.set_axisbelow(True)
        self._finish(ax, title, xlabel, ylabel)
