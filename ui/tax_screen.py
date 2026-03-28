"""
ui/tax_screen.py — Tax calculation and regime comparison. Modern theme.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QFormLayout, QFrame, QScrollArea,
    QMessageBox, QDoubleSpinBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ui.theme import Theme
from core.session import session
from models.person import get_person
from models.fd_interest_record import get_total_fd_interest
from models.savings_interest import get_total_savings_interest
from models.tax_profile import get_tax_profile
from engines.tax_engine import calculate_and_save_tax, get_tax_summary


class TaxScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self._build_ui()

    def _build_ui(self):
        self.setObjectName("taxRoot")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 20)
        layout.setSpacing(16)

        # Header
        header = QHBoxLayout()
        self.person_label = QLabel("Select a person from the top bar")
        self.person_label.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.person_label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY};")
        header.addWidget(self.person_label)
        header.addStretch()
        btn_calc = QPushButton("⚡  Calculate Tax")
        btn_calc.setObjectName("primaryBtn")
        btn_calc.setFixedHeight(38)
        btn_calc.clicked.connect(self._on_calculate)
        header.addWidget(btn_calc)
        layout.addLayout(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        cl = QVBoxLayout(content)
        cl.setSpacing(16)
        cl.setContentsMargins(0,0,0,0)

        cl.addWidget(self._build_income_section())
        cl.addWidget(self._build_deductions_section())
        cl.addWidget(self._build_results_section())
        cl.addStretch()

        scroll.setWidget(content)
        layout.addWidget(scroll)

    def _build_income_section(self) -> QGroupBox:
        group = QGroupBox("📥  Income Details")
        layout = QFormLayout(group)
        layout.setSpacing(12)

        self.salary_input = self._spin()
        layout.addRow("Salary Income:", self.salary_input)

        self.fd_interest_input = self._spin(readonly=True)
        layout.addRow("FD Interest (auto):", self.fd_interest_input)

        self.savings_interest_input = self._spin(readonly=True)
        layout.addRow("Savings Interest (auto):", self.savings_interest_input)

        self.other_income_input = self._spin()
        layout.addRow("Other Income:", self.other_income_input)

        self.gross_income_label = QLabel("₹ 0.00")
        self.gross_income_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self.gross_income_label.setStyleSheet(f"color: {Theme.PRIMARY};")
        layout.addRow("Gross Total Income:", self.gross_income_label)

        return group

    def _build_deductions_section(self) -> QGroupBox:
        group = QGroupBox("📤  Deductions (Old Regime Only)")
        layout = QFormLayout(group)
        layout.setSpacing(12)

        self.deduction_80c = self._spin()
        layout.addRow("80C (max ₹1.5L):", self.deduction_80c)

        self.deduction_80d = self._spin()
        layout.addRow("80D (max ₹25K):", self.deduction_80d)

        self.home_loan_interest = self._spin()
        layout.addRow("Home Loan Interest:", self.home_loan_interest)

        self.hra_exemption = self._spin()
        layout.addRow("HRA Exemption:", self.hra_exemption)

        note = QLabel("Standard deduction of ₹50,000 is applied automatically.")
        note.setObjectName("mutedLabel")
        layout.addRow("", note)

        return group

    def _build_results_section(self) -> QGroupBox:
        group = QGroupBox("📊  Tax Calculation Results")
        layout = QHBoxLayout(group)
        layout.setSpacing(16)

        # Old regime card
        old_card = self._regime_card("Old Regime", Theme.WARNING, Theme.WARNING_LIGHT)
        old_form = QFormLayout()
        old_form.setSpacing(8)
        self.old_taxable = self._result_lbl()
        self.old_tax     = self._result_lbl()
        self.old_cess    = self._result_lbl()
        self.old_total   = self._result_lbl(bold=True)
        old_form.addRow("Taxable Income:", self.old_taxable)
        old_form.addRow("Base Tax:", self.old_tax)
        old_form.addRow("Cess (4%):", self.old_cess)
        old_form.addRow("Total Tax:", self.old_total)
        old_card.layout().addLayout(old_form)
        layout.addWidget(old_card)

        # New regime card
        new_card = self._regime_card("New Regime", Theme.INFO, Theme.INFO_LIGHT)
        new_form = QFormLayout()
        new_form.setSpacing(8)
        self.new_taxable = self._result_lbl()
        self.new_tax     = self._result_lbl()
        self.new_cess    = self._result_lbl()
        self.new_total   = self._result_lbl(bold=True)
        new_form.addRow("Taxable Income:", self.new_taxable)
        new_form.addRow("Base Tax:", self.new_tax)
        new_form.addRow("Cess (4%):", self.new_cess)
        new_form.addRow("Total Tax:", self.new_total)
        new_card.layout().addLayout(new_form)
        layout.addWidget(new_card)

        # Recommendation
        rec_col = QVBoxLayout()
        rec_label = QLabel("Recommendation")
        rec_label.setObjectName("sectionTitle")
        rec_col.addWidget(rec_label)
        rec_col.addSpacing(8)
        self.recommendation_label = QLabel("Calculate to\nsee recommendation")
        self.recommendation_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self.recommendation_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.recommendation_label.setStyleSheet(f"""
            background-color: {Theme.SURFACE_ALT};
            color: {Theme.TEXT_SECONDARY};
            border: 1px solid {Theme.BORDER};
            border-radius: 10px;
            padding: 20px;
        """)
        rec_col.addWidget(self.recommendation_label)
        layout.addLayout(rec_col)

        return group

    def _regime_card(self, title: str, accent: str, bg: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {Theme.SURFACE};
                border: 1px solid {Theme.BORDER};
                border-top: 3px solid {accent};
                border-radius: 10px;
                padding: 0px;
            }}
        """)
        vl = QVBoxLayout(card)
        vl.setContentsMargins(16, 12, 16, 12)
        vl.setSpacing(8)
        title_lbl = QLabel(title)
        title_lbl.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title_lbl.setStyleSheet(f"color: {accent}; background: transparent; border: none;")
        vl.addWidget(title_lbl)
        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet(f"background: {accent}44; border: none;")
        vl.addWidget(div)
        return card

    def _spin(self, readonly=False) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(0, 99999999.99)
        spin.setDecimals(2)
        spin.setGroupSeparatorShown(True)
        spin.setPrefix("₹ ")
        spin.valueChanged.connect(self._update_gross)
        if readonly:
            spin.setReadOnly(True)
            spin.setStyleSheet(
                f"background: {Theme.SURFACE_ALT}; color: {Theme.TEXT_SECONDARY}; border: 1px solid {Theme.BORDER};"
            )
        return spin

    def _result_lbl(self, bold=False) -> QLabel:
        lbl = QLabel("—")
        style = f"font-size: 13px; color: {Theme.TEXT_PRIMARY}; background: transparent; border: none;"
        if bold:
            style += f" font-weight: 700; font-size: 14px; color: {Theme.TEXT_PRIMARY};"
        lbl.setStyleSheet(style)
        return lbl

    def _update_gross(self):
        gross = (self.salary_input.value() + self.fd_interest_input.value() +
                 self.savings_interest_input.value() + self.other_income_input.value())
        self.gross_income_label.setText(f"₹ {gross:,.2f}")

    def refresh(self):
        person_id = session.selected_person_id
        fy = session.selected_fy
        if not person_id:
            self.person_label.setText("⚠  Please select a person from the top bar")
            self.person_label.setStyleSheet(f"color: {Theme.WARNING}; font-size: 13px;")
            self._clear_inputs()
            return
        person = get_person(person_id)
        if person:
            self.person_label.setText(f"Tax for {person['full_name']}  ·  FY {fy}")
            self.person_label.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; font-size: 13px; font-weight: 700;")
        self.fd_interest_input.setValue(get_total_fd_interest(fy, person_id))
        self.savings_interest_input.setValue(get_total_savings_interest(fy, person_id))
        summary = get_tax_summary(person_id, fy)
        if summary:
            profile = get_tax_profile(person_id, fy)
            if profile:
                self.salary_input.setValue(profile.get("salary_income", 0))
                self.other_income_input.setValue(profile.get("other_income", 0))
                self.deduction_80c.setValue(profile.get("deductions_80c", 0))
                self.deduction_80d.setValue(profile.get("deductions_80d", 0))
                self.home_loan_interest.setValue(profile.get("home_loan_interest", 0))
                self.hra_exemption.setValue(profile.get("hra_exemption", 0))
                self._display_results_from_summary(summary, profile)
        self._update_gross()

    def _clear_inputs(self):
        for s in [self.salary_input, self.fd_interest_input, self.savings_interest_input,
                  self.other_income_input, self.deduction_80c, self.deduction_80d,
                  self.home_loan_interest, self.hra_exemption]:
            s.setValue(0)
        for l in [self.old_taxable,self.old_tax,self.old_cess,self.old_total,
                  self.new_taxable,self.new_tax,self.new_cess,self.new_total]:
            l.setText("—")
        self.recommendation_label.setText("Calculate to\nsee recommendation")
        self.recommendation_label.setStyleSheet(f"""
            background-color: {Theme.SURFACE_ALT}; color: {Theme.TEXT_SECONDARY};
            border: 1px solid {Theme.BORDER}; border-radius: 10px; padding: 20px;
        """)

    def _on_calculate(self):
        person_id = session.selected_person_id
        if not person_id:
            QMessageBox.warning(self, "No Person", "Please select a person from the top bar.")
            return
        result = calculate_and_save_tax(
            person_id=person_id, financial_year=session.selected_fy,
            salary_income=self.salary_input.value(),
            fd_interest=self.fd_interest_input.value(),
            savings_interest=self.savings_interest_input.value(),
            other_income=self.other_income_input.value(),
            deductions_80c=self.deduction_80c.value(),
            deductions_80d=self.deduction_80d.value(),
            home_loan_interest=self.home_loan_interest.value(),
            hra_exemption=self.hra_exemption.value()
        )
        self._show_calc_result(result)
        if self.parent_window: self.parent_window.refresh_overview()
        QMessageBox.information(self, "Tax Calculated",
            f"Tax saved for FY {session.selected_fy}\nRecommended: {result['recommended']}")

    def _show_calc_result(self, result):
        old = result["old_regime"]; new = result["new_regime"]
        self.old_taxable.setText(f"₹ {old['taxable_income']:,.2f}")
        self.old_tax.setText(f"₹ {old['base_tax']:,.2f}")
        self.old_cess.setText(f"₹ {old['cess']:,.2f}")
        self.old_total.setText(f"₹ {old['total_tax']:,.2f}")
        self.new_taxable.setText(f"₹ {new['taxable_income']:,.2f}")
        self.new_tax.setText(f"₹ {new['base_tax']:,.2f}")
        self.new_cess.setText(f"₹ {new['cess']:,.2f}")
        self.new_total.setText(f"₹ {new['total_tax']:,.2f}")
        savings = abs(old['total_tax'] - new['total_tax'])
        is_old  = result['recommended'] == "Old Regime"
        color   = Theme.WARNING if is_old else Theme.INFO
        bg      = Theme.WARNING_LIGHT if is_old else Theme.INFO_LIGHT
        self.recommendation_label.setText(
            f"{'🏆 Old Regime' if is_old else '🏆 New Regime'}\nSave ₹ {savings:,.2f}")
        self.recommendation_label.setStyleSheet(f"""
            background-color: {bg}; color: {color};
            border: 2px solid {color}; border-radius: 10px;
            padding: 20px; font-weight: 700;
        """)

    def _display_results_from_summary(self, summary, profile):
        self.old_taxable.setText(f"₹ {profile.get('taxable_income_old_regime',0):,.2f}")
        self.old_tax.setText(f"₹ {profile.get('tax_old_regime',0):,.2f}")
        self.old_cess.setText(f"₹ {profile.get('cess_amount',0):,.2f}")
        self.old_total.setText(f"₹ {profile.get('total_tax_old',0):,.2f}")
        self.new_taxable.setText(f"₹ {profile.get('taxable_income_new_regime',0):,.2f}")
        self.new_tax.setText(f"₹ {profile.get('tax_new_regime',0):,.2f}")
        self.new_cess.setText(f"₹ {profile.get('tax_new_regime',0)*0.04:,.2f}")
        self.new_total.setText(f"₹ {profile.get('total_tax_new',0):,.2f}")
        is_old = summary['recommended'] == "Old Regime"
        color = Theme.WARNING if is_old else Theme.INFO
        bg    = Theme.WARNING_LIGHT if is_old else Theme.INFO_LIGHT
        self.recommendation_label.setText(
            f"{'🏆 Old Regime' if is_old else '🏆 New Regime'}\nSave ₹ {summary['savings']:,.2f}")
        self.recommendation_label.setStyleSheet(f"""
            background-color: {bg}; color: {color};
            border: 2px solid {color}; border-radius: 10px;
            padding: 20px; font-weight: 700;
        """)
