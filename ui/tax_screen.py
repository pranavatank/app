"""
ui/tax_screen.py — Comprehensive tax estimator similar to Income Tax portal.
FIX: btn_calc now uses Theme.btn() for guaranteed visibility.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QGroupBox, QFormLayout, QFrame, QScrollArea,
    QMessageBox, QDoubleSpinBox, QComboBox, QSplitter
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ui.theme import Theme
from ui.icons import set_btn_icon, icon as app_icon, icon_label as app_icon_label, is_available as icons_available
from ui.widgets.advance_tax_banner import AdvanceTaxBanner
from core.session import session
from models.person import get_person
from models.fd_interest_record import get_total_fd_interest
from models.savings_interest import get_total_savings_interest
from models.tax_profile import get_tax_profile
from models.ais_tis_import import get_ais_tis_data
from engines.tax_engine import calculate_and_save_tax, get_tax_summary
from engines.advance_tax_engine import calculate_advance_tax
from config import get_assessment_year


class TaxScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.data_source = "ais"
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 14)
        layout.setSpacing(12)

        # Advance tax reminder banner
        self.advance_tax_banner = AdvanceTaxBanner(self)
        layout.addWidget(self.advance_tax_banner)

        # Header card
        header_card = QFrame()
        header_card.setObjectName("TaxHeaderCard")
        header_card.setStyleSheet(
            Theme.card_style(
                bg=Theme.SURFACE,
                border_color=Theme.BORDER,
                radius=12,
                padding=0,
                selector="QFrame#TaxHeaderCard",
            )
        )
        header_layout = QHBoxLayout(header_card)
        header_layout.setContentsMargins(16, 12, 16, 12)
        header_layout.setSpacing(12)

        head_left = QVBoxLayout()
        title = QLabel("Tax Planner")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet(Theme.title_style(16))
        head_left.addWidget(title)

        self.person_label = QLabel("Select a person from the top bar")
        self.person_label.setFont(QFont("Segoe UI", 12, QFont.Weight.DemiBold))
        self.person_label.setStyleSheet(Theme.text_style(color=Theme.TEXT_SECONDARY, size=12, weight=600))
        head_left.addWidget(self.person_label)
        header_layout.addLayout(head_left)
        header_layout.addStretch()

        source_label = QLabel("Data Source")
        source_label.setStyleSheet(Theme.section_label_style())
        header_layout.addWidget(source_label)

        self.source_combo = QComboBox()
        self.source_combo.addItems(["AIS/TIS Data", "App Actual Data"])
        self.source_combo.setFixedWidth(170)
        self.source_combo.setFixedHeight(40)
        self.source_combo.setAccessibleName("Tax data source selector")
        self.source_combo.setAccessibleDescription("Choose whether the tax estimate uses AIS/TIS data or app data.")
        self.source_combo.currentIndexChanged.connect(self._on_source_changed)
        header_layout.addWidget(self.source_combo)

        self.btn_calc = Theme.btn("  Estimate Tax", "primary", height=40, min_width=158)
        set_btn_icon(self.btn_calc, "calculate")
        self.btn_calc.setAccessibleName("Estimate tax")
        self.btn_calc.setAccessibleDescription("Calculate tax from the selected data source.")
        self.btn_calc.clicked.connect(self._on_calculate)
        header_layout.addWidget(self.btn_calc)
        layout.addWidget(header_card)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(8)

        # Left rail: forms
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        left_scroll.setStyleSheet("background: transparent; border: none;")

        left_content = QWidget()
        left_content.setStyleSheet("background: transparent;")
        left_layout = QVBoxLayout(left_content)
        left_layout.setSpacing(14)
        left_layout.setContentsMargins(0, 0, 8, 0)

        left_layout.addWidget(self._build_basic_info_section())
        left_layout.addWidget(self._build_salary_section())
        left_layout.addWidget(self._build_house_property_section())
        left_layout.addWidget(self._build_capital_gains_section())
        left_layout.addWidget(self._build_business_section())
        left_layout.addWidget(self._build_other_sources_section())
        left_layout.addWidget(self._build_deductions_section())
        left_layout.addWidget(self._build_tds_section())
        left_layout.addStretch()

        left_scroll.setWidget(left_content)
        splitter.addWidget(left_scroll)

        # Right rail: context + results
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.Shape.NoFrame)
        right_scroll.setStyleSheet("background: transparent; border: none;")

        right_content = QWidget()
        right_content.setStyleSheet("background: transparent;")
        right_layout = QVBoxLayout(right_content)
        right_layout.setSpacing(12)
        right_layout.setContentsMargins(8, 0, 0, 0)

        right_layout.addWidget(self._build_context_panel())
        right_layout.addWidget(self._build_results_section())
        right_layout.addStretch()

        right_scroll.setWidget(right_content)
        splitter.addWidget(right_scroll)

        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter, 1)
        self._connect_signals()
        self._update_context_panel()

    def _build_context_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("TaxContextPanel")
        panel.setStyleSheet(
            Theme.tinted_surface_style(
                radius=12,
                border_color=Theme.BORDER,
                selector="QFrame#TaxContextPanel",
            )
        )

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        title = QLabel("Current Context")
        title.setStyleSheet(Theme.text_style(color=Theme.TEXT_PRIMARY, size=12, weight=700))
        layout.addWidget(title)

        row1 = QHBoxLayout(); row1.setSpacing(8)
        self.ctx_person = QLabel("Person: —")
        self.ctx_person.setStyleSheet(Theme.badge_style(Theme.PRIMARY_LIGHT, Theme.PRIMARY_DARK, radius=10, padding="4px 10px", size=11, weight=600))
        row1.addWidget(self.ctx_person)
        row1.addStretch()
        layout.addLayout(row1)

        row2 = QHBoxLayout(); row2.setSpacing(8)
        self.ctx_fy = QLabel("FY: —")
        self.ctx_fy.setStyleSheet(Theme.badge_style(Theme.SURFACE_ALT, Theme.TEXT_SECONDARY, radius=10, padding="4px 10px", size=11, weight=600))
        row2.addWidget(self.ctx_fy)

        self.ctx_source = QLabel("Source: AIS/TIS")
        self.ctx_source.setStyleSheet(Theme.badge_style(Theme.INFO_LIGHT, Theme.INFO_DARK, radius=10, padding="4px 10px", size=11, weight=600))
        row2.addWidget(self.ctx_source)
        row2.addStretch()
        layout.addLayout(row2)

        return panel

    def _update_context_panel(self):
        pid = session.selected_person_id
        person_name = "All / Not selected"
        if pid:
            p = get_person(pid)
            if p:
                person_name = p.get("full_name") or person_name

        self.ctx_person.setText(f"Person: {person_name}")
        self.ctx_fy.setText(f"FY: {session.selected_fy or '—'}")
        self.ctx_source.setText(f"Source: {'AIS/TIS' if self.data_source == 'ais' else 'App Actual'}")

    # ── Section builders ──────────────────────────────────────────────────────

    def _section_group(self, title: str) -> QGroupBox:
        group = QGroupBox(title)
        group.setStyleSheet(
            Theme.group_box_style() +
            "\nQLabel { border: none; background: transparent; }\n"
        )
        return group

    def _recommendation_style(self, bg: str, fg: str, emphasize: bool = False) -> str:
        border = f"2px solid {fg}" if emphasize else f"1px solid {Theme.BORDER}"
        weight = 700 if emphasize else 600
        return (
            f"background-color: {bg}; color: {fg}; "
            f"border: {border}; border-radius: 10px; "
            f"padding: 20px; font-weight: {weight};"
        )

    def _build_basic_info_section(self) -> QGroupBox:
        group = self._section_group("Basic Information")
        layout = QFormLayout(group); layout.setSpacing(12)
        self.pan_label       = QLabel("—"); layout.addRow("PAN:", self.pan_label)
        self.taxpayer_label  = QLabel("—"); layout.addRow("Name of Taxpayer:", self.taxpayer_label)
        self.ay_label        = QLabel("—")
        self.ay_label.setStyleSheet(Theme.text_style(color=Theme.PRIMARY, weight=600))
        layout.addRow("Assessment Year:", self.ay_label)
        self.category_label  = QLabel("Individual"); layout.addRow("Taxpayer Category:", self.category_label)
        self.age_label       = QLabel("Below 60 years"); layout.addRow("Your Age:", self.age_label)
        return group

    def _build_salary_section(self) -> QGroupBox:
        group = self._section_group("Income — Salaries")
        layout = QFormLayout(group); layout.setSpacing(12)
        self.gross_salary    = self._spin(); layout.addRow("Gross Salary:", self.gross_salary)
        self.exemption_10    = self._spin(); layout.addRow("Exemption claimed u/s 10:", self.exemption_10)
        self.deduction_16ia  = self._spin(readonly=True)
        self.deduction_16ia.setValue(50000)
        layout.addRow("Deduction u/s 16(ia) (Standard ₹50K):", self.deduction_16ia)
        self.deduction_16ii  = self._spin(); layout.addRow("Deduction u/s 16(ii) (Entertainment):", self.deduction_16ii)
        self.deduction_16iii = self._spin(); layout.addRow("Deduction u/s 16(iii) (Professional Tax):", self.deduction_16iii)
        return group

    def _build_house_property_section(self) -> QGroupBox:
        group = self._section_group("Income — House Property")
        layout = QFormLayout(group); layout.setSpacing(12)
        self.self_occupied_interest = self._spin()
        layout.addRow("Self-occupied — Interest on Borrowed Capital:", self.self_occupied_interest)
        self.annual_rent     = self._spin(); layout.addRow("Let-out — Annual Rent Received:", self.annual_rent)
        self.municipal_tax   = self._spin(); layout.addRow("Less: Municipal Taxes Paid:", self.municipal_tax)
        self.unrealized_rent = self._spin(); layout.addRow("Less: Unrealized Rent:", self.unrealized_rent)
        self.letout_interest = self._spin(); layout.addRow("Less: Interest on Borrowed Capital u/s 24(b):", self.letout_interest)
        return group

    def _build_capital_gains_section(self) -> QGroupBox:
        group = self._section_group("Income — Capital Gains")
        layout = QFormLayout(group); layout.setSpacing(12)
        self.stcg_normal = self._spin(); layout.addRow("Short Term Capital Gains (Normal rates):", self.stcg_normal)
        self.stcg_111a   = self._spin(); layout.addRow("STCG u/s 111A (@ 20%):", self.stcg_111a)
        self.ltcg_20     = self._spin(); layout.addRow("Long Term Capital Gains (@ 20%):", self.ltcg_20)
        self.ltcg_112a   = self._spin(); layout.addRow("LTCG u/s 112A (@ 12.5%):", self.ltcg_112a)
        self.ltcg_other  = self._spin(); layout.addRow("LTCG Other (@ 12.5%):", self.ltcg_other)
        return group

    def _build_business_section(self) -> QGroupBox:
        group = self._section_group("Income — Business / Profession")
        layout = QFormLayout(group); layout.setSpacing(12)
        self.presumptive_income      = self._spin(); layout.addRow("Presumptive Income u/s 44AD/44ADA:", self.presumptive_income)
        self.manufacturing_income    = self._spin(); layout.addRow("Manufacturing Business Income:", self.manufacturing_income)
        self.other_business_income   = self._spin(); layout.addRow("Other Business/Profession Income:", self.other_business_income)
        return group

    def _build_other_sources_section(self) -> QGroupBox:
        group = self._section_group("Income — Other Sources")
        layout = QFormLayout(group); layout.setSpacing(12)
        self.savings_interest_input  = self._spin(readonly=True)
        layout.addRow("Interest from Savings Bank Account:", self.savings_interest_input)
        self.fd_interest_input       = self._spin(readonly=True)
        layout.addRow("Interest from Deposit (Bank/Post Office):", self.fd_interest_input)
        self.other_interest          = self._spin(); layout.addRow("Other Interest Income:", self.other_interest)
        self.dividend_income         = self._spin(); layout.addRow("Dividend Income (Normal rates):", self.dividend_income)
        self.rental_income           = self._spin(); layout.addRow("Rental Income:", self.rental_income)
        self.lottery_winnings        = self._spin(); layout.addRow("Winnings from Lotteries/Races:", self.lottery_winnings)
        self.online_game_winnings    = self._spin(); layout.addRow("Winnings from Online Games u/s 115BBJ:", self.online_game_winnings)
        self.other_income_input      = self._spin(); layout.addRow("Any Other Income:", self.other_income_input)
        self.gross_income_label = QLabel("₹ 0.00")
        self.gross_income_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self.gross_income_label.setStyleSheet(Theme.text_style(color=Theme.PRIMARY, size=14, weight=700))
        layout.addRow("Gross Total Income:", self.gross_income_label)
        return group

    def _build_deductions_section(self) -> QGroupBox:
        group = self._section_group("Deductions (Old Regime Only)")
        layout = QFormLayout(group); layout.setSpacing(12)
        self.deduction_80c    = self._spin(); layout.addRow("80C — LIC, PF, PPF, NSC (max ₹1.5L):", self.deduction_80c)
        self.deduction_80ccc  = self._spin(); layout.addRow("80CCC — Pension Fund:", self.deduction_80ccc)
        self.deduction_80ccd1 = self._spin(); layout.addRow("80CCD(1) — NPS Employee:", self.deduction_80ccd1)
        self.deduction_80ccd1b= self._spin(); layout.addRow("80CCD(1B) — Additional NPS (max ₹50K):", self.deduction_80ccd1b)
        self.deduction_80ccd2 = self._spin(); layout.addRow("80CCD(2) — NPS Employer:", self.deduction_80ccd2)
        self.deduction_80d    = self._spin(); layout.addRow("80D — MediClaim Premium (max ₹25K):", self.deduction_80d)
        self.deduction_80g    = self._spin(); layout.addRow("80G — Donations:", self.deduction_80g)
        self.deduction_80e    = self._spin(); layout.addRow("80E — Interest on Education Loan:", self.deduction_80e)
        self.deduction_80ee   = self._spin(); layout.addRow("80EE — Interest on Home Loan:", self.deduction_80ee)
        self.deduction_80tta  = self._spin(); layout.addRow("80TTA — Interest on Savings (max ₹10K):", self.deduction_80tta)
        self.deduction_80ttb  = self._spin(); layout.addRow("80TTB — Senior Citizens Deposits:", self.deduction_80ttb)
        self.home_loan_interest = self._spin(); layout.addRow("Home Loan Interest u/s 24(b):", self.home_loan_interest)
        self.hra_exemption    = self._spin(); layout.addRow("HRA Exemption:", self.hra_exemption)
        note = QLabel("Standard deduction of ₹50,000 is applied automatically in salary section.")
        note.setStyleSheet(Theme.text_style(color=Theme.TEXT_MUTED, size=12))
        layout.addRow("", note)
        return group

    def _build_tds_section(self) -> QGroupBox:
        group = self._section_group("TDS / TCS & Tax Payments")
        layout = QFormLayout(group); layout.setSpacing(12)
        self.tds_salary          = self._spin(); layout.addRow("TDS on Salary:", self.tds_salary)
        self.tds_other           = self._spin(); layout.addRow("TDS on Other Income:", self.tds_other)
        self.tcs_collected       = self._spin(); layout.addRow("TCS Collected:", self.tcs_collected)
        self.advance_tax         = self._spin(); layout.addRow("Advance Tax Paid:", self.advance_tax)
        self.self_assessment_tax = self._spin(); layout.addRow("Self-Assessment Tax Paid:", self.self_assessment_tax)
        return group

    def _build_results_section(self) -> QGroupBox:
        group = self._section_group("Tax Calculation Results")
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        old_card = self._regime_card("Old Regime", Theme.WARNING, Theme.WARNING_LIGHT)
        old_form = QFormLayout(); old_form.setSpacing(6)
        self.old_taxable = self._result_lbl(); self.old_tax = self._result_lbl()
        self.old_cess    = self._result_lbl(); self.old_total = self._result_lbl(bold=True)
        old_form.addRow("Taxable Income:", self.old_taxable)
        old_form.addRow("Base Tax:", self.old_tax)
        old_form.addRow("Cess (4%):", self.old_cess)
        old_form.addRow("Total Tax:", self.old_total)
        old_card.layout().addLayout(old_form)
        layout.addWidget(old_card)

        new_card = self._regime_card("New Regime", Theme.INFO, Theme.INFO_LIGHT)
        new_form = QFormLayout(); new_form.setSpacing(6)
        self.new_taxable = self._result_lbl(); self.new_tax = self._result_lbl()
        self.new_cess    = self._result_lbl(); self.new_total = self._result_lbl(bold=True)
        new_form.addRow("Taxable Income:", self.new_taxable)
        new_form.addRow("Base Tax:", self.new_tax)
        new_form.addRow("Cess (4%):", self.new_cess)
        new_form.addRow("Total Tax:", self.new_total)
        new_card.layout().addLayout(new_form)
        layout.addWidget(new_card)

        rec_label = QLabel("Recommendation")
        rec_label.setStyleSheet(Theme.section_label_style())
        layout.addWidget(rec_label)

        self.recommendation_label = QLabel("Calculate to\nsee recommendation")
        self.recommendation_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self.recommendation_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.recommendation_label.setStyleSheet(
            self._recommendation_style(Theme.SURFACE_ALT, Theme.TEXT_SECONDARY, emphasize=False)
        )
        layout.addWidget(self.recommendation_label)

        helper = QLabel("Tip: Use App Actual Data when AIS/TIS is outdated.")
        helper.setWordWrap(True)
        helper.setStyleSheet(Theme.muted_style(11))
        layout.addWidget(helper)
        return group

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _regime_card(self, title: str, accent: str, bg: str) -> QFrame:
        card = QFrame()
        card.setObjectName("TaxRegimeCard")
        card.setStyleSheet(
            Theme.card_style(
                bg=bg,
                border_color=accent,
                radius=10,
                padding=0,
                left_accent=accent,
                selector="QFrame#TaxRegimeCard",
            )
        )
        vl = QVBoxLayout(card); vl.setContentsMargins(16,12,16,12); vl.setSpacing(8)
        t = QLabel(title); t.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        t.setStyleSheet(Theme.text_style(color=accent, size=13, weight=700))
        vl.addWidget(t)
        div = QFrame(); div.setFixedHeight(1)
        div.setStyleSheet(f"background: {accent}44; border: none;")
        vl.addWidget(div)
        return card

    def _spin(self, readonly=False) -> QDoubleSpinBox:
        s = QDoubleSpinBox()
        s.setRange(0, 99_999_999.99)
        s.setDecimals(2); s.setGroupSeparatorShown(True); s.setPrefix("₹ ")
        if readonly:
            s.setReadOnly(True)
            s.setStyleSheet(f"background: {Theme.SURFACE_ALT}; color: {Theme.TEXT_SECONDARY}; border: 1px solid {Theme.BORDER};")
        return s

    def _result_lbl(self, bold=False) -> QLabel:
        l = QLabel("—")
        if bold:
            l.setStyleSheet(
                Theme.text_style(color=Theme.TEXT_PRIMARY, size=14, weight=700)
                + " border: none; background: transparent; padding: 0; margin: 0;"
            )
        else:
            l.setStyleSheet(
                Theme.text_style(color=Theme.TEXT_PRIMARY, size=13, weight=400)
                + " border: none; background: transparent; padding: 0; margin: 0;"
            )
        return l

    def _connect_signals(self):
        for spin in [self.gross_salary, self.exemption_10, self.deduction_16ii, self.deduction_16iii,
                     self.self_occupied_interest, self.annual_rent, self.municipal_tax, self.unrealized_rent,
                     self.letout_interest, self.stcg_normal, self.stcg_111a, self.ltcg_20, self.ltcg_112a,
                     self.ltcg_other, self.presumptive_income, self.manufacturing_income, self.other_business_income,
                     self.savings_interest_input, self.fd_interest_input, self.other_interest,
                     self.dividend_income, self.rental_income, self.lottery_winnings,
                     self.online_game_winnings, self.other_income_input]:
            spin.valueChanged.connect(self._update_gross)

    def _on_source_changed(self):
        self.data_source = "ais" if self.source_combo.currentIndex() == 0 else "app"
        self._update_context_panel()
        self.refresh()

    def _update_gross(self):
        salary = max(0, self.gross_salary.value() - self.exemption_10.value() -
                     self.deduction_16ia.value() - self.deduction_16ii.value() - self.deduction_16iii.value())
        nav = self.annual_rent.value() - self.municipal_tax.value() - self.unrealized_rent.value()
        house = max(-200000, nav - nav*0.30 - self.letout_interest.value() - self.self_occupied_interest.value())
        cg = (self.stcg_normal.value() + self.stcg_111a.value() + self.ltcg_20.value() +
              self.ltcg_112a.value() + self.ltcg_other.value())
        biz = (self.presumptive_income.value() + self.manufacturing_income.value() + self.other_business_income.value())
        others = (self.savings_interest_input.value() + self.fd_interest_input.value() +
                  self.other_interest.value() + self.dividend_income.value() +
                  self.rental_income.value() + self.lottery_winnings.value() +
                  self.online_game_winnings.value() + self.other_income_input.value())
        gross = salary + max(0, house) + cg + biz + others
        self.gross_income_label.setText(f"₹ {gross:,.2f}")

    def refresh(self):
        pid = session.selected_person_id
        fy  = session.selected_fy
        self._update_context_panel()
        if not pid:
            self.person_label.setText("Please select a person from the top bar")
            self.person_label.setStyleSheet(Theme.text_style(color=Theme.WARNING, size=13, weight=600))
            self._clear_inputs()
            self.advance_tax_banner.clear()
            return
        person = get_person(pid)
        if person:
            ay = get_assessment_year(fy)
            self.person_label.setText(f"Tax Estimator for {person['full_name']}  ·  FY {fy}")
            self.person_label.setStyleSheet(Theme.text_style(color=Theme.TEXT_PRIMARY, size=13, weight=700))
            self.taxpayer_label.setText(person["full_name"])
            self.pan_label.setText(person.get("pan_number","—"))
            self.ay_label.setText(ay)
        if self.data_source == "ais":
            self._load_ais_data(pid, fy)
        else:
            self._load_app_data(pid, fy)
        self._update_gross()
        self._update_advance_tax_banner()

    def _load_ais_data(self, pid, fy):
        ais = get_ais_tis_data(pid, fy, source_type="AIS")
        if not ais:
            ais = get_ais_tis_data(pid, fy, source_type="TIS")
        if ais:
            self.gross_salary.setValue(ais.get("salary_income",0))
            self.fd_interest_input.setValue(ais.get("fd_interest",0))
            self.savings_interest_input.setValue(ais.get("savings_interest",0))
            self.other_interest.setValue(ais.get("other_interest",0))
            self.dividend_income.setValue(ais.get("dividend_income",0))
            self.rental_income.setValue(ais.get("rental_income",0))
            self.other_income_input.setValue(ais.get("other_income",0))
            self.tds_salary.setValue(ais.get("tds_deducted",0))
        else:
            self._clear_income_fields()

    def _load_app_data(self, pid, fy):
        self.fd_interest_input.setValue(get_total_fd_interest(fy, pid))
        self.savings_interest_input.setValue(get_total_savings_interest(fy, pid))
        profile = get_tax_profile(pid, fy)
        if profile:
            self.gross_salary.setValue(profile.get("salary_income",0))
            self.other_income_input.setValue(profile.get("other_income",0))
            self.deduction_80c.setValue(profile.get("deductions_80c",0))
            self.deduction_80d.setValue(profile.get("deductions_80d",0))
            self.home_loan_interest.setValue(profile.get("home_loan_interest",0))
            self.hra_exemption.setValue(profile.get("hra_exemption",0))
            summary = get_tax_summary(pid, fy)
            if summary:
                self._display_results_from_summary(summary, profile)

    def _clear_income_fields(self):
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
                  self.deduction_80c, self.deduction_80ccc, self.deduction_80ccd1,
                  self.deduction_80ccd1b, self.deduction_80ccd2, self.deduction_80d,
                  self.deduction_80g, self.deduction_80e, self.deduction_80ee,
                  self.deduction_80tta, self.deduction_80ttb, self.home_loan_interest, self.hra_exemption,
                  self.tds_salary, self.tds_other, self.tcs_collected, self.advance_tax, self.self_assessment_tax]:
            s.setValue(0)
        for l in [self.old_taxable, self.old_tax, self.old_cess, self.old_total,
                  self.new_taxable, self.new_tax, self.new_cess, self.new_total]:
            l.setText("—")
        self.recommendation_label.setText("Calculate to\nsee recommendation")
        self.recommendation_label.setStyleSheet(
            self._recommendation_style(Theme.SURFACE_ALT, Theme.TEXT_SECONDARY, emphasize=False)
        )

    def _on_calculate(self):
        pid = session.selected_person_id
        if not pid:
            QMessageBox.warning(self, "No Person", "Please select a person from the top bar.")
            return
        salary = max(0, self.gross_salary.value() - self.exemption_10.value() -
                     self.deduction_16ia.value() - self.deduction_16ii.value() - self.deduction_16iii.value())
        other_income = (self.other_interest.value() + self.dividend_income.value() +
                        self.rental_income.value() + self.lottery_winnings.value() +
                        self.online_game_winnings.value() + self.other_income_input.value())
        total_80c = min(150000, self.deduction_80c.value() + self.deduction_80ccc.value() + self.deduction_80ccd1.value())
        result = calculate_and_save_tax(
            person_id=pid, financial_year=session.selected_fy,
            salary_income=salary,
            fd_interest=self.fd_interest_input.value(),
            savings_interest=self.savings_interest_input.value(),
            other_income=other_income,
            deductions_80c=total_80c,
            deductions_80d=self.deduction_80d.value(),
            home_loan_interest=self.home_loan_interest.value(),
            hra_exemption=self.hra_exemption.value(),
        )
        self._show_calc_result(result)
        if self.parent_window:
            self.parent_window.refresh_overview()
        QMessageBox.information(self, "Tax Estimated",
            f"Tax calculated for FY {session.selected_fy}\n\nRecommended: {result['recommended']}")

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
        savings = abs(old["total_tax"] - new["total_tax"])
        is_old  = result["recommended"] == "Old Regime"
        color   = Theme.WARNING if is_old else Theme.INFO
        bg      = Theme.WARNING_LIGHT if is_old else Theme.INFO_LIGHT
        self.recommendation_label.setText(
            f"{'Old Regime ✓' if is_old else 'New Regime ✓'}\nSave ₹ {savings:,.2f}")
        self.recommendation_label.setStyleSheet(self._recommendation_style(bg, color, emphasize=True))

    def _display_results_from_summary(self, summary, profile):
        self.old_taxable.setText(f"₹ {profile.get('taxable_income_old_regime',0):,.2f}")
        self.old_tax.setText(f"₹ {profile.get('tax_old_regime',0):,.2f}")
        self.old_cess.setText(f"₹ {profile.get('cess_amount',0):,.2f}")
        self.old_total.setText(f"₹ {profile.get('total_tax_old',0):,.2f}")
        self.new_taxable.setText(f"₹ {profile.get('taxable_income_new_regime',0):,.2f}")
        self.new_tax.setText(f"₹ {profile.get('tax_new_regime',0):,.2f}")
        self.new_cess.setText(f"₹ {profile.get('tax_new_regime',0)*0.04:,.2f}")
        self.new_total.setText(f"₹ {profile.get('total_tax_new',0):,.2f}")
        is_old = summary["recommended"] == "Old Regime"
        color  = Theme.WARNING if is_old else Theme.INFO
        bg     = Theme.WARNING_LIGHT if is_old else Theme.INFO_LIGHT
        self.recommendation_label.setText(
            f"{'Old Regime ✓' if is_old else 'New Regime ✓'}\nSave ₹ {summary['savings']:,.2f}")
        self.recommendation_label.setStyleSheet(self._recommendation_style(bg, color, emphasize=True))

    def _update_advance_tax_banner(self):
        """Calculate and display advance tax reminder."""
        pid = session.selected_person_id
        fy = session.selected_fy
        
        if not pid:
            self.advance_tax_banner.clear()
            return
        
        profile = get_tax_profile(pid, fy)
        if not profile:
            self.advance_tax_banner.clear()
            return
        
        # Use the better regime's tax
        tax_old = profile.get("total_tax_old", 0)
        tax_new = profile.get("total_tax_new", 0)
        annual_tax = min(tax_old, tax_new) if tax_old > 0 and tax_new > 0 else max(tax_old, tax_new)
        
        gross_income = profile.get("gross_total_income", 0)
        tds = profile.get("tds_deducted", 0)
        advance_paid = profile.get("advance_tax_paid", 0)
        
        result = calculate_advance_tax(
            financial_year=fy,
            gross_income=gross_income,
            annual_tax=annual_tax,
            tds_deducted=tds,
            advance_tax_paid=advance_paid,
        )
        
        self.advance_tax_banner.update_reminder(result)
