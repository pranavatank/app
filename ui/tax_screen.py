"""
ui/tax_screen.py — Comprehensive tax estimator similar to Income Tax portal.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QFormLayout, QFrame, QScrollArea,
    QMessageBox, QDoubleSpinBox, QComboBox, QRadioButton, QButtonGroup
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ui.theme import Theme
from core.session import session
from models.person import get_person
from models.fd_interest_record import get_total_fd_interest
from models.savings_interest import get_total_savings_interest
from models.tax_profile import get_tax_profile
from models.ais_tis_import import get_ais_tis_data
from engines.tax_engine import calculate_and_save_tax, get_tax_summary
from config import get_assessment_year


class TaxScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.data_source = "ais"  # "ais" or "app"
        self._build_ui()

    def _build_ui(self):
        self.setObjectName("taxRoot")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 20)
        layout.setSpacing(16)

        # Header with data source selector
        header = QHBoxLayout()
        self.person_label = QLabel("Select a person from the top bar")
        self.person_label.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.person_label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY};")
        header.addWidget(self.person_label)
        header.addStretch()
        
        # Data source selector
        source_label = QLabel("Data Source:")
        source_label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 12px;")
        header.addWidget(source_label)
        
        self.source_combo = QComboBox()
        self.source_combo.addItems(["AIS/TIS Data", "App Actual Data"])
        self.source_combo.setFixedWidth(160)
        self.source_combo.currentIndexChanged.connect(self._on_source_changed)
        header.addWidget(self.source_combo)
        
        btn_calc = QPushButton("⚡  Estimate Tax")
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

        cl.addWidget(self._build_basic_info_section())
        cl.addWidget(self._build_salary_section())
        cl.addWidget(self._build_house_property_section())
        cl.addWidget(self._build_capital_gains_section())
        cl.addWidget(self._build_business_section())
        cl.addWidget(self._build_other_sources_section())
        cl.addWidget(self._build_deductions_section())
        cl.addWidget(self._build_tds_section())
        cl.addWidget(self._build_results_section())
        cl.addStretch()

        scroll.setWidget(content)
        layout.addWidget(scroll)
        
        # Connect all value changed signals after all widgets are created
        self._connect_signals()

    def _build_basic_info_section(self) -> QGroupBox:
        group = QGroupBox("📋  Basic Information")
        layout = QFormLayout(group)
        layout.setSpacing(12)

        self.pan_label = QLabel("—")
        layout.addRow("PAN:", self.pan_label)

        self.taxpayer_label = QLabel("—")
        layout.addRow("Name of Taxpayer:", self.taxpayer_label)

        self.ay_label = QLabel("—")
        self.ay_label.setStyleSheet(f"color: {Theme.PRIMARY}; font-weight: 600;")
        layout.addRow("Assessment Year:", self.ay_label)

        self.category_label = QLabel("Individual")
        layout.addRow("Taxpayer Category:", self.category_label)

        self.age_label = QLabel("Below 60 years")
        layout.addRow("Your Age:", self.age_label)

        return group

    def _build_salary_section(self) -> QGroupBox:
        group = QGroupBox("💼  Income under the head Salaries")
        layout = QFormLayout(group)
        layout.setSpacing(12)

        self.gross_salary = self._spin()
        layout.addRow("Gross Salary:", self.gross_salary)

        self.exemption_10 = self._spin()
        layout.addRow("Exemption claimed u/s 10:", self.exemption_10)

        self.deduction_16ia = self._spin(readonly=True)
        self.deduction_16ia.setValue(50000)  # Standard deduction
        layout.addRow("Deduction u/s 16(ia) (Standard):", self.deduction_16ia)

        self.deduction_16ii = self._spin()
        layout.addRow("Deduction u/s 16(ii) (Entertainment):", self.deduction_16ii)

        self.deduction_16iii = self._spin()
        layout.addRow("Deduction u/s 16(iii) (Professional Tax):", self.deduction_16iii)

        return group

    def _build_house_property_section(self) -> QGroupBox:
        group = QGroupBox("🏠  Income under the head House Property")
        layout = QFormLayout(group)
        layout.setSpacing(12)

        # Self-occupied
        self.self_occupied_interest = self._spin()
        layout.addRow("Self-occupied - Interest on Borrowed Capital:", self.self_occupied_interest)

        # Let-out property
        self.annual_rent = self._spin()
        layout.addRow("Let-out - Annual Rent Received:", self.annual_rent)

        self.municipal_tax = self._spin()
        layout.addRow("Less: Municipal Taxes Paid:", self.municipal_tax)

        self.unrealized_rent = self._spin()
        layout.addRow("Less: Unrealized Rent:", self.unrealized_rent)

        self.letout_interest = self._spin()
        layout.addRow("Less: Interest on Borrowed Capital u/s 24(b):", self.letout_interest)

        return group

    def _build_capital_gains_section(self) -> QGroupBox:
        group = QGroupBox("📈  Income under the head Capital Gains")
        layout = QFormLayout(group)
        layout.setSpacing(12)

        self.stcg_normal = self._spin()
        layout.addRow("Short Term Capital Gains (Normal rates):", self.stcg_normal)

        self.stcg_111a = self._spin()
        layout.addRow("STCG u/s 111A (@ 20%):", self.stcg_111a)

        self.ltcg_20 = self._spin()
        layout.addRow("Long Term Capital Gains (@ 20%):", self.ltcg_20)

        self.ltcg_112a = self._spin()
        layout.addRow("LTCG u/s 112A (@ 12.5%):", self.ltcg_112a)

        self.ltcg_other = self._spin()
        layout.addRow("LTCG Other (@ 12.5%):", self.ltcg_other)

        return group

    def _build_business_section(self) -> QGroupBox:
        group = QGroupBox("💼  Income under the head Business or Profession")
        layout = QFormLayout(group)
        layout.setSpacing(12)

        self.presumptive_income = self._spin()
        layout.addRow("Presumptive Income u/s 44AD/44ADA:", self.presumptive_income)

        self.manufacturing_income = self._spin()
        layout.addRow("Manufacturing Business Income:", self.manufacturing_income)

        self.other_business_income = self._spin()
        layout.addRow("Other Business/Profession Income:", self.other_business_income)

        return group

    def _build_other_sources_section(self) -> QGroupBox:
        group = QGroupBox("💰  Income under the head Other Sources")
        layout = QFormLayout(group)
        layout.setSpacing(12)

        self.savings_interest_input = self._spin(readonly=True)
        layout.addRow("Interest from Savings Bank Account:", self.savings_interest_input)

        self.fd_interest_input = self._spin(readonly=True)
        layout.addRow("Interest from Deposit (Bank/Post Office):", self.fd_interest_input)

        self.other_interest = self._spin()
        layout.addRow("Other Interest Income:", self.other_interest)

        self.dividend_income = self._spin()
        layout.addRow("Dividend Income (Taxable at Normal rates):", self.dividend_income)

        self.rental_income = self._spin()
        layout.addRow("Rental Income:", self.rental_income)

        self.lottery_winnings = self._spin()
        layout.addRow("Winnings from Lotteries/Races/Card Games:", self.lottery_winnings)

        self.online_game_winnings = self._spin()
        layout.addRow("Winnings from Online Games u/s 115BBJ:", self.online_game_winnings)

        self.other_income_input = self._spin()
        layout.addRow("Any Other Income:", self.other_income_input)

        # Gross Total Income
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
        layout.addRow("80C (LIC, PF, PPF, NSC - max ₹1.5L):", self.deduction_80c)

        self.deduction_80ccc = self._spin()
        layout.addRow("80CCC (Pension Fund):", self.deduction_80ccc)

        self.deduction_80ccd1 = self._spin()
        layout.addRow("80CCD(1) (NPS Employee contribution):", self.deduction_80ccd1)

        self.deduction_80ccd1b = self._spin()
        layout.addRow("80CCD(1B) (Additional NPS - max ₹50K):", self.deduction_80ccd1b)

        self.deduction_80ccd2 = self._spin()
        layout.addRow("80CCD(2) (NPS Employer contribution):", self.deduction_80ccd2)

        self.deduction_80d = self._spin()
        layout.addRow("80D (MediClaim Premium - max ₹25K):", self.deduction_80d)

        self.deduction_80g = self._spin()
        layout.addRow("80G (Donations):", self.deduction_80g)

        self.deduction_80e = self._spin()
        layout.addRow("80E (Interest on Education Loan):", self.deduction_80e)

        self.deduction_80ee = self._spin()
        layout.addRow("80EE (Interest on Home Loan):", self.deduction_80ee)

        self.deduction_80tta = self._spin()
        layout.addRow("80TTA (Interest on Savings - max ₹10K):", self.deduction_80tta)

        self.deduction_80ttb = self._spin()
        layout.addRow("80TTB (Interest on Deposits - Senior Citizens):", self.deduction_80ttb)

        self.home_loan_interest = self._spin()
        layout.addRow("Home Loan Interest (24b):", self.home_loan_interest)

        self.hra_exemption = self._spin()
        layout.addRow("HRA Exemption:", self.hra_exemption)

        note = QLabel("Standard deduction of ₹50,000 is applied automatically.")
        note.setObjectName("mutedLabel")
        layout.addRow("", note)

        return group

    def _build_tds_section(self) -> QGroupBox:
        group = QGroupBox("💳  TDS/TCS & Tax Payments")
        layout = QFormLayout(group)
        layout.setSpacing(12)

        self.tds_salary = self._spin()
        layout.addRow("TDS on Salary:", self.tds_salary)

        self.tds_other = self._spin()
        layout.addRow("TDS on Other Income:", self.tds_other)

        self.tcs_collected = self._spin()
        layout.addRow("TCS Collected:", self.tcs_collected)

        self.advance_tax = self._spin()
        layout.addRow("Advance Tax Paid:", self.advance_tax)

        self.self_assessment_tax = self._spin()
        layout.addRow("Self-Assessment Tax Paid:", self.self_assessment_tax)

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
        # Don't connect signal yet - will be connected after all widgets are created
        if readonly:
            spin.setReadOnly(True)
            spin.setStyleSheet(
                f"background: {Theme.SURFACE_ALT}; color: {Theme.TEXT_SECONDARY}; border: 1px solid {Theme.BORDER};"
            )
        return spin

    def _on_source_changed(self):
        self.data_source = "ais" if self.source_combo.currentIndex() == 0 else "app"
        self.refresh()

    def _connect_signals(self):
        """Connect all spinbox signals after widgets are created."""
        spinboxes = [
            self.gross_salary, self.exemption_10, self.deduction_16ii, self.deduction_16iii,
            self.self_occupied_interest, self.annual_rent, self.municipal_tax, self.unrealized_rent,
            self.letout_interest, self.stcg_normal, self.stcg_111a, self.ltcg_20, self.ltcg_112a,
            self.ltcg_other, self.presumptive_income, self.manufacturing_income, self.other_business_income,
            self.savings_interest_input, self.fd_interest_input, self.other_interest, 
            self.dividend_income, self.rental_income, self.lottery_winnings,
            self.online_game_winnings, self.other_income_input
        ]
        for spin in spinboxes:
            spin.valueChanged.connect(self._update_gross)

    def _result_lbl(self, bold=False) -> QLabel:
        lbl = QLabel("—")
        style = f"font-size: 13px; color: {Theme.TEXT_PRIMARY}; background: transparent; border: none;"
        if bold:
            style += f" font-weight: 700; font-size: 14px; color: {Theme.TEXT_PRIMARY};"
        lbl.setStyleSheet(style)
        return lbl

    def _update_gross(self):
        # Calculate salary income
        salary = self.gross_salary.value() - self.exemption_10.value() - \
                 self.deduction_16ia.value() - self.deduction_16ii.value() - self.deduction_16iii.value()
        
        # Calculate house property income
        nav = self.annual_rent.value() - self.municipal_tax.value() - self.unrealized_rent.value()
        std_ded = nav * 0.30
        house_income = nav - std_ded - self.letout_interest.value() - self.self_occupied_interest.value()
        
        # Capital gains
        capital_gains = (self.stcg_normal.value() + self.stcg_111a.value() + 
                        self.ltcg_20.value() + self.ltcg_112a.value() + self.ltcg_other.value())
        
        # Business income
        business = (self.presumptive_income.value() + self.manufacturing_income.value() + 
                   self.other_business_income.value())
        
        # Other sources
        other_sources = (self.savings_interest_input.value() + self.fd_interest_input.value() + 
                        self.other_interest.value() + self.dividend_income.value() + 
                        self.rental_income.value() + self.lottery_winnings.value() + 
                        self.online_game_winnings.value() + self.other_income_input.value())
        
        gross = max(0, salary) + max(0, house_income) + capital_gains + business + other_sources
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
            ay = get_assessment_year(fy)
            self.person_label.setText(f"Tax Estimator for {person['full_name']}  ·  FY {fy}")
            self.person_label.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; font-size: 13px; font-weight: 700;")
            self.taxpayer_label.setText(person['full_name'])
            self.pan_label.setText(person.get('pan_number', '—'))
            self.ay_label.setText(ay)
        
        # Load data based on source
        if self.data_source == "ais":
            self._load_ais_data(person_id, fy)
        else:
            self._load_app_data(person_id, fy)
        
        self._update_gross()

    def _load_ais_data(self, person_id: int, fy: str):
        """Load data from AIS/TIS import."""
        ais_data = get_ais_tis_data(person_id, fy)
        
        if ais_data:
            # Salary
            self.gross_salary.setValue(ais_data.get('salary_income', 0))
            
            # Interest income
            self.fd_interest_input.setValue(ais_data.get('fd_interest', 0))
            self.savings_interest_input.setValue(ais_data.get('savings_interest', 0))
            self.other_interest.setValue(ais_data.get('other_interest', 0))
            
            # Other income
            self.dividend_income.setValue(ais_data.get('dividend_income', 0))
            self.rental_income.setValue(ais_data.get('rental_income', 0))
            self.other_income_input.setValue(ais_data.get('other_income', 0))
            
            # TDS
            self.tds_salary.setValue(ais_data.get('tds_deducted', 0))
        else:
            # No AIS data, clear fields
            self._clear_income_fields()

    def _load_app_data(self, person_id: int, fy: str):
        """Load data from app's actual records."""
        # Load interest from app
        self.fd_interest_input.setValue(get_total_fd_interest(fy, person_id))
        self.savings_interest_input.setValue(get_total_savings_interest(fy, person_id))
        
        # Load saved tax profile if exists
        profile = get_tax_profile(person_id, fy)
        if profile:
            self.gross_salary.setValue(profile.get("salary_income", 0))
            self.other_income_input.setValue(profile.get("other_income", 0))
            self.deduction_80c.setValue(profile.get("deductions_80c", 0))
            self.deduction_80d.setValue(profile.get("deductions_80d", 0))
            self.home_loan_interest.setValue(profile.get("home_loan_interest", 0))
            self.hra_exemption.setValue(profile.get("hra_exemption", 0))
            
            # Display saved results
            summary = get_tax_summary(person_id, fy)
            if summary:
                self._display_results_from_summary(summary, profile)

    def _clear_income_fields(self):
        """Clear all income input fields."""
        for s in [self.gross_salary, self.exemption_10, self.deduction_16ii, self.deduction_16iii,
                  self.self_occupied_interest, self.annual_rent, self.municipal_tax, self.unrealized_rent,
                  self.letout_interest, self.stcg_normal, self.stcg_111a, self.ltcg_20, self.ltcg_112a,
                  self.ltcg_other, self.presumptive_income, self.manufacturing_income, self.other_business_income,
                  self.other_interest, self.dividend_income, self.rental_income, self.lottery_winnings,
                  self.online_game_winnings, self.other_income_input]:
            s.setValue(0)

    def _clear_inputs(self):
        self._clear_income_fields()
        for s in [self.fd_interest_input, self.savings_interest_input,
                  self.deduction_80c, self.deduction_80ccc, self.deduction_80ccd1, self.deduction_80ccd1b,
                  self.deduction_80ccd2, self.deduction_80d, self.deduction_80g, self.deduction_80e,
                  self.deduction_80ee, self.deduction_80tta, self.deduction_80ttb,
                  self.home_loan_interest, self.hra_exemption,
                  self.tds_salary, self.tds_other, self.tcs_collected, self.advance_tax, self.self_assessment_tax]:
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
        
        # Calculate net salary income
        salary = self.gross_salary.value() - self.exemption_10.value() - \
                 self.deduction_16ia.value() - self.deduction_16ii.value() - self.deduction_16iii.value()
        
        # Calculate total interest
        total_interest = (self.fd_interest_input.value() + self.savings_interest_input.value() + 
                         self.other_interest.value())
        
        # Calculate other income
        other_income = (self.dividend_income.value() + self.rental_income.value() + 
                       self.lottery_winnings.value() + self.online_game_winnings.value() + 
                       self.other_income_input.value())
        
        # Total deductions for 80C family
        total_80c = min(150000, self.deduction_80c.value() + self.deduction_80ccc.value() + 
                       self.deduction_80ccd1.value())
        
        result = calculate_and_save_tax(
            person_id=person_id, 
            financial_year=session.selected_fy,
            salary_income=max(0, salary),
            fd_interest=self.fd_interest_input.value(),
            savings_interest=self.savings_interest_input.value(),
            other_income=total_interest - self.fd_interest_input.value() - self.savings_interest_input.value() + other_income,
            deductions_80c=total_80c,
            deductions_80d=self.deduction_80d.value(),
            home_loan_interest=self.home_loan_interest.value(),
            hra_exemption=self.hra_exemption.value()
        )
        
        self._show_calc_result(result)
        if self.parent_window: 
            self.parent_window.refresh_overview()
        
        QMessageBox.information(self, "Tax Estimated",
            f"Tax calculated for FY {session.selected_fy}\nRecommended: {result['recommended']}")

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
