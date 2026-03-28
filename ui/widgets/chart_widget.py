"""
ui/widgets/chart_widget.py — Matplotlib chart widget (Phase 7)
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

from ui.theme import Theme
from core.session import session


class ChartWidget(QWidget):
    """Embeddable matplotlib chart widget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Get theme colors
        self._update_theme()
        
        self.figure = Figure(figsize=(8, 5), facecolor=self.colors['bg_primary'])
        self.canvas = FigureCanvas(self.figure)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas)

    def _update_theme(self):
        """Update colors from current theme."""
        theme_name = session.get_theme() if hasattr(session, 'get_theme') else 'light'
        self.colors = Theme.get_colors(theme_name)

    def clear(self):
        """Clear the figure."""
        self.figure.clear()

    def plot_line(self, x_data, y_data, title="", xlabel="", ylabel="", color=None):
        """Plot a line chart."""
        self._update_theme()
        if color is None:
            color = self.colors['primary']
            
        self.clear()
        ax = self.figure.add_subplot(111)
        ax.plot(x_data, y_data, color=color, linewidth=2, marker='o', markersize=4)
        ax.set_title(title, color=self.colors['text_primary'], fontsize=12, fontweight='bold')
        ax.set_xlabel(xlabel, color=self.colors['text_secondary'])
        ax.set_ylabel(ylabel, color=self.colors['text_secondary'])
        ax.grid(True, alpha=0.2, color=self.colors['border'])
        ax.set_facecolor(self.colors['bg_secondary'])
        ax.tick_params(colors=self.colors['text_secondary'])
        self.figure.patch.set_facecolor(self.colors['bg_primary'])
        self.figure.tight_layout()
        self.canvas.draw()

    def plot_bar(self, categories, values, title="", xlabel="", ylabel="", color=None):
        """Plot a bar chart."""
        self._update_theme()
        if color is None:
            color = self.colors['success']
            
        self.clear()
        ax = self.figure.add_subplot(111)
        bars = ax.bar(categories, values, color=color, alpha=0.8)
        ax.set_title(title, color=self.colors['text_primary'], fontsize=12, fontweight='bold')
        ax.set_xlabel(xlabel, color=self.colors['text_secondary'])
        ax.set_ylabel(ylabel, color=self.colors['text_secondary'])
        ax.grid(True, alpha=0.2, color=self.colors['border'], axis='y')
        ax.set_facecolor(self.colors['bg_secondary'])
        ax.tick_params(colors=self.colors['text_secondary'])
        self.figure.patch.set_facecolor(self.colors['bg_primary'])
        
        # Rotate x labels if too many
        if len(categories) > 5:
            ax.tick_params(axis='x', rotation=45)
        
        self.figure.tight_layout()
        self.canvas.draw()

    def plot_pie(self, labels, values, title=""):
        """Plot a pie chart."""
        self._update_theme()
        self.clear()
        ax = self.figure.add_subplot(111)
        
        # Use theme chart colors
        colors = [
            self.colors['chart_1'], self.colors['chart_2'], self.colors['chart_3'],
            self.colors['chart_4'], self.colors['chart_5'], self.colors['chart_6'],
            self.colors['chart_7'], self.colors['chart_8']
        ]
        
        wedges, texts, autotexts = ax.pie(
            values, labels=labels, autopct='%1.1f%%',
            colors=colors[:len(labels)], startangle=90,
            textprops={'color': self.colors['text_primary']}
        )
        
        for autotext in autotexts:
            autotext.set_color(self.colors['bg_primary'])
            autotext.set_fontweight('bold')
        
        ax.set_title(title, color=self.colors['text_primary'], fontsize=12, fontweight='bold')
        ax.set_facecolor(self.colors['bg_secondary'])
        self.figure.patch.set_facecolor(self.colors['bg_primary'])
        self.figure.tight_layout()
        self.canvas.draw()

    def plot_comparison(self, categories, values1, values2, label1="", label2="", 
                       title="", xlabel="", ylabel=""):
        """Plot a comparison bar chart."""
        self._update_theme()
        self.clear()
        ax = self.figure.add_subplot(111)
        
        import numpy as np
        x = np.arange(len(categories))
        width = 0.35
        
        bars1 = ax.bar(x - width/2, values1, width, label=label1, 
                      color=self.colors['primary'], alpha=0.8)
        bars2 = ax.bar(x + width/2, values2, width, label=label2, 
                      color=self.colors['danger'], alpha=0.8)
        
        ax.set_title(title, color=self.colors['text_primary'], fontsize=12, fontweight='bold')
        ax.set_xlabel(xlabel, color=self.colors['text_secondary'])
        ax.set_ylabel(ylabel, color=self.colors['text_secondary'])
        ax.set_xticks(x)
        ax.set_xticklabels(categories)
        ax.legend(facecolor=self.colors['bg_secondary'], 
                 edgecolor=self.colors['border'], 
                 labelcolor=self.colors['text_primary'])
        ax.grid(True, alpha=0.2, color=self.colors['border'], axis='y')
        ax.set_facecolor(self.colors['bg_secondary'])
        ax.tick_params(colors=self.colors['text_secondary'])
        self.figure.patch.set_facecolor(self.colors['bg_primary'])
        
        self.figure.tight_layout()
        self.canvas.draw()
