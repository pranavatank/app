"""
ui/dialogs/password_dialog.py — Reusable password dialog with optional save toggle.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QFormLayout, QLineEdit,
    QCheckBox, QHBoxLayout
)
from PyQt6.QtCore import Qt

from ui.theme import Theme


class PasswordDialog(QDialog):
    """Generic password entry dialog with optional save checkbox."""

    def __init__(
        self,
        parent=None,
        title: str = "Enter Password",
        info_text: str | None = None,
        hint_text: str | None = None,
        placeholder_text: str = "Enter password",
        prefill_password: str | None = None,
        save_label: str | None = None,
        save_checked: bool = True,
        accept_label: str = "Continue",
        cancel_label: str = "Cancel",
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(460)
        self._save_label = save_label
        self._build_ui(
            info_text=info_text,
            hint_text=hint_text,
            placeholder_text=placeholder_text,
            prefill_password=prefill_password,
            save_checked=save_checked,
            accept_label=accept_label,
            cancel_label=cancel_label,
        )

    def _build_ui(
        self,
        info_text: str | None,
        hint_text: str | None,
        placeholder_text: str,
        prefill_password: str | None,
        save_checked: bool,
        accept_label: str,
        cancel_label: str,
    ) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(16)

        if info_text:
            info = QLabel(info_text)
            info.setWordWrap(True)
            info.setAccessibleName("Password dialog information")
            info.setAccessibleDescription("Explains why the password is needed.")
            info.setStyleSheet(
                Theme.text_style(color=Theme.TEXT_PRIMARY, size=13)
                + f" background: {Theme.PRIMARY_LIGHT}; border: 1px solid {Theme.INFO}; "
                  f"border-radius: 8px; padding: 12px;"
            )
            layout.addWidget(info)

        if prefill_password:
            note = QLabel("Saved password found. Edit to update if needed.")
            note.setWordWrap(True)
            note.setAccessibleName("Saved password note")
            note.setStyleSheet(Theme.muted_style(11))
            layout.addWidget(note)

        form = QFormLayout()
        form.setSpacing(12)
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText(placeholder_text)
        self.password_input.setFixedHeight(40)
        self.password_input.setAccessibleName("Password input")
        self.password_input.setAccessibleDescription("Enter the password to unlock the file.")
        self.password_input.setToolTip("Enter the password to unlock the file.")
        self.password_input.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        if prefill_password:
            self.password_input.setText(prefill_password)
            self.password_input.setCursorPosition(0)
        self.password_input.returnPressed.connect(self.accept)
        form.addRow("Password:", self.password_input)

        self.show_check = QCheckBox("Show password")
        self.show_check.setStyleSheet(Theme.text_style(color=Theme.TEXT_PRIMARY, size=13))
        self.show_check.stateChanged.connect(self._toggle_visibility)
        self.show_check.setAccessibleName("Show password toggle")
        self.show_check.setAccessibleDescription("Toggle whether the password is visible.")
        form.addRow("", self.show_check)
        layout.addLayout(form)

        if self._save_label:
            self.save_check = QCheckBox(self._save_label)
            self.save_check.setChecked(save_checked)
            self.save_check.setStyleSheet(Theme.text_style(color=Theme.TEXT_PRIMARY, size=12))
            self.save_check.setAccessibleName("Save password toggle")
            self.save_check.setAccessibleDescription("Toggle whether the password should be saved for later use.")
            layout.addWidget(self.save_check)
        else:
            self.save_check = None

        if hint_text:
            hint = QLabel(hint_text)
            hint.setWordWrap(True)
            hint.setStyleSheet(
                Theme.text_style(color=Theme.TEXT_SECONDARY, size=12)
                + f" background: {Theme.SURFACE_ALT}; border: 1px solid {Theme.BORDER}; "
                  f"border-radius: 8px; padding: 10px;"
            )
            layout.addWidget(hint)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_cancel = Theme.btn(cancel_label, "secondary", height=38, min_width=100)
        btn_cancel.clicked.connect(self.reject)
        btn_cancel.setShortcut("Escape")
        btn_cancel.setAccessibleName("Cancel password dialog")
        btn_cancel.setAccessibleDescription("Close the dialog without continuing.")
        btn_row.addWidget(btn_cancel)
        btn_ok = Theme.btn(accept_label, "primary", height=38, min_width=140)
        btn_ok.clicked.connect(self.accept)
        btn_ok.setDefault(True)
        btn_ok.setShortcut("Return")
        btn_ok.setAccessibleName("Confirm password")
        btn_ok.setAccessibleDescription("Continue after entering the password.")
        btn_row.addWidget(btn_ok)
        layout.addLayout(btn_row)

        self.setTabOrder(self.password_input, self.show_check)
        if self.save_check:
            self.setTabOrder(self.show_check, self.save_check)
            self.setTabOrder(self.save_check, btn_cancel)
        else:
            self.setTabOrder(self.show_check, btn_cancel)
        self.setTabOrder(btn_cancel, btn_ok)

    def _toggle_visibility(self, state: int) -> None:
        mode = QLineEdit.EchoMode.Normal if state else QLineEdit.EchoMode.Password
        self.password_input.setEchoMode(mode)

    def get_password(self) -> str:
        return self.password_input.text().strip()

    def should_save(self) -> bool:
        if not self.save_check:
            return False
        return bool(self.save_check.isChecked())
