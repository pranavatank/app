"""
ui/income_management_screen.py — Income expectation and tracking with modern UI
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QHeaderView, QDialog, QFormLayout,
    QDateEdit, QDoubleSpinBox, QTextEdit, QMessageBox, QFrame, QLineEdit,
    QTableWidget, QTableWidgetItem
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QFont, QColor

from ui.widgets.excel_table import ExcelTableWithStats
from ui.theme import Theme
from ui.date_utils import format_display_date
from core.session import session
from config import get_current_financial_year, get_all_financial_years
from models.person import get_all_persons
from models.bank_account import get_accounts_for_person, get_all_accounts
from models.income_expectation import (
    add_income_expectation, get_income_expectations, update_income_expectation,
    delete_income_expectation, link_actual_transaction, unlink_actual_transaction,
    auto_link_income_expectations
)
from models.transaction import get_transactions

INCOME_TYPES = ["Salary", "Pension", "Dividend", "Interest", "Rental Income", "Business Income", "Other Income"]
FREQUENCIES = ["Monthly", "Quarterly", "Half-Yearly", "Yearly", "One-Time"]


class IncomeManagementScreen(QWidget):
    def __init__(self, parent_window=None):
        super().__init__()
        self._parent_window = parent_window
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 18)
        layout.setSpacing(16)

        # Header with actions
        header = QHBoxLayout()
        title = QLabel("Income Management")
        title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        title.setStyleSheet(Theme.title_style(15))
        header.addWidget(title)
        header.addStretch()

        btn_add = Theme.btn("＋  Add Expected Income", "primary", height=38, min_width=170)
        btn_add.clicked.connect(self._add_expectation)
        header.addWidget(btn_add)

        btn_auto_link = Theme.btn("⚡  Auto-Link All", "success", height=38, min_width=130)
        btn_auto_link.clicked.connect(self._auto_link_all)
        header.addWidget(btn_auto_link)

        btn_edit = Theme.btn("✏  Edit", "edit", height=38, min_width=90)
        btn_edit.clicked.connect(self._edit_expectation)
        header.addWidget(btn_edit)

        btn_delete = Theme.btn("🗑  Delete", "danger", height=38, min_width=95)
        btn_delete.clicked.connect(self._delete_expectation)
        header.addWidget(btn_delete)

        layout.addLayout(header)

        # Filter bar
        layout.addWidget(self._build_filter_bar())

        # Summary cards
        layout.addWidget(self._build_summary_cards())

        # Table with Excel-like features
        self.table_widget = ExcelTableWithStats(show_checkboxes=True)
        self.table = self.table_widget.table
        self.table.setHeaders([
            "Person", "Income Type", "Frequency", "Expected Date", "Expected Amount",
            "Actual Date", "Actual Amount", "Variance", "Status", "Account", "ID"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.doubleClicked.connect(self._edit_expectation)
        self.table.keyPressEvent = self._handle_key_press
        
        for i, w in enumerate([120, 130, 100, 110, 130, 110, 130, 110, 90, 160, 0]):
            self.table.setColumnWidth(i, w)
        self.table.setColumnHidden(10, True)
        
        layout.addWidget(self.table_widget, stretch=1)

        self.status_label = QLabel("")
        self.status_label.setObjectName("mutedLabel")
        layout.addWidget(self.status_label)

    def _handle_key_press(self, event):
        """Handle keyboard shortcuts including Delete key"""
        from PyQt6.QtCore import Qt
        if event.key() == Qt.Key.Key_Delete:
            self._delete_selected_expectations()
        else:
            super(type(self.table), self.table).keyPressEvent(event)

    def _delete_selected_expectations(self):
        """Delete all checked expectations"""
        checked_rows = []
        for row in range(self.table.rowCount()):
            checkbox = self.table.cellWidget(row, 0)
            if checkbox and checkbox.findChild(QWidget).isChecked():
                exp_id = int(self.table.item(row, 10).text())
                checked_rows.append((row, exp_id))
        
        if not checked_rows:
            QMessageBox.warning(self, "No Selection", "Please select expectations to delete.")
            return
        
        reply = QMessageBox.question(
            self, "Delete Expectations",
            f"Delete {len(checked_rows)} expectation{'s' if len(checked_rows) != 1 else ''}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            for _, exp_id in checked_rows:
                delete_income_expectation(exp_id)
            self.refresh()
            if self._parent_window:
                self._parent_window.refresh_overview()

    def _build_filter_bar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("filterBar")
        bar.setStyleSheet(Theme.filter_bar_style())
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(12)

        def lbl(t):
            l = QLabel(t)
            l.setStyleSheet(Theme.section_label_style())
            return l

        layout.addWidget(lbl("Person"))
        self.f_person = QComboBox()
        self.f_person.setFixedWidth(140)
        self.f_person.setFixedHeight(32)
        self.f_person.setAccessibleName("Income person filter")
        self.f_person.addItem("All Persons", userData=None)
        layout.addWidget(self.f_person)

        layout.addWidget(lbl("FY"))
        self.f_fy = QComboBox()
        self.f_fy.setFixedWidth(95)
        self.f_fy.setFixedHeight(32)
        self.f_fy.setAccessibleName("Income financial year filter")
        for fy in reversed(get_all_financial_years(since_year=2020)):
            self.f_fy.addItem(fy)
        self.f_fy.setCurrentText(session.selected_fy)
        layout.addWidget(self.f_fy)

        layout.addWidget(lbl("Type"))
        self.f_type = QComboBox()
        self.f_type.setFixedWidth(130)
        self.f_type.setFixedHeight(32)
        self.f_type.setAccessibleName("Income type filter")
        self.f_type.addItem("All Types", userData=None)
        for it in INCOME_TYPES:
            self.f_type.addItem(it)
        layout.addWidget(self.f_type)

        layout.addWidget(lbl("Status"))
        self.f_status = QComboBox()
        self.f_status.setFixedWidth(110)
        self.f_status.setFixedHeight(32)
        self.f_status.setAccessibleName("Income status filter")
        self.f_status.addItems(["All", "Pending", "Received", "Overdue"])
        layout.addWidget(self.f_status)

        layout.addStretch()

        btn_filter = Theme.btn("Apply", "primary", height=32, min_width=80)
        btn_filter.setAccessibleName("Apply income filters")
        btn_filter.clicked.connect(self.refresh)
        layout.addWidget(btn_filter)

        btn_clear = Theme.btn("Clear", "secondary", height=32, min_width=70)
        btn_clear.setAccessibleName("Clear income filters")
        btn_clear.clicked.connect(self._clear_filters)
        layout.addWidget(btn_clear)

        return bar

    def _build_summary_cards(self) -> QWidget:
        container = QFrame()
        container.setStyleSheet(f"background: transparent; border: none;")
        layout = QHBoxLayout(container)
        layout.setSpacing(14)
        layout.setContentsMargins(0, 0, 0, 0)

        self.card_expected = self._create_summary_card("Expected Total", "₹ —", Theme.PRIMARY)
        self.card_actual = self._create_summary_card("Actual Received", "₹ —", Theme.SUCCESS)
        self.card_pending = self._create_summary_card("Pending", "₹ —", Theme.WARNING)
        self.card_variance = self._create_summary_card("Variance", "₹ —", Theme.INFO)

        layout.addWidget(self.card_expected)
        layout.addWidget(self.card_actual)
        layout.addWidget(self.card_pending)
        layout.addWidget(self.card_variance)

        return container

    def _create_summary_card(self, title: str, value: str, color: str) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        card.setFixedHeight(85)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)

        lbl_title = QLabel(title)
        lbl_title.setStyleSheet(Theme.section_label_style())
        layout.addWidget(lbl_title)

        lbl_value = QLabel(value)
        lbl_value.setObjectName("cardValue")
        lbl_value.setStyleSheet(Theme.text_style(color=color, size=20, weight=700))
        layout.addWidget(lbl_value)

        layout.addStretch()
        return card

    def refresh(self):
        self._reload_persons()
        self._fetch_and_display()

    def _reload_persons(self):
        self.f_person.blockSignals(True)
        self.f_person.clear()
        persons = get_all_persons()
        self.f_person.addItem("All Persons", userData=None)
        for p in persons:
            self.f_person.addItem(p["full_name"], userData=p["person_id"])
        if session.selected_person_id:
            for i in range(self.f_person.count()):
                if self.f_person.itemData(i) == session.selected_person_id:
                    self.f_person.setCurrentIndex(i)
                    break
        self.f_person.blockSignals(False)

    def _fetch_and_display(self):
        pid = self.f_person.currentData()
        fy = self.f_fy.currentText() or None
        income_type = self.f_type.currentText()
        income_type = None if income_type == "All Types" else income_type
        status_filter = self.f_status.currentText()
        from datetime import datetime
        today = datetime.now().date()

        rows = get_income_expectations(person_id=pid, financial_year=fy, income_type=income_type)

        # Apply status filter
        if status_filter != "All":
            filtered = []
            for r in rows:
                exp_date_str = r["expected_date"]
                if "-" in exp_date_str:
                    exp_date = datetime.strptime(exp_date_str, "%Y-%m-%d").date()
                else:
                    # Day-only for recurring - use current month
                    day = int(exp_date_str)
                    exp_date = today.replace(day=min(day, 28))
                
                if status_filter == "Pending":
                    if r["actual_transaction_id"] is None and exp_date >= today:
                        filtered.append(r)
                elif status_filter == "Received":
                    if r["actual_transaction_id"] is not None:
                        filtered.append(r)
                elif status_filter == "Overdue":
                    if r["actual_transaction_id"] is None and exp_date < today:
                        filtered.append(r)
            rows = filtered

        self._populate_table(rows)
        self._update_summary(rows)

    def _populate_table(self, rows):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))

        from datetime import datetime
        from PyQt6.QtWidgets import QTableWidgetItem
        today = datetime.now().date()

        for idx, row in enumerate(rows):
            # Handle both full dates and day-only values
            exp_date_str = row["expected_date"]
            if "-" in exp_date_str:
                exp_date = datetime.strptime(exp_date_str, "%Y-%m-%d").date()
            else:
                # Day-only for recurring frequencies - use current month for comparison
                day = int(exp_date_str)
                exp_date = today.replace(day=min(day, 28))  # Safe day for comparison
            
            is_linked = row["actual_transaction_id"] is not None
            is_overdue = not is_linked and exp_date < today

            def item(text, align=Qt.AlignmentFlag.AlignLeft):
                it = QTableWidgetItem(str(text) if text is not None else "—")
                it.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
                return it

            def amt_item(val, color=None):
                it = QTableWidgetItem(f"₹ {val:,.2f}" if val is not None else "—")
                it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if color:
                    it.setForeground(QColor(color))
                return it

            self.table.setItem(idx, 0, item(row["person_name"]))
            self.table.setItem(idx, 1, item(row["income_type"]))
            self.table.setItem(idx, 2, item(row["frequency"]))
            # Display day-only as "Day X" for recurring frequencies
            exp_display = format_display_date(row["expected_date"]) if "-" in row["expected_date"] else f"Day {row['expected_date']}"
            self.table.setItem(idx, 3, item(exp_display))
            self.table.setItem(idx, 4, amt_item(row["expected_amount"]))
            
            actual_date = format_display_date(row.get("actual_date"))
            self.table.setItem(idx, 5, item(actual_date))
            
            actual_amt = row.get("actual_amount")
            self.table.setItem(idx, 6, amt_item(actual_amt, Theme.SUCCESS if actual_amt else None))

            # Variance
            if actual_amt:
                variance = actual_amt - row["expected_amount"]
                var_color = Theme.SUCCESS if variance >= 0 else Theme.DANGER
                var_text = f"₹ {variance:+,.2f}"
                var_item = QTableWidgetItem(var_text)
                var_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                var_item.setForeground(QColor(var_color))
                self.table.setItem(idx, 7, var_item)
            else:
                self.table.setItem(idx, 7, item("—"))

            # Status
            if is_linked:
                status = "Received"
                status_color = Theme.SUCCESS
            elif is_overdue:
                status = "Overdue"
                status_color = Theme.DANGER
            else:
                status = "Pending"
                status_color = Theme.WARNING
            
            status_item = item(status)
            status_item.setForeground(QColor(status_color))
            self.table.setItem(idx, 8, status_item)

            self.table.setItem(idx, 9, item(f"{row.get('bank_display_name', row['bank_name'])} ({row['account_type']})"))
            self.table.setItem(idx, 10, QTableWidgetItem(str(row["expectation_id"])))
            self.table.setRowHeight(idx, 32)

        self.table.setSortingEnabled(True)
        count = self.table.rowCount()
        self.status_label.setText(f"Showing {count} income expectation{'s' if count != 1 else ''}.")

    def _update_summary(self, rows):
        expected_total = sum(r["expected_amount"] for r in rows)
        actual_total = sum(r.get("actual_amount") or 0 for r in rows if r["actual_transaction_id"])
        pending_total = sum(r["expected_amount"] for r in rows if not r["actual_transaction_id"])
        variance = actual_total - (expected_total - pending_total)

        self.card_expected.findChild(QLabel, "cardValue").setText(session.mask(expected_total))
        self.card_actual.findChild(QLabel, "cardValue").setText(session.mask(actual_total))
        self.card_pending.findChild(QLabel, "cardValue").setText(session.mask(pending_total))
        
        var_label = self.card_variance.findChild(QLabel, "cardValue")
        var_label.setText(session.mask(variance))
        var_label.setStyleSheet(f"color: {Theme.SUCCESS if variance >= 0 else Theme.DANGER}; font-size: 20px; font-weight: 700;")

    def _add_expectation(self):
        persons = get_all_persons()
        if not persons:
            QMessageBox.information(self, "No Persons", "Add a family member first.")
            return
        
        dlg = IncomeExpectationDialog(self, persons=persons,
                                     preselect_person_id=session.selected_person_id)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            frequency = data["frequency"]
            
            if frequency in ["Monthly", "Quarterly", "Half-Yearly"]:
                count_map = {"Monthly": 12, "Quarterly": 4, "Half-Yearly": 2}
                expected_count = count_map[frequency]
                reply = QMessageBox.question(
                    self, "Create Multiple Records",
                    f"This will create {expected_count} {frequency.lower()} records for FY {data['financial_year']}. Continue?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return
            
            add_income_expectation(**data)
            self.refresh()
            if self._parent_window:
                self._parent_window.refresh_overview()
            
            if frequency in ["Monthly", "Quarterly", "Half-Yearly"]:
                QMessageBox.information(self, "Success", f"Created {frequency.lower()} income expectations for the financial year.")

    def _edit_expectation(self):
        exp = self._selected_expectation()
        if not exp:
            return
        
        dlg = IncomeExpectationDialog(self, persons=get_all_persons(), existing=exp)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            update_income_expectation(
                exp["expectation_id"],
                expected_amount=data["expected_amount"],
                expected_date=data["expected_date"],
                frequency=data["frequency"],
                notes=data.get("notes")
            )
            self.refresh()
            if self._parent_window:
                self._parent_window.refresh_overview()

    def _delete_expectation(self):
        """Delete checked expectations or current selection"""
        checked_rows = []
        for row in range(self.table.rowCount()):
            checkbox = self.table.cellWidget(row, 0)
            if checkbox and checkbox.findChild(QWidget).isChecked():
                exp_id = int(self.table.item(row, 10).text())
                checked_rows.append(exp_id)
        
        if checked_rows:
            reply = QMessageBox.question(
                self, "Delete Expectations",
                f"Delete {len(checked_rows)} expectation{'s' if len(checked_rows) != 1 else ''}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                for exp_id in checked_rows:
                    delete_income_expectation(exp_id)
                self.refresh()
                if self._parent_window:
                    self._parent_window.refresh_overview()
        else:
            exp = self._selected_expectation()
            if not exp:
                return
            
            reply = QMessageBox.question(
                self, "Delete Expectation",
                f"Delete {exp['income_type']} expectation of ₹{exp['expected_amount']:,.2f}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                delete_income_expectation(exp["expectation_id"])
                self.refresh()
                if self._parent_window:
                    self._parent_window.refresh_overview()

    def _auto_link_all(self):
        """Auto-link all unlinked expectations with matching transactions."""
        pid = self.f_person.currentData()
        fy = self.f_fy.currentText()
        
        if not pid:
            QMessageBox.information(
                self, "Select Person",
                "Please select a specific person to auto-link their income."
            )
            return
        
        # Get all accounts for this person
        accounts = get_accounts_for_person(pid)
        if not accounts:
            QMessageBox.information(self, "No Accounts", "No accounts found for this person.")
            return
        
        total_linked = 0
        for account in accounts:
            linked = auto_link_income_expectations(pid, account["account_id"], fy)
            total_linked += linked
        
        if total_linked > 0:
            QMessageBox.information(
                self, "Auto-Link Complete",
                f"Successfully linked {total_linked} expectation{'s' if total_linked != 1 else ''} with actual transactions."
            )
            self.refresh()
            if self._parent_window:
                self._parent_window.refresh_overview()
        else:
            QMessageBox.information(
                self, "No Matches",
                "No matching transactions found to link automatically.\n\n"
                "Transactions must be in the same month as expected date."
            )

    def _selected_expectation(self):
        if not self.table.selectedItems():
            QMessageBox.warning(self, "No Selection", "Please select an income expectation.")
            return None
        
        row = self.table.currentRow()
        exp_id = int(self.table.item(row, 10).text())
        
        pid = self.f_person.currentData()
        fy = self.f_fy.currentText()
        rows = get_income_expectations(person_id=pid, financial_year=fy)
        return next((r for r in rows if r["expectation_id"] == exp_id), None)

    def _clear_filters(self):
        self.f_person.setCurrentIndex(0)
        self.f_fy.setCurrentText(get_current_financial_year())
        self.f_type.setCurrentIndex(0)
        self.f_status.setCurrentIndex(0)
        self.refresh()


class IncomeExpectationDialog(QDialog):
    def __init__(self, parent=None, persons=None, existing=None, preselect_person_id=None):
        super().__init__(parent)
        self._persons = persons or []
        self._existing = existing
        self._preselect_pid = preselect_person_id
        self.setWindowTitle("Edit Income Expectation" if existing else "Add Income Expectation")
        self.setMinimumWidth(520)
        self.setModal(True)
        self._build_ui()
        if existing:
            self._prefill(existing)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(28, 24, 28, 20)

        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.cmb_person = QComboBox()
        for p in self._persons:
            self.cmb_person.addItem(p["full_name"], userData=p["person_id"])
        if self._preselect_pid:
            for i in range(self.cmb_person.count()):
                if self.cmb_person.itemData(i) == self._preselect_pid:
                    self.cmb_person.setCurrentIndex(i)
                    break
        form.addRow("Person *", self.cmb_person)

        self.cmb_account = QComboBox()
        self._populate_accounts()
        form.addRow("Account *", self.cmb_account)
        
        # Connect signal AFTER both widgets are created
        self.cmb_person.currentIndexChanged.connect(self._on_person_changed)

        self.cmb_type = QComboBox()
        self.cmb_type.addItems(INCOME_TYPES)
        form.addRow("Income Type *", self.cmb_type)

        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setRange(0.01, 99_999_999.99)
        self.amount_spin.setDecimals(2)
        self.amount_spin.setGroupSeparatorShown(True)
        self.amount_spin.setPrefix("₹ ")
        form.addRow("Expected Amount *", self.amount_spin)

        self.cmb_frequency = QComboBox()
        self.cmb_frequency.addItems(FREQUENCIES)
        self.cmb_frequency.currentTextChanged.connect(self._on_frequency_changed)
        form.addRow("Frequency *", self.cmb_frequency)

        # Date input changes based on frequency
        self.date_container = QWidget()
        self.date_layout = QHBoxLayout(self.date_container)
        self.date_layout.setContentsMargins(0, 0, 0, 0)
        
        self.day_spin = QComboBox()
        for i in range(1, 32):
            suffix = "st" if i in [1, 21, 31] else "nd" if i in [2, 22] else "rd" if i in [3, 23] else "th"
            self.day_spin.addItem(f"{i}{suffix}", userData=i)
        self.date_layout.addWidget(self.day_spin)
        
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setDisplayFormat("dd/MM/yy")
        self.date_layout.addWidget(self.date_edit)
        self.date_edit.hide()
        
        form.addRow("Expected Date *", self.date_container)

        self.fy_edit = QComboBox()
        for fy in reversed(get_all_financial_years(since_year=2020)):
            self.fy_edit.addItem(fy)
        self.fy_edit.setCurrentText(get_current_financial_year())
        if self._existing:
            self.fy_edit.setEnabled(False)  # Can't change FY when editing
        form.addRow("Financial Year *", self.fy_edit)
        
        if self._existing:
            info_label = QLabel("Note: Editing only updates this specific record")
            info_label.setStyleSheet(f"color: {Theme.WARNING}; font-size: 11px; font-style: italic;")
            form.addRow("", info_label)

        self.notes_edit = QTextEdit()
        self.notes_edit.setFixedHeight(68)
        self.notes_edit.setPlaceholderText("Optional notes...")
        form.addRow("Notes", self.notes_edit)
        
        # Show linked transaction if exists
        if self._existing and self._existing.get("actual_transaction_id"):
            linked_frame = QFrame()
            linked_frame.setStyleSheet(f"""
                QFrame {{
                    background: {Theme.SUCCESS_LIGHT};
                    border: 1px solid {Theme.SUCCESS};
                    border-radius: 8px;
                    padding: 12px;
                }}
            """)
            linked_layout = QVBoxLayout(linked_frame)
            linked_layout.setSpacing(8)
            
            linked_title = QLabel("🔗  Linked Transaction")
            linked_title.setStyleSheet(f"color: {Theme.SUCCESS_DARK}; font-weight: 600; font-size: 12px;")
            linked_layout.addWidget(linked_title)
            
            linked_info = QLabel(
                f"Date: {format_display_date(self._existing.get('actual_date'))}\n"
                f"Amount: ₹{self._existing.get('actual_amount', 0):,.2f}\n"
                f"Description: {self._existing.get('description', 'N/A')}"
            )
            linked_info.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; font-size: 11px;")
            linked_layout.addWidget(linked_info)
            
            btn_unlink = Theme.btn("❌  Unlink Transaction", "danger", height=32, min_width=140)
            btn_unlink.clicked.connect(self._on_unlink)
            linked_layout.addWidget(btn_unlink)
            
            form.addRow("", linked_frame)
        else:
            btn_link = Theme.btn("🔗  Link to Transaction", "success", height=32, min_width=150)
            btn_link.clicked.connect(self._on_link_transaction)
            form.addRow("", btn_link)

        layout.addLayout(form)

        from PyQt6.QtWidgets import QDialogButtonBox
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Save" if self._existing else "Add")
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        self._on_frequency_changed(self.cmb_frequency.currentText())

    def _on_link_transaction(self):
        """Open dialog to link a transaction"""
        dlg = LinkActualDialog(self, expectation=self._existing)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            txn_id = dlg.get_selected_transaction_id()
            if txn_id:
                link_actual_transaction(self._existing["expectation_id"], txn_id)
                QMessageBox.information(self, "Linked", "Transaction has been linked.")
                self.accept()

    def _on_unlink(self):
        """Unlink the transaction from this expectation"""
        reply = QMessageBox.question(
            self, "Unlink Transaction",
            "Are you sure you want to unlink this transaction?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            unlink_actual_transaction(self._existing["expectation_id"])
            QMessageBox.information(self, "Unlinked", "Transaction has been unlinked.")
            self.accept()  # Close dialog and refresh

    def _on_frequency_changed(self, frequency):
        if frequency in ["Monthly", "Quarterly", "Half-Yearly"]:
            self.day_spin.show()
            self.date_edit.hide()
        else:
            self.day_spin.hide()
            self.date_edit.show()

    def _populate_accounts(self):
        self.cmb_account.clear()
        pid = self.cmb_person.currentData()
        accounts = get_accounts_for_person(pid) if pid else []
        for a in accounts:
            self.cmb_account.addItem(
                f"{a.get('bank_display_name', a['bank_name'])} ({a['account_type']})",
                userData=a["account_id"]
            )

    def _on_person_changed(self):
        self._populate_accounts()

    def _prefill(self, exp):
        for i in range(self.cmb_person.count()):
            if self.cmb_person.itemData(i) == exp["person_id"]:
                self.cmb_person.setCurrentIndex(i)
                break
        
        self._populate_accounts()
        for i in range(self.cmb_account.count()):
            if self.cmb_account.itemData(i) == exp["account_id"]:
                self.cmb_account.setCurrentIndex(i)
                break

        idx = self.cmb_type.findText(exp["income_type"])
        if idx >= 0:
            self.cmb_type.setCurrentIndex(idx)

        self.amount_spin.setValue(exp["expected_amount"])

        idx = self.cmb_frequency.findText(exp["frequency"])
        if idx >= 0:
            self.cmb_frequency.setCurrentIndex(idx)

        # Set date based on frequency
        if exp["frequency"] in ["Monthly", "Quarterly", "Half-Yearly"]:
            # For recurring frequencies, expected_date is stored as day number (1-31)
            try:
                day = int(exp["expected_date"])
                for i in range(self.day_spin.count()):
                    if self.day_spin.itemData(i) == day:
                        self.day_spin.setCurrentIndex(i)
                        break
            except ValueError:
                # Fallback: try parsing as full date
                from datetime import datetime
                try:
                    date_obj = datetime.strptime(exp["expected_date"], "%Y-%m-%d")
                    day = date_obj.day
                    for i in range(self.day_spin.count()):
                        if self.day_spin.itemData(i) == day:
                            self.day_spin.setCurrentIndex(i)
                            break
                except ValueError:
                    pass
        else:
            qd = QDate.fromString(exp["expected_date"], "yyyy-MM-dd")
            if qd.isValid():
                self.date_edit.setDate(qd)

        self.fy_edit.setCurrentText(exp["financial_year"])
        self.notes_edit.setPlainText(exp.get("notes") or "")

    def _on_accept(self):
        if not self.cmb_account.currentData():
            QMessageBox.warning(self, "Missing", "Please select an account.")
            return
        if self.amount_spin.value() <= 0:
            QMessageBox.warning(self, "Invalid", "Amount must be > 0.")
            return
        self.accept()

    def get_data(self) -> dict:
        frequency = self.cmb_frequency.currentText()
        
        if frequency in ["Monthly", "Quarterly", "Half-Yearly"]:
            expected_date = str(self.day_spin.currentData())
        else:
            expected_date = self.date_edit.date().toString("yyyy-MM-dd")
        
        return {
            "person_id": self.cmb_person.currentData(),
            "account_id": self.cmb_account.currentData(),
            "income_type": self.cmb_type.currentText(),
            "expected_amount": self.amount_spin.value(),
            "expected_date": expected_date,
            "frequency": frequency,
            "financial_year": self.fy_edit.currentText(),
            "notes": self.notes_edit.toPlainText().strip() or None,
        }


class LinkActualDialog(QDialog):
    def __init__(self, parent=None, expectation=None):
        super().__init__(parent)
        self._expectation = expectation
        self.setWindowTitle("Link Actual Transaction")
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)
        self.setModal(True)
        self._build_ui()
        self._load_transactions()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 20, 24, 20)

        info = QLabel(f"Select actual transaction for: {self._expectation['income_type']} - ₹{self._expectation['expected_amount']:,.2f}")
        info.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; font-size: 13px; font-weight: 600;")
        layout.addWidget(info)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Date", "Category", "Amount", "Description", "ID"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setColumnHidden(4, True)
        layout.addWidget(self.table)

        from PyQt6.QtWidgets import QDialogButtonBox
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_transactions(self):
        # Get income transactions for the same person, account, and FY
        transactions = get_transactions(
            person_id=self._expectation["person_id"],
            account_id=self._expectation["account_id"],
            financial_year=self._expectation["financial_year"],
            transaction_type="Income"
        )
        
        # Filter out already linked transactions
        from models.income_expectation import get_income_expectations
        all_expectations = get_income_expectations(
            person_id=self._expectation["person_id"],
            financial_year=self._expectation["financial_year"]
        )
        linked_ids = {e["actual_transaction_id"] for e in all_expectations if e["actual_transaction_id"]}
        
        transactions = [t for t in transactions if t["transaction_id"] not in linked_ids]

        self.table.setRowCount(0)
        for txn in transactions:
            r = self.table.rowCount()
            self.table.insertRow(r)
            
            self.table.setItem(r, 0, QTableWidgetItem(format_display_date(txn.get("transaction_date"))))
            self.table.setItem(r, 1, QTableWidgetItem(txn.get("category") or "—"))
            self.table.setItem(r, 2, QTableWidgetItem(f"₹ {txn['amount']:,.2f}"))
            self.table.setItem(r, 3, QTableWidgetItem(txn.get("description") or "—"))
            self.table.setItem(r, 4, QTableWidgetItem(str(txn["transaction_id"])))

    def _on_accept(self):
        if not self.table.selectedItems():
            QMessageBox.warning(self, "No Selection", "Please select a transaction.")
            return
        self.accept()

    def get_selected_transaction_id(self):
        if not self.table.selectedItems():
            return None
        row = self.table.currentRow()
        return int(self.table.item(row, 4).text())
