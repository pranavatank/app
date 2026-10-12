"""
ui/dialogs/fd_planner_dialog.py — Compare current FD rates and split savings
across banks so each stays within the DICGC insurance limit.
"""

from datetime import date
from urllib.parse import urlparse

from dateutil.relativedelta import relativedelta
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QComboBox, QLineEdit,
    QSpinBox, QCheckBox, QTableWidget, QTableWidgetItem, QHeaderView, QInputDialog, QFrame,
    QScrollArea, QWidget, QTabWidget, QApplication
)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QFont, QDoubleValidator, QDesktopServices, QColor

from ui.theme import Theme
from ui.widgets.kpi_tile import KpiTile
from ui.widgets.loader import Loader
from ui.widgets.money_label import format_inr
from ui.widgets.toast_utils import show_success, show_warning
from ui.date_utils import format_display_date
from core.session import session
from core.settings import get_setting, set_setting
from config import (
    DICGC_INSURANCE_LIMIT, FD_TDS_FORM_NAME, FD_TDS_FORM_NAME_SENIOR, get_current_financial_year
)
from models.person import get_all_persons
from engines.interest_engine import _is_senior_citizen_in_fy
from engines.fd_rate_source import (
    load_cached_rates, fetch_rates, get_rates_source_url, set_rates_source_url, is_stale
)
from engines.fd_allocation_engine import TENURE_LABELS, get_existing_exposure, get_savings_total, suggest_household_allocation
from engines.investment_options import best_overflow_option
from ui.dialogs.fd_coverage_tab import CoverageTab
from ui.dialogs.investment_options_tab import InvestmentOptionsTab

_EXCLUDED_BANKS_SETTING = "fd_planner_excluded_banks"
_ALL_PERSONS = -1


def _fmt_rate(value: float | None) -> str:
    return "—" if value is None else f"{value:.2f}"


def _right_aligned_item(text: str) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    return item


class _NumericItem(QTableWidgetItem):
    def __init__(self, value: float | None):
        super().__init__(_fmt_rate(value))
        self.sort_value = -1.0 if value is None else float(value)
        self.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    def __lt__(self, other):
        if isinstance(other, _NumericItem):
            return self.sort_value < other.sort_value
        return super().__lt__(other)


def _row_note(row: dict, form_name: str) -> str:
    parts = []
    if not row["fully_insured"]:
        parts.append("Above insured limit")
    if row["tds_risk"]:
        parts.append(f"TDS likely — submit {form_name} if eligible")
    return "; ".join(parts)


def _is_senior(person_id) -> bool:
    if not person_id:
        return False
    try:
        return _is_senior_citizen_in_fy(person_id, get_current_financial_year())
    except Exception:
        return False


class FDPlannerDialog(QDialog):
    RATE_COLUMNS = ["Use", "Bank", "Type", "Highest %", "1 Year %", "3 Years %", "5 Years %", "Senior +%"]
    RESULT_COLUMNS = [
        "Person", "Bank", "Rate %", "Invest", "Interest", "Maturity Value", "Matures On",
        "Already at Bank", "Insured After", "Note",
    ]

    def __init__(self, parent=None, person_id: int | None = None):
        super().__init__(parent)
        self._person_id = person_id or session.selected_person_id
        self._snapshot = load_cached_rates()
        self._last_result = None
        self._persons = get_all_persons()
        self.setWindowTitle("FD Planner")
        self.setModal(True)
        self.setMinimumSize(1100, 640)
        self.resize(1240, 860)
        self._build_ui()
        self._populate_rates()
        self._on_person_changed()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(14)

        title = QLabel("FD Planner")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        subtitle = QLabel(
            "Compare current FD rates and split your savings across banks so each bank stays within the DICGC insurance limit."
        )
        subtitle.setProperty("textrole", "muted-sm")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 8, 0)
        body_layout.setSpacing(14)

        self._build_rates_section(body_layout)

        plan_label = QLabel("Plan your split")
        plan_label.setProperty("textrole", "title-sm")
        body_layout.addWidget(plan_label)
        self._build_inputs(body_layout)

        kpi_row = QHBoxLayout()
        self.kpi_invested = KpiTile(label="Invested", value=0, is_currency=True, accent="primary")
        self.kpi_rate = KpiTile(label="Weighted Rate", value="—", is_currency=False)
        self.kpi_interest = KpiTile(label="Total Interest", value=0, is_currency=True)
        self.kpi_extra = KpiTile(label="Extra vs Average Rate", value=0, is_currency=True)
        for tile in (self.kpi_invested, self.kpi_rate, self.kpi_interest, self.kpi_extra):
            kpi_row.addWidget(tile)
        body_layout.addLayout(kpi_row)

        self.warning_banner = QFrame()
        self.warning_banner.setStyleSheet(Theme.banner_style("warning"))
        banner_layout = QHBoxLayout(self.warning_banner)
        banner_layout.setContentsMargins(14, 10, 14, 10)
        self.warning_lbl = QLabel()
        self.warning_lbl.setWordWrap(True)
        banner_layout.addWidget(self.warning_lbl)
        self.warning_banner.setVisible(False)
        body_layout.addWidget(self.warning_banner)

        self._build_results_table(body_layout)

        scroll.setWidget(body)
        self.tabs = QTabWidget()
        self.tabs.addTab(scroll, "Split Savings")
        self.coverage_tab = CoverageTab()
        self.tabs.addTab(self.coverage_tab, "My Coverage")
        self.options_tab = InvestmentOptionsTab()
        self.tabs.addTab(self.options_tab, "Other Safe Options")
        self.tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self.tabs, stretch=1)
        self._build_footer(layout)

    def _build_rates_section(self, layout: QVBoxLayout) -> None:
        header = QHBoxLayout()

        self.rates_info_lbl = QLabel()
        self.rates_info_lbl.setProperty("textrole", "muted-sm")
        self.rates_info_lbl.setWordWrap(True)
        header.addWidget(self.rates_info_lbl, stretch=1)

        btn_refresh = Theme.btn("Refresh Rates", "secondary", height=Theme.HEIGHT_MD, min_width=130)
        btn_refresh.setAccessibleName("Refresh FD rates")
        btn_refresh.clicked.connect(self._on_refresh_rates)
        header.addWidget(btn_refresh)

        btn_open = Theme.btn("Open Source", "secondary", height=Theme.HEIGHT_MD, min_width=120)
        btn_open.setAccessibleName("Open FD rates source page")
        btn_open.clicked.connect(self._on_open_source)
        header.addWidget(btn_open)

        btn_change = Theme.btn("Change Source…", "secondary", height=Theme.HEIGHT_MD, min_width=140)
        btn_change.setAccessibleName("Change FD rates source")
        btn_change.clicked.connect(self._on_change_source)
        header.addWidget(btn_change)
        layout.addLayout(header)

        self.rates_table = QTableWidget(0, len(self.RATE_COLUMNS))
        self.rates_table.setHorizontalHeaderLabels(self.RATE_COLUMNS)
        self.rates_table.verticalHeader().setVisible(False)
        self.rates_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.rates_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._size_columns(self.rates_table, stretch_columns={1})
        self.rates_table.setFixedHeight(260)
        self.rates_table.setAccessibleName("Current FD rates")
        self.rates_table.itemChanged.connect(self._on_rate_item_changed)
        layout.addWidget(self.rates_table)

    def _build_inputs(self, layout: QVBoxLayout) -> None:
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)
        for column in (1, 3, 5):
            grid.setColumnStretch(column, 1)

        self.person_combo = QComboBox()
        if len(self._persons) > 1:
            self.person_combo.addItem("All family members", _ALL_PERSONS)
        for person in self._persons:
            self.person_combo.addItem(person["full_name"], person["person_id"])
        index = self.person_combo.findData(self._person_id)
        self.person_combo.setCurrentIndex(max(index, 0))
        self.person_combo.currentIndexChanged.connect(self._on_person_changed)

        self.amount_edit = QLineEdit()
        self.amount_edit.setValidator(QDoubleValidator(0.0, 1e11, 2, self.amount_edit))
        self.amount_edit.setPlaceholderText("e.g. 1500000")
        self.amount_edit.setAccessibleName("Amount to invest")
        self.amount_edit.setMinimumWidth(140)

        self.btn_use_savings = Theme.btn("Use My Savings", "secondary", height=Theme.HEIGHT_MD, min_width=140)
        self.btn_use_savings.setAccessibleName("Fill amount from savings balance")
        self.btn_use_savings.setToolTip("Fill in your savings balance minus the amount you keep aside")
        self.btn_use_savings.clicked.connect(self._on_use_savings)
        amount_row = QHBoxLayout()
        amount_row.setSpacing(8)
        amount_row.addWidget(self.amount_edit, stretch=1)
        amount_row.addWidget(self.btn_use_savings)

        self.tenure_combo = QComboBox()
        for key, label in TENURE_LABELS.items():
            self.tenure_combo.addItem(label, key)

        self.keep_aside_spin = QSpinBox()
        self.keep_aside_spin.setRange(0, 10000000)
        self.keep_aside_spin.setSingleStep(25000)
        self.keep_aside_spin.setValue(100000)
        self.keep_aside_spin.setPrefix("₹ ")
        self.keep_aside_spin.setToolTip("Emergency money to leave in savings instead of FDs")
        self.keep_aside_spin.setAccessibleName("Amount to keep aside")

        self.max_banks_spin = QSpinBox()
        self.max_banks_spin.setRange(1, 25)
        self.max_banks_spin.setValue(5)

        self.min_per_bank_spin = QSpinBox()
        self.min_per_bank_spin.setRange(1000, 1000000)
        self.min_per_bank_spin.setSingleStep(5000)
        self.min_per_bank_spin.setValue(10000)
        self.min_per_bank_spin.setPrefix("₹ ")

        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(100000, 5000000)
        self.limit_spin.setSingleStep(100000)
        self.limit_spin.setValue(int(DICGC_INSURANCE_LIMIT))
        self.limit_spin.setPrefix("₹ ")
        self.limit_spin.setToolTip("DICGC cover per depositor per bank. Change only if the official limit changes.")

        grid.addWidget(QLabel("Person"), 0, 0)
        grid.addWidget(self.person_combo, 0, 1)
        grid.addWidget(QLabel("Amount to invest"), 0, 2)
        grid.addLayout(amount_row, 0, 3)
        grid.addWidget(QLabel("Tenure"), 0, 4)
        grid.addWidget(self.tenure_combo, 0, 5)
        grid.addWidget(QLabel("Keep aside"), 1, 0)
        grid.addWidget(self.keep_aside_spin, 1, 1)
        grid.addWidget(QLabel("Max banks per person"), 1, 2)
        grid.addWidget(self.max_banks_spin, 1, 3)
        grid.addWidget(QLabel("Min per bank"), 1, 4)
        grid.addWidget(self.min_per_bank_spin, 1, 5)
        grid.addWidget(QLabel("Insured limit per bank"), 2, 0)
        grid.addWidget(self.limit_spin, 2, 1)
        grid.addLayout(self._build_option_row(), 3, 0, 1, 6)
        layout.addLayout(grid)

    def _build_option_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(20)

        self.senior_check = QCheckBox("Senior citizen rates")
        self.sfb_check = QCheckBox("Include small finance banks")
        self.sfb_check.setChecked(True)
        self.existing_check = QCheckBox("Count my existing deposits at these banks")
        self.existing_check.setChecked(True)
        self.interest_cap_check = QCheckBox("Keep interest within insured limit")
        self.interest_cap_check.setChecked(True)
        for check in (self.senior_check, self.sfb_check, self.existing_check, self.interest_cap_check):
            row.addWidget(check)

        row.addStretch()
        self.btn_suggest = Theme.btn("Suggest Split", "primary", height=Theme.HEIGHT_MD, min_width=150)
        self.btn_suggest.clicked.connect(self._on_suggest)
        row.addWidget(self.btn_suggest)
        return row

    def _build_results_table(self, layout: QVBoxLayout) -> None:
        header = QHBoxLayout()
        results_title = QLabel("Suggested split")
        results_title.setProperty("textrole", "title-sm")
        header.addWidget(results_title)
        header.addStretch()
        self.btn_copy = Theme.btn("Copy Plan", "secondary", height=Theme.HEIGHT_MD, min_width=120)
        self.btn_copy.setAccessibleName("Copy suggested plan")
        self.btn_copy.setEnabled(False)
        self.btn_copy.clicked.connect(self._on_copy_plan)
        header.addWidget(self.btn_copy)
        layout.addLayout(header)

        self.results_table = QTableWidget(0, len(self.RESULT_COLUMNS))
        self.results_table.setHorizontalHeaderLabels(self.RESULT_COLUMNS)
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._size_columns(self.results_table, stretch_columns={1, 9})
        self.results_table.setMinimumHeight(260)
        self.results_table.setAccessibleName("Suggested FD split")
        layout.addWidget(self.results_table)

    def _build_footer(self, layout: QVBoxLayout) -> None:
        disclaimer = QLabel(
            "Rates come from the source page and change often — confirm the rate on the bank's website before booking. "
            f"DICGC insures up to {format_inr(DICGC_INSURANCE_LIMIT)} per depositor per bank, counting savings, FDs and interest together."
        )
        disclaimer.setProperty("textrole", "muted-sm")
        disclaimer.setWordWrap(True)
        layout.addWidget(disclaimer)

        footer = QHBoxLayout()
        footer.addStretch()
        btn_close = Theme.btn("Close", "secondary", height=Theme.HEIGHT_MD)
        btn_close.clicked.connect(self.accept)
        footer.addWidget(btn_close)
        layout.addLayout(footer)

    @staticmethod
    def _size_columns(table: QTableWidget, stretch_columns: set[int]) -> None:
        header = table.horizontalHeader()
        for column in range(table.columnCount()):
            mode = QHeaderView.ResizeMode.Stretch if column in stretch_columns else QHeaderView.ResizeMode.ResizeToContents
            header.setSectionResizeMode(column, mode)

    def _excluded_from_settings(self) -> set[str]:
        return set(get_setting(_EXCLUDED_BANKS_SETTING, []) or [])

    def _excluded_banks(self) -> list[str]:
        excluded = []
        for row in range(self.rates_table.rowCount()):
            if self.rates_table.item(row, 0).checkState() == Qt.CheckState.Unchecked:
                excluded.append(self.rates_table.item(row, 1).text())
        return sorted(excluded)

    def _populate_rates(self) -> None:
        excluded = self._excluded_from_settings()
        banks = self._snapshot.get("banks", [])
        self.rates_table.blockSignals(True)
        self.rates_table.setSortingEnabled(False)
        self.rates_table.setRowCount(len(banks))
        for row, bank in enumerate(banks):
            self._set_rate_row(row, bank, excluded)
        self._highlight_best_rates()
        self.rates_table.horizontalHeader().setSortIndicator(3, Qt.SortOrder.DescendingOrder)
        self.rates_table.setSortingEnabled(True)
        self.rates_table.blockSignals(False)
        self._update_rates_info()

    def _set_rate_row(self, row: int, bank: dict, excluded: set[str]) -> None:
        use_item = QTableWidgetItem()
        use_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        use_item.setCheckState(
            Qt.CheckState.Unchecked if bank["bank_name"] in excluded else Qt.CheckState.Checked
        )
        self.rates_table.setItem(row, 0, use_item)
        self.rates_table.setItem(row, 1, QTableWidgetItem(bank["bank_name"]))
        self.rates_table.setItem(row, 2, QTableWidgetItem(bank["bank_type"]))
        rate_values = [
            bank.get("highest_rate"), bank.get("rate_1y"), bank.get("rate_3y"),
            bank.get("rate_5y"), bank.get("senior_extra"),
        ]
        for column, value in enumerate(rate_values, start=3):
            self.rates_table.setItem(row, column, _NumericItem(value))

    def _highlight_best_rates(self) -> None:
        for column in (4, 5, 6):
            items = [self.rates_table.item(row, column) for row in range(self.rates_table.rowCount())]
            values = [item.sort_value for item in items if item.sort_value >= 0]
            if not values:
                continue
            best = max(values)
            for item in items:
                if item.sort_value == best:
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                    item.setForeground(QColor(Theme.SUCCESS))
                    item.setToolTip("Best rate for this tenure")

    def _update_rates_info(self) -> None:
        snapshot = self._snapshot
        source_url = snapshot.get("source_url", "")
        host = urlparse(source_url).netloc or source_url
        parts = [
            f"Source: {host}",
            f"Rates as of {format_display_date(snapshot.get('as_of'))}",
            f"Fetched {format_display_date((snapshot.get('fetched_at') or '')[:10])}",
        ]
        if snapshot.get("is_bundled"):
            parts.append("Built-in snapshot — click Refresh Rates for the latest")
        elif is_stale(snapshot):
            parts.append("May be outdated — click Refresh Rates")
        self.rates_info_lbl.setText(" · ".join(parts))

    def _on_rate_item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() != 0:
            return
        set_setting(_EXCLUDED_BANKS_SETTING, self._excluded_banks())

    def _on_refresh_rates(self) -> None:
        url = get_rates_source_url()
        Loader.run(
            self,
            fn=lambda: fetch_rates(url),
            message="Fetching latest FD rates…",
            on_done=self._on_rates_fetched,
            on_error=self._on_rates_error,
        )

    def _on_rates_fetched(self, snapshot: dict) -> None:
        self._snapshot = snapshot
        self._populate_rates()
        show_success(f"Loaded current rates for {len(snapshot['banks'])} banks")

    def _on_rates_error(self, err) -> None:
        show_warning(f"Couldn't fetch FD rates ({err}). Showing the last saved rates.", duration_ms=6000)

    def _on_open_source(self) -> None:
        QDesktopServices.openUrl(QUrl(self._snapshot.get("source_url") or get_rates_source_url()))

    def _on_change_source(self) -> None:
        text, ok = QInputDialog.getText(
            self,
            "FD Rates Source",
            "Web page URL with an FD rate table (leave empty for the default):",
            text=get_rates_source_url(),
        )
        if ok:
            set_rates_source_url(text)
            show_success("Rates source updated — click Refresh Rates to load it")

    def _on_person_changed(self, *_) -> None:
        if self._is_household():
            self.senior_check.setChecked(False)
            self.senior_check.setEnabled(False)
            self.senior_check.setToolTip("In family mode, senior rates are applied per person from their date of birth.")
        else:
            self.senior_check.setEnabled(True)
            self.senior_check.setToolTip("")
            self.senior_check.setChecked(_is_senior(self.person_combo.currentData()))
        if hasattr(self, "tabs"):
            self._refresh_current_tab()

    def _on_use_savings(self) -> None:
        persons = self._selected_persons()
        if not persons:
            show_warning("Add a person with bank accounts first.")
            return
        savings = get_savings_total([p["person_id"] for p in persons])
        keep = self.keep_aside_spin.value()
        spare = max(savings - keep, 0)
        if spare <= 0:
            show_warning(
                f"No spare savings above the {format_inr(keep)} you keep aside "
                f"(savings balance {format_inr(savings)})."
            )
            return
        self.amount_edit.setText(f"{spare:.0f}")
        show_success(f"Filled {format_inr(spare)} from savings of {format_inr(savings)}")

    def _on_suggest(self) -> None:
        amount = self._current_amount()
        if amount <= 0:
            show_warning("Enter the amount you want to invest.")
            return

        depositors = self._build_depositors()
        result = suggest_household_allocation(
            amount,
            self._snapshot.get("banks", []),
            self.tenure_combo.currentData(),
            depositors,
            per_bank_limit=self.limit_spin.value(),
            max_banks=self.max_banks_spin.value(),
            min_per_bank=self.min_per_bank_spin.value(),
            include_small_finance=self.sfb_check.isChecked(),
            count_interest_in_limit=self.interest_cap_check.isChecked(),
            excluded_banks=self._excluded_banks(),
        )
        self._last_result = result
        self._show_result(result, depositors)

    def _show_result(self, result: dict, depositors: list[dict]) -> None:
        rows = result["rows"]
        self.results_table.setColumnHidden(0, len(depositors) <= 1)
        senior_by_name = {d["name"]: d["is_senior"] for d in depositors}
        matures_on = format_display_date((date.today() + relativedelta(months=result["tenure_months"])).isoformat())
        self.results_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            form_name = FD_TDS_FORM_NAME_SENIOR if senior_by_name.get(row["person_name"]) else FD_TDS_FORM_NAME
            self._set_result_row(row_index, row, form_name, matures_on)

        self.kpi_invested.set_value(result["allocated"])
        self.kpi_rate.set_value(f"{result['weighted_rate']:.2f}%" if rows else "—", is_currency=False)
        self.kpi_interest.set_value(result["total_interest"])
        self.kpi_extra.set_value(result["extra_vs_average"])

        messages = self._result_messages(result, any(d["is_senior"] for d in depositors))
        self.warning_lbl.setText("\n".join(messages))
        self.warning_banner.setVisible(bool(messages))
        self.btn_copy.setEnabled(bool(rows))

    def _set_result_row(self, row_index: int, row: dict, form_name: str, matures_on: str) -> None:
        cells = [
            row["person_name"],
            row["bank_name"],
            f"{row['rate']:.2f}",
            format_inr(row["amount"]),
            format_inr(row["interest"]),
            format_inr(row["maturity_value"]),
            matures_on,
            format_inr(row["existing_amount"]),
            format_inr(row["insured_total_after"]),
            _row_note(row, form_name),
        ]
        text_columns = (0, 1, 6, 9)
        for column, text in enumerate(cells):
            item = QTableWidgetItem(text) if column in text_columns else _right_aligned_item(text)
            self.results_table.setItem(row_index, column, item)

    def _result_messages(self, result: dict, is_senior: bool) -> list[str]:
        messages = []
        if result["unallocated"] > 0:
            messages.append(
                f"{format_inr(result['unallocated'])} could not be placed without crossing the "
                f"{format_inr(result['per_bank_limit'])} insured limit at the selected banks. "
                "Raise Max banks, tick more banks, or invest it in another family member's name — "
                "each depositor gets separate cover."
            )
            option = best_overflow_option(result["tenure_months"], is_senior, result["unallocated"])
            if option:
                messages.append(
                    f"Government-backed option for the rest: {option['name']} at {option['rate']:.2f}% — "
                    "no insurance cap applies. See the Other Safe Options tab."
                )
        if result["skipped_full"]:
            messages.append("Skipped — no insured room left: " + ", ".join(result["skipped_full"]) + ".")
        if not result["rows"]:
            messages.append("No bank has a rate for this tenure with the current filters.")
        return messages

    def _on_copy_plan(self) -> None:
        if not self._last_result or not self._last_result["rows"]:
            return
        visible = [c for c in range(self.results_table.columnCount()) if not self.results_table.isColumnHidden(c)]
        lines = ["\t".join(self.RESULT_COLUMNS[c] for c in visible)]
        for row in range(self.results_table.rowCount()):
            lines.append("\t".join(self.results_table.item(row, c).text() for c in visible))
        result = self._last_result
        lines.append(
            f"Total: {format_inr(result['allocated'])} at {result['weighted_rate']:.2f}% → "
            f"{format_inr(result['total_interest'])} interest"
        )
        QApplication.clipboard().setText("\n".join(lines))
        show_success("Plan copied — paste it into a note or spreadsheet")

    def _on_tab_changed(self, _index: int) -> None:
        self._refresh_current_tab()

    def _refresh_current_tab(self) -> None:
        widget = self.tabs.currentWidget()
        if widget is self.coverage_tab:
            self.coverage_tab.refresh(self._selected_persons(), self.limit_spin.value())
        elif widget is self.options_tab:
            self.options_tab.refresh(self._current_amount(), self._options_senior(), self._best_bank_rate())

    def _selected_persons(self) -> list[dict]:
        data = self.person_combo.currentData()
        if data == _ALL_PERSONS:
            return list(self._persons)
        return [p for p in self._persons if p["person_id"] == data]

    def _is_household(self) -> bool:
        return self.person_combo.currentData() == _ALL_PERSONS

    def _current_amount(self) -> float:
        try:
            return float(self.amount_edit.text().replace(",", "") or 0)
        except ValueError:
            return 0

    def _build_depositors(self) -> list[dict]:
        persons = self._selected_persons()
        count_existing = self.existing_check.isChecked()
        if not persons:
            return [{"name": "", "is_senior": self.senior_check.isChecked(), "exposure": {}}]
        if self._is_household():
            return [
                {
                    "name": person["full_name"],
                    "is_senior": _is_senior(person["person_id"]),
                    "exposure": get_existing_exposure(person["person_id"]) if count_existing else {},
                }
                for person in persons
            ]
        person = persons[0]
        return [{
            "name": person["full_name"],
            "is_senior": self.senior_check.isChecked(),
            "exposure": get_existing_exposure(person["person_id"]) if count_existing else {},
        }]

    def _options_senior(self) -> bool:
        if self._is_household():
            return any(_is_senior(p["person_id"]) for p in self._persons)
        return self.senior_check.isChecked()

    def _best_bank_rate(self) -> float | None:
        key = self.tenure_combo.currentData()
        excluded = set(self._excluded_banks())
        rates = [
            bank[key] for bank in self._snapshot.get("banks", [])
            if bank.get(key) is not None and bank["bank_name"] not in excluded
        ]
        return max(rates) if rates else None
