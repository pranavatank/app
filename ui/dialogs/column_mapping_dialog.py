from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QHBoxLayout, QComboBox, QPushButton
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from ui.theme import Theme
from ui.icons import icon_label
import pandas as pd
from core.settings import get_setting, set_setting


class ColumnMappingDialog(QDialog):
    """Dialog to let user map Excel columns to expected fields.

    If `account_id` is provided, the mapping will be persisted per-account in settings.
    """

    def __init__(self, parent, file_path, account_id: int | None = None, initial_mapping: dict | None = None, sample_limit: int = 20):
        super().__init__(parent)
        self.setWindowTitle("Map Columns")
        self.setModal(True)
        self.setMinimumWidth(620)
        self.file_path = file_path
        self.account_id = account_id
        self.mapping = {}

        # Read headers
        try:
            df = pd.read_excel(file_path, nrows=sample_limit)
        except Exception:
            try:
                df = pd.read_csv(file_path, nrows=sample_limit)
            except Exception:
                df = None

        headers = list(df.columns) if df is not None else []
        choices = ["(none)"] + headers

        layout = QVBoxLayout(self)
        title_row = QHBoxLayout()
        title_row.setSpacing(10)
        title_row.addWidget(icon_label("list_view", size=20, color=Theme.PRIMARY))
        title = QLabel("Map Columns")
        title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        title.setProperty("textrole", "title-md")
        title_row.addWidget(title)
        title_row.addStretch()
        layout.addLayout(title_row)

        intro = QLabel("Map the columns from your file to the required fields.")
        intro.setWordWrap(True)
        intro.setAccessibleName("Mapping instructions")
        intro.setAccessibleDescription("Explains how to map file columns to the expected import fields.")
        layout.addWidget(intro)

        self._combos = {}
        fields = [
            ("date_col", "Date Column"),
            ("desc_col", "Description Column"),
            ("debit_col", "Debit Column"),
            ("credit_col", "Credit Column"),
            ("balance_col", "Balance Column"),
            ("ref_col", "Reference Column"),
            ("amount_col", "Amount Column"),
            ("drcr_col", "Dr/Cr Column"),
        ]

        for key, label in fields:
            row = QHBoxLayout()
            field_label = QLabel(label)
            field_label.setAccessibleName(f"{label} label")
            row.addWidget(field_label)
            cb = QComboBox()
            cb.addItems(choices)
            cb.setAccessibleName(label)
            cb.setAccessibleDescription(f"Choose the source column for {label.lower()}.")
            cb.setToolTip(f"Choose the source column for {label.lower()}.")
            cb.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            row.addWidget(cb)
            layout.addLayout(row)
            self._combos[key] = cb

        # Load saved mapping for account if available
        saved = {}
        if self.account_id:
            saved = get_setting(f"column_mapping:{self.account_id}", {}) or {}
        # Merge: initial_mapping -> saved
        merged = dict(saved)
        if initial_mapping:
            merged.update({k: v for k, v in (initial_mapping or {}).items() if v})
        for k, v in merged.items():
            if k in self._combos and v in choices:
                self._combos[k].setCurrentText(v)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        ok = Theme.btn("Save", "primary")
        ok.clicked.connect(self._on_ok)
        ok.setDefault(True)
        ok.setShortcut("Return")
        ok.setAccessibleName("Save column mapping")
        ok.setAccessibleDescription("Save the selected column mappings and close the dialog.")
        cancel = Theme.btn("Cancel", "secondary")
        cancel.clicked.connect(self.reject)
        cancel.setShortcut("Escape")
        cancel.setAccessibleName("Cancel column mapping")
        cancel.setAccessibleDescription("Close the dialog without saving changes.")
        btn_row.addWidget(ok)
        btn_row.addWidget(cancel)
        layout.addLayout(btn_row)

    def _on_ok(self):
        for k, cb in self._combos.items():
            v = cb.currentText()
            self.mapping[k] = None if v == "(none)" else v
        # Persist mapping per-account if account_id provided
        if self.account_id:
            try:
                set_setting(f"column_mapping:{self.account_id}", self.mapping)
            except Exception:
                pass
        self.accept()

    def get_mapping(self):
        return self.mapping
