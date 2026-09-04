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

from ui.theme import Theme
from ui.icons import icon as app_icon, icon_label
from ui.date_utils import format_display_date
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
        self.interest_chart.setFixedHeight(350)
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
        layout.addWidget(self.table_widget)

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
            QMessageBox.warning(self, "No Selection", "Please select an FD."); return
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
            QMessageBox.information(self, "Select Person", "Please select a person first.")
            return

        linked = auto_link_fd_records(session.selected_person_id, session.selected_fy)
        if linked > 0:
            QMessageBox.information(self, "Auto-Link Complete", f"Linked {linked} FD record(s) with account transactions.")
            self.refresh()
            if self.parent_window:
                self.parent_window.refresh_overview()
        else:
            QMessageBox.information(self, "No Matches", "No FD references were matched in account transactions.")

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
            QMessageBox.warning(self, "Save Errors",
                f"Saved {saved} FD(s).\n\nErrors:\n{error_msg}")
        else:
            QMessageBox.information(self, "Success",
                f"Successfully saved {saved} FD(s)!")

        self.refresh()
        if self.parent_window:
            self.parent_window.refresh_overview()

    def _on_recalculate_selected(self):
        """Recalculate maturity for selected FDs based on edited values."""
        checked_rows = self.table.getCheckedRows()
        if not checked_rows:
            QMessageBox.information(self, "No Selection", "Please select FDs to recalculate using checkboxes.")
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
            QMessageBox.warning(self, "Recalculation Errors", 
                f"Recalculated {recalculated} FD(s).\n\nErrors:\n{error_msg}")
        else:
            QMessageBox.information(self, "Success", 
                f"Successfully recalculated {recalculated} FD(s)!")

        self.refresh()
        if self.parent_window:
            self.parent_window.refresh_overview()


class FDDialog(QDialog):
    def __init__(self, parent, mode="add", fd_id=None):
        super().__init__(parent)
        self.mode = mode; self.fd_id = fd_id; self.fd_data = None
        self.setWindowTitle("Add Fixed Deposit" if mode=="add" else "Edit Fixed Deposit")
        self.setMinimumWidth(500)
        self._build_ui()
        if mode == "edit" and fd_id:
            self._load_fd()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(14)

        title = QLabel("Fixed Deposit Details")
        title.setStyleSheet(f"font-weight: 700; font-size: 15px; color: {Theme.TEXT_PRIMARY};")
        layout.addWidget(title)

        helper = QLabel("Enter FD inputs below. Scroll for advanced fields and bulk-create options.")
        helper.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 12px;")
        layout.addWidget(helper)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        form_container = QWidget()
        form_container_layout = QVBoxLayout(form_container)
        form_container_layout.setContentsMargins(0, 0, 0, 0)
        form_container_layout.setSpacing(12)

        form = QFormLayout(); form.setSpacing(12)

        self.person_combo = QComboBox()
        for p in get_all_persons():
            self.person_combo.addItem(p["full_name"], userData=p["person_id"])
        self.person_combo.currentIndexChanged.connect(self._on_person_changed)
        form.addRow("Person:", self.person_combo)

        self.account_combo = QComboBox()
        form.addRow("Bank Account:", self.account_combo)
        self._on_person_changed()

        self.principal_input = QLineEdit(); self.principal_input.setPlaceholderText("e.g. 100000")
        self.principal_input.setValidator(QDoubleValidator(0.01, 99_999_999.99, 2, self.principal_input))
        self.principal_input.textChanged.connect(self._calc)
        form.addRow("Principal (₹):", self.principal_input)

        self.fd_no_input = QLineEdit(); self.fd_no_input.setPlaceholderText("FD/TD unique number")
        form.addRow("FD No / TD No:", self.fd_no_input)

        self.rate_input = QLineEdit(); self.rate_input.setPlaceholderText("e.g. 7.5")
        self.rate_input.setValidator(QDoubleValidator(0.01, 100.0, 2, self.rate_input))
        self.rate_input.textChanged.connect(self._calc)
        form.addRow("Interest Rate (%):", self.rate_input)

        tenure_row = QHBoxLayout()
        self.tenure_years_input = QLineEdit(); self.tenure_years_input.setPlaceholderText("Years")
        self.tenure_years_input.textChanged.connect(self._calc)
        tenure_row.addWidget(self.tenure_years_input)
        self.tenure_months_input = QLineEdit(); self.tenure_months_input.setPlaceholderText("Months")
        self.tenure_months_input.textChanged.connect(self._calc)
        tenure_row.addWidget(self.tenure_months_input)
        self.tenure_days_input = QLineEdit(); self.tenure_days_input.setPlaceholderText("Days")
        self.tenure_days_input.textChanged.connect(self._calc)
        tenure_row.addWidget(self.tenure_days_input)
        form.addRow("Tenure (Y/M/D):", tenure_row)

        self.compounding_combo = QComboBox()
        self.compounding_combo.addItems(COMPOUNDING_TYPES)
        self.compounding_combo.currentTextChanged.connect(self._calc)
        form.addRow("Compounding:", self.compounding_combo)

        self.amount_method_combo = QComboBox()
        self.amount_method_combo.addItem("Current Formula", userData="Formula")
        self.amount_method_combo.addItem("Bank-style Daily (Leap-aware)", userData="BankStyle")
        self.amount_method_combo.currentIndexChanged.connect(self._calc)
        form.addRow("Use Amount For FY/Tax:", self.amount_method_combo)

        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate())
        self.start_date.dateChanged.connect(self._calc)
        form.addRow("Start Date:", self.start_date)

        # Calculated outputs
        self.maturity_date_lbl = QLabel("—")
        self.maturity_date_lbl.setStyleSheet(f"font-weight: 700; color: {Theme.TEXT_PRIMARY};")
        form.addRow("Maturity Date:", self.maturity_date_lbl)

        self.maturity_amount_formula_lbl = QLabel("—")
        self.maturity_amount_formula_lbl.setStyleSheet(f"font-weight: 700; color: {Theme.TEXT_PRIMARY};")
        form.addRow("Maturity (Current Formula):", self.maturity_amount_formula_lbl)

        self.maturity_amount_bank_lbl = QLabel("—")
        self.maturity_amount_bank_lbl.setStyleSheet(f"font-weight: 700; color: {Theme.TEXT_PRIMARY};")
        form.addRow("Maturity (Bank-style Daily):", self.maturity_amount_bank_lbl)

        self.maturity_amount_lbl = QLabel("—")
        self.maturity_amount_lbl.setStyleSheet(f"font-weight: 700; font-size: 15px; color: {Theme.SUCCESS};")
        form.addRow("Selected Maturity Amount:", self.maturity_amount_lbl)

        self.expected_interest_input = QLineEdit(); self.expected_interest_input.setPlaceholderText("Auto = Maturity - Principal")
        form.addRow("Expected Interest (₹):", self.expected_interest_input)

        self.actual_interest_input = QLineEdit(); self.actual_interest_input.setPlaceholderText("Optional")
        form.addRow("Actual Interest (₹):", self.actual_interest_input)

        self.fd_count_spin = QSpinBox()
        self.fd_count_spin.setRange(1, 25)
        self.fd_count_spin.setValue(1)
        form.addRow("No. of FDs:", self.fd_count_spin)

        self.fd_numbers_input = QLineEdit()
        self.fd_numbers_input.setPlaceholderText("Comma-separated FD Nos when count > 1")
        form.addRow("FD Nos (Bulk):", self.fd_numbers_input)

        form_container_layout.addLayout(form)
        scroll.setWidget(form_container)
        layout.addWidget(scroll, 1)

        btns = QHBoxLayout(); btns.addStretch()
        btn_show = Theme.btn("Show Calculations", "secondary", height=36, min_width=130)
        btn_show.clicked.connect(self._on_show_calculations)
        btns.addWidget(btn_show)
        btn_cancel = Theme.btn("Cancel", "secondary", height=36, min_width=95)
        btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_cancel)
        btn_save = Theme.btn("Save FD", "primary", height=36, min_width=100)
        btn_save.clicked.connect(self._on_save)
        btns.addWidget(btn_save)
        layout.addLayout(btns)

    def _on_person_changed(self):
        pid = self.person_combo.currentData()
        self.account_combo.clear()
        for acc in get_accounts_for_person(pid):
            self.account_combo.addItem(f"{acc.get('bank_display_name', acc['bank_name'])} ({acc['account_type']})", userData=acc["account_id"])

    def _calc(self):
        try:
            p = float(self.principal_input.text() or 0)
            r = float(self.rate_input.text() or 0)
            y = int(self.tenure_years_input.text() or 0)
            m = int(self.tenure_months_input.text() or 0)
            d = int(self.tenure_days_input.text() or 0)
            c = self.compounding_combo.currentText()
            s = self.start_date.date().toPyDate()
            if p > 0 and r > 0 and (y > 0 or m > 0 or d > 0):
                mat_date = calculate_fd_maturity_date(s, y, m, d)
                mat_formula = calculate_fd_maturity_flexible(p, r, s, mat_date, c, y, m, d)
                mat_bank = calculate_fd_maturity_bank_style(
                    p, r, s, mat_date, c,
                    y, m, d,
                )
                method = self.amount_method_combo.currentData()
                selected = mat_bank if method == "BankStyle" else mat_formula
                self.maturity_date_lbl.setText(mat_date.strftime("%d/%m/%y"))
                self.maturity_amount_formula_lbl.setText(f"₹ {mat_formula:,.2f}")
                self.maturity_amount_bank_lbl.setText(f"₹ {mat_bank:,.2f}")
                self.maturity_amount_lbl.setText(f"₹ {selected:,.2f}")
            else:
                self.maturity_date_lbl.setText("—")
                self.maturity_amount_formula_lbl.setText("—")
                self.maturity_amount_bank_lbl.setText("—")
                self.maturity_amount_lbl.setText("—")
        except (ValueError, Exception):
            self.maturity_date_lbl.setText("—")
            self.maturity_amount_formula_lbl.setText("—")
            self.maturity_amount_bank_lbl.setText("—")
            self.maturity_amount_lbl.setText("—")

    def _next_financial_year(self, fy: str) -> str:
        start = int(fy.split("-")[0]) + 1
        return f"{start}-{str(start + 1)[2:]}"

    def _input_snapshot(self) -> dict | None:
        try:
            principal = float(self.principal_input.text() or 0)
            rate = float(self.rate_input.text() or 0)
            tenure_years = int(self.tenure_years_input.text() or 0)
            tenure_months = int(self.tenure_months_input.text() or 0)
            tenure_days = int(self.tenure_days_input.text() or 0)
            compounding = self.compounding_combo.currentText()
            method = self.amount_method_combo.currentData() or "Formula"
            start = self.start_date.date().toPyDate()

            if principal <= 0 or rate <= 0:
                return None
            if tenure_years <= 0 and tenure_months <= 0 and tenure_days <= 0:
                return None

            maturity_date = calculate_fd_maturity_date(start, tenure_years, tenure_months, tenure_days)
            maturity_formula = calculate_fd_maturity_flexible(
                principal, rate, start, maturity_date, compounding,
                tenure_years, tenure_months, tenure_days
            )
            maturity_bank = calculate_fd_maturity_bank_style(
                principal, rate, start, maturity_date, compounding,
                tenure_years, tenure_months, tenure_days
            )
            maturity_selected = maturity_bank if method == "BankStyle" else maturity_formula

            if not (self.expected_interest_input.text() or "").strip():
                self.expected_interest_input.setText(f"{(maturity_selected - principal):.2f}")

            return {
                "principal": principal,
                "rate": rate,
                "tenure_years": tenure_years,
                "tenure_months": tenure_months,
                "tenure_days": tenure_days,
                "compounding": compounding,
                "method": method,
                "start": start,
                "maturity_date": maturity_date,
                "maturity_formula": maturity_formula,
                "maturity_bank": maturity_bank,
                "maturity_selected": maturity_selected,
            }
        except (ValueError, Exception):
            return None

    def _fy_interest_from_snapshot(self, snap: dict, financial_year: str) -> tuple[float, int]:
        fy_start, fy_end = fy_date_range(financial_year)
        overlap_start = max(snap["start"], fy_start)
        overlap_end = min(snap["maturity_date"], fy_end)
        if overlap_start > overlap_end:
            return 0.0, 0

        overlap_days = (overlap_end - overlap_start).days + 1
        total_days = (snap["maturity_date"] - snap["start"]).days + 1
        total_interest = snap["maturity_selected"] - snap["principal"]
        fy_interest = (total_interest * overlap_days) / total_days
        return round(fy_interest, 2), overlap_days

    def _quarter_rows_from_snapshot(self, snap: dict) -> list[dict]:
        total_interest = snap["maturity_selected"] - snap["principal"]
        rows = calculate_fd_quarterly_credit_breakdown(
            principal=float(snap["principal"]),
            rate=float(snap["rate"]),
            start_date=snap["start"],
            maturity_date=snap["maturity_date"],
            compounding=snap["compounding"],
            total_interest=float(total_interest),
        )
        return [{
            **r,
            "period": f"{r['period_start']} to {r['period_end']}",
        } for r in rows]

    def _build_report_text(self, snap: dict) -> str:
        method_text = "Bank-style Daily (Leap-aware)" if snap["method"] == "BankStyle" else "Current Formula"
        total_interest = snap["maturity_selected"] - snap["principal"]

        quarter_rows = self._quarter_rows_from_snapshot(snap)

        lines = [
            "FD Calculation Report",
            "=" * 70,
            f"Principal:            Rs {snap['principal']:,.2f}",
            f"Rate:                 {snap['rate']:.2f}%",
            f"Compounding:          {snap['compounding']}",
            f"Start Date:           {snap['start'].strftime('%d/%m/%y')}",
            f"Maturity Date:        {snap['maturity_date'].strftime('%d/%m/%y')}",
            f"Tenure Input:         {snap['tenure_years']}y {snap['tenure_months']}m {snap['tenure_days']}d",
            "",
            "Method-wise Maturity",
            "-" * 70,
            f"Current Formula:      Rs {snap['maturity_formula']:,.2f}",
            f"Bank-style Daily:     Rs {snap['maturity_bank']:,.2f}",
            f"Selected Method:      {method_text}",
            f"Selected Maturity:    Rs {snap['maturity_selected']:,.2f}",
            f"Selected Interest:    Rs {total_interest:,.2f}",
            "",
            "Quarter-wise Interest Allocation (Selected Method)",
            "-" * 70,
            "FY         AY         Quarter  Days  Interest",
        ]

        current_fy = get_current_financial_year()
        next_fy = self._next_financial_year(current_fy)
        current_fy_interest = 0.0
        next_fy_interest = 0.0

        for row in quarter_rows:
            lines.append(f"{row['fy']:<10} {row['ay']:<10} {row['quarter']:<8} {row['days']:<5} Rs {row['interest']:,.2f}")
            if row["fy"] == current_fy:
                current_fy_interest += row["interest"]
            if row["fy"] == next_fy:
                next_fy_interest += row["interest"]

        lines.extend([
            "",
            f"Current FY ({current_fy}) Interest: Rs {current_fy_interest:,.2f}",
            f"Next FY ({next_fy}) Interest:    Rs {next_fy_interest:,.2f}",
        ])

        return "\n".join(lines)

    def _on_show_calculations(self):
        snap = self._input_snapshot()
        if not snap:
            QMessageBox.warning(
                self,
                "Incomplete Input",
                "Enter valid Principal, Rate, and at least one tenure value (Years/Months/Days)."
            )
            return

        report = self._build_report_text(snap)
        quarter_rows = self._quarter_rows_from_snapshot(snap)

        dlg = QDialog(self)
        dlg.setWindowTitle("FD Calculation Details")
        dlg.setMinimumSize(860, 620)
        v = QVBoxLayout(dlg)
        v.setContentsMargins(16, 14, 16, 12)
        v.setSpacing(10)

        title = QLabel("Detailed FD Calculation")
        title.setStyleSheet(f"font-weight: 700; color: {Theme.TEXT_PRIMARY}; font-size: 14px;")
        v.addWidget(title)

        summary = QLabel(
            f"Selected Maturity: ₹ {snap['maturity_selected']:,.2f}   |   "
            f"Selected Interest: ₹ {snap['maturity_selected'] - snap['principal']:,.2f}"
        )
        summary.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; font-weight: 600;")
        v.addWidget(summary)

        q_title = QLabel("Quarter-wise Interest")
        q_title.setStyleSheet(f"font-weight: 700; color: {Theme.TEXT_PRIMARY};")
        v.addWidget(q_title)

        q_table = QTableWidget()
        q_table.setColumnCount(6)
        q_table.setHorizontalHeaderLabels(["FY", "AY", "Quarter", "Period", "Days", "Interest"])
        q_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        for i, w in enumerate([90, 90, 70, 240, 70, 120]):
            q_table.setColumnWidth(i, w)
        q_table.setRowCount(len(quarter_rows))
        for i, row in enumerate(quarter_rows):
            q_table.setItem(i, 0, QTableWidgetItem(row["fy"]))
            q_table.setItem(i, 1, QTableWidgetItem(row["ay"]))
            q_table.setItem(i, 2, QTableWidgetItem(row["quarter"]))
            q_table.setItem(i, 3, QTableWidgetItem(row["period"]))
            q_table.setItem(i, 4, QTableWidgetItem(str(row["days"])))
            q_table.setItem(i, 5, QTableWidgetItem(f"₹ {row['interest']:,.2f}"))
            q_table.setRowHeight(i, 28)
        q_table.setMinimumHeight(220)
        q_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        q_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        v.addWidget(q_table)

        txt = QPlainTextEdit()
        txt.setReadOnly(True)
        txt.setPlainText(report)
        txt.setMaximumHeight(210)
        v.addWidget(txt)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_close = Theme.btn("Close", "primary", height=36, min_width=95)
        btn_close.clicked.connect(dlg.accept)
        btn_row.addWidget(btn_close)
        v.addLayout(btn_row)

        dlg.exec()

    def _load_fd(self):
        from models.fixed_deposit import get_fd
        self.fd_data = get_fd(self.fd_id)
        if not self.fd_data: return
        for i in range(self.person_combo.count()):
            if self.person_combo.itemData(i) == self.fd_data["person_id"]:
                self.person_combo.setCurrentIndex(i); break
        for i in range(self.account_combo.count()):
            if self.account_combo.itemData(i) == self.fd_data["account_id"]:
                self.account_combo.setCurrentIndex(i); break
        self.principal_input.setText(str(self.fd_data["principal_amount"]))
        self.fd_no_input.setText(self.fd_data.get("fd_reference_no") or "")
        self.rate_input.setText("" if self.fd_data.get("interest_rate") is None else str(self.fd_data["interest_rate"]))
        years = self.fd_data.get("tenure_years")
        months = self.fd_data.get("tenure_months")
        days = self.fd_data.get("tenure_days")
        self.tenure_years_input.setText("" if years in (None, 0) else str(years))
        self.tenure_months_input.setText("" if months in (None, 0) else str(months))
        self.tenure_days_input.setText("" if days in (None, 0) else str(days))
        self.compounding_combo.setCurrentText(self.fd_data.get("compounding_type") or "Quarterly")
        method = self.fd_data.get("maturity_calc_method") or "Formula"
        idx = self.amount_method_combo.findData(method)
        self.amount_method_combo.setCurrentIndex(idx if idx >= 0 else 0)
        exp_i = self.fd_data.get("expected_interest_amount")
        act_i = self.fd_data.get("actual_interest_amount")
        self.expected_interest_input.setText("" if exp_i in (None, 0) else str(exp_i))
        self.actual_interest_input.setText("" if act_i in (None, 0) else str(act_i))
        self.fd_count_spin.setValue(1)
        self.fd_count_spin.setEnabled(False)
        self.fd_numbers_input.setEnabled(False)
        s = date.fromisoformat(self.fd_data["start_date"])
        self.start_date.setDate(QDate(s.year, s.month, s.day))
        self._calc()

    def _on_save(self):
        try:
            account_id = self.account_combo.currentData()
            person_id  = self.person_combo.currentData()
            principal  = float(self.principal_input.text())
            rate       = float(self.rate_input.text())
            tenure_years  = int(self.tenure_years_input.text() or 0)
            tenure_months = int(self.tenure_months_input.text() or 0)
            tenure_days   = int(self.tenure_days_input.text() or 0)
            compounding= self.compounding_combo.currentText()
            start      = self.start_date.date().toPyDate()
            fd_ref_no = (self.fd_no_input.text() or "").strip() or None
            expected_interest = float(self.expected_interest_input.text()) if (self.expected_interest_input.text() or "").strip() else None
            actual_interest = float(self.actual_interest_input.text()) if (self.actual_interest_input.text() or "").strip() else None
            if not account_id or principal<=0 or rate<=0 or rate>100 or (tenure_years<=0 and tenure_months<=0 and tenure_days<=0):
                QMessageBox.warning(self,"Invalid","Please fill all fields correctly (interest rate must be between 0 and 100)."); return
            mat_date = calculate_fd_maturity_date(start, tenure_years, tenure_months, tenure_days)
            mat_formula = calculate_fd_maturity_flexible(
                principal, rate, start, mat_date, compounding,
                tenure_years, tenure_months, tenure_days
            )
            mat_bank = calculate_fd_maturity_bank_style(
                principal, rate, start, mat_date, compounding,
                tenure_years, tenure_months, tenure_days,
            )
            method = self.amount_method_combo.currentData() or "Formula"
            mat_amt = mat_bank if method == "BankStyle" else mat_formula
            if expected_interest is None:
                expected_interest = round(mat_amt - principal, 2)
            if self.mode == "add":
                fd_count = int(self.fd_count_spin.value())
                fd_numbers = [n.strip() for n in (self.fd_numbers_input.text() or "").split(",") if n.strip()]
                if fd_count > 1 and fd_numbers and len(fd_numbers) != fd_count:
                    QMessageBox.warning(self, "Invalid FD Nos", "For bulk create, provide exactly one FD no per record.")
                    return

                if fd_count > 1 and not fd_numbers:
                    QMessageBox.warning(self, "FD Nos Required", "For bulk create, provide comma-separated unique FD numbers.")
                    return

                created = 0
                for i in range(fd_count):
                    ref = fd_ref_no
                    if fd_numbers:
                        ref = fd_numbers[i]
                    fd_id = add_fd(
                        account_id, person_id, principal, start.isoformat(),
                        tenure_months, rate, compounding, mat_date.isoformat(), mat_amt,
                        mat_formula, mat_bank, method,
                        tenure_years, tenure_days,
                        ref,
                        expected_interest,
                        actual_interest,
                    )
                    allocate_fd_interest_to_fy(fd_id)
                    created += 1
                QMessageBox.information(self, "Success", f"{created} Fixed Deposit record(s) added!")
            else:
                update_fd(self.fd_id, principal, start.isoformat(), tenure_months, rate,
                          compounding, mat_date.isoformat(), mat_amt, "Active",
                          mat_formula, mat_bank, method,
                          tenure_years, tenure_days,
                          fd_ref_no,
                          expected_interest,
                          actual_interest,
                          self.fd_data.get("linked_transaction_id"),
                          self.fd_data.get("source_statement_file"),
                          self.fd_data.get("source_transaction_id"))
                allocate_fd_interest_to_fy(self.fd_id)
                QMessageBox.information(self, "Success", "Fixed Deposit updated!")
            self.accept()
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Please enter valid numeric values.")
        except Exception as e:
            QMessageBox.warning(self, "Could Not Save", f"Failed to save the fixed deposit: {e}")


class LinkFDTransactionDialog(QDialog):
    def __init__(self, parent, fd_id: int):
        super().__init__(parent)
        self.fd_id = fd_id
        self._selected_txn_id = None
        self.setWindowTitle("Link Account Transaction")
        self.setMinimumSize(920, 520)
        self._build_ui()
        self._load_rows()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 18)
        layout.setSpacing(12)

        title = QLabel("Fetch and link transaction from the same account")
        title.setStyleSheet(f"font-weight: 700; color: {Theme.TEXT_PRIMARY};")
        layout.addWidget(title)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Date", "Type", "Amount", "Category", "Mode", "Description", "Txn ID"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        for i, w in enumerate([95, 75, 110, 120, 95, 340, 70]):
            self.table.setColumnWidth(i, w)
        layout.addWidget(self.table)

        btns = QHBoxLayout()
        btns.addStretch()

        btn_unlink = Theme.btn("Unlink", "danger", height=36, min_width=90)
        btn_unlink.clicked.connect(self._on_unlink)
        btns.addWidget(btn_unlink)

        btn_cancel = Theme.btn("Cancel", "secondary", height=36, min_width=90)
        btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_cancel)

        btn_link = Theme.btn("Link Selected", "primary", height=36, min_width=120)
        btn_link.clicked.connect(self._on_link)
        btns.addWidget(btn_link)

        layout.addLayout(btns)

    def _load_rows(self):
        rows = get_fd_link_candidates(self.fd_id)
        self.table.setRowCount(0)
        for row in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(format_display_date(row.get("transaction_date"))))
            self.table.setItem(r, 1, QTableWidgetItem(display_transaction_type(row.get("transaction_type") or "—")))
            self.table.setItem(r, 2, QTableWidgetItem(f"₹ {float(row.get('amount') or 0):,.2f}"))
            self.table.setItem(r, 3, QTableWidgetItem(row.get("category") or "—"))
            self.table.setItem(r, 4, QTableWidgetItem(row.get("mode") or "—"))
            self.table.setItem(r, 5, QTableWidgetItem((row.get("description") or "")[:220]))
            self.table.setItem(r, 6, QTableWidgetItem(str(row.get("transaction_id"))))
            self.table.setRowHeight(r, 30)

    def _on_unlink(self):
        unlink_fd_transaction(self.fd_id)
        self._selected_txn_id = None
        self.accept()

    def _on_link(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Please select a transaction to link.")
            return
        self._selected_txn_id = int(self.table.item(row, 6).text())
        self.accept()

    def get_selected_transaction_id(self):
        return self._selected_txn_id
