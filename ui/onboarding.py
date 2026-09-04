from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
from PyQt6.QtCore import Qt
from ui.theme.theme import Theme


class OnboardingDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Welcome to Personal Financial Manager")
        self.setModal(True)
        self.setFixedSize(640, 360)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        title = QLabel("Welcome! Here's a quick tour")
        title.setProperty("textrole", "title-xl")
        title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        root.addWidget(title)

        steps = [
            "1. Import bank statements via Import → Statement.",
            "2. Use 'Map Columns' when Excel headers don't match.",
            "3. Review and edit imported rows before committing.",
            "4. Backups run automatically every 24 hours.",
            "5. Use Settings to toggle themes and security options.",
        ]
        for s in steps:
            lbl = QLabel(s)
            lbl.setProperty("textrole", "body-md")
            lbl.setWordWrap(True)
            root.addWidget(lbl)

        root.addStretch(1)
        h = QHBoxLayout()
        h.addStretch(1)
        btn = Theme.btn("Got it — take me to the app", "primary")
        btn.clicked.connect(self.accept)
        h.addWidget(btn)
        root.addLayout(h)
