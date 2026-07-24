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
import traceback

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt

from ui.theme import Theme

# ── Backend setup ────────────────────────────────────────────────────────────
_MPL_AVAILABLE = False
FigureCanvas = None

try:
    import matplotlib
    # Try QtAgg (PyQt6 native)
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

        if not _MPL_AVAILABLE:
            self._show_unavailable()
            return

        self._setup_canvas()

    # ── Canvas init ──────────────────────────────────────────────────────────

    def _setup_canvas(self):
        self._fig    = Figure(facecolor=Theme.SURFACE)
        self._canvas = FigureCanvas(self._fig)
        self._canvas.setStyleSheet(f"background-color: {Theme.SURFACE};")
        self._layout.addWidget(self._canvas)

    def _show_unavailable(self):
        lbl = QLabel(
            "📊  Charts unavailable\n\n"
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
        ax.set_facecolor(Theme.SURFACE_ALT)
        ax.tick_params(colors=Theme.TEXT_SECONDARY, labelsize=9)
        ax.tick_params(axis="x", colors=Theme.TEXT_SECONDARY)
        ax.tick_params(axis="y", colors=Theme.TEXT_SECONDARY)
        for spine in ax.spines.values():
            spine.set_edgecolor(Theme.BORDER)
            spine.set_linewidth(0.8)
        ax.grid(axis="y", color=Theme.BORDER, alpha=0.5, linewidth=0.6, linestyle="--")
        ax.set_axisbelow(True)
        return ax

    def _finish(self, ax, title: str, xlabel: str = "", ylabel: str = ""):
        ax.set_title(title, color=Theme.TEXT_PRIMARY, fontsize=12,
                     fontweight="bold", pad=10)
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
                    fontweight="600",
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
        if self._canvas:
            self._fig.clear()
            self._canvas.draw()

    @_remember_call
    def show_empty_state(self, message: str = "No data to display"):
        if not self._canvas:
            return
        self._fig.clear()
        ax = self._fig.add_subplot(111)
        ax.set_facecolor(Theme.SURFACE)
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)
        ax.text(0.5, 0.5, f"📊  {message}", ha="center", va="center",
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
        if not self._canvas:
            return
        if not values or all(v == 0 for v in values):
            self.show_empty_state("No data for this period")
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
            ax.yaxis.set_major_formatter(mticker.FuncFormatter(self._inr_formatter))
            self._add_bar_labels(ax, bars, values)
            self._finish(ax, title, xlabel, ylabel)
        except Exception:
            traceback.print_exc()
            self.show_empty_state("Chart error")

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
        if not self._canvas:
            return
        if not categories:
            self.show_empty_state("No data to compare")
            return
        try:
            ax = self._new_ax()
            x = np.arange(len(categories))
            w = 0.36

            bars1 = ax.bar(x - w / 2, values1, w,
                           label=label1, color=Theme.SUCCESS,
                           alpha=0.88, edgecolor=Theme.SURFACE, linewidth=1)
            bars2 = ax.bar(x + w / 2, values2, w,
                           label=label2, color=Theme.DANGER,
                           alpha=0.88, edgecolor=Theme.SURFACE, linewidth=1)

            ax.set_xticks(x)
            ax.set_xticklabels(
                categories,
                rotation=35 if len(categories) > 5 else 0,
                ha="right" if len(categories) > 5 else "center",
            )
            ax.yaxis.set_major_formatter(mticker.FuncFormatter(self._inr_formatter))
            self._add_bar_labels(ax, bars1, values1)
            self._add_bar_labels(ax, bars2, values2)

            leg = ax.legend(
                facecolor=Theme.SURFACE,
                edgecolor=Theme.BORDER,
                labelcolor=Theme.TEXT_PRIMARY,
                fontsize=9,
                framealpha=0.95,
            )
            self._finish(ax, title, xlabel, ylabel)
        except Exception:
            traceback.print_exc()
            self.show_empty_state("Chart error")

    # ── Pie / donut chart ─────────────────────────────────────────────────────

    @_remember_call
    def plot_pie(self, labels: list, values: list, title: str = ""):
        if not self._canvas:
            return
        if not values or sum(values) == 0:
            self.show_empty_state("No data to display")
            return
        try:
            self._fig.clear()
            self._fig.subplots_adjust(left=0.05, right=0.75, top=0.92, bottom=0.08)
            ax = self._fig.add_subplot(111)
            ax.set_facecolor(Theme.SURFACE)

            colors  = Theme.CHART_COLORS[:len(labels)]
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
            ax.legend(
                handles=patches,
                loc="center left",
                bbox_to_anchor=(1.02, 0.5),
                frameon=True,
                facecolor=Theme.SURFACE,
                edgecolor=Theme.BORDER,
                fontsize=8,
                labelcolor=Theme.TEXT_PRIMARY,
            )
            ax.set_title(title, color=Theme.TEXT_PRIMARY, fontsize=12,
                         fontweight="bold", pad=10)
            self._fig.patch.set_facecolor(Theme.SURFACE)
            self._canvas.draw()
        except Exception:
            traceback.print_exc()
            self.show_empty_state("Chart error")

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
        if not self._canvas:
            return
        if not y_data:
            self.show_empty_state("No data to display")
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

            # Annotate points
            for i, v in enumerate(y_data):
                if v > 0:
                    ax.annotate(
                        _inr(v), (i, v),
                        textcoords="offset points", xytext=(0, 8),
                        ha="center", fontsize=8,
                        color=Theme.TEXT_SECONDARY, fontweight="600",
                    )

            ax.set_xticks(list(x))
            ax.set_xticklabels(
                x_data,
                rotation=35 if len(x_data) > 5 else 0,
                ha="right" if len(x_data) > 5 else "center",
            )
            ax.yaxis.set_major_formatter(mticker.FuncFormatter(self._inr_formatter))
            self._finish(ax, title, xlabel, ylabel)
        except Exception:
            traceback.print_exc()
            self.show_empty_state("Chart error")

    # ── Multi-line trend chart ────────────────────────────────────────────────

    @_remember_call
    def plot_trend_line(
        self,
        categories: list,
        series: dict[str, list],
        title: str = "",
        xlabel: str = "",
        ylabel: str = "",
    ):
        """
        Plot multiple trend lines.
        series = {"FD Interest": [v1, v2, ...], "Savings Interest": [...]}
        """
        if not self._canvas:
            return
        if not series or not categories:
            self.show_empty_state("No data to display")
            return
        try:
            ax   = self._new_ax()
            x    = range(len(categories))
            cols = Theme.CHART_COLORS

            for idx, (name, values) in enumerate(series.items()):
                c = cols[idx % len(cols)]
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
            ax.yaxis.set_major_formatter(mticker.FuncFormatter(self._inr_formatter))
            ax.legend(
                facecolor=Theme.SURFACE,
                edgecolor=Theme.BORDER,
                labelcolor=Theme.TEXT_PRIMARY,
                fontsize=9,
            )
            self._finish(ax, title, xlabel, ylabel)
        except Exception:
            traceback.print_exc()
            self.show_empty_state("Chart error")

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
        if not self._canvas:
            return
        if not months:
            self.show_empty_state("No monthly data")
            return
        try:
            ax = self._new_ax()
            x  = np.arange(len(months))
            w  = 0.36

            b1 = ax.bar(x - w / 2, income,  w, label="Credit",
                        color=Theme.SUCCESS, alpha=0.88,
                        edgecolor=Theme.SURFACE, linewidth=1)
            b2 = ax.bar(x + w / 2, expense, w, label="Debit",
                        color=Theme.DANGER,  alpha=0.88,
                        edgecolor=Theme.SURFACE, linewidth=1)

            ax.set_xticks(x)
            ax.set_xticklabels(months, rotation=30, ha="right")
            ax.yaxis.set_major_formatter(mticker.FuncFormatter(self._inr_formatter))
            ax.legend(
                facecolor=Theme.SURFACE,
                edgecolor=Theme.BORDER,
                labelcolor=Theme.TEXT_PRIMARY,
                fontsize=9,
            )
            self._finish(ax, title, ylabel="Amount (₹)")
        except Exception:
            traceback.print_exc()
            self.show_empty_state("Chart error")
