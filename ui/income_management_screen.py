"""
ui/income_management_screen.py — Income expectations, FD interest, and income composition analysis
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QFrame, QTableWidget, QTableWidgetItem, QHeaderView, QDialog, QFormLayout,
    QDateEdit, QDoubleSpinBox, QTextEdit, QMessageBox, QLineEdit, QSpinBox,
    QSizePolicy, QScrollArea
)
from PyQt6.QtCore import Qt, QDate, pyqtSignal
from PyQt6.QtGui import QFont, QColor

from datetime import date, datetime
from dateutil.relativedelta import relativedelta

from ui.widgets.chart_widget import ChartWidget
from ui.widgets.states import EmptyState
from ui.widgets.toast_utils import show_success, show_warning, show_info
from ui.theme import Theme
from ui.icons import set_btn_icon
from ui.date_utils import format_display_date
from core.session import session

from config import (
    get_current_financial_year, get_all_financial_years, fy_date_range,
    COMPOUNDING_TYPES, FD_TDS_FORM_NAME, FD_TDS_FORM_NAME_SENIOR
)
from models.person import get_all_persons
from models.bank_account import get_accounts_for_person, get_all_accounts
from models.income_expectation import (
    get_income_expectations, auto_link_income_expectations,
    add_income_expectation, update_income_expectation, delete_income_expectation
)
from models.transaction import get_transactions
from models.fixed_deposit import get_all_fds
from models.fd_interest_record import get_fd_interest_by_fy
from models.savings_interest import get_savings_interest_by_fy
from engines.interest_engine import (
    fd_interest_for_fy, fd_interest_accrued_to,
    calculate_savings_interest_for_fy, fd_tds_threshold_status
)


def _format_inr(value: float) -> str:
    """Format value in Indian Rupee with commas (e.g., 256642 -> 2,56,642)."""
    if value is None:
        return "—"

    # Format to 2 decimals
    formatted = f"{abs(value):,.2f}"

    # Replace commas with Indian-style grouping: 2,56,642.00
    parts = str(abs(value)).split('.')
    integer_part = parts[0]
    decimal_part = parts[1] if len(parts) > 1 else "00"

    # Indian grouping: split from right, first 3 digits, then 2-digit groups
    if len(integer_part) <= 3:
        indian_formatted = integer_part
    else:
        # Reverse, group by 2s except first group which is 3
        reversed_int = integer_part[::-1]
        groups = []
        groups.append(reversed_int[0:3][::-1])  # Last 3 digits
        for i in range(3, len(reversed_int), 2):
            groups.append(reversed_int[i:i+2][::-1])
        indian_formatted = ','.join(groups[::-1])

    sign = "-" if value < 0 else ""
    return f"{sign}₹{indian_formatted}.{decimal_part[:2].ljust(2, '0')}"


class IncomeManagementScreen(QWidget):
    """Income & Expectations analysis with charts and ledger."""

    def __init__(self, parent_window=None):
        super().__init__()
        self._parent_window = parent_window
        self._selected_fy = get_current_financial_year()
        self._selected_person_id = None
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        """Build main screen layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 18)
        layout.setSpacing(16)

        # Header with title, FY selector, and person selector
        layout.addLayout(self._build_header())

        # KPI tiles
        layout.addLayout(self._build_kpi_tiles())

        # Panels in a scrollable area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setObjectName("panelScroll")

        panel_container = QWidget()
        panel_layout = QVBoxLayout(panel_container)
        panel_layout.setSpacing(20)
        panel_layout.setContentsMargins(0, 0, 0, 0)

        # 5 panels
        panel_layout.addWidget(self._build_panel_1_vs_actual())
        panel_layout.addWidget(self._build_panel_2_composition())
        panel_layout.addWidget(self._build_panel_3_fd_runway())
        panel_layout.addWidget(self._build_panel_4_tds_gauges())
        panel_layout.addWidget(self._build_panel_5_ledger())

        panel_layout.addStretch()
        scroll.setWidget(panel_container)
        layout.addWidget(scroll, stretch=1)

    def _build_header(self) -> QHBoxLayout:
        """Build header with title, FY, and person selectors."""
        header = QHBoxLayout()
        header.setSpacing(16)

        # Title
        title = QLabel("Income & Expectations")
        title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        title.setProperty("textrole", "title-md")
        header.addWidget(title)

        header.addSpacing(20)

        # FY selector
        lbl_fy = QLabel("FY")
        lbl_fy.setProperty("textrole", "section-label")
        header.addWidget(lbl_fy)

        self.cmb_fy = QComboBox()
        self.cmb_fy.setMinimumWidth(90)
        for fy in reversed(get_all_financial_years(since_year=2020)):
            self.cmb_fy.addItem(fy)
        self.cmb_fy.setCurrentText(self._selected_fy)
        self.cmb_fy.currentTextChanged.connect(self._on_fy_changed)
        header.addWidget(self.cmb_fy)

        # Person selector (including HUF and "All")
        lbl_person = QLabel("Person")
        lbl_person.setProperty("textrole", "section-label")
        header.addWidget(lbl_person)

        self.cmb_person = QComboBox()
        self.cmb_person.setMinimumWidth(140)
        self.cmb_person.addItem("All Persons", userData=None)
        for p in get_all_persons():
            self.cmb_person.addItem(p["full_name"], userData=p["person_id"])
        self.cmb_person.currentIndexChanged.connect(self._on_person_changed)
        header.addWidget(self.cmb_person)

        header.addStretch()
        return header

    def _build_kpi_tiles(self) -> QHBoxLayout:
        """Build 4 KPI tiles: Expected, Received, Still Expected, Projected Tax."""
        kpi_layout = QHBoxLayout()
        kpi_layout.setSpacing(14)

        self.kpi_expected = self._create_kpi_tile("Expected Income", "₹ —", "kpiExpected")
        self.kpi_received = self._create_kpi_tile("Received to Date", "₹ —", "kpiReceived")
        self.kpi_pending = self._create_kpi_tile("Still Expected", "₹ —", "kpiPending")
        self.kpi_tax = self._create_kpi_tile("Projected Tax", "₹ —", "kpiTax")

        kpi_layout.addWidget(self.kpi_expected)
        kpi_layout.addWidget(self.kpi_received)
        kpi_layout.addWidget(self.kpi_pending)
        kpi_layout.addWidget(self.kpi_tax)

        return kpi_layout

    def _create_kpi_tile(self, title: str, value: str, object_name: str) -> QFrame:
        """Create a single KPI tile using QSS class."""
        tile = QFrame()
        tile.setObjectName(object_name)
        tile.setMinimumHeight(85)

        layout = QVBoxLayout(tile)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)

        lbl_title = QLabel(title)
        lbl_title.setProperty("textrole", "section-label")
        layout.addWidget(lbl_title)

        lbl_value = QLabel(value)
        lbl_value.setObjectName(f"{object_name}_value")
        layout.addWidget(lbl_value)

        layout.addStretch()
        return tile

    def _build_panel_1_vs_actual(self) -> QFrame:
        """Panel 1: Expected vs Actual by month (grouped bars)."""
        panel = QFrame()
        panel.setObjectName("analysisPanel")

        layout = QVBoxLayout(panel)
        layout.setSpacing(12)

        title = QLabel("Expected vs Actual by Month")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        layout.addWidget(title)

        self.chart_vs_actual = ChartWidget()
        self.chart_vs_actual.setMinimumHeight(280)
        layout.addWidget(self.chart_vs_actual)

        return panel

    def _build_panel_2_composition(self) -> QFrame:
        """Panel 2: Income composition (stacked bars by FY or donut for single FY)."""
        panel = QFrame()
        panel.setObjectName("analysisPanel")

        layout = QVBoxLayout(panel)
        layout.setSpacing(12)

        title = QLabel("Income Composition by Source")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        layout.addWidget(title)

        self.chart_composition = ChartWidget()
        self.chart_composition.setMinimumHeight(280)
        layout.addWidget(self.chart_composition)

        return panel

    def _build_panel_3_fd_runway(self) -> QFrame:
        """Panel 3: FD interest accrual by FY with current FY marked."""
        panel = QFrame()
        panel.setObjectName("analysisPanel")

        layout = QVBoxLayout(panel)
        layout.setSpacing(12)

        title = QLabel("FD Interest Runway (By Financial Year)")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        layout.addWidget(title)

        self.chart_fd_runway = ChartWidget()
        self.chart_fd_runway.setMinimumHeight(280)
        layout.addWidget(self.chart_fd_runway)

        return panel

    def _build_panel_4_tds_gauges(self) -> QFrame:
        """Panel 4: Per-bank TDS threshold gauges with 15G/15H badge."""
        panel = QFrame()
        panel.setObjectName("analysisPanel")

        layout = QVBoxLayout(panel)
        layout.setSpacing(12)

        title = QLabel("FD TDS Threshold Status by Bank")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        layout.addWidget(title)

        # Use a table for TDS status
        self.table_tds = QTableWidget()
        self.table_tds.setColumnCount(5)
        self.table_tds.setHorizontalHeaderLabels(["Bank", "Total Interest", "Status", "Crossing Quarter", "Form"])
        self.table_tds.setAccessibleName("FD TDS threshold status table")
        self.table_tds.setAccessibleDescription("Shows per-bank TDS threshold status and whether the threshold is exceeded.")
        self.table_tds.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_tds.setMaximumHeight(250)
        self.table_tds.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table_tds.verticalHeader().setVisible(False)
        layout.addWidget(self.table_tds)

        return panel

    def _build_panel_5_ledger(self) -> QFrame:
        """Panel 5: Expectation ledger with inline editing and auto-match."""
        panel = QFrame()
        panel.setObjectName("analysisPanel")

        layout = QVBoxLayout(panel)
        layout.setSpacing(12)

        # Title and button
        title_layout = QHBoxLayout()
        title = QLabel("Income Expectation Ledger")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title_layout.addWidget(title)
        title_layout.addStretch()

        btn_auto_match = Theme.btn("Auto-Match", "success", height=32, min_width=100)
        set_btn_icon(btn_auto_match, "auto_link")
        btn_auto_match.setAccessibleName("Auto-match income expectations")
        btn_auto_match.setAccessibleDescription("Automatically match income expectations with transactions in the ledger.")
        btn_auto_match.clicked.connect(self._on_auto_match_ledger)
        title_layout.addWidget(btn_auto_match)

        layout.addLayout(title_layout)

        # Ledger table
        self.table_ledger = QTableWidget()
        self.table_ledger.setColumnCount(8)
        self.table_ledger.setHorizontalHeaderLabels([
            "Month", "Type", "Source", "Expected", "Actual", "Variance", "Status", "Matched Txn"
        ])
        self.table_ledger.setAccessibleName("Income expectation ledger table")
        self.table_ledger.setAccessibleDescription("Shows income expectations with expected amounts, actual receipts, variance, and matching transaction status.")
        self.table_ledger.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_ledger.setMinimumHeight(300)
        self.table_ledger.verticalHeader().setVisible(False)
        layout.addWidget(self.table_ledger)

        return panel

    def refresh_theme(self):
        """Called after live theme switch."""
        # Refresh charts (KPI tiles use static QSS classes)
        for chart in [self.chart_vs_actual, self.chart_composition, self.chart_fd_runway]:
            chart.refresh_theme()

        self.refresh()

    def _on_fy_changed(self, fy):
        """Handle FY change."""
        self._selected_fy = fy
        self.refresh()

    def _on_person_changed(self):
        """Handle person change."""
        self._selected_person_id = self.cmb_person.currentData()
        self.refresh()

    def refresh(self):
        """Refresh all panels with current selections."""
        fy = self._selected_fy
        person_id = self._selected_person_id

        # Fetch data
        expectations = self._fetch_expectations(person_id, fy)

        if not expectations:
            self._show_empty_state()
            return

        # Update KPIs
        self._update_kpi_tiles(expectations, person_id, fy)

        # Update charts and tables
        self._populate_chart_1(expectations)
        self._populate_chart_2(person_id, fy)
        self._populate_chart_3(person_id, fy)
        self._populate_table_4_tds(person_id, fy)
        self._populate_table_5_ledger(expectations)

    def _show_empty_state(self):
        """Show empty state when no data."""
        # Clear all panels
        self.chart_vs_actual.show_empty_state("No income expectations for this selection")
        self.chart_composition.show_empty_state("Add income expectations to analyze composition")
        self.chart_fd_runway.show_empty_state("No FD interest data available")
        self.table_tds.setRowCount(0)
        self.table_ledger.setRowCount(0)

    def _fetch_expectations(self, person_id, fy):
        """Fetch income expectations for the selection."""
        try:
            return get_income_expectations(person_id=person_id, financial_year=fy)
        except Exception as e:
            show_warning(f"Error fetching expectations: {e}")
            return []

    def _update_kpi_tiles(self, expectations, person_id, fy):
        """Update KPI values based on expectations."""
        total_expected = sum(e["expected_amount"] for e in expectations)
        total_received = sum(e.get("actual_amount", 0) for e in expectations if e["actual_transaction_id"])
        total_pending = total_expected - total_received

        # Projected tax (rough estimate: assume 15% on FD interest over 50k)
        fd_interest_total = self._get_total_fd_interest(person_id, fy)
        projected_tax = max(0, (fd_interest_total - 50000) * 0.10) if fd_interest_total > 50000 else 0

        # Update tiles
        self.kpi_expected.findChild(QLabel, "kpiValue").setText(_format_inr(total_expected))
        self.kpi_received.findChild(QLabel, "kpiValue").setText(_format_inr(total_received))

        # Percentage for received
        pct = (total_received / total_expected * 100) if total_expected > 0 else 0
        self.kpi_pending.findChild(QLabel, "kpiValue").setText(_format_inr(total_pending))
        self.kpi_tax.findChild(QLabel, "kpiValue").setText(_format_inr(projected_tax))

    def _get_total_fd_interest(self, person_id, fy):
        """Get total FD interest for person in FY."""
        try:
            fds = get_all_fds()
            if person_id:
                fds = [fd for fd in fds if fd["person_id"] == person_id]

            total = 0.0
            for fd in fds:
                total += fd_interest_for_fy(fd, fy)
            return total
        except Exception:
            return 0.0

    def _populate_chart_1(self, expectations):
        """Chart 1: Expected vs Actual by month."""
        try:
            # Group by month
            months_data = {}
            fy_start, fy_end = fy_date_range(self._selected_fy)

            # Initialize all months
            current = fy_start
            while current <= fy_end:
                month_key = f"{current.strftime('%b')} {current.day}"
                months_data[month_key] = {"expected": 0, "actual": 0}
                current += relativedelta(months=1)

            # Populate with expectations
            for exp in expectations:
                try:
                    exp_date = datetime.strptime(exp["expected_date"], "%Y-%m-%d").date()
                except ValueError:
                    # For recurring frequencies stored as day number
                    continue

                month_key = f"{exp_date.strftime('%b')} {exp_date.day}"
                months_data[month_key]["expected"] += exp["expected_amount"]

                if exp["actual_transaction_id"]:
                    months_data[month_key]["actual"] += exp.get("actual_amount", 0)

            # Draw grouped bar chart
            if months_data:
                labels = list(months_data.keys())
                expected_vals = [months_data[k]["expected"] for k in labels]
                actual_vals = [months_data[k]["actual"] for k in labels]

                self.chart_vs_actual.plot_comparison(
                    categories=labels,
                    values1=expected_vals,
                    values2=actual_vals,
                    label1="Expected",
                    label2="Actual",
                    title="Expected vs Actual by Month"
                )
            else:
                self.chart_vs_actual.show_empty_state("No monthly data")
        except Exception as e:
            self.chart_vs_actual.show_empty_state(f"Error: {str(e)[:50]}")

    def _populate_chart_2(self, person_id, fy):
        """Chart 2: Income composition by source (donut chart)."""
        try:
            expectations = get_income_expectations(person_id=person_id, financial_year=fy)

            # Group by income type
            composition = {}
            for exp in expectations:
                income_type = exp["income_type"]
                composition[income_type] = composition.get(income_type, 0) + exp["expected_amount"]

            if composition:
                # Use pie/donut chart for single FY
                labels = list(composition.keys())
                values = list(composition.values())

                self.chart_composition.plot_pie(
                    labels=labels,
                    values=values,
                    title="Income Composition by Source"
                )
            else:
                self.chart_composition.show_empty_state("No income composition data")
        except Exception as e:
            self.chart_composition.show_empty_state(f"Error: {str(e)[:50]}")

    def _populate_chart_3(self, person_id, fy):
        """Chart 3: FD interest runway by FY."""
        try:
            fds = get_all_fds()
            if person_id:
                fds = [fd for fd in fds if fd["person_id"] == person_id]

            # Collect interest by FY
            fy_interest = {}
            current_fy = fy

            # Look at current FY and next 2 FYs
            for i in range(3):
                check_fy = self._add_fy_years(current_fy, i)
                total = sum(fd_interest_for_fy(fd, check_fy) for fd in fds)
                if total > 0:
                    fy_interest[check_fy] = total

            if fy_interest:
                labels = list(fy_interest.keys())
                values = list(fy_interest.values())

                self.chart_fd_runway.plot_bar(
                    title="FD Interest Runway",
                    labels=labels,
                    values=values,
                    color=Theme.PRIMARY
                )
            else:
                self.chart_fd_runway.show_empty_state("No FD interest data")
        except Exception as e:
            self.chart_fd_runway.show_empty_state(f"Error: {str(e)[:50]}")

    def _populate_table_4_tds(self, person_id, fy):
        """Table 4: Per-bank TDS threshold status."""
        try:
            if not person_id:
                self.table_tds.setRowCount(0)
                return

            status = fd_tds_threshold_status(person_id, fy)
            banks = status.get("banks", [])

            self.table_tds.setRowCount(len(banks))

            for row, bank in enumerate(banks):
                # Bank name
                self.table_tds.setItem(row, 0, QTableWidgetItem(bank["bank_name"]))

                # Total interest
                interest_item = QTableWidgetItem(_format_inr(bank["total_interest"]))
                interest_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table_tds.setItem(row, 1, interest_item)

                # Status (exceeds or OK)
                status_text = "⚠ Exceeds" if bank["exceeds"] else "✓ OK"
                status_item = QTableWidgetItem(status_text)
                color = Theme.DANGER if bank["exceeds"] else Theme.SUCCESS
                status_item.setForeground(QColor(color))
                self.table_tds.setItem(row, 2, status_item)

                # Crossing quarter
                crossing = bank.get("crossing_quarter", "—")
                self.table_tds.setItem(row, 3, QTableWidgetItem(str(crossing)))

                # Form badge
                form_text = bank["form_name"]
                if bank["form_on_file"]:
                    form_text += " ✓ On file"
                    form_item = QTableWidgetItem(form_text)
                    form_item.setForeground(QColor(Theme.SUCCESS))
                else:
                    form_item = QTableWidgetItem(form_text)
                    if bank["exceeds"]:
                        form_item.setForeground(QColor(Theme.DANGER))

                self.table_tds.setItem(row, 4, form_item)
        except Exception as e:
            show_warning(f"Error loading TDS status: {e}")

    def _populate_table_5_ledger(self, expectations):
        """Table 5: Expectation ledger."""
        try:
            self.table_ledger.setRowCount(len(expectations))

            for row, exp in enumerate(expectations):
                # Month
                try:
                    exp_date = datetime.strptime(exp["expected_date"], "%Y-%m-%d").date()
                    month_text = exp_date.strftime("%b %Y")
                except ValueError:
                    month_text = f"Day {exp['expected_date']}"

                self.table_ledger.setItem(row, 0, QTableWidgetItem(month_text))

                # Type
                self.table_ledger.setItem(row, 1, QTableWidgetItem(exp["income_type"]))

                # Source (account)
                source = f"{exp.get('bank_display_name', exp['bank_name'])} ({exp['account_type']})"
                self.table_ledger.setItem(row, 2, QTableWidgetItem(source))

                # Expected amount
                exp_item = QTableWidgetItem(_format_inr(exp["expected_amount"]))
                exp_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table_ledger.setItem(row, 3, exp_item)

                # Actual amount
                actual = exp.get("actual_amount", 0) if exp["actual_transaction_id"] else None
                actual_item = QTableWidgetItem(_format_inr(actual) if actual else "—")
                actual_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if actual:
                    actual_item.setForeground(QColor(Theme.SUCCESS))
                self.table_ledger.setItem(row, 4, actual_item)

                # Variance
                if actual:
                    variance = actual - exp["expected_amount"]
                    variance_item = QTableWidgetItem(_format_inr(variance))
                    variance_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    color = Theme.SUCCESS if variance >= 0 else Theme.DANGER
                    variance_item.setForeground(QColor(color))
                    self.table_ledger.setItem(row, 5, variance_item)
                else:
                    self.table_ledger.setItem(row, 5, QTableWidgetItem("—"))

                # Status
                if exp["actual_transaction_id"]:
                    status = "Received"
                    color = Theme.SUCCESS
                else:
                    exp_date_obj = datetime.strptime(exp["expected_date"], "%Y-%m-%d").date() if "-" in exp["expected_date"] else date.today()
                    if exp_date_obj < date.today():
                        status = "Overdue"
                        color = Theme.DANGER
                    else:
                        status = "Pending"
                        color = Theme.WARNING

                status_item = QTableWidgetItem(status)
                status_item.setForeground(QColor(color))
                self.table_ledger.setItem(row, 6, status_item)

                # Matched transaction
                matched_text = f"Txn #{exp['actual_transaction_id']}" if exp["actual_transaction_id"] else "—"
                self.table_ledger.setItem(row, 7, QTableWidgetItem(matched_text))
        except Exception as e:
            show_warning(f"Error populating ledger: {e}")

    def _on_auto_match_ledger(self):
        """Auto-match expectations with transactions."""
        person_id = self._selected_person_id
        if not person_id:
            show_warning("Please select a specific person to auto-match.")
            return

        fy = self._selected_fy
        accounts = get_accounts_for_person(person_id)

        total_matched = 0
        for account in accounts:
            matched = auto_link_income_expectations(person_id, account["account_id"], fy)
            total_matched += matched

        if total_matched > 0:
            show_success(f"Auto-matched {total_matched} expectation{'s' if total_matched != 1 else ''}.")
            self.refresh()
        else:
            show_info("No matching transactions found.")

    def _add_fy_years(self, fy_str, years):
        """Add years to a FY string like '2024-25'."""
        start_year = int(fy_str.split("-")[0])
        new_year = start_year + years
        return f"{new_year}-{str(new_year + 1)[2:]}"
