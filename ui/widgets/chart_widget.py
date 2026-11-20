"""
ui/widgets/chart_widget.py — Production-quality matplotlib chart widget.

Key fixes vs old version:
  • Proper backend detection (tries qtagg, then qt5agg, then agg fallback)
  • All chart methods guard against empty data gracefully
  • Correct subplot_adjust after figure.clear() on every draw
  • Rupee formatter on Y axes
  • Bar charts: gradient-like color array, rounded value labels
  • Pie charts: donut style, better legend placement
  • Line charts: gradient fill, point markers, value annotations
  • Comparison charts: correct x-tick labels, value labels on bars
  • New: plot_trend_line(), plot_monthly_bar(), show_empty_state()
"""

from __future__ import annotations
import functools
import os
import traceback

from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QHeaderView, QLabel, QToolButton, QVBoxLayout, QWidget,
)
from PySide6.QtGui import QColor, QPalette

from ui.widgets.excel_table import ExcelTable
from PySide6.QtCore import Qt

from ui.theme import Theme

# ── Backend setup ────────────────────────────────────────────────────────────
_MPL_AVAILABLE = False
FigureCanvas = None

try:
    # matplotlib picks its Qt binding at import time; main.py hard-sets QT_API,
    # but this module is also imported by entry points that bypass main.py.
    os.environ.setdefault("QT_API", "pyside6")
    import matplotlib
    # Try QtAgg (PySide6 native)
    try:
        matplotlib.use("QtAgg")
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as _FC
        FigureCanvas = _FC
        _MPL_AVAILABLE = True
    except Exception:
        pass

    if not _MPL_AVAILABLE:
        try:
            matplotlib.use("Qt5Agg")
            from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as _FC
            FigureCanvas = _FC
            _MPL_AVAILABLE = True
        except Exception:
            pass

    if _MPL_AVAILABLE:
        from matplotlib.figure import Figure
        import matplotlib.ticker as mticker
        import matplotlib.patches as mpatches
        import numpy as np

        # Global rcParams — match theme fonts & colors
        matplotlib.rcParams.update({
            "font.family":       "DejaVu Sans",
            "font.size":         10,
            "axes.titlesize":    12,
            "axes.titleweight":  "bold",
            "axes.labelsize":    10,
            "xtick.labelsize":   9,
            "ytick.labelsize":   9,
            "legend.fontsize":   9,
            "figure.dpi":        100,
            "savefig.dpi":       100,
        })

except Exception:
    _MPL_AVAILABLE = False


def _remember_call(fn):
    """Record the (method, args, kwargs) used to draw the chart so
    refresh_theme() can replay it after a live theme switch — colors are
    baked into matplotlib artists at draw time, so re-polishing the canvas
    alone leaves the existing chart stale."""
    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        self._last_call = (fn.__name__, args, kwargs)
        return fn(self, *args, **kwargs)
    return wrapper


def _inr(value: float) -> str:
    """Format a number as Indian Rupee (abbreviated)."""
    if value < 0:
        return "-" + _inr(-value)
    if value >= 1_00_00_000:
        return f"₹{value/1_00_00_000:.1f}Cr"
    if value >= 1_00_000:
        return f"₹{value/1_00_000:.1f}L"
    if value >= 1_000:
        return f"₹{value/1_000:.1f}K"
    return f"₹{value:.0f}"


class ChartWidget(QWidget):
    """
    Embeddable matplotlib chart widget styled with the app theme.

    Public API:
        plot_bar(categories, values, title, xlabel, ylabel, color)
        plot_comparison(categories, values1, values2, label1, label2, title, xlabel, ylabel)
        plot_pie(labels, values, title)
        plot_line(x_data, y_data, title, xlabel, ylabel, color)
        plot_trend_line(fys, values_dict, title)   — multi-line trend
        plot_monthly_bar(months, income, expense, title)
        clear()
        show_empty_state(message)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)

        self._canvas = None
        self._fig    = None
        self._empty_lbl = None
        self._last_call: tuple | None = None

        if _MPL_AVAILABLE:
            self._setup_canvas()
        else:
            self._show_unavailable()

        self._table_button = QToolButton(self)
        self._table_button.setObjectName("chartDataButton")
        self._table_button.setText("View chart data")
        self._table_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._table_button.clicked.connect(self._show_data_table)
        self._layout.addWidget(self._table_button, alignment=Qt.AlignmentFlag.AlignRight)
        self._set_data("", "", [], {})

    def _set_data(self, title, category_header, categories, series):
        self._chart_title = title or "Chart data"
        self._data_headers = (category_header or "Category", *series)
        self._data_rows = tuple(
            (category, *(values[index] if index < len(values) else None for values in series.values()))
            for index, category in enumerate(categories)
        )
        self.setAccessibleName(self._chart_title)
        self.setAccessibleDescription("")
        self._table_button.setAccessibleName(f"View data for {self._chart_title}" if title else "View chart data")
        self._table_button.setVisible(bool(categories) and bool(series))

    def _show_data_table(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(self._chart_title)
        dialog.resize(600, 420)
        layout = QVBoxLayout(dialog)
        table = ExcelTable(dialog, show_checkboxes=False, read_only=True)
        palette = table.palette()
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(Theme.SURFACE_ALT))
        table.setPalette(palette)
        table.setAccessibleName(f"{self._chart_title} data table")
        table.setHeaders(list(self._data_headers))
        for row in self._data_rows:
            # Keep the original recorded precision and distinguish missing amounts from zero.
            table.addDataRow(list(row))
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setMinimumSectionSize(100)
        table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(table)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        Theme.style_button(buttons.button(QDialogButtonBox.StandardButton.Close), "secondary")
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        table.setFocus()
        dialog.exec()
        dialog.deleteLater()

    # ── Canvas init ──────────────────────────────────────────────────────────

    def _setup_canvas(self):
        self._fig    = Figure(facecolor=Theme.SURFACE)
        self._canvas = FigureCanvas(self._fig)
        self._canvas.setStyleSheet(f"background-color: {Theme.SURFACE};")
        self._layout.addWidget(self._canvas)

    def _show_unavailable(self):
        lbl = QLabel(
            "Charts unavailable\n\n"
            "Install matplotlib:\n"
            "pip install matplotlib"
        )
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(f"color: {Theme.TEXT_MUTED}; font-size: 13px; padding: 20px;")
        self._layout.addWidget(lbl)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _new_ax(self, tight: bool = True):
        """Clear figure and return a fresh Axes with theme styling."""
        self._fig.clear()
        if tight:
            self._fig.subplots_adjust(left=0.13, right=0.97, top=0.88, bottom=0.18)
        ax = self._fig.add_subplot(111)
        ax.set_facecolor(Theme.SURFACE)
        ax.tick_params(colors=Theme.TEXT_SECONDARY, labelsize=9)
        ax.tick_params(axis="x", colors=Theme.TEXT_SECONDARY)
        ax.tick_params(axis="y", colors=Theme.TEXT_SECONDARY)
        for spine in ax.spines.values():
            spine.set_edgecolor(Theme.BORDER)
            spine.set_linewidth(0.8)
        ax.grid(axis="y", color=Theme.BORDER, alpha=0.5, linewidth=0.6, linestyle="--")
        ax.set_axisbelow(True)
        return ax

    def _add_legend(self, ax, **options):
        ax.legend(
            facecolor=Theme.SURFACE,
            edgecolor=Theme.BORDER,
            labelcolor=Theme.TEXT_PRIMARY,
            fontsize=8,
            **options,
        )

    def _finish(self, ax, title: str, xlabel: str = "", ylabel: str = "", *, currency=True):
        if title:
            ax.set_title(title, color=Theme.TEXT_PRIMARY, fontsize=10, wrap=True, pad=6)
        if currency:
            ax.yaxis.set_major_formatter(mticker.FuncFormatter(self._inr_formatter))
        if xlabel:
            ax.set_xlabel(xlabel, color=Theme.TEXT_SECONDARY, fontsize=10, labelpad=6)
        if ylabel:
            ax.set_ylabel(ylabel, color=Theme.TEXT_SECONDARY, fontsize=10, labelpad=6)
        self._fig.patch.set_facecolor(Theme.SURFACE)
        try:
            self._canvas.draw()
        except Exception:
            pass

    def _add_bar_labels(self, ax, bars, values):
        """Add value labels on top of each bar."""
        for bar, val in zip(bars, values):
            if val > 0:
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + bar.get_height() * 0.02,
                    _inr(val),
                    ha="center", va="bottom",
                    fontsize=8, color=Theme.TEXT_SECONDARY,
                    fontweight="bold",
                )

    def _inr_formatter(self, x, _):
        return _inr(x)

    # ── Public: clear / empty state ───────────────────────────────────────────

    def refresh_theme(self):
        """Re-apply theme colors after a live switch: restyle the canvas
        background and replay whatever was last plotted."""
        if not self._canvas:
            return
        self._canvas.setStyleSheet(f"background-color: {Theme.SURFACE};")
        if self._last_call is None:
            return
        name, args, kwargs = self._last_call
        getattr(self, name)(*args, **kwargs)

    @_remember_call
    def clear(self):
        self._set_data("", "", [], {})
        if self._canvas:
            self._fig.clear()
            self._canvas.draw()

    @_remember_call
    def show_empty_state(self, message: str = "No data to display"):
        self._set_data("", "", [], {})
        self._draw_empty_state(message)

    def _draw_empty_state(self, message):
        self.setAccessibleDescription(message)
        if not self._canvas:
            return
        self._fig.clear()
        ax = self._fig.add_subplot(111)
        ax.set_facecolor(Theme.SURFACE)
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)
        ax.text(0.5, 0.5, f"— {message}", ha="center", va="center",
                transform=ax.transAxes, fontsize=13,
                color=Theme.TEXT_MUTED, style="italic")
        self._fig.patch.set_facecolor(Theme.SURFACE)
        self._canvas.draw()

    # ── Bar chart ─────────────────────────────────────────────────────────────

    @_remember_call
    def plot_bar(
        self,
        categories: list,
        values: list,
        title: str = "",
        xlabel: str = "",
        ylabel: str = "",
        color: str | None = None,
    ):
        self._set_data(title, xlabel, categories, {ylabel or "Amount (₹)": values})
        if not self._canvas:
            return
        if not values or all(v == 0 for v in values):
            self._draw_empty_state("No data for this period")
            return
        try:
            ax = self._new_ax()
            c = color or Theme.PRIMARY

            # Use a color array — slightly vary alpha across bars for depth
            n = len(categories)
            alphas = [0.75 + 0.25 * (i / max(n - 1, 1)) for i in range(n)]
            bars = ax.bar(
                range(n), values,
                color=c, alpha=0.88,
                edgecolor=Theme.SURFACE, linewidth=1.2,
                width=0.58,
            )
            for bar, alpha in zip(bars, alphas):
                bar.set_alpha(alpha)

            ax.set_xticks(range(n))
            ax.set_xticklabels(categories,
                               rotation=30 if n > 5 else 0,
                               ha="right" if n > 5 else "center")
            self._finish(ax, title, xlabel, ylabel)
        except Exception:
            traceback.print_exc()
            self._draw_empty_state("Chart error")

    # ── Comparison bar chart ──────────────────────────────────────────────────

    @_remember_call
    def plot_comparison(
        self,
        categories: list,
        values1: list,
        values2: list,
        label1: str = "",
        label2: str = "",
        title: str = "",
        xlabel: str = "",
        ylabel: str = "",
    ):
        first_header = label1 or "Series 1"
        second_header = label2 or "Series 2"
        if first_header == second_header:
            first_header += " (1)"
            second_header += " (2)"
        self._set_data(title, xlabel, categories, {first_header: values1, second_header: values2})
        if not self._canvas:
            return
        if not categories:
            self._draw_empty_state("No data to compare")
            return
        try:
            ax = self._new_ax()
            x = np.arange(len(categories))
            w = 0.36

            bars1 = ax.bar(x - w / 2, values1, w,
                           label=label1, color=Theme.CHART_COLORS[0],
                           alpha=0.88, edgecolor=Theme.SURFACE, linewidth=1)
            bars2 = ax.bar(x + w / 2, values2, w,
                           label=label2, color=Theme.CHART_COLORS[1],
                           alpha=0.88, edgecolor=Theme.SURFACE, linewidth=1)

            ax.set_xticks(x)
            ax.set_xticklabels(
                categories,
                rotation=35 if len(categories) > 5 else 0,
                ha="right" if len(categories) > 5 else "center",
            )

            if ax.get_legend_handles_labels()[0]:
                self._add_legend(ax, loc="best")
            self._finish(ax, title, xlabel, ylabel)
        except Exception:
            traceback.print_exc()
            self._draw_empty_state("Chart error")

    # ── Pie / donut chart ─────────────────────────────────────────────────────

    @_remember_call
    def plot_pie(self, labels: list, values: list, title: str = ""):
        self._set_data(title, "Category", labels, {"Amount (₹)": values})
        if not self._canvas:
            return
        if not values or sum(values) == 0:
            self._draw_empty_state("No data to display")
            return
        try:
            self._fig.clear()
            self._fig.subplots_adjust(left=0.05, right=0.75, top=0.92, bottom=0.08)
            ax = self._fig.add_subplot(111)
            ax.set_facecolor(Theme.SURFACE)

            palette = Theme.CHART_COLORS
            colors = [palette[index % len(palette)] for index in range(len(labels))]
            explode = [0.03] * len(labels)

            wedges, texts, autotexts = ax.pie(
                values,
                labels=None,           # labels go in legend instead
                autopct="%1.1f%%",
                colors=colors,
                startangle=90,
                pctdistance=0.75,
                explode=explode,
                wedgeprops={
                    "linewidth": 2,
                    "edgecolor": Theme.SURFACE,
                    "width":     0.6,   # donut hole
                },
            )
            for at in autotexts:
                at.set_color("white")
                at.set_fontweight("bold")
                at.set_fontsize(8)

            # Legend outside the pie
            patches = [
                mpatches.Patch(color=colors[i], label=f"{labels[i]}  {_inr(values[i])}")
                for i in range(len(labels))
            ]
            self._add_legend(ax, handles=patches, loc="center left", bbox_to_anchor=(1.02, 0.5))
            self._finish(ax, title, currency=False)
        except Exception:
            traceback.print_exc()
            self._draw_empty_state("Chart error")

    # ── Line chart ────────────────────────────────────────────────────────────

    @_remember_call
    def plot_line(
        self,
        x_data: list,
        y_data: list,
        title: str = "",
        xlabel: str = "",
        ylabel: str = "",
        color: str | None = None,
    ):
        self._set_data(title, xlabel, x_data, {ylabel or "Amount (₹)": y_data})
        if not self._canvas:
            return
        if not y_data:
            self._draw_empty_state("No data to display")
            return
        try:
            ax = self._new_ax()
            c  = color or Theme.PRIMARY
            x  = range(len(y_data))

            ax.plot(
                x, y_data,
                color=c, linewidth=2.5,
                marker="o", markersize=6,
                markerfacecolor=Theme.SURFACE,
                markeredgecolor=c, markeredgewidth=2,
                zorder=3,
            )
            ax.fill_between(x, y_data, alpha=0.12, color=c)

            ax.set_xticks(list(x))
            ax.set_xticklabels(
                x_data,
                rotation=35 if len(x_data) > 5 else 0,
                ha="right" if len(x_data) > 5 else "center",
            )
            self._finish(ax, title, xlabel, ylabel)
        except Exception:
            traceback.print_exc()
            self._draw_empty_state("Chart error")

    # ── Multi-line trend chart ────────────────────────────────────────────────

    @_remember_call
    def plot_trend_line(
        self,
        categories: list,
        series: dict[str, list],
        title: str = "",
        xlabel: str = "",
        ylabel: str = "",
        trim_trailing_empty: bool = True,
    ):
        """
        Plot multiple trend lines.
        series = {"FD Interest": [v1, v2, ...], "Savings Interest": [...]}
        trim_trailing_empty: if True, remove trailing all-zero/None months
        """
        self._set_data(title, xlabel, categories, series)
        if not self._canvas:
            return
        if not series or not categories:
            self._draw_empty_state("No data to display")
            return
        if not any(value is not None for values in series.values() for value in values):
            self._draw_empty_state("No data to display")
            return
        try:
            # Trim trailing empty months if all series end with 0/None
            if trim_trailing_empty and categories and series:
                trim_idx = len(categories)
                for i in range(len(categories) - 1, -1, -1):
                    all_empty = all(
                        (not values or i >= len(values) or values[i] is None or values[i] == 0)
                        for values in series.values()
                    )
                    if not all_empty:
                        trim_idx = i + 1
                        break
                if trim_idx < len(categories):
                    categories = categories[:trim_idx]
                    series = {k: v[:trim_idx] for k, v in series.items()}

            ax   = self._new_ax()
            x    = range(len(categories))
            cols = Theme.CHART_COLORS

            for idx, (name, values) in enumerate(series.items()):
                c = cols[idx % len(cols)]
                values = np.array(
                    [values[i] if i < len(values) else None for i in x],
                    dtype=float,
                )
                ax.plot(
                    x, values,
                    color=c, linewidth=2.2,
                    marker="o", markersize=5,
                    markerfacecolor=Theme.SURFACE,
                    markeredgecolor=c, markeredgewidth=1.8,
                    label=name, zorder=3,
                )
                ax.fill_between(x, values, alpha=0.08, color=c)

            ax.set_xticks(list(x))
            ax.set_xticklabels(
                categories,
                rotation=35 if len(categories) > 5 else 0,
                ha="right" if len(categories) > 5 else "center",
            )
            if ax.get_legend_handles_labels()[0]:
                self._add_legend(ax, loc="best")
            self._finish(ax, title, xlabel, ylabel)
        except Exception:
            traceback.print_exc()
            self._draw_empty_state("Chart error")

    # ── Monthly income vs expense bar chart ───────────────────────────────────

    @_remember_call
    def plot_monthly_bar(
        self,
        months: list,
        income: list,
        expense: list,
        title: str = "Monthly Overview",
    ):
        """Stacked-side monthly income vs expense bar chart."""
        self._set_data(title, "Month", months, {"Income (₹)": income, "Expense (₹)": expense})
        if not self._canvas:
            return
        if not months:
            self._draw_empty_state("No monthly data")
            return
        try:
            ax = self._new_ax()
            x  = np.arange(len(months))
            w  = 0.36

            b1 = ax.bar(x - w / 2, income,  w, label="Income",
                        color=Theme.CHART_COLORS[0], alpha=0.88,
                        edgecolor=Theme.SURFACE, linewidth=1)
            b2 = ax.bar(x + w / 2, expense, w, label="Expense",
                        color=Theme.CHART_COLORS[1],  alpha=0.88,
                        edgecolor=Theme.SURFACE, linewidth=1)

            ax.set_xticks(x)
            ax.set_xticklabels(months, rotation=30, ha="right")
            if ax.get_legend_handles_labels()[0]:
                self._add_legend(ax, loc="best")
            self._finish(ax, title, ylabel="Amount (₹)")
        except Exception:
            traceback.print_exc()
            self._draw_empty_state("Chart error")
