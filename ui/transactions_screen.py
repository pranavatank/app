"""
ui/transactions_screen.py — Transaction management with modern theme.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QLineEdit, QTableWidget,
    QTableWidgetItem, QHeaderView, QDialog, QDialogButtonBox,
    QFormLayout, QDateEdit, QDoubleSpinBox, QTextEdit,
    QMessageBox, QFrame, QAbstractItemView, QCheckBox, QTabWidget
)
from PyQt6.QtCore import Qt, QDate, QTimer
from PyQt6.QtGui import QFont, QColor

from ui.widgets.excel_table import ExcelTableWithStats
from ui.widgets.chart_widget import ChartWidget
from ui.widgets.states import EmptyState
from ui.widgets.toast_utils import show_success, show_warning

from ui.theme import Theme
from ui.icons import icon as app_icon, is_available as icons_available
from ui.date_utils import format_display_date
from core.session import session
from config import (
    INCOME_CATEGORIES, EXPENSE_CATEGORIES,
    TRANSACTION_MODES, get_all_financial_years, get_current_financial_year
)
from models.person import get_all_persons
from models.bank_account import get_accounts_for_person, get_all_accounts
from models.transaction import (
    get_transactions, add_transaction, update_transaction, delete_transaction,
    reprocess_internal_transfers, display_transaction_type, normalize_transaction_type,
    get_category_summary
)

_COL_DATE=0; _COL_TYPE=1; _COL_CAT=2; _COL_MODE=3; _COL_REF=4; _COL_DESC=5
_COL_AMOUNT=6; _COL_BAL=7; _COL_ACCT=8; _COL_PERSON=9; _COL_ID=10

# Month names for monthly chart
_MONTHS = [
    ("Apr", 4), ("May", 5), ("Jun", 6),
    ("Jul", 7), ("Aug", 8), ("Sep", 9),
    ("Oct", 10), ("Nov", 11), ("Dec", 12),
    ("Jan", 1), ("Feb", 2), ("Mar", 3),
]


def _monthly_data(person_id, financial_year: str, account_id: int | None = None):
    """Return (month_labels, income_list, expense_list) for a FY."""
    from core.database import get_connection
    fy_year = int(financial_year.split("-")[0])

    labels, income_vals, expense_vals = [], [], []
    conn = get_connection()
    for name, month in _MONTHS:
        year = fy_year if month >= 4 else fy_year + 1
        from calendar import monthrange
        last_day = monthrange(year, month)[1]
        m_start = f"{year}-{month:02d}-01"
        m_end   = f"{year}-{month:02d}-{last_day:02d}"

        q = """
            SELECT transaction_type, SUM(amount) AS total
            FROM Transactions
            WHERE transaction_date BETWEEN ? AND ?
              AND COALESCE(is_internal_transfer, 0) = 0
        """
        params = [m_start, m_end]
        if person_id:
            q += " AND person_id = ?"
            params.append(person_id)
        if account_id:
            q += " AND account_id = ?"
            params.append(account_id)
        q += " GROUP BY transaction_type"

        rows = conn.execute(q, params).fetchall()
        row_map = {r["transaction_type"]: r["total"] or 0 for r in rows}

        labels.append(name)
        income_vals.append(row_map.get("Income", 0))
        expense_vals.append(row_map.get("Expense", 0))

    conn.close()
    return labels, income_vals, expense_vals


class _DateSortItem(QTableWidgetItem):
    def __lt__(self, other):
        if not isinstance(other, QTableWidgetItem):
            return super().__lt__(other)
        left_iso = self.data(Qt.ItemDataRole.UserRole)
        right_iso = other.data(Qt.ItemDataRole.UserRole)
        if left_iso and right_iso:
            left_date = QDate.fromString(str(left_iso), "yyyy-MM-dd")
            right_date = QDate.fromString(str(right_iso), "yyyy-MM-dd")
            if left_date.isValid() and right_date.isValid():
                return left_date < right_date
        return super().__lt__(other)


class TransactionsScreen(QWidget):
    def __init__(self, parent_window=None):
        super().__init__()
        self._parent_window = parent_window
        self._all_persons: list[dict] = []
        self._all_accounts: list[dict] = []
        self._current_rows: list[dict] = []
        self._dirty = False
        self._dirty_reminder_shown = False
        self._dirty_timer = QTimer(self)
        self._dirty_timer.setSingleShot(True)
        self._dirty_timer.timeout.connect(self._show_dirty_reminder)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 18)
        layout.setSpacing(16)

        # Action bar
        layout.addWidget(self._build_action_bar())
        # Unsaved banner
        layout.addWidget(self._build_unsaved_bar())
        # Filter bar
        layout.addWidget(self._build_filter_bar())

        # Charts tabs (Monthly and Categories)
        self.charts_tabs = QTabWidget()
        self.charts_tabs.setAccessibleName("Transaction charts")
        self.charts_tabs.setAccessibleDescription("View monthly and category breakdowns.")
        self.monthly_chart = ChartWidget()
        self.category_chart = ChartWidget()
        self.charts_tabs.addTab(self.monthly_chart, "Monthly")
        self.charts_tabs.addTab(self.category_chart, "Categories")
        self.charts_tabs.setFixedHeight(380)
        layout.addWidget(self.charts_tabs)

        # Table container (will hold table or empty state)
        self.table_container = QWidget()
        self.table_container_layout = QVBoxLayout(self.table_container)
        self.table_container_layout.setContentsMargins(0, 0, 0, 0)
        self.table_container_layout.setSpacing(0)

        self.table_widget = self._build_table()
        self.table_container_layout.addWidget(self.table_widget, stretch=1)

        self._empty_state = None
        layout.addWidget(self.table_container, stretch=1)

        # Status
        self.status_label = QLabel("")
        self.status_label.setObjectName("mutedLabel")
        layout.addWidget(self.status_label)

    def _build_action_bar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("actionBar")
        bar.setStyleSheet(Theme.action_bar_style())
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        self.btn_add = Theme.btn("  Add Transaction", "primary", height=40, min_width=140)
        self.btn_add.setIcon(app_icon("add", color="#FFFFFF", size=16))
        self.btn_add.clicked.connect(self._add_transaction)
        layout.addWidget(self.btn_add)

        self.btn_edit = Theme.btn("  Edit", "edit", height=40, min_width=96)
        self.btn_edit.setIcon(app_icon("edit", color="#FFFFFF", size=16))
        self.btn_edit.setEnabled(False)
        self.btn_edit.clicked.connect(self._edit_transaction)
        layout.addWidget(self.btn_edit)

        self.btn_delete = Theme.btn("  Delete", "danger", height=40, min_width=105)
        self.btn_delete.setIcon(app_icon("delete", color="#FFFFFF", size=16))
        self.btn_delete.setEnabled(False)
        self.btn_delete.clicked.connect(self._delete_transaction)
        layout.addWidget(self.btn_delete)

        self.btn_reprocess = Theme.btn("Reprocess Data", "secondary", height=40, min_width=130)
        self.btn_reprocess.setIcon(app_icon("refresh", size=16))
        self.btn_reprocess.clicked.connect(self._reprocess_data)
        layout.addWidget(self.btn_reprocess)

        layout.addStretch()

        # Pill badges
        self.lbl_income_sum  = self._badge("Credit: —",  Theme.SUCCESS_LIGHT, Theme.SUCCESS_DARK)
        self.lbl_expense_sum = self._badge("Debit: —", Theme.DANGER_LIGHT,  Theme.DANGER_DARK)
        self.lbl_net_sum     = self._badge("Net: —",     Theme.PRIMARY_LIGHT, Theme.PRIMARY_DARK)
        layout.addWidget(self.lbl_income_sum)
        layout.addWidget(self.lbl_expense_sum)
        layout.addWidget(self.lbl_net_sum)

        self.action_bar = bar  # keep ref for theme refresh
        return bar

    def _build_unsaved_bar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("unsavedBar")
        bar.setStyleSheet(self._unsaved_bar_css())
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(10)

        self.unsaved_label = QLabel("Unsaved changes. Save to keep edits.")
        self.unsaved_label.setProperty("textrole", "emphasis-sm")
        layout.addWidget(self.unsaved_label)
        layout.addStretch()

        self.btn_save = Theme.btn("Save Changes", "primary", height=32, min_width=120)
        self.btn_save.clicked.connect(self._save_table_changes)
        layout.addWidget(self.btn_save)

        self.btn_discard = Theme.btn("Discard", "secondary", height=32, min_width=90)
        self.btn_discard.clicked.connect(lambda: self._discard_changes(confirm=True))
        layout.addWidget(self.btn_discard)

        bar.hide()
        self.btn_save.setEnabled(False)
        self.btn_discard.setEnabled(False)
        self._unsaved_bar = bar
        return bar

    def _badge(self, text, bg, fg) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(Theme.badge_style(bg, fg))
        return lbl

    @staticmethod
    def _unsaved_bar_css() -> str:
        return f"""
            QFrame#unsavedBar {{
                background: {Theme.SURFACE_ALT};
                border: 1px solid {Theme.BORDER};
                border-radius: 10px;
            }}
        """

    def _build_filter_bar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("filterBar")
        bar.setStyleSheet(Theme.filter_bar_style())
        self.filter_bar = bar  # keep ref for theme refresh
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(12)

        def lbl(t):
            l = QLabel(t)
            l.setProperty("textrole", "section-label")
            return l

        layout.addWidget(lbl("Person"))
        self.f_person = QComboBox(); self.f_person.setFixedWidth(140); self.f_person.setFixedHeight(32)
        self.f_person.addItem("All Persons", userData=None)
        self.f_person.currentIndexChanged.connect(self._on_filter_person_changed)
        layout.addWidget(self.f_person)

        layout.addWidget(lbl("Account"))
        self.f_account = QComboBox(); self.f_account.setFixedWidth(180); self.f_account.setFixedHeight(32)
        self.f_account.addItem("All Accounts", userData=None)
        layout.addWidget(self.f_account)

        layout.addWidget(lbl("FY"))
        self.f_fy = QComboBox(); self.f_fy.setFixedWidth(95); self.f_fy.setFixedHeight(32)
        for fy in reversed(get_all_financial_years(since_year=2020)):
            self.f_fy.addItem(fy)
        self.f_fy.setCurrentText(session.selected_fy)
        layout.addWidget(self.f_fy)

        layout.addWidget(lbl("Type"))
        self.f_type = QComboBox(); self.f_type.setFixedWidth(110); self.f_type.setFixedHeight(32)
        self.f_type.addItems(["All Types", "Credit", "Debit", "Transfer"])
        layout.addWidget(self.f_type)

        layout.addWidget(lbl("Search"))
        self.f_search = QLineEdit(); self.f_search.setPlaceholderText("description / category …")
        self.f_search.setFixedWidth(180); self.f_search.setFixedHeight(32)
        layout.addWidget(self.f_search)

        layout.addStretch()

        btn_filter = Theme.btn("Apply", "primary", height=32, min_width=80)
        btn_filter.clicked.connect(self.refresh)
        layout.addWidget(btn_filter)

        btn_clear = Theme.btn("Clear", "secondary", height=32, min_width=70)
        btn_clear.clicked.connect(self._clear_filters)
        layout.addWidget(btn_clear)

        return bar

    def _build_table(self) -> QWidget:
        headers = ["Date","Type","Category","Mode","Reference No","Description","Amount (₹)","Balance After (₹)","Account","Person","ID"]
        self.table_widget = ExcelTableWithStats(show_checkboxes=True)
        self.table = self.table_widget.table
        self.table.editable = True  # Enable editing for certain columns
        self.table.setHeaders(headers)
        # Amount and Balance After are the only free-numeric editable columns
        # (Category/Mode/Reference/Description are editable but free text).
        self.table.setNumericColumns({_COL_AMOUNT+1, _COL_BAL+1})
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.EditKeyPressed)
        self.table.setSortingEnabled(True)
        self.table.cellDataChanged.connect(self._on_table_data_changed)
        self.table.itemChanged.connect(lambda _: self._mark_dirty())
        # Override delete to ensure DB stays in sync when using Delete key.
        self.table.deleteSelectedRows = self._delete_selected_rows

        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        for i, w in enumerate([40,90,80,130,100,150,210,110,130,160,120,0]):
            self.table.setColumnWidth(i, w)
        self.table.setColumnHidden(_COL_ID+1, True)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.doubleClicked.connect(self._edit_transaction)
        return self.table_widget

    def refresh(self):
        if not self._confirm_unsaved("refresh transactions"):
            return
        self._reload_filter_persons()
        self._fetch_and_display()
        self._refresh_charts()

    def refresh_theme(self):
        """Called after a live theme switch — rebuilds all inline-styled
        widgets (unsaved bar, filter bar, pill badges) and re-tints the
        table rows, which carry baked QColor foreground colours."""
        if hasattr(self, 'action_bar') and self.action_bar:
            self.action_bar.setStyleSheet(Theme.action_bar_style())
        if hasattr(self, '_unsaved_bar') and self._unsaved_bar:
            self._unsaved_bar.setStyleSheet(self._unsaved_bar_css())
        if hasattr(self, 'filter_bar') and self.filter_bar:
            self.filter_bar.setStyleSheet(Theme.filter_bar_style())
        if hasattr(self, 'lbl_income_sum'):
            self.lbl_income_sum.setStyleSheet(Theme.badge_style(Theme.SUCCESS_LIGHT, Theme.SUCCESS_DARK))
        if hasattr(self, 'lbl_expense_sum'):
            self.lbl_expense_sum.setStyleSheet(Theme.badge_style(Theme.DANGER_LIGHT, Theme.DANGER_DARK))
        if hasattr(self, 'lbl_net_sum'):
            self.lbl_net_sum.setStyleSheet(Theme.badge_style(Theme.PRIMARY_LIGHT, Theme.PRIMARY_DARK))
        if hasattr(self, 'table_widget') and self.table_widget:
            self.table_widget.refresh_theme()
        if hasattr(self, 'monthly_chart') and self.monthly_chart:
            self.monthly_chart.refresh_theme()
        if hasattr(self, 'category_chart') and self.category_chart:
            self.category_chart.refresh_theme()
        # Re-populate the table so row text colours (baked QColor) refresh too
        if hasattr(self, '_current_rows') and self._current_rows is not None:
            self._populate_table(self._current_rows)

    def _reload_filter_persons(self):
        self.f_person.blockSignals(True)
        self.f_person.clear()
        self._all_persons = get_all_persons()
        self.f_person.addItem("All Persons", userData=None)
        for p in self._all_persons:
            self.f_person.addItem(p["full_name"], userData=p["person_id"])
        if session.selected_person_id:
            for i in range(self.f_person.count()):
                if self.f_person.itemData(i) == session.selected_person_id:
                    self.f_person.setCurrentIndex(i); break
        self.f_person.blockSignals(False)
        self._reload_filter_accounts()

    def _reload_filter_accounts(self):
        self.f_account.blockSignals(True)
        self.f_account.clear()
        pid = self.f_person.currentData()
        if pid is None:
            self._all_accounts = get_all_accounts()
            self.f_account.addItem("All Accounts", userData=None)
            for a in self._all_accounts:
                self.f_account.addItem(f"{a['person_name']} — {a.get('bank_display_name', a['bank_name'])} ({a['account_type']})", userData=a["account_id"])
        else:
            self._all_accounts = get_accounts_for_person(pid)
            self.f_account.addItem("All Accounts", userData=None)
            for a in self._all_accounts:
                self.f_account.addItem(f"{a.get('bank_display_name', a['bank_name'])} ({a['account_type']})", userData=a["account_id"])
        self.f_account.blockSignals(False)

    def _fetch_and_display(self):
        pid  = self.f_person.currentData()
        aid  = self.f_account.currentData()
        fy   = self.f_fy.currentText() or None
        typ_text = self.f_type.currentText()
        typ = None if typ_text == "All Types" else normalize_transaction_type(typ_text)
        term = self.f_search.text().strip().lower()

        rows = get_transactions(account_id=aid, person_id=pid, financial_year=fy, transaction_type=typ)
        if term:
            rows = [r for r in rows if term in (r.get("description") or "").lower()
                    or term in (r.get("category") or "").lower()
                    or term in (r.get("reference_no") or "").lower()]

        self._current_rows = rows
        self._populate_table(rows)
        self._update_pills(rows)
        self.btn_edit.setEnabled(False)
        self.btn_delete.setEnabled(False)

    def _populate_table(self, rows):
        # Show empty state if no transactions
        if not rows:
            if self._empty_state is None:
                self._empty_state = EmptyState(
                    icon_name="transactions",
                    headline="No transactions",
                    explanation="Import a bank statement to see your transactions here.",
                    action_text="Import Statement",
                    parent=self.table_container
                )
                self._empty_state.action_clicked.connect(self._trigger_import)
                self.table_container_layout.addWidget(self._empty_state)
            self.table_widget.setVisible(False)
            if self._empty_state:
                self._empty_state.setVisible(True)
            return

        # Hide empty state and show table
        if self._empty_state:
            self._empty_state.setVisible(False)
        self.table_widget.setVisible(True)

        # Block signals during refresh
        self.table.blockSignals(True)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)

        type_colors = {
            "Income":   QColor(Theme.SUCCESS),
            "Expense":  QColor(Theme.DANGER),
            "Transfer": QColor(Theme.INFO),
        }

        for row in rows:
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
            
            txn_type = row.get("transaction_type", "")
            display_type = display_transaction_type(txn_type)
            color    = type_colors.get(normalize_transaction_type(txn_type), QColor(Theme.TEXT_PRIMARY))

            def item(text, align=Qt.AlignmentFlag.AlignLeft):
                it = QTableWidgetItem(str(text) if text is not None else "—")
                it.setForeground(color)
                it.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
                return it

            def amt_item(val):
                it = QTableWidgetItem(f"{val:,.2f}" if val is not None else "—")
                it.setForeground(color)
                it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                return it

            date_display = format_display_date(row.get("transaction_date"))
            date_item = _DateSortItem(date_display)
            date_item.setForeground(color)
            date_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            date_item.setData(Qt.ItemDataRole.UserRole, row.get("transaction_date"))
            self.table.setItem(r, _COL_DATE+1, date_item)
            
            type_item = item(display_type)
            self.table.setItem(r, _COL_TYPE+1, type_item)
            
            # Category - editable
            cat_item = item(row.get("category",""))
            cat_item.setFlags(cat_item.flags() | Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, _COL_CAT+1, cat_item)
            
            # Mode - editable
            mode_item = item(row.get("mode",""))
            mode_item.setFlags(mode_item.flags() | Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, _COL_MODE+1, mode_item)
            
            # Reference - editable
            ref_item = item(row.get("reference_no") or "—")
            ref_item.setFlags(ref_item.flags() | Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, _COL_REF+1, ref_item)
            
            # Description - editable
            desc_item = item(row.get("description",""))
            desc_item.setFlags(desc_item.flags() | Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, _COL_DESC+1, desc_item)
            
            # Amount - editable
            amt_item_val = amt_item(row.get("amount"))
            amt_item_val.setFlags(amt_item_val.flags() | Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, _COL_AMOUNT+1, amt_item_val)
            
            # Balance - editable
            bal_item_val = amt_item(row.get("balance_after"))
            bal_item_val.setFlags(bal_item_val.flags() | Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, _COL_BAL+1, bal_item_val)
            
            self.table.setItem(r, _COL_ACCT+1,   item(row.get("bank_display_name") or row.get("bank_name", "")))
            self.table.setItem(r, _COL_PERSON+1, item(row.get("person_name","")))
            self.table.setItem(r, _COL_ID+1,     QTableWidgetItem(str(row["transaction_id"])))
            self.table.setRowHeight(r, 32)

        self.table.setSortingEnabled(True)
        self.table.blockSignals(False)  # Re-enable signals
        count = self.table.rowCount()
        self.status_label.setText(f"Showing {count} transaction{'s' if count!=1 else ''}.")

    def _update_pills(self, rows):
        income  = sum(
            r["amount"] for r in rows
            if r.get("transaction_type") == "Income" and not r.get("is_internal_transfer")
        )
        expense = sum(
            r["amount"] for r in rows
            if r.get("transaction_type") == "Expense" and not r.get("is_internal_transfer")
        )
        net = income - expense
        self.lbl_income_sum.setText(f"Credit: ₹ {income:,.2f}")
        self.lbl_expense_sum.setText(f"Debit: ₹ {expense:,.2f}")
        sign = "+" if net >= 0 else ""
        self.lbl_net_sum.setText(f"Net: {sign}₹ {net:,.2f}")

    def _refresh_charts(self):
        """Refresh the monthly and category charts based on current filters."""
        pid = self.f_person.currentData()
        aid = self.f_account.currentData()
        fy  = self.f_fy.currentText() or session.selected_fy
        if not fy:
            return
        self._refresh_monthly_chart(pid, aid, fy)
        self._refresh_category_chart(pid, aid, fy)

    def _refresh_monthly_chart(self, pid, aid, fy):
        """Refresh the monthly bar chart."""
        try:
            months, income, expense = _monthly_data(pid, fy, aid)
            if all(v == 0 for v in income) and all(v == 0 for v in expense):
                self.monthly_chart.show_empty_state("No monthly data for this period")
                return
            self.monthly_chart.plot_monthly_bar(
                months=months,
                income=income,
                expense=expense,
                title=f"Monthly Overview — FY {fy}",
            )
        except Exception:
            self.monthly_chart.show_empty_state("Could not load monthly data")

    def _refresh_category_chart(self, pid, aid, fy):
        """Refresh the category pie chart."""
        cats = get_category_summary(person_id=pid, financial_year=fy, account_id=aid)
        if not cats:
            self.category_chart.show_empty_state("No category data for this period")
            return
        top = cats[:8]
        self.category_chart.plot_pie(
            labels=[c["category"] or "Uncategorised" for c in top],
            values=[c["total"] for c in top],
            title=f"Debit by Category — FY {fy}",
        )

    def _reprocess_data(self):
        reply = QMessageBox.question(
            self,
            "Reprocess Internal Transfers",
            "This will scan bank-transfer-like entries across all accounts "
            "and relink internal transfers. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        pairs, marked = reprocess_internal_transfers()
        self._fetch_and_display()
        if self._parent_window:
            self._parent_window.refresh_overview()
        show_success(f"Linked pairs: {pairs}\nTransactions marked as Internal Transfer: {marked}")

    def _add_transaction(self):
        persons  = get_all_persons()
        accounts = get_all_accounts()
        if not persons:
            show_warning("Add a family member first.")
            return
        if not accounts:
            show_warning("Add a bank account first.")
            return
        dlg = TransactionDialog(self, persons=persons, accounts=accounts,
                                preselect_person_id=session.selected_person_id,
                                preselect_account_id=session.selected_account_id)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            add_transaction(**dlg.get_data())
            self._fetch_and_display()
            if self._parent_window: self._parent_window.refresh_overview()

    def _edit_transaction(self):
        txn = self._selected_transaction()
        if txn is None: return
        dlg = TransactionDialog(self, persons=get_all_persons(),
                                accounts=get_all_accounts(), existing=txn)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            update_transaction(txn["transaction_id"], data["transaction_date"],
                               data["transaction_type"], data["amount"],
                               data.get("category"), data.get("mode"), data.get("description"), data.get("reference_no"),
                               data.get("balance_after"))
            self._fetch_and_display()
            if self._parent_window: self._parent_window.refresh_overview()

    def _delete_transaction(self):
        txn = self._selected_transaction()
        if txn is None: return
        desc = txn.get("description") or f"₹ {txn['amount']:,.2f}"
        reply = QMessageBox.question(self, "Confirm Delete",
            f"Delete \"{desc}\"?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            delete_transaction(txn["transaction_id"])
            self._fetch_and_display()
            if self._parent_window: self._parent_window.refresh_overview()

    def _delete_selected_rows(self):
        selected_rows = {item.row() for item in self.table.selectedItems()}
        if not selected_rows:
            return

        txn_ids = []
        for row in selected_rows:
            id_item = self.table.item(row, _COL_ID+1)
            if id_item is not None:
                try:
                    txn_ids.append(int(id_item.text()))
                except ValueError:
                    continue

        if not txn_ids:
            return

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete {len(txn_ids)} selected transaction(s)?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        for txn_id in txn_ids:
            delete_transaction(txn_id)

        self._fetch_and_display()
        if self._parent_window:
            self._parent_window.refresh_overview()

    def _selected_transaction(self):
        if not self.table.selectedItems(): return None
        id_item = self.table.item(self.table.currentRow(), _COL_ID+1)
        if id_item is None: return None
        txn_id = int(id_item.text())
        return next((r for r in self._current_rows if r["transaction_id"] == txn_id), None)

    def _trigger_import(self):
        """Trigger statement import (navigate to the import screen via parent)."""
        if self._parent_window:
            # Navigate to statement import screen (index 5)
            self._parent_window._navigate(5)

    def _on_selection_changed(self):
        has = bool(self.table.selectedItems())
        self.btn_edit.setEnabled(has)
        self.btn_delete.setEnabled(has)

    def _on_table_data_changed(self):
        """Handle data changes in table (after paste or edit)."""
        self._mark_dirty()

    def _mark_dirty(self):
        if self._dirty:
            return
        self._dirty = True
        self._dirty_reminder_shown = False
        self._unsaved_bar.show()
        self.btn_save.setEnabled(True)
        self.btn_discard.setEnabled(True)
        self._dirty_timer.start(45000)

    def _clear_dirty(self):
        self._dirty = False
        self._dirty_reminder_shown = False
        self._dirty_timer.stop()
        self._unsaved_bar.hide()
        self.btn_save.setEnabled(False)
        self.btn_discard.setEnabled(False)

    def _show_dirty_reminder(self):
        if not self._dirty or self._dirty_reminder_shown:
            return
        self._dirty_reminder_shown = True
        show_warning("You have unsaved changes in Transactions. Click 'Save Changes' to keep them.")

    def has_unsaved_changes(self) -> bool:
        return self._dirty

    def _confirm_unsaved(self, action_label: str) -> bool:
        if not self._dirty:
            return True
        reply = QMessageBox(self)
        reply.setWindowTitle("Unsaved Changes")
        reply.setText(f"You have unsaved changes. Save before you {action_label}?")
        reply.setStandardButtons(QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
        reply.setDefaultButton(QMessageBox.StandardButton.Save)
        choice = reply.exec()
        if choice == QMessageBox.StandardButton.Save:
            return self._save_table_changes()
        if choice == QMessageBox.StandardButton.Discard:
            self._discard_changes(confirm=False)
            return True
        return False

    def _parse_money(self, text: str) -> float | None:
        raw = (text or "").replace("₹", "").replace(",", "").strip()
        if raw in ("", "—"):
            return None
        try:
            return float(raw)
        except ValueError:
            return None

    def _collect_row_values(self, row_index: int) -> dict | None:
        id_item = self.table.item(row_index, _COL_ID+1)
        if id_item is None:
            return None
        try:
            txn_id = int(id_item.text())
        except ValueError:
            return None

        def _text(col):
            item = self.table.item(row_index, col)
            return item.text().strip() if item else ""

        category = _text(_COL_CAT+1)
        mode = _text(_COL_MODE+1)
        reference = _text(_COL_REF+1)
        description = _text(_COL_DESC+1)
        amount = self._parse_money(_text(_COL_AMOUNT+1))
        balance = self._parse_money(_text(_COL_BAL+1))

        if category in ("—", ""):
            category = None
        if mode in ("—", ""):
            mode = None
        if reference in ("—", ""):
            reference = None
        if description in ("—", ""):
            description = None
        if reference is not None:
            reference = reference.strip().upper()

        return {
            "transaction_id": txn_id,
            "category": category,
            "mode": mode,
            "reference_no": reference,
            "description": description,
            "amount": amount,
            "balance_after": balance,
        }

    def _save_table_changes(self) -> bool:
        if not self._dirty:
            return True

        originals = {r["transaction_id"]: r for r in self._current_rows}
        updates = []

        for row in range(self.table.rowCount()):
            data = self._collect_row_values(row)
            if not data:
                continue
            orig = originals.get(data["transaction_id"])
            if not orig:
                continue

            if data["amount"] is None or data["amount"] <= 0:
                show_warning(f"Row {row+1}: Amount must be > 0.")
                return False

            changed = False
            def _norm(v):
                return (v or "").strip()

            if _norm(orig.get("category")) != _norm(data["category"]):
                changed = True
            if _norm(orig.get("mode")) != _norm(data["mode"]):
                changed = True
            if _norm(orig.get("description")) != _norm(data["description"]):
                changed = True
            if _norm(orig.get("reference_no")) != _norm(data["reference_no"]):
                changed = True

            if abs(float(orig.get("amount") or 0) - float(data["amount"] or 0)) > 0.005:
                changed = True

            orig_bal = orig.get("balance_after")
            if orig_bal is None and data["balance_after"] is None:
                pass
            else:
                if abs(float(orig_bal or 0) - float(data["balance_after"] or 0)) > 0.005:
                    changed = True

            if changed:
                updates.append((orig, data))

        if not updates:
            self._clear_dirty()
            return True

        for orig, data in updates:
            update_transaction(
                data["transaction_id"],
                orig.get("transaction_date"),
                orig.get("transaction_type"),
                data["amount"],
                data.get("category"),
                data.get("mode"),
                data.get("description"),
                data.get("reference_no"),
                data.get("balance_after"),
            )

        self._clear_dirty()
        self._fetch_and_display()
        if self._parent_window:
            self._parent_window.refresh_overview()
        show_success(f"Saved {len(updates)} change(s).")
        return True

    def _discard_changes(self, confirm: bool = True):
        if confirm:
            reply = QMessageBox.question(
                self,
                "Discard Changes",
                "Discard all unsaved changes?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        self._clear_dirty()
        self._fetch_and_display()

    def _on_filter_person_changed(self): self._reload_filter_accounts()

    def _clear_filters(self):
        if not self._confirm_unsaved("clear filters"):
            return
        self.f_person.setCurrentIndex(0)
        self.f_account.setCurrentIndex(0)
        self.f_fy.setCurrentText(get_current_financial_year())
        self.f_type.setCurrentIndex(0)
        self.f_search.clear()
        self._fetch_and_display()


class TransactionDialog(QDialog):
    def __init__(self, parent=None, persons=None, accounts=None,
                 existing=None, preselect_person_id=None, preselect_account_id=None):
        super().__init__(parent)
        self._persons  = persons or []
        self._accounts = accounts or []
        self._existing = existing
        self._preselect_pid = preselect_person_id
        self._preselect_aid = preselect_account_id
        self.setWindowTitle("Edit Transaction" if existing else "Add Transaction")
        self.setMinimumWidth(500)
        self.setModal(True)
        self._build_ui()
        if existing: self._prefill(existing)

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
        self.cmb_person.currentIndexChanged.connect(self._on_person_changed)
        if self._preselect_pid:
            for i in range(self.cmb_person.count()):
                if self.cmb_person.itemData(i) == self._preselect_pid:
                    self.cmb_person.setCurrentIndex(i); break
        form.addRow("Person *", self.cmb_person)

        self.cmb_account = QComboBox()
        self._populate_accounts()
        if self._preselect_aid:
            for i in range(self.cmb_account.count()):
                if self.cmb_account.itemData(i) == self._preselect_aid:
                    self.cmb_account.setCurrentIndex(i); break
        form.addRow("Account *", self.cmb_account)

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setDisplayFormat("dd/MM/yy")
        form.addRow("Date *", self.date_edit)

        self.cmb_type = QComboBox()
        self.cmb_type.addItems(["Credit","Debit","Transfer"])
        self.cmb_type.currentTextChanged.connect(self._on_type_changed)
        form.addRow("Type *", self.cmb_type)

        self.cmb_category = QComboBox()
        self._populate_categories("Credit")
        form.addRow("Category", self.cmb_category)

        self.cmb_mode = QComboBox()
        self.cmb_mode.addItems([""]+TRANSACTION_MODES)
        form.addRow("Mode", self.cmb_mode)

        self.ref_input = QLineEdit()
        self.ref_input.setPlaceholderText("Optional reference no. (UTR/IB/SCREF/...)")
        form.addRow("Reference No", self.ref_input)

        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setRange(0.01, 99_999_999.99)
        self.amount_spin.setDecimals(2)
        self.amount_spin.setGroupSeparatorShown(True)
        self.amount_spin.setPrefix("₹ ")
        form.addRow("Amount *", self.amount_spin)

        self.bal_spin = QDoubleSpinBox()
        self.bal_spin.setRange(-99_999_999.99, 99_999_999.99)
        self.bal_spin.setDecimals(2)
        self.bal_spin.setGroupSeparatorShown(True)
        self.bal_spin.setPrefix("₹ ")
        self.bal_spin.setSpecialValueText("—")
        self.bal_spin.setValue(self.bal_spin.minimum())
        form.addRow("Balance After", self.bal_spin)

        self.desc_edit = QTextEdit()
        self.desc_edit.setFixedHeight(68)
        self.desc_edit.setPlaceholderText("Optional description / notes …")
        form.addRow("Description", self.desc_edit)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Save" if self._existing else "Add")
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _populate_accounts(self):
        self.cmb_account.clear()
        pid = self.cmb_person.currentData()
        for a in self._accounts:
            if pid is None or a.get("person_id") == pid:
                self.cmb_account.addItem(f"{a.get('bank_display_name', a['bank_name'])} ({a['account_type']})", userData=a["account_id"])

    def _populate_categories(self, txn_type):
        self.cmb_category.clear()
        self.cmb_category.addItem("", userData=None)
        norm = normalize_transaction_type(txn_type)
        if norm == "Income": self.cmb_category.addItems(INCOME_CATEGORIES)
        elif norm == "Expense": self.cmb_category.addItems(EXPENSE_CATEGORIES)
        else: self.cmb_category.addItem("Transfer")

    def _prefill(self, txn):
        for i in range(self.cmb_person.count()):
            if self.cmb_person.itemData(i) == txn.get("person_id"):
                self.cmb_person.setCurrentIndex(i); break
        self._populate_accounts()
        for i in range(self.cmb_account.count()):
            if self.cmb_account.itemData(i) == txn.get("account_id"):
                self.cmb_account.setCurrentIndex(i); break
        d = txn.get("transaction_date","")
        if d:
            qd = QDate.fromString(d,"yyyy-MM-dd")
            if qd.isValid(): self.date_edit.setDate(qd)
        typ = display_transaction_type(txn.get("transaction_type", "Income"))
        self.cmb_type.setCurrentText(typ)
        self._populate_categories(typ)
        idx = self.cmb_category.findText(txn.get("category") or "")
        if idx >= 0: self.cmb_category.setCurrentIndex(idx)
        idx = self.cmb_mode.findText(txn.get("mode") or "")
        if idx >= 0: self.cmb_mode.setCurrentIndex(idx)
        self.ref_input.setText(txn.get("reference_no") or "")
        self.amount_spin.setValue(txn.get("amount",0.0))
        bal = txn.get("balance_after")
        if bal is not None: self.bal_spin.setValue(bal)
        self.desc_edit.setPlainText(txn.get("description") or "")

    def _on_person_changed(self): self._populate_accounts()
    def _on_type_changed(self, t): self._populate_categories(t)

    def _on_accept(self):
        if not self.cmb_account.currentData():
            show_warning("Please select an account."); return
        if self.amount_spin.value() <= 0:
            show_warning("Amount must be > 0."); return
        self.accept()

    def get_data(self) -> dict:
        bal_val = self.bal_spin.value()
        bal = None if bal_val == self.bal_spin.minimum() else bal_val
        return {
            "account_id":       self.cmb_account.currentData(),
            "person_id":        self.cmb_person.currentData(),
            "transaction_date": self.date_edit.date().toString("yyyy-MM-dd"),
            "transaction_type": normalize_transaction_type(self.cmb_type.currentText()),
            "category":         self.cmb_category.currentText().strip() or None,
            "mode":             self.cmb_mode.currentText().strip() or None,
            "reference_no":     self.ref_input.text().strip().upper() or None,
            "amount":           self.amount_spin.value(),
            "description":      self.desc_edit.toPlainText().strip() or None,
            "balance_after":    bal,
            "source":           "Manual",
        }
