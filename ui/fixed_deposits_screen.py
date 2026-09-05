"""
ui/fixed_deposits_screen.py — FD management screen with modern theme.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QDialog,
    QFormLayout, QLineEdit, QComboBox, QDateEdit, QMessageBox, QFrame,
    QPlainTextEdit, QSpinBox, QScrollArea, QCheckBox
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QFont, QColor, QDoubleValidator

from datetime import date
from dateutil.relativedelta import relativedelta

from ui.widgets.excel_table import ExcelTableWithStats
from ui.widgets.chart_widget import ChartWidget
from ui.widgets.states import EmptyState
from ui.widgets.toast_utils import show_success, show_warning, show_info

from ui.theme import Theme
from ui.icons import icon as app_icon, icon_label
from ui.date_utils import format_display_date
from ui.dialogs.fd_dialog import FDDialog
from ui.dialogs.link_fd_transaction_dialog import LinkFDTransactionDialog
from core.session import session
from config import COMPOUNDING_TYPES, fy_date_range, get_assessment_year, get_current_financial_year, FD_TDS_FORM_NAME, get_all_financial_years
from models.person import get_all_persons
from models.bank_account import get_accounts_for_person
from models.transaction import display_transaction_type
from models.fixed_deposit import (
    add_fd,
    get_all_fds,
    update_fd,
    delete_fd,
    get_fd_link_candidates,
    link_fd_transaction,
    unlink_fd_transaction,
    auto_link_fd_records,
)
from models.fd_interest_record import get_total_fd_interest
from models.savings_interest import get_total_savings_interest
from engines.interest_engine import (
    calculate_fd_maturity,
    calculate_fd_maturity_bank_style,
    calculate_fd_maturity_date,
    calculate_fd_maturity_flexible,
    calculate_fd_quarterly_credit_breakdown,
    allocate_fd_interest_to_fy,
    fd_tds_threshold_status,
)


class FixedDepositsScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 20)
        layout.setSpacing(16)

        # Header
        self.header_frame = QFrame()
        self.header_frame.setObjectName("pageHeader")
        self.header_frame.setStyleSheet(Theme.page_header_style())
        header = QHBoxLayout(self.header_frame)
        header.setContentsMargins(20, 16, 20, 16)
        self._title_lbl = title = QLabel("Fixed Deposits")
        title.setObjectName("fdTitle")
        title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        header.addWidget(title)
        self._subtitle_lbl = subtitle = QLabel("Track FD principal, expected vs actual interest, and transaction linkage")
        subtitle.setObjectName("fdSubtitle")
        header.addWidget(subtitle)
        header.addStretch()

        btn_add = Theme.btn("  Add FD", "primary", height=38, min_width=110)
        btn_add.setIcon(app_icon("add", color="#FFFFFF", size=16))
        btn_add.setAccessibleName("Add fixed deposit")
        btn_add.clicked.connect(self._on_add_fd)
        header.addWidget(btn_add)

        btn_del = Theme.btn("  Delete Selected", "danger", height=38, min_width=145)
        btn_del.setIcon(app_icon("delete", color="#FFFFFF", size=16))
        btn_del.setAccessibleName("Delete selected fixed deposit")
        btn_del.clicked.connect(self._on_delete_fd)
        header.addWidget(btn_del)

        btn_link = Theme.btn("  Link Txn", "success", height=38, min_width=108)
        btn_link.setIcon(app_icon("link", color="#FFFFFF", size=16))
        btn_link.setAccessibleName("Link transaction to fixed deposit")
        btn_link.clicked.connect(self._on_link_fd_transaction)
        header.addWidget(btn_link)

        btn_auto = Theme.btn("  Auto-Link", "success", height=38, min_width=108)
        btn_auto.setIcon(app_icon("auto_link", color="#FFFFFF", size=16))
        btn_auto.setAccessibleName("Auto-link fixed deposit transactions")
        btn_auto.clicked.connect(self._on_auto_link)
        header.addWidget(btn_auto)

        btn_recalc = Theme.btn("  Recalculate Selected", "primary", height=38, min_width=165)
        btn_recalc.setIcon(app_icon("recalculate", color="#FFFFFF", size=16))
        btn_recalc.setAccessibleName("Recalculate selected fixed deposits")
        btn_recalc.clicked.connect(self._on_recalculate_selected)
        header.addWidget(btn_recalc)

        btn_save = Theme.btn("  Save Changes", "success", height=38, min_width=125)
        btn_save.setIcon(app_icon("save", color="#FFFFFF", size=16))
        btn_save.setAccessibleName("Save fixed deposit changes")
        btn_save.clicked.connect(self._on_save_changes)
        header.addWidget(btn_save)

        layout.addWidget(self.header_frame)

        # TDS-threshold reminder banner (hidden until FD interest crosses the limit)
        self.tds_banner = QFrame()
        self.tds_banner.setObjectName("tdsBanner")
        self.tds_banner.setStyleSheet(Theme.banner_style("warning"))
        tds_layout = QHBoxLayout(self.tds_banner)
        tds_layout.setContentsMargins(14, 10, 14, 10)
        tds_layout.setSpacing(10)
        self._tds_icon = icon_label("warning", size=20, color=Theme.WARNING_DARK)
        tds_layout.addWidget(self._tds_icon)
        self.tds_banner_label = QLabel("")
        self.tds_banner_label.setWordWrap(True)
        self.tds_banner_label.setProperty("textrole", "emphasis-sm")
        self.tds_banner_label.setProperty("color", "warning")
        tds_layout.addWidget(self.tds_banner_label, stretch=1)
        self.tds_banner.setVisible(False)
        layout.addWidget(self.tds_banner)

        # Interest trend chart
        self.interest_chart = ChartWidget()
        self.interest_chart.setMinimumHeight(350)
        layout.addWidget(self.interest_chart)

        # Table
        self.table_widget = ExcelTableWithStats(show_checkboxes=True)
        self.table = self.table_widget.table
        self.table.setAccessibleName("Fixed deposits table")
        self.table.setAccessibleDescription("Editable list of fixed deposit records and calculations.")
        self.table.editable = True  # Enable editing
        self.table.setHeaders([
            "Person", "Bank", "FD No", "Principal", "Rate %", "Tenure",
            "Compounding", "Start Date", "Maturity Date", "Maturity Amount",
            "Expected Interest", "Actual Interest", "Method", "Status"
        ])
        # Principal, Rate %, Actual Interest are the only strictly-numeric
        # editable columns (FD No/Tenure/Compounding/Start Date are editable
        # too but not plain numbers) — reject non-numeric pastes into them.
        self.table.setNumericColumns({4, 5, 12})
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked | QTableWidget.EditTrigger.EditKeyPressed)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)  # Allow multi-cell selection
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems)  # Select individual cells
        self.table.setHorizontalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        self.table.setVerticalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        self.table.doubleClicked.connect(self._on_edit_fd)
        self.table.cellDataChanged.connect(self._on_table_data_changed)
        self.table.itemChanged.connect(self._on_item_changed)  # Track manual edits
        # Override the base ExcelTable delete (which only removes UI rows)
        # so pressing Delete also removes the underlying FD records.
        self.table.deleteSelectedRows = self._delete_selected_fds
        for i, w in enumerate([40,110,120,110,110,70,90,100,100,110,130,130,120,110,85]):
            self.table.setColumnWidth(i, w)

        # Table container (will hold table or empty state)
        self.table_container = QWidget()
        self.table_container_layout = QVBoxLayout(self.table_container)
        self.table_container_layout.setContentsMargins(0, 0, 0, 0)
        self.table_container_layout.setSpacing(0)
        self.table_container_layout.addWidget(self.table_widget)
        self._empty_state = None

        layout.addWidget(self.table_container)

        # Info label
        self._info_lbl = info_label = QLabel("Tip: Edit cells directly, then click 'Save Changes' or 'Recalculate Selected' to update database")
        info_label.setObjectName("fdInfoLabel")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        self.status_label = QLabel("")
        self.status_label.setObjectName("fdStatusLabel")
        layout.addWidget(self.status_label)

    def refresh(self):
        # Block signals during refresh to avoid triggering itemChanged
        self.table.blockSignals(True)
        fds = get_all_fds(person_id=session.selected_person_id)

        # Show empty state if no FDs
        if not fds:
            if self._empty_state is None:
                self._empty_state = EmptyState(
                    icon_name="piggy-bank",
                    headline="No fixed deposits",
                    explanation="Add a fixed deposit to track principal, interest, and maturity.",
                    action_text="Add FD",
                    parent=self.table_container
                )
                self._empty_state.action_clicked.connect(self._on_add_fd)
                self.table_container_layout.insertWidget(0, self._empty_state)
            self.table_widget.setVisible(False)
            if self._empty_state:
                self._empty_state.setVisible(True)
            self._refresh_interest_chart()
            self.table.blockSignals(False)
            return

        # Hide empty state and show table
        if self._empty_state:
            self._empty_state.setVisible(False)
        self.table_widget.setVisible(True)

        self.table.setRowCount(0)
        self.table.setSortingEnabled(False)  # Disable sorting during population
        self._refresh_interest_chart()

        status_colors = {
            "Active":  QColor(Theme.SUCCESS),
            "Matured": QColor(Theme.WARNING),
            "Pending Details": QColor(Theme.INFO),
            "Closed":  QColor(Theme.TEXT_MUTED),
        }

        for fd in fds:
            r = self.table.rowCount()
            self.table.insertRow(r)
            
            # Add checkbox widget in column 0
            cb = QCheckBox()
            cb.setChecked(False)
            cb_widget = QWidget()
            cb_layout = QHBoxLayout(cb_widget)
            cb_layout.addWidget(cb)
            cb_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cb_layout.setContentsMargins(0, 0, 0, 0)
            self.table.setCellWidget(r, 0, cb_widget)

            def item(text, align=Qt.AlignmentFlag.AlignLeft, editable=False):
                it = QTableWidgetItem(str(text) if text is not None else "—")
                it.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
                if editable:
                    it.setFlags(it.flags() | Qt.ItemFlag.ItemIsEditable)
                else:
                    it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                return it

            # Checkbox column is at index 0, data starts at index 1
            # Read-only columns
            self.table.setItem(r, 0+1, item(fd["person_name"], editable=False))
            self.table.setItem(r, 1+1, item(fd["bank_name"], editable=False))
            
            # Editable columns
            self.table.setItem(r, 2+1, item(fd.get("fd_reference_no") or "—", editable=True))
            self.table.setItem(r, 3+1, item(session.mask(fd["principal_amount"]), Qt.AlignmentFlag.AlignRight, editable=True))
            
            rate = fd.get("interest_rate")
            rate_text = "—" if rate is None else f"{rate:.2f}"
            self.table.setItem(r, 4+1, item(rate_text, Qt.AlignmentFlag.AlignRight, editable=True))
            
            tenure_text = self._format_tenure(fd)
            self.table.setItem(r, 5+1, item(tenure_text, editable=True))
            
            self.table.setItem(r, 6+1, item(fd.get("compounding_type") or "—", editable=True))
            self.table.setItem(r, 7+1, item(format_display_date(fd.get("start_date")), editable=True))
            
            # Read-only calculated fields
            self.table.setItem(r, 8+1, item(format_display_date(fd.get("maturity_date")), editable=False))
            
            maturity_amount = fd.get("maturity_amount")
            maturity_text = "—" if maturity_amount is None else session.mask(maturity_amount)
            self.table.setItem(r, 9+1, item(maturity_text, Qt.AlignmentFlag.AlignRight, editable=False))

            exp_i = fd.get("expected_interest_amount")
            exp_t = "—" if exp_i in (None, 0) else session.mask(exp_i)
            self.table.setItem(r, 10+1, item(exp_t, Qt.AlignmentFlag.AlignRight, editable=False))

            # Actual Interest - editable
            act_i = fd.get("actual_interest_amount")
            act_t = "—" if act_i in (None, 0) else session.mask(act_i)
            self.table.setItem(r, 11+1, item(act_t, Qt.AlignmentFlag.AlignRight, editable=True))

            # Read-only
            method = fd.get("maturity_calc_method") or "Formula"
            method_text = "Bank-style" if method == "BankStyle" else "Formula"
            self.table.setItem(r, 12+1, item(method_text, editable=False))

            status_item = item(fd["status"], editable=False)
            status_item.setForeground(status_colors.get(fd["status"], QColor(Theme.TEXT_MUTED)))
            self.table.setItem(r, 13+1, status_item)

            # Store FD ID in first data column
            self.table.item(r, 0+1).setData(Qt.ItemDataRole.UserRole, fd["fd_id"])
            self.table.setRowHeight(r, 32)

        self.table.setSortingEnabled(True)  # Re-enable sorting
        self.table.blockSignals(False)  # Re-enable signals
        count = self.table.rowCount()
        self.status_label.setText(f"Showing {count} fixed deposit{'s' if count!=1 else ''}.")
        self.status_label.setStyleSheet("")  # Reset style
        self._update_tds_banner()

    def _update_tds_banner(self):
        """Show a reminder when a person's FD interest with any bank crosses
        the TDS threshold this FY — with the quarter it crosses in (banks that
        credit interest quarterly deduct TDS in that quarter) and which form
        to file to avoid the deduction."""
        pid = session.selected_person_id
        fy = session.selected_fy
        if not pid or not fy:
            self.tds_banner.setVisible(False)
            return
        status = fd_tds_threshold_status(pid, fy)
        exceeding = [b for b in status["banks"] if b["exceeds"]]
        if not exceeding:
            self.tds_banner.setVisible(False)
            return
        threshold = status["threshold"]
        parts = []
        for b in exceeding:
            q = b["crossing_quarter"]
            q_txt = f", crosses in {q}" if q else ""
            parts.append(f"{b['bank_name']} (₹{b['total_interest']:,.0f}{q_txt})")
        banks_txt = "; ".join(parts)
        self.tds_banner_label.setText(
            f"FD interest crosses the ₹{threshold:,.0f} TDS limit — {banks_txt}. "
            f"File {FD_TDS_FORM_NAME} with the bank as soon as possible to avoid tax being deducted."
        )
        self.tds_banner.setVisible(True)

    def _refresh_interest_chart(self):
        """Refresh the FD and Savings interest trend chart."""
        if not hasattr(self, 'interest_chart') or not self.interest_chart:
            return

        fys = list(reversed(get_all_financial_years(since_year=2020)))
        pid = session.selected_person_id

        fd_interests  = [get_total_fd_interest(fy, pid)      for fy in fys]
        sav_interests = [get_total_savings_interest(fy, pid)  for fy in fys]

        if all(v == 0 for v in fd_interests) and all(v == 0 for v in sav_interests):
            self.interest_chart.show_empty_state("No interest records found")
            return

        self.interest_chart.plot_trend_line(
            categories=fys,
            series={
                "FD Interest":      fd_interests,
                "Savings Interest": sav_interests,
            },
            title="Interest Income Trend",
            xlabel="Financial Year",
            ylabel="Amount (₹)",
        )

    def refresh_theme(self):
        """Called after a live theme switch. The interest chart (matplotlib
        canvas) needs explicit theme refresh since it can't use QSS.
        Table is rebuilt on refresh() which picks up new theme colors."""
        if hasattr(self, "table_widget") and self.table_widget:
            self.table_widget.refresh_theme()
        if hasattr(self, "interest_chart") and self.interest_chart:
            self.interest_chart.refresh_theme()
        self.refresh()

    def _format_tenure(self, fd: dict) -> str:
        years = fd.get("tenure_years") or 0
        months = fd.get("tenure_months") or 0
        days = fd.get("tenure_days") or 0
        if years == 0 and months == 0 and days == 0:
            return "—"

        parts = []
        if years:
            parts.append(f"{years}y")
        if months:
            parts.append(f"{months}m")
        if days:
            parts.append(f"{days}d")
        return " ".join(parts)

    def _on_add_fd(self):
        if FDDialog(self, mode="add").exec() == QDialog.DialogCode.Accepted:
            self.refresh()
            if self.parent_window: self.parent_window.refresh_overview()

    def _on_edit_fd(self):
        row = self.table.currentRow()
        if row < 0: return
        fd_id = self.table.item(row, 0+1).data(Qt.ItemDataRole.UserRole)
        if FDDialog(self, mode="edit", fd_id=fd_id).exec() == QDialog.DialogCode.Accepted:
            self.refresh()
            if self.parent_window: self.parent_window.refresh_overview()

    def _on_delete_fd(self):
        row = self.table.currentRow()
        if row < 0:
            show_warning("Please select an FD."); return
        fd_id = self.table.item(row, 0+1).data(Qt.ItemDataRole.UserRole)
        reply = QMessageBox.question(self, "Delete FD", "Delete this Fixed Deposit?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            delete_fd(fd_id)
            self.refresh()
            if self.parent_window: self.parent_window.refresh_overview()

    def _delete_selected_fds(self):
        """Delete key handler for the table — unlike the base ExcelTable
        implementation, this actually deletes the underlying FD records,
        not just the UI rows (mirrors transactions_screen.py's override)."""
        selected_rows = sorted({item.row() for item in self.table.selectedItems()}, reverse=True)
        if not selected_rows:
            return
        reply = QMessageBox.question(
            self, "Delete Fixed Deposits",
            f"Delete {len(selected_rows)} selected fixed deposit(s)?\n\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        for row in selected_rows:
            id_item = self.table.item(row, 1)
            fd_id = id_item.data(Qt.ItemDataRole.UserRole) if id_item else None
            if fd_id:
                delete_fd(fd_id)
        self.refresh()
        if self.parent_window:
            self.parent_window.refresh_overview()

    def _selected_fd_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Please select an FD.")
            return None
        return self.table.item(row, 0+1).data(Qt.ItemDataRole.UserRole)

    def _on_link_fd_transaction(self):
        fd_id = self._selected_fd_id()
        if not fd_id:
            return

        dlg = LinkFDTransactionDialog(self, fd_id)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            txn_id = dlg.get_selected_transaction_id()
            if txn_id:
                link_fd_transaction(fd_id, txn_id)
                self.refresh()
                if self.parent_window:
                    self.parent_window.refresh_overview()

    def _on_auto_link(self):
        if not session.selected_person_id:
            show_warning("Please select a person first.")
            return

        linked = auto_link_fd_records(session.selected_person_id, session.selected_fy)
        if linked > 0:
            show_success(f"Linked {linked} FD record(s) with account transactions.")
            self.refresh()
            if self.parent_window:
                self.parent_window.refresh_overview()
        else:
            show_info("No FD references were matched in account transactions.")

    def _on_table_data_changed(self):
        """Handle data changes in table (after paste or edit)."""
        # Show indicator that changes need to be saved
        self.status_label.setText(f"⚠️ Unsaved changes - Click 'Save Changes' or 'Recalculate Selected' to update database")
        self.status_label.setStyleSheet(f"color: {Theme.WARNING}; font-weight: 600;")

    def _on_item_changed(self, item):
        """Handle individual cell edits."""
        if not self.table.signalsBlocked():
            self._on_table_data_changed()

    def _on_save_changes(self):
        """Save all edited values to database without recalculation."""
        checked_rows = self.table.getCheckedRows()
        if not checked_rows:
            reply = QMessageBox.question(
                self,
                "Save All Changes",
                "No rows selected. Save changes for ALL FDs?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                checked_rows = list(range(self.table.rowCount()))
            else:
                return

        saved = 0
        errors = []

        for row in checked_rows:
            try:
                fd_id = self.table.item(row, 0+1).data(Qt.ItemDataRole.UserRole)
                if not fd_id:
                    continue

                # Get current FD data
                from models.fixed_deposit import get_fd
                fd_data = get_fd(fd_id)
                if not fd_data:
                    continue

                # Extract edited values from table
                fd_no = self.table.item(row, 2+1).text()
                if fd_no == "—":
                    fd_no = None

                principal_text = self.table.item(row, 3+1).text().replace("₹", "").replace(",", "").strip()
                principal = float(principal_text) if principal_text and principal_text != "—" else fd_data["principal_amount"]

                rate_text = self.table.item(row, 4+1).text().replace("%", "").strip()
                rate = float(rate_text) if rate_text and rate_text != "—" else fd_data.get("interest_rate")

                if principal <= 0:
                    raise ValueError("Principal must be greater than 0")
                if rate <= 0 or rate > 100:
                    raise ValueError("Interest rate must be between 0 and 100")

                tenure_text = self.table.item(row, 5+1).text().strip()
                # Parse tenure
                years, months, days = fd_data.get("tenure_years", 0), fd_data.get("tenure_months", 0), fd_data.get("tenure_days", 0)
                if tenure_text and tenure_text != "—":
                    import re
                    y_match = re.search(r'(\d+)y', tenure_text)
                    m_match = re.search(r'(\d+)m', tenure_text)
                    d_match = re.search(r'(\d+)d', tenure_text)
                    if y_match:
                        years = int(y_match.group(1))
                    if m_match:
                        months = int(m_match.group(1))
                    if d_match:
                        days = int(d_match.group(1))

                compounding = self.table.item(row, 6+1).text().strip()
                if compounding == "—":
                    compounding = fd_data.get("compounding_type", "Quarterly")

                start_date_text = self.table.item(row, 7+1).text().strip()
                # Parse start date
                from datetime import datetime
                start_date = None
                try:
                    start_date = datetime.strptime(start_date_text, "%d/%m/%y").date()
                except:
                    try:
                        start_date = datetime.strptime(start_date_text, "%Y-%m-%d").date()
                    except:
                        # If parsing fails, use existing date from database
                        if isinstance(fd_data["start_date"], str):
                            start_date = date.fromisoformat(fd_data["start_date"])
                        else:
                            start_date = fd_data["start_date"]

                actual_interest_text = self.table.item(row, 11+1).text().replace("₹", "").replace(",", "").strip()
                actual_interest = None
                if actual_interest_text and actual_interest_text != "—":
                    try:
                        actual_interest = float(actual_interest_text)
                    except:
                        pass

                # Update FD with edited values (keep existing calculated values)
                update_fd(
                    fd_id,
                    principal,
                    start_date.isoformat(),
                    months,
                    rate,
                    compounding,
                    fd_data["maturity_date"],  # Keep existing
                    fd_data["maturity_amount"],  # Keep existing
                    fd_data["status"],
                    fd_data.get("maturity_amount_formula"),  # Keep existing
                    fd_data.get("maturity_amount_bank"),  # Keep existing
                    fd_data.get("maturity_calc_method", "Formula"),
                    years,
                    days,
                    fd_no,
                    fd_data.get("expected_interest_amount"),  # Keep existing
                    actual_interest,
                    fd_data.get("linked_transaction_id"),
                    fd_data.get("source_statement_file"),
                    fd_data.get("source_transaction_id")
                )
                saved += 1

            except Exception as e:
                errors.append(f"Row {row+1}: {str(e)}")

        # Show results
        if errors:
            error_msg = "\n".join(errors[:10])
            if len(errors) > 10:
                error_msg += f"\n... and {len(errors)-10} more errors"
            show_warning(f"Saved {saved} FD(s).\n\nErrors:\n{error_msg}")
        else:
            show_success(f"Successfully saved {saved} FD(s)!")

        self.refresh()
        if self.parent_window:
            self.parent_window.refresh_overview()

    def _on_recalculate_selected(self):
        """Recalculate maturity for selected FDs based on edited values."""
        checked_rows = self.table.getCheckedRows()
        if not checked_rows:
            show_warning("Please select FDs to recalculate using checkboxes.")
            return

        recalculated = 0
        errors = []

        for row in checked_rows:
            try:
                fd_id = self.table.item(row, 0+1).data(Qt.ItemDataRole.UserRole)
                if not fd_id:
                    continue

                # Extract values from table
                principal_text = self.table.item(row, 3+1).text().replace("₹", "").replace(",", "").strip()
                rate_text = self.table.item(row, 4+1).text().replace("%", "").strip()
                tenure_text = self.table.item(row, 5+1).text().strip()
                compounding = self.table.item(row, 6+1).text().strip()
                start_date_text = self.table.item(row, 7+1).text().strip()

                # Parse values
                if not principal_text or principal_text == "—":
                    errors.append(f"Row {row+1}: Missing principal")
                    continue
                principal = float(principal_text)
                if principal <= 0:
                    errors.append(f"Row {row+1}: Principal must be greater than 0")
                    continue

                if not rate_text or rate_text == "—":
                    errors.append(f"Row {row+1}: Missing rate")
                    continue
                rate = float(rate_text)
                if rate <= 0 or rate > 100:
                    errors.append(f"Row {row+1}: Interest rate must be between 0 and 100")
                    continue

                # Parse tenure (format: "2y 3m 5d" or "24m" or "730d")
                years, months, days = 0, 0, 0
                if tenure_text and tenure_text != "—":
                    import re
                    y_match = re.search(r'(\d+)y', tenure_text)
                    m_match = re.search(r'(\d+)m', tenure_text)
                    d_match = re.search(r'(\d+)d', tenure_text)
                    if y_match:
                        years = int(y_match.group(1))
                    if m_match:
                        months = int(m_match.group(1))
                    if d_match:
                        days = int(d_match.group(1))

                if years == 0 and months == 0 and days == 0:
                    errors.append(f"Row {row+1}: Missing or invalid tenure")
                    continue

                # Parse start date
                from datetime import datetime
                start_date = None
                try:
                    start_date = datetime.strptime(start_date_text, "%d/%m/%y").date()
                except:
                    try:
                        start_date = datetime.strptime(start_date_text, "%Y-%m-%d").date()
                    except:
                        errors.append(f"Row {row+1}: Invalid start date format")
                        continue

                if not compounding or compounding == "—":
                    compounding = "Quarterly"

                # Calculate maturity
                if not compounding:
                    compounding = "Quarterly"
                    
                mat_date = calculate_fd_maturity_date(start_date, years, months, days)
                mat_formula = calculate_fd_maturity_flexible(
                    principal, rate, start_date, mat_date, compounding,
                    years, months, days
                )
                mat_bank = calculate_fd_maturity_bank_style(
                    principal, rate, start_date, mat_date, compounding,
                    years, months, days
                )

                # Get method from table or use Formula as default
                method_text = self.table.item(row, 12+1).text()
                method = "BankStyle" if "Bank" in method_text else "Formula"
                mat_amt = mat_bank if method == "BankStyle" else mat_formula

                # Update FD in database
                update_fd(
                    fd_id, principal, start_date.isoformat(), months, rate,
                    compounding or "Quarterly", mat_date.isoformat(), mat_amt, "Active",
                    mat_formula, mat_bank, method,
                    years, days,
                    self.table.item(row, 2+1).text() if self.table.item(row, 2+1).text() != "—" else None,
                    mat_amt - principal,  # expected interest
                    None,  # actual interest - keep existing
                    None,  # linked_transaction_id
                    None,  # source_statement_file
                    None   # source_transaction_id
                )
                allocate_fd_interest_to_fy(fd_id)
                recalculated += 1

            except Exception as e:
                errors.append(f"Row {row+1}: {str(e)}")

        # Show results
        if errors:
            error_msg = "\n".join(errors[:10])
            if len(errors) > 10:
                error_msg += f"\n... and {len(errors)-10} more errors"
            show_warning(f"Recalculated {recalculated} FD(s).\n\nErrors:\n{error_msg}")
        else:
            show_success(f"Successfully recalculated {recalculated} FD(s)!")

        self.refresh()
        if self.parent_window:
            self.parent_window.refresh_overview()


