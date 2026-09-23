"""
ui/income_prediction_screen.py — Income prediction engine dashboard.

Displays:
1. Header with FY and as_of date
2. Headroom view: projected income vs 1,200,000 limit
3. TDS Risk view: table + bar chart of projected interest per bank
4. Timeline view: cumulative monthly projection line chart
5. Comparison: "Our Data - Prediction" vs "ITR-Side Actuals"
6. Advisory: warnings and disclaimers
7. Estimation marking: (Est.) labels and banner for estimated FDs
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QScrollArea
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor

from ui.theme import Theme
from ui.widgets.kpi_tile import KpiTile
from ui.widgets.chart_widget import ChartWidget
from ui.widgets.excel_table import ExcelTableWithStats
from ui.widgets.section import CollapsibleSection
from ui.widgets.money_label import format_inr, MoneyLabel
from ui.widgets.states import EmptyState
from ui.widgets.loader import Loader
from core.session import session


class IncomePredictionScreen(QWidget):
    """Income prediction dashboard showing FY income projection and compliance risks."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._prediction_data = {}
        self._build_ui()
        self.load_data()

    def _build_ui(self):
        """Build the screen layout with all sections."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(28, 22, 28, 18)
        main_layout.setSpacing(16)

        # Header: Title, FY, and as_of date
        main_layout.addWidget(self._build_header())

        # Create a scrollable area for content sections
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background: {Theme.BG}; }}")

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(16)

        # Headroom section
        content_layout.addWidget(self._build_headroom_section())

        # TDS Risk section
        content_layout.addWidget(self._build_tds_risk_section())

        # Timeline section
        content_layout.addWidget(self._build_timeline_section())

        # Comparison section
        content_layout.addWidget(self._build_comparison_section())

        # Strategies section
        content_layout.addWidget(self._build_strategy_section())

        # Advisory section
        content_layout.addWidget(self._build_advisory_section())

        content_layout.addStretch()

        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll, stretch=1)

    def _build_header(self) -> QWidget:
        """Build the header with title, FY, and as_of date."""
        header = QFrame()
        header.setStyleSheet(f"QFrame {{ background: {Theme.SURFACE}; border: none; border-radius: {Theme.RADIUS_CARD}px; }}")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        title = QLabel("Income Prediction")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title.setProperty("textrole", "title-lg")
        layout.addWidget(title)

        layout.addStretch()

        # FY and as_of date (right-aligned)
        fy_text = self._prediction_data.get("financial_year", "—")
        as_of_text = self._prediction_data.get("as_of", "—")
        if as_of_text != "—" and len(as_of_text) >= 10:
            # Extract just the date part (YYYY-MM-DD)
            as_of_text = as_of_text[:10]

        info_label = QLabel(f"FY {fy_text}  ·  As of {as_of_text}")
        info_label.setFont(QFont("Segoe UI", 11))
        info_label.setProperty("textrole", "secondary")
        layout.addWidget(info_label)

        return header

    def _build_headroom_section(self) -> QWidget:
        """Build the headroom view: projected income vs limit."""
        section = CollapsibleSection("Income Headroom", expanded=True, accent="income_prediction")

        layout = section.content_layout()
        layout.setSpacing(12)

        # Get data
        fy_info = self._prediction_data.get("fy_income", {})
        projected_total = fy_info.get("projected_total", 0)
        limit = fy_info.get("limit", 1_200_000)
        headroom = fy_info.get("headroom", 0)
        is_over_limit = fy_info.get("is_over_limit", False)
        is_estimated = fy_info.get("is_estimated", False)

        # KPI tiles
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(12)

        est_marker = " (Est.)" if is_estimated else ""
        verdict_text = "Over Limit" if is_over_limit else "Safe"
        verdict_color = Theme.DANGER_TEXT if is_over_limit else Theme.SUCCESS_TEXT

        kpi1 = KpiTile(
            label=f"Projected Total{est_marker}",
            value=projected_total,
            is_currency=True,
            accent="primary",
            icon="income_prediction"
        )
        kpi1.setAccessibleName("Projected Income Total")
        kpi_row.addWidget(kpi1)

        kpi2 = KpiTile(
            label="Annual Limit",
            value=limit,
            is_currency=True,
            accent="warning",
            icon="lock"
        )
        kpi2.setAccessibleName("Annual Income Limit")
        kpi_row.addWidget(kpi2)

        kpi3 = KpiTile(
            label="Headroom",
            value=headroom,
            is_currency=True,
            accent="success",
            icon="trend"
        )
        kpi3.setAccessibleName("Income Headroom")
        kpi_row.addWidget(kpi3)

        layout.addLayout(kpi_row)

        # Verdict badge
        verdict_label = QLabel(verdict_text)
        verdict_label.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        verdict_label.setStyleSheet(f"color: {verdict_color}; padding: 8px 12px;")
        layout.addWidget(verdict_label)

        return section

    def _build_tds_risk_section(self) -> QWidget:
        """Build TDS Risk view: table + bar chart."""
        section = CollapsibleSection("TDS Risk Analysis", expanded=True, accent="income_prediction")

        layout = section.content_layout()
        layout.setSpacing(12)

        by_bank = self._prediction_data.get("tds_risk", {}).get("by_bank", [])

        if not by_bank:
            empty = EmptyState(
                icon_name="no_data",
                headline="No TDS data",
                explanation="No FD or savings accounts to analyze.",
                action_text="Add Accounts",
                accent="income_prediction"
            )
            Theme.style_button(empty.btn_action, "secondary")
            layout.addWidget(empty)
            return section

        # Table
        self.tds_table = QTableWidget()
        self.tds_table.setAccessibleName("TDS Risk Table")
        self.tds_table.setColumnCount(5)
        self.tds_table.setHorizontalHeaderLabels(["Bank", "Projected Interest", "TDS Threshold", "Status", "Over Threshold"])
        self.tds_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tds_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tds_table.setAlternatingRowColors(True)

        for bank_data in by_bank:
            row = self.tds_table.rowCount()
            self.tds_table.insertRow(row)

            bank_name = bank_data.get("bank_name", "—")
            proj_interest = bank_data.get("projected_interest", 0)
            threshold = bank_data.get("threshold", 0)
            will_cross = bank_data.get("will_cross", False)
            amount_over = bank_data.get("amount_over", 0)
            is_estimated = bank_data.get("is_estimated", False)

            est_marker = " (Est.)" if is_estimated else ""

            # Bank name
            item_bank = QTableWidgetItem(bank_name)
            self.tds_table.setItem(row, 0, item_bank)

            # Projected interest
            item_proj = QTableWidgetItem(format_inr(proj_interest) + est_marker)
            self.tds_table.setItem(row, 1, item_proj)

            # Threshold
            item_threshold = QTableWidgetItem(format_inr(threshold))
            self.tds_table.setItem(row, 2, item_threshold)

            # Status (approaching if within 10%, crossing if over)
            pct_of_threshold = (proj_interest / threshold * 100) if threshold > 0 else 0
            if will_cross:
                status = "❌ Will Cross"
                status_color = Theme.DANGER_TEXT
            elif pct_of_threshold >= 90:
                status = "⚠ Approaching"
                status_color = Theme.WARNING_TEXT
            else:
                status = "✓ Safe"
                status_color = Theme.SUCCESS_TEXT

            item_status = QTableWidgetItem(status)
            item_status.setForeground(QColor(status_color))
            self.tds_table.setItem(row, 3, item_status)

            # Amount over
            over_text = format_inr(amount_over) if will_cross else "—"
            item_over = QTableWidgetItem(over_text)
            self.tds_table.setItem(row, 4, item_over)

            self.tds_table.setRowHeight(row, 32)

        layout.addWidget(self.tds_table)

        # Chart
        self.tds_chart = ChartWidget()
        self.tds_chart.setAccessibleName("TDS Risk Chart")
        self.tds_chart.setMinimumHeight(250)

        bank_names = [b.get("bank_name", "—") for b in by_bank]
        proj_values = [b.get("projected_interest", 0) for b in by_bank]
        self.tds_chart.plot_bar(
            categories=bank_names,
            values=proj_values,
            title="Projected Interest per Bank",
            ylabel="Interest Amount (₹)"
        )
        layout.addWidget(self.tds_chart)

        return section

    def _build_timeline_section(self) -> QWidget:
        """Build Timeline view: line chart + table of monthly projections."""
        section = CollapsibleSection("Monthly Timeline", expanded=True, accent="income_prediction")

        layout = section.content_layout()
        layout.setSpacing(12)

        timeline = self._prediction_data.get("timeline", {})
        months = timeline.get("months", [])

        if not months:
            empty = EmptyState(
                icon_name="no_data",
                headline="No timeline data",
                explanation="Monthly projection data unavailable.",
                action_text="Retry",
                accent="income_prediction"
            )
            Theme.style_button(empty.btn_action, "secondary")
            layout.addWidget(empty)
            return section

        # Line chart
        self.timeline_chart = ChartWidget()
        self.timeline_chart.setAccessibleName("Monthly Timeline Chart")
        self.timeline_chart.setMinimumHeight(280)

        month_names = [m.get("month_name", "—") for m in months]
        cumulative_values = [m.get("cumulative_projected", 0) for m in months]

        self.timeline_chart.plot_line(
            x_data=month_names,
            y_data=cumulative_values,
            title="Cumulative Projected Income",
            xlabel="Month",
            ylabel="Cumulative Amount (₹)"
        )
        layout.addWidget(self.timeline_chart)

        # Month table (compact)
        self.timeline_table = QTableWidget()
        self.timeline_table.setAccessibleName("Monthly Timeline Table")
        self.timeline_table.setColumnCount(3)
        self.timeline_table.setHorizontalHeaderLabels(["Month", "Monthly Projected", "Cumulative"])
        self.timeline_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.timeline_table.setMaximumHeight(200)
        self.timeline_table.setAlternatingRowColors(True)

        for month_data in months:
            row = self.timeline_table.rowCount()
            self.timeline_table.insertRow(row)

            month_name = month_data.get("month_name", "—")
            monthly_proj = month_data.get("monthly_projected", 0)
            cumulative_proj = month_data.get("cumulative_projected", 0)
            is_estimated = month_data.get("is_estimated", False)

            est_marker = " (Est.)" if is_estimated else ""

            item_month = QTableWidgetItem(month_name)
            self.timeline_table.setItem(row, 0, item_month)

            item_monthly = QTableWidgetItem(format_inr(monthly_proj) + est_marker)
            self.timeline_table.setItem(row, 1, item_monthly)

            item_cumulative = QTableWidgetItem(format_inr(cumulative_proj))
            self.timeline_table.setItem(row, 2, item_cumulative)

            self.timeline_table.setRowHeight(row, 28)

        layout.addWidget(self.timeline_table)

        return section

    def _build_comparison_section(self) -> QWidget:
        """Build Comparison: Our Data vs ITR-Side (26AS/AIS/TIS)."""
        section = CollapsibleSection("Income Comparison", expanded=False, accent="income_prediction")

        layout = section.content_layout()
        layout.setSpacing(12)

        # Two-column layout: our data and ITR actuals cards
        comp_row = QHBoxLayout()
        comp_row.setSpacing(12)

        # Left card: Our Data - Prediction
        our_data_card = self._build_our_data_card()
        comp_row.addWidget(our_data_card)

        # Right card: ITR-Side Actuals
        itr_card = self._build_itr_actuals_card()
        comp_row.addWidget(itr_card)

        layout.addLayout(comp_row)

        # Comparison table: item-by-item comparison
        comparison = self._prediction_data.get("comparison", {})
        rows = comparison.get("rows", [])

        if rows:
            self.comparison_table = QTableWidget()
            self.comparison_table.setAccessibleName("Income Comparison Table")
            self.comparison_table.setColumnCount(4)
            self.comparison_table.setHorizontalHeaderLabels(["Item", "Our Data", "ITR-Side", "Coverage"])
            self.comparison_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            self.comparison_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            self.comparison_table.setAlternatingRowColors(True)

            for row_data in rows:
                row = self.comparison_table.rowCount()
                self.comparison_table.insertRow(row)

                label = row_data.get("label", "—")
                our_value = row_data.get("our_value", 0)
                itr_value = row_data.get("itr_value", 0)
                our_under_reports = row_data.get("our_under_reports", False)

                # Item label
                item_label = QTableWidgetItem(label)
                self.comparison_table.setItem(row, 0, item_label)

                # Our Data value
                item_our = QTableWidgetItem(format_inr(our_value))
                self.comparison_table.setItem(row, 1, item_our)

                # ITR-Side value
                item_itr = QTableWidgetItem(format_inr(itr_value))
                self.comparison_table.setItem(row, 2, item_itr)

                # Coverage text (Our data under-reports vs covers this figure)
                if our_under_reports:
                    coverage_text = "Our data under-reports this figure"
                    coverage_color = Theme.INFO_TEXT
                else:
                    coverage_text = "Our data covers this figure"
                    coverage_color = Theme.INFO_TEXT

                item_coverage = QTableWidgetItem(coverage_text)
                item_coverage.setForeground(QColor(coverage_color))
                self.comparison_table.setItem(row, 3, item_coverage)

                self.comparison_table.setRowHeight(row, 32)

            layout.addWidget(self.comparison_table)

        return section

    def _build_our_data_card(self) -> QFrame:
        """Build 'Our Data - Prediction' card."""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {Theme.SURFACE};
                border: 1px solid {Theme.BORDER};
                border-radius: {Theme.RADIUS_CARD}px;
            }}
        """)
        card.setGraphicsEffect(Theme.shadow_card())

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # Title
        title = QLabel("Our Data - Prediction")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title.setProperty("textrole", "emphasis-md")
        layout.addWidget(title)

        # Content
        realised = self._prediction_data.get("realised_income", {})
        projected_fd = self._prediction_data.get("projected_fd_interest", {})
        projected_savings = self._prediction_data.get("projected_savings_interest", {})
        expected = self._prediction_data.get("expected_income", {})

        taxable_realised = realised.get("taxable", 0)
        fd_total = projected_fd.get("total", 0)
        fd_estimated = projected_fd.get("estimated_fd_count", 0)
        fd_known = projected_fd.get("known_fd_count", 0)
        savings_total = projected_savings.get("total", 0)
        expected_total = expected.get("total", 0)

        # Build table of components
        rows = [
            ("Realised Income (Taxable)", taxable_realised),
            ("Projected FD Interest", fd_total),
            ("Savings Interest (rest of FY, est.)", savings_total),
            ("Expected Income", expected_total),
        ]

        for label, value in rows:
            row_layout = QHBoxLayout()
            row_layout.setSpacing(8)

            lbl = QLabel(label)
            lbl.setFont(QFont("Segoe UI", 11))
            lbl.setProperty("textrole", "secondary")
            row_layout.addWidget(lbl)

            row_layout.addStretch()

            val_lbl = MoneyLabel(value)
            row_layout.addWidget(val_lbl)

            layout.addLayout(row_layout)

        # Footnote
        if fd_estimated > 0:
            note = QLabel(f"Note: {fd_estimated} FD(s) use estimated 7.5% rate; {fd_known} known rate(s).")
            note.setFont(QFont("Segoe UI", 9))
            note.setProperty("textrole", "muted-sm")
            layout.addWidget(note)

        layout.addStretch()

        return card

    def _build_itr_actuals_card(self) -> QFrame:
        """Build 'ITR-Side Actuals' card from 26AS/AIS/TIS imports."""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {Theme.SURFACE};
                border: 1px solid {Theme.BORDER};
                border-radius: {Theme.RADIUS_CARD}px;
            }}
        """)
        card.setGraphicsEffect(Theme.shadow_card())

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # Read ITR actuals from prediction data
        itr = self._prediction_data.get("itr_actuals", {})

        # If no data, show empty state
        if not itr.get("has_data"):
            empty = EmptyState(
                icon_name="import_pdf",
                headline="Tax documents not imported",
                explanation="Import your 26AS, AIS or TIS from the Tax Documents screen to compare.",
                action_text="Open Tax Documents",
                accent="income_prediction"
            )
            Theme.style_button(empty.btn_action, "secondary")
            layout.addWidget(empty)
            return card

        # Title: prefer AIS, fallback to TIS
        ais_data = itr.get("ais")
        tis_data = itr.get("tis")
        if ais_data:
            title_text = "ITR-Side Actuals (26AS / AIS)"
        else:
            title_text = "ITR-Side Actuals (26AS / TIS)"

        title = QLabel(title_text)
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title.setProperty("textrole", "emphasis-md")
        layout.addWidget(title)

        # Select which source to use for interest/dividend/TDS
        source = ais_data if ais_data else tis_data
        prefix = "AIS" if ais_data else "TIS"

        # Data rows to display
        form26as = itr.get("form26as")
        rows = []

        if form26as:
            rows.append(("26AS TDS Deducted", form26as.get("total_tds", 0)))

        if source:
            rows.append((f"{prefix} FD Interest", source.get("fd_interest", 0)))
            rows.append((f"{prefix} Savings Interest", source.get("savings_interest", 0)))
            rows.append((f"{prefix} Total Interest", source.get("total_interest", 0)))
            rows.append((f"{prefix} Dividend", source.get("dividend_income", 0)))
            rows.append((f"{prefix} TDS", source.get("tds_deducted", 0)))

        # Build table of components using QHBoxLayout + addStretch() pattern
        for label, value in rows:
            row_layout = QHBoxLayout()
            row_layout.setSpacing(8)

            lbl = QLabel(label)
            lbl.setFont(QFont("Segoe UI", 11))
            lbl.setProperty("textrole", "secondary")
            row_layout.addWidget(lbl)

            row_layout.addStretch()

            val_lbl = MoneyLabel(value)
            row_layout.addWidget(val_lbl)

            layout.addLayout(row_layout)

        layout.addStretch()

        return card

    def _build_strategy_section(self) -> QWidget:
        """Concrete actions for staying under the limit and keeping TDS off."""
        section = CollapsibleSection("Strategies", expanded=True, accent="income_prediction")

        layout = section.content_layout()
        layout.setSpacing(12)

        # Get strategies and context from advisory data
        advisory = self._prediction_data.get("advisory", {})
        strategies = advisory.get("strategies", [])
        context = advisory.get("context", {})

        # Show empty state if no strategies
        if not strategies:
            empty = EmptyState(
                icon_name="no_data",
                headline="No actions needed",
                explanation="Projected income is within the limit and no bank is near the threshold.",
                action_text="Refresh",
                accent="income_prediction"
            )
            Theme.style_button(empty.btn_action, "secondary")
            layout.addWidget(empty)
            return section

        # Context line: Limit · Headroom · TDS threshold · Form name
        if context:
            context_text = f"Limit {format_inr(context.get('limit', 0))} · Headroom {format_inr(context.get('headroom', 0))} · TDS threshold {format_inr(context.get('tds_threshold', 0))} · {context.get('form_name', '—')}"
            context_lbl = QLabel(context_text)
            context_lbl.setFont(QFont("Segoe UI", 11))
            context_lbl.setProperty("textrole", "muted-sm")
            layout.addWidget(context_lbl)

        # Build one card per strategy
        for strategy in strategies:
            card = QFrame()
            card.setStyleSheet(f"""
                QFrame {{
                    background: {Theme.SURFACE};
                    border: 1px solid {Theme.BORDER};
                    border-radius: {Theme.RADIUS_CARD}px;
                }}
            """)
            card.setGraphicsEffect(Theme.shadow_card())

            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(16, 12, 16, 12)
            card_layout.setSpacing(8)

            # Priority pill + title row
            header_layout = QHBoxLayout()
            header_layout.setSpacing(8)

            # Priority pill
            priority = strategy.get("priority", 0)
            if priority == 1:
                priority_text = "Act first"
                priority_color = Theme.WARNING_TEXT
            elif priority in (2, 3):
                priority_text = "Plan"
                priority_color = Theme.INFO_TEXT
            else:
                priority_text = "Consider"
                priority_color = Theme.TEXT_MUTED

            priority_lbl = QLabel(priority_text)
            priority_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            priority_lbl.setStyleSheet(f"color: {priority_color};")
            header_layout.addWidget(priority_lbl)

            # Title
            title_lbl = QLabel(strategy.get("title", "—"))
            title_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
            title_lbl.setProperty("textrole", "emphasis-md")
            header_layout.addWidget(title_lbl)

            header_layout.addStretch()

            card_layout.addLayout(header_layout)

            # Action text
            action_text = strategy.get("action", "")
            if action_text:
                action_lbl = QLabel(action_text)
                action_lbl.setFont(QFont("Segoe UI", 11))
                action_lbl.setProperty("textrole", "secondary")
                action_lbl.setWordWrap(True)
                card_layout.addWidget(action_lbl)

            # Amount row (if amount > 0)
            amount = strategy.get("amount", 0)
            if amount > 0:
                amount_layout = QHBoxLayout()
                amount_layout.setSpacing(8)

                # Label for amount with (Est.) marker
                is_estimated = strategy.get("is_estimated", False)
                amount_label_text = "Amount"
                if is_estimated:
                    amount_label_text += " (Est.)"

                amount_lbl = QLabel(amount_label_text)
                amount_lbl.setFont(QFont("Segoe UI", 11))
                amount_lbl.setProperty("textrole", "secondary")
                amount_layout.addWidget(amount_lbl)

                amount_layout.addStretch()

                amount_value = MoneyLabel(amount)
                amount_layout.addWidget(amount_value)

                card_layout.addLayout(amount_layout)

            layout.addWidget(card)

        return section

    def _build_advisory_section(self) -> QWidget:
        """Build Advisory: warnings + disclaimer."""
        section = CollapsibleSection("Advisories", expanded=True, accent="income_prediction")

        layout = section.content_layout()
        layout.setSpacing(8)

        advisory = self._prediction_data.get("advisory", {})
        warnings = advisory.get("warnings", [])

        if warnings:
            for warning in warnings:
                severity = warning.get("severity", "info")
                title = warning.get("title", "—")
                detail = warning.get("detail", "")

                # Color by severity
                if severity == "error":
                    color = Theme.DANGER_TEXT
                    icon = "❌"
                elif severity == "warning":
                    color = Theme.WARNING_TEXT
                    icon = "⚠"
                else:
                    color = Theme.INFO_TEXT
                    icon = "ℹ"

                # Build warning row
                row_layout = QHBoxLayout()
                row_layout.setSpacing(8)

                icon_lbl = QLabel(icon)
                icon_lbl.setFont(QFont("Segoe UI", 12))
                row_layout.addWidget(icon_lbl)

                text_layout = QVBoxLayout()
                text_layout.setSpacing(2)

                title_lbl = QLabel(title)
                title_lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
                title_lbl.setStyleSheet(f"color: {color};")
                text_layout.addWidget(title_lbl)

                if detail:
                    detail_lbl = QLabel(detail)
                    detail_lbl.setFont(QFont("Segoe UI", 10))
                    detail_lbl.setProperty("textrole", "secondary")
                    detail_lbl.setWordWrap(True)
                    text_layout.addWidget(detail_lbl)

                row_layout.addLayout(text_layout)
                row_layout.addStretch()

                layout.addLayout(row_layout)
        else:
            no_warnings = QLabel("No advisories at this time.")
            no_warnings.setFont(QFont("Segoe UI", 11))
            no_warnings.setProperty("textrole", "muted-sm")
            layout.addWidget(no_warnings)

        # Disclaimer
        disclaimer = advisory.get("disclaimer", "")
        if disclaimer:
            divider = QFrame()
            divider.setFrameShape(QFrame.Shape.HLine)
            divider.setStyleSheet(f"color: {Theme.BORDER};")
            layout.addWidget(divider)

            disc_lbl = QLabel(disclaimer)
            disc_lbl.setFont(QFont("Segoe UI", 10))
            disc_lbl.setProperty("textrole", "muted-sm")
            disc_lbl.setWordWrap(True)
            layout.addWidget(disc_lbl)

        return section

    def load_data(self):
        """Load prediction data from the engine."""
        person_id = session.selected_person_id
        if not person_id:
            # "All persons" is the default. Fall back to the sole person when
            # there is exactly one, so the screen is useful without a filter.
            try:
                from models.person import get_all_persons
                people = get_all_persons() or []
                if len(people) == 1:
                    person_id = people[0]["person_id"]
            except Exception:
                person_id = None
        if not person_id:
            return

        def _load():
            from engines.prediction_engine import get_prediction_summary
            try:
                return get_prediction_summary(person_id, financial_year=None, as_of=None)
            except Exception as e:
                print(f"Error loading prediction: {e}")
                return {}

        def _on_done(result):
            if result:
                self._prediction_data = result
                self._refresh_all_sections()

        def _on_error(err):
            print(f"Prediction loading failed: {err}")

        Loader.run(self, fn=_load, message="Loading prediction…", on_done=_on_done, on_error=_on_error)

    def _refresh_all_sections(self):
        """Rebuild every section against freshly loaded data.

        Sections read self._prediction_data at build time, so once the async
        load returns the layout has to be rebuilt - otherwise the screen keeps
        showing the empty state it was constructed with.
        """
        old = self.layout()
        if old is not None:
            while old.count():
                item = old.takeAt(0)
                w = item.widget()
                if w is not None:
                    w.setParent(None)
                    w.deleteLater()
            # A QWidget can only have one layout; detach the spent one.
            QWidget().setLayout(old)
        self._build_ui()

    def refresh_theme(self):
        """Called after a live theme switch — refresh all chart and table widgets."""
        # Refresh each chart widget with guard against missing attributes
        if getattr(self, 'tds_chart', None):
            self.tds_chart.refresh_theme()
        if getattr(self, 'timeline_chart', None):
            self.timeline_chart.refresh_theme()
