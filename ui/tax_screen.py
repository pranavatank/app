"""
ui/tax_screen.py — Tax estimator for New Regime only (FY 2023-24 onwards).

The owner has irrevocably opted into the New Regime (Form 10-IEA).
This screen shows only New Regime inputs and calculations.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QGroupBox, QFormLayout, QFrame, QScrollArea,
    QDoubleSpinBox, QComboBox, QSplitter, QSizePolicy, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor

from ui.theme import Theme
from ui.icons import set_btn_icon
from ui.widgets.advance_tax_banner import AdvanceTaxBanner
from ui.widgets.toast_utils import show_success, show_danger
from ui.widgets.section import CollapsibleSection
from ui.widgets.money_label import format_inr
from core.session import session
from models.person import get_person, get_all_persons
from models.fd_interest_record import get_total_fd_interest
from models.savings_interest import get_total_savings_interest
from models.tax_profile import get_tax_profile
from models.ais_tis_import import get_ais_tis_data
from engines.tax_engine import (
    calculate_and_save_tax,
    calculate_new_regime_tax,
    calculate_gross_total_income,
    project_next_year_income,
    get_recommended_itr_form,
)
from engines.advance_tax_engine import calculate_advance_tax
from config import get_assessment_year


def _format_indian_currency(value: float) -> str:
    """Format amount in Indian digit grouping: 2,56,642."""
    if value is None or value == 0:
        return "₹ 0.00"

    is_negative = value < 0
    value = abs(value)

    # Split into integer and decimal parts
    integer_part = int(value)
    decimal_part = value - integer_part

    # Format integer with Indian grouping
    s = str(integer_part)
    if len(s) <= 3:
        formatted_int = s
    else:
        # Last 3 digits, then groups of 2 from the right
        last_three = s[-3:]
        remaining = s[:-3]
        groups = []
        while len(remaining) > 2:
            groups.insert(0, remaining[-2:])
            remaining = remaining[:-2]
        if remaining:
            groups.insert(0, remaining)
        formatted_int = ",".join(groups) + "," + last_three

    # Add decimal part
    decimal_str = f"{decimal_part:.2f}"[1:]  # Get .xx part
    result = f"{formatted_int}{decimal_str}"

    if is_negative:
        result = "-" + result

    return f"₹ {result}"


class WaterfallRow(QWidget):
    """A visual waterfall row showing a label, proportional bar, and value."""

    def __init__(self, label: str, is_subtotal: bool = False, parent=None):
        super().__init__(parent)
        self.label_text = label
        self.is_subtotal = is_subtotal
        self.value = None  # None means not-yet-computed
        self._max_value = 1  # Will be set when rendering

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 6)
        layout.setSpacing(8)

        # Label
        self.label = QLabel(label)
        self.label.setMinimumWidth(180)
        if is_subtotal:
            font = QFont("Segoe UI", 10, QFont.Weight.DemiBold)
            self.label.setFont(font)
        else:
            font = QFont("Segoe UI", 10)
            self.label.setFont(font)
        layout.addWidget(self.label)

        # Bar container
        bar_container = QWidget()
        bar_layout = QHBoxLayout(bar_container)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        bar_layout.setSpacing(0)

        self.bar = QFrame()
        self.bar.setFixedHeight(20)
        self.bar.setMaximumWidth(200)
        self.bar.setStyleSheet(f"background-color: transparent; border-radius: 2px;")
        bar_layout.addWidget(self.bar)
        bar_layout.addStretch()

        layout.addWidget(bar_container, 1)

        # Value label
        self.value_label = QLabel("—")
        self.value_label.setMinimumWidth(100)
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        if is_subtotal:
            font = QFont("Segoe UI", 10, QFont.Weight.DemiBold)
            self.value_label.setFont(font)
        else:
            font = QFont("Segoe UI", 10)
            self.value_label.setFont(font)
        layout.addWidget(self.value_label)

    def set_value(self, value: float, max_value: float = None):
        """Set the value and update display.

        Args:
            value: The numeric value (None means not-yet-computed, 0 means zero)
            max_value: The max value for scaling the bar (optional)
        """
        self.value = value

        # Update value label
        if value is None:
            # Not yet computed
            self.value_label.setText("—")
            self.value_label.setStyleSheet(f"color: {Theme.TEXT_MUTED};")
            self.bar.setStyleSheet(f"background-color: transparent; border-radius: 2px;")
        elif value == 0:
            # Computed and zero
            self.value_label.setText(format_inr(0))
            self.value_label.setStyleSheet(f"color: {Theme.TEXT_MUTED};")
            self.bar.setStyleSheet(f"background-color: transparent; border-radius: 2px;")
        else:
            # Has a value
            self.value_label.setText(format_inr(value))

            # Color based on sign
            if value > 0:
                color = Theme.SUCCESS_TEXT
                bar_color = Theme.SUCCESS_LIGHT
            else:
                color = Theme.DANGER_TEXT
                bar_color = Theme.DANGER_LIGHT

            self.value_label.setStyleSheet(f"color: {color};")

            # Update bar width based on value
            if max_value and max_value > 0:
                ratio = min(1.0, abs(value) / max_value)
                bar_width = int(200 * ratio)
            else:
                bar_width = 50

            self.bar.setFixedWidth(bar_width)
            self.bar.setStyleSheet(f"background-color: {bar_color}; border-radius: 2px;")

        # Apply subtotal styling
        if self.is_subtotal:
            self.label.setProperty("textrole", "emphasis-md")
            # Add background tint for subtotals
            self.setStyleSheet(f"background-color: {Theme.SURFACE_ALT}; border-radius: 2px;")
            if hasattr(self, '_top_divider') and self._top_divider:
                self._top_divider.show()

    def add_top_divider(self):
        """Add a divider line above this row (for subtotals)."""
        # This is handled at the parent level, not here
        pass


class TaxScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.data_source = "ais"
        self._section_groups: list[QGroupBox] = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 14)
        layout.setSpacing(12)

        # Advance tax reminder banner
        self.advance_tax_banner = AdvanceTaxBanner(self)
        layout.addWidget(self.advance_tax_banner)

        # Header card
        self._header_card = header_card = QFrame()
        header_card.setObjectName("TaxHeaderCard")
        header_layout = QHBoxLayout(header_card)
        header_layout.setContentsMargins(16, 12, 16, 12)
        header_layout.setSpacing(12)

        head_left = QVBoxLayout()
        title = QLabel("Tax Planner")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setProperty("textrole", "title-lg")
        head_left.addWidget(title)

        self.person_label = QLabel("Select a person")
        self.person_label.setFont(QFont("Segoe UI", 12, QFont.Weight.DemiBold))
        self.person_label.setProperty("textrole", "emphasis-sm")
        head_left.addWidget(self.person_label)
        header_layout.addLayout(head_left)

        # Person selector (shown when multiple persons exist)
        self.person_combo = QComboBox()
        self.person_combo.setMinimumWidth(150)
        self.person_combo.setMinimumHeight(40)
        self.person_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.person_combo.setAccessibleName("Tax person selector")
        self.person_combo.setAccessibleDescription("Choose the person for tax planning.")
        self.person_combo.currentIndexChanged.connect(self._on_person_selected)
        header_layout.addWidget(self.person_combo)

        header_layout.addStretch()

        source_label = QLabel("Data Source")
        source_label.setProperty("textrole", "section-label")
        header_layout.addWidget(source_label)

        self.source_combo = QComboBox()
        self.source_combo.addItems(["AIS/TIS Data", "App Actual Data"])
        self.source_combo.setMinimumWidth(150)
        self.source_combo.setMinimumHeight(40)
        self.source_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
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

        # Context and results splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(8)

        # Left rail: forms
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        left_scroll.setObjectName("transparentBg")

        left_content = QWidget()
        left_content.setObjectName("transparentSurface")
        left_layout = QVBoxLayout(left_content)
        left_layout.setSpacing(14)
        left_layout.setContentsMargins(0, 0, 8, 0)

        left_layout.addWidget(self._build_basic_info_section())
        left_layout.addWidget(self._build_salary_section())
        left_layout.addWidget(self._build_capital_gains_section())
        left_layout.addWidget(self._build_business_section())
        left_layout.addWidget(self._build_other_sources_section())
        left_layout.addWidget(self._build_taxes_paid_section())
        left_layout.addStretch()

        left_scroll.setWidget(left_content)
        splitter.addWidget(left_scroll)

        # Right rail: context + results + projection
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.Shape.NoFrame)
        right_scroll.setObjectName("transparentBg")

        right_content = QWidget()
        right_content.setObjectName("transparentSurface")
        right_layout = QVBoxLayout(right_content)
        right_layout.setSpacing(12)
        right_layout.setContentsMargins(8, 0, 0, 0)

        right_layout.addWidget(self._build_waterfall_section())
        right_layout.addWidget(self._build_projection_section())
        right_layout.addStretch()

        right_scroll.setWidget(right_content)
        splitter.addWidget(right_scroll)

        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter, 1)
        self._connect_signals()
        self._update_context_panel()

    def _on_person_selected(self):
        """Handle person selection change from the person combo."""
        pid = self.person_combo.currentData()
        if pid is not None:
            session.set_person(pid)
            self.refresh()

    def _update_context_panel(self):
        """Update person label and populate person combo."""
        persons = get_all_persons()
        pid = session.selected_person_id

        # Update person label
        if pid:
            p = get_person(pid)
            if p:
                self.person_label.setText(f"Tax Estimator for {p.get('full_name', 'Unknown')}")
            else:
                self.person_label.setText("Select a person")
        else:
            self.person_label.setText("Select a person")

        # Populate person combo
        self.person_combo.blockSignals(True)
        self.person_combo.clear()

        # Always add "All Persons" option
        self.person_combo.addItem("All Persons", userData=None)

        # Add all persons
        for p in persons:
            self.person_combo.addItem(p["full_name"], userData=p["person_id"])

        # Select the current person if set
        if pid:
            for i in range(self.person_combo.count()):
                if self.person_combo.itemData(i) == pid:
                    self.person_combo.setCurrentIndex(i)
                    break
        else:
            self.person_combo.setCurrentIndex(0)

        self.person_combo.blockSignals(False)

        # If exactly 1 person exists and none is selected, auto-select
        if len(persons) == 1 and not pid:
            self.person_combo.setCurrentIndex(1)  # Index 1 is the only person
            session.set_person(persons[0]["person_id"])

        # Hide combo if only one person (show in label instead)
        self.person_combo.setVisible(len(persons) > 1)

    # ── Section builders ──────────────────────────────────────────────────────

    def _section_group(self, title: str, collapsible: bool = True) -> QWidget:
        if collapsible:
            section = CollapsibleSection(title, expanded=False)
            self._section_groups.append(section)
            return section
        else:
            # Non-collapsible sections remain as QGroupBox for backward compatibility
            group = QGroupBox(title)
            group.setCheckable(False)
            group.setStyleSheet(
                Theme.group_box_style() +
                "\nQLabel { border: none; background: transparent; }\n"
            )
            self._section_groups.append(group)
            return group

    def _build_basic_info_section(self) -> QGroupBox:
        group = self._section_group("Basic Information", collapsible=False)
        layout = QFormLayout(group); layout.setSpacing(12)
        self.pan_label       = QLabel("—"); layout.addRow("PAN:", self.pan_label)
        self.taxpayer_label  = QLabel("—"); layout.addRow("Name of Taxpayer:", self.taxpayer_label)
        self.ay_label        = QLabel("—")
        self.ay_label.setProperty("textrole", "emphasis-sm")
        self.ay_label.setProperty("color", "primary")
        layout.addRow("Assessment Year:", self.ay_label)
        self.category_label  = QLabel("Individual"); layout.addRow("Taxpayer Category:", self.category_label)
        self.age_label       = QLabel("Below 60 years"); layout.addRow("Your Age:", self.age_label)
        return group

    def _build_salary_section(self) -> QWidget:
        group = self._section_group("Salary & Pension Income")
        if isinstance(group, CollapsibleSection):
            layout = QFormLayout()
            group.content_layout().insertLayout(0, layout)
        else:
            layout = QFormLayout(group)
        layout.setSpacing(12)
        self.gross_salary    = self._spin(); layout.addRow("Gross Salary:", self._wrap_left_align(self.gross_salary))
        self.exemption_10    = self._spin(); layout.addRow("Exemption claimed u/s 10:", self._wrap_left_align(self.exemption_10))
        self.deduction_16ii  = self._spin(); layout.addRow("Deduction u/s 16(ii) (Entertainment):", self._wrap_left_align(self.deduction_16ii))
        self.deduction_16iii = self._spin(); layout.addRow("Deduction u/s 16(iii) (Professional Tax):", self._wrap_left_align(self.deduction_16iii))
        self.pension_income  = self._spin(); layout.addRow("Pension Income:", self._wrap_left_align(self.pension_income))
        return group

    def _build_capital_gains_section(self) -> QWidget:
        group = self._section_group("Capital Gains Income")
        if isinstance(group, CollapsibleSection):
            layout = QFormLayout()
            group.content_layout().insertLayout(0, layout)
        else:
            layout = QFormLayout(group)
        layout.setSpacing(12)
        self.stcg_normal = self._spin(); layout.addRow("Short Term Capital Gains (Normal rates):", self._wrap_left_align(self.stcg_normal))
        self.stcg_111a   = self._spin(); layout.addRow("STCG u/s 111A (@ 15%):", self._wrap_left_align(self.stcg_111a))
        self.ltcg_20     = self._spin(); layout.addRow("Long Term Capital Gains (@ 20%):", self._wrap_left_align(self.ltcg_20))
        self.ltcg_112a   = self._spin(); layout.addRow("LTCG u/s 112A (@ 12.5%):", self._wrap_left_align(self.ltcg_112a))
        return group

    def _build_business_section(self) -> QWidget:
        group = self._section_group("Business / Professional Income")
        if isinstance(group, CollapsibleSection):
            layout = QFormLayout()
            group.content_layout().insertLayout(0, layout)
        else:
            layout = QFormLayout(group)
        layout.setSpacing(12)
        self.presumptive_income      = self._spin(); layout.addRow("Presumptive Income u/s 44ADA:", self._wrap_left_align(self.presumptive_income))
        self.manufacturing_income    = self._spin(); layout.addRow("Manufacturing Business Income:", self._wrap_left_align(self.manufacturing_income))
        self.other_business_income   = self._spin(); layout.addRow("Other Business/Profession Income:", self._wrap_left_align(self.other_business_income))
        return group

    def _build_other_sources_section(self) -> QWidget:
        group = self._section_group("Other Income Sources")
        if isinstance(group, CollapsibleSection):
            layout = QFormLayout()
            group.content_layout().insertLayout(0, layout)
        else:
            layout = QFormLayout(group)
        layout.setSpacing(12)
        self.savings_interest_input  = self._spin(readonly=True)
        layout.addRow("Interest from Savings Bank Account:", self._wrap_left_align(self.savings_interest_input))
        self.fd_interest_input       = self._spin(readonly=True)
        layout.addRow("Interest from Deposit (Bank/Post Office):", self._wrap_left_align(self.fd_interest_input))
        self.other_interest          = self._spin(); layout.addRow("Other Interest Income:", self._wrap_left_align(self.other_interest))
        self.dividend_income         = self._spin(); layout.addRow("Dividend Income (Normal rates):", self._wrap_left_align(self.dividend_income))
        self.rental_income           = self._spin(); layout.addRow("Rental Income:", self._wrap_left_align(self.rental_income))
        self.lottery_winnings        = self._spin(); layout.addRow("Winnings from Lotteries/Races:", self._wrap_left_align(self.lottery_winnings))
        self.online_game_winnings    = self._spin(); layout.addRow("Winnings from Online Games u/s 115BBJ:", self._wrap_left_align(self.online_game_winnings))
        self.other_income_input      = self._spin(); layout.addRow("Any Other Income:", self._wrap_left_align(self.other_income_input))
        self.gross_income_label = QLabel("₹ 0.00")
        self.gross_income_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self.gross_income_label.setProperty("textrole", "emphasis-lg")
        self.gross_income_label.setProperty("color", "primary")
        layout.addRow("Gross Total Income:", self.gross_income_label)
        return group

    def _build_taxes_paid_section(self) -> QWidget:
        group = self._section_group("Taxes Already Paid")
        if isinstance(group, CollapsibleSection):
            layout = QFormLayout()
            group.content_layout().insertLayout(0, layout)
        else:
            layout = QFormLayout(group)
        layout.setSpacing(12)
        note = QLabel("Used to work out what you still owe, or your refund, below.")
        note.setWordWrap(True)
        note.setProperty("textrole", "muted-sm")
        layout.addRow("", note)
        self.tds_salary          = self._spin(); layout.addRow("TDS on Salary:", self._wrap_left_align(self.tds_salary))
        self.tds_other           = self._spin(); layout.addRow("TDS on Other Income:", self._wrap_left_align(self.tds_other))
        self.tcs_collected       = self._spin(); layout.addRow("TCS Collected:", self._wrap_left_align(self.tcs_collected))
        self.advance_tax         = self._spin(); layout.addRow("Advance Tax Paid:", self._wrap_left_align(self.advance_tax))
        self.self_assessment_tax = self._spin(); layout.addRow("Self-Assessment Tax Paid:", self._wrap_left_align(self.self_assessment_tax))
        return group

    def _build_waterfall_section(self) -> QGroupBox:
        """Build the auditable tax calculation waterfall."""
        group = self._section_group("Tax Calculation Waterfall", collapsible=False)
        layout = QVBoxLayout(group)
        layout.setSpacing(6)

        # Title
        title = QLabel("New Regime Tax Breakdown")
        title.setProperty("textrole", "emphasis-md")
        layout.addWidget(title)

        # Waterfall rows container
        waterfall_container = QWidget()
        waterfall_layout = QVBoxLayout(waterfall_container)
        waterfall_layout.setContentsMargins(0, 0, 0, 0)
        waterfall_layout.setSpacing(2)

        # Gross income (subtotal)
        self.waterfall_gross = WaterfallRow("Gross Income", is_subtotal=True)
        waterfall_layout.addWidget(self.waterfall_gross)

        # Standard deduction
        self.waterfall_std_ded = WaterfallRow("Less: Standard Deduction")
        waterfall_layout.addWidget(self.waterfall_std_ded)

        # Divider for taxable income
        divider1 = QFrame()
        divider1.setFrameShape(QFrame.Shape.HLine)
        divider1.setStyleSheet(f"color: {Theme.DIVIDER};")
        divider1.setFixedHeight(1)
        waterfall_layout.addWidget(divider1)

        # Taxable income (subtotal)
        self.waterfall_taxable = WaterfallRow("Taxable Income", is_subtotal=True)
        waterfall_layout.addWidget(self.waterfall_taxable)

        # Slab tax
        self.waterfall_slab_tax = WaterfallRow("Slab Tax")
        waterfall_layout.addWidget(self.waterfall_slab_tax)

        # Special rate tax (if applicable)
        self.waterfall_special_tax = WaterfallRow("Special Rate Tax (s.111A/112A)")
        self.waterfall_special_label = "Special Rate Tax (s.111A/112A)"
        waterfall_layout.addWidget(self.waterfall_special_tax)

        # Total tax before rebate
        self.waterfall_base_tax = WaterfallRow("Total Tax")
        waterfall_layout.addWidget(self.waterfall_base_tax)

        # 87A Rebate
        self.waterfall_rebate = WaterfallRow("Less: Rebate u/s 87A")
        waterfall_layout.addWidget(self.waterfall_rebate)

        # Marginal relief (if applicable)
        self.waterfall_marginal = WaterfallRow("Marginal Relief")
        self.waterfall_marginal_label = "Marginal Relief"
        waterfall_layout.addWidget(self.waterfall_marginal)

        # Tax after rebate
        self.waterfall_after_rebate = WaterfallRow("Tax After Rebate")
        waterfall_layout.addWidget(self.waterfall_after_rebate)

        # Surcharge
        self.waterfall_surcharge = WaterfallRow("Plus: Surcharge")
        waterfall_layout.addWidget(self.waterfall_surcharge)

        # Cess
        self.waterfall_cess = WaterfallRow("Plus: Cess (4%)")
        waterfall_layout.addWidget(self.waterfall_cess)

        # Divider for total liability
        divider2 = QFrame()
        divider2.setFrameShape(QFrame.Shape.HLine)
        divider2.setStyleSheet(f"color: {Theme.DIVIDER};")
        divider2.setFixedHeight(1)
        waterfall_layout.addWidget(divider2)

        # Total tax liability (subtotal)
        self.waterfall_total = WaterfallRow("Total Tax Liability", is_subtotal=True)
        waterfall_layout.addWidget(self.waterfall_total)

        # Taxes paid
        self.waterfall_taxes_paid = WaterfallRow("Less: Taxes Paid")
        waterfall_layout.addWidget(self.waterfall_taxes_paid)

        # Divider for net payable
        divider3 = QFrame()
        divider3.setFrameShape(QFrame.Shape.HLine)
        divider3.setStyleSheet(f"color: {Theme.DIVIDER};")
        divider3.setFixedHeight(1)
        waterfall_layout.addWidget(divider3)

        # Net payable/refund (subtotal)
        self.waterfall_net = WaterfallRow("Net Payable / Refund", is_subtotal=True)
        waterfall_layout.addWidget(self.waterfall_net)

        layout.addWidget(waterfall_container)

        # ITR recommendation
        itr_frame = QFrame()
        itr_layout = QVBoxLayout(itr_frame); itr_layout.setSpacing(4); itr_layout.setContentsMargins(0, 8, 0, 0)
        itr_label = QLabel("ITR Form Recommendation")
        itr_label.setProperty("textrole", "section-label")
        itr_layout.addWidget(itr_label)
        self.waterfall_itr = QLabel("—")
        self.waterfall_itr.setProperty("textrole", "emphasis-md")
        itr_layout.addWidget(self.waterfall_itr)
        layout.addWidget(itr_frame)

        return group

    def _build_projection_section(self) -> QWidget:
        group = self._section_group("Next Year Projection")
        if isinstance(group, CollapsibleSection):
            layout = QVBoxLayout()
            group.content_layout().insertLayout(0, layout)
        else:
            layout = QVBoxLayout(group)
        layout.setSpacing(10)

        self.proj_subtitle = QLabel("Select a person to project next year")
        self.proj_subtitle.setWordWrap(True)
        self.proj_subtitle.setProperty("textrole", "muted-sm")
        layout.addWidget(self.proj_subtitle)

        form = QFormLayout(); form.setSpacing(6)
        self.proj_expected = self._result_lbl()
        self.proj_fd       = self._result_lbl()
        self.proj_savings  = self._result_lbl()
        self.proj_gross    = self._result_lbl(bold=True)
        self.proj_taxable  = self._result_lbl()
        self.proj_tax      = self._result_lbl()
        form.addRow("Expected Income:", self.proj_expected)
        form.addRow("FD Interest (real):", self.proj_fd)
        form.addRow("Savings Interest (est.):", self.proj_savings)
        form.addRow("Projected Gross Income:", self.proj_gross)
        form.addRow("Projected Taxable Income:", self.proj_taxable)
        form.addRow("Projected Tax (New Regime):", self.proj_tax)
        layout.addLayout(form)

        # Slab position
        self._proj_slab_card = QFrame()
        self._proj_slab_card.setObjectName("ProjSlabCard")
        slab_l = QVBoxLayout(self._proj_slab_card); slab_l.setSpacing(4)
        self.proj_slab_label = QLabel("—")
        self.proj_slab_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self.proj_slab_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.proj_slab_label.setWordWrap(True)
        self.proj_slab_label.setProperty("textrole", "metric")
        slab_l.addWidget(self.proj_slab_label)
        self.proj_slab_sub = QLabel("")
        self.proj_slab_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.proj_slab_sub.setWordWrap(True)
        self.proj_slab_sub.setProperty("textrole", "muted-sm")
        slab_l.addWidget(self.proj_slab_sub)
        layout.addWidget(self._proj_slab_card)

        note = QLabel(
            "FD interest is real (from deposits running into next year). "
            "Salary and savings interest are projected — treat the total as an estimate."
        )
        note.setWordWrap(True)
        note.setProperty("textrole", "muted-sm")
        layout.addWidget(note)
        return group

    def _update_projection(self):
        pid = session.selected_person_id
        fy  = session.selected_fy
        if not pid or not fy:
            self.proj_subtitle.setText("Select a person to project next year")
            for l in (self.proj_expected, self.proj_fd, self.proj_savings,
                      self.proj_gross, self.proj_taxable, self.proj_tax):
                l.setText("—")
            self.proj_slab_label.setText("—")
            self.proj_slab_label.setProperty("textrole", "metric")
            self.proj_slab_sub.setText("")
            return

        proj = project_next_year_income(pid, fy)
        src = ("from your income expectations" if proj["income_source"] == "expectations"
               else "assuming salary unchanged from this year")
        self.proj_subtitle.setText(
            f"FY {proj['next_fy']}  ·  AY {proj['assessment_year']} — expected income {src}")
        self.proj_expected.setText(_format_indian_currency(proj['expected_income']))
        self.proj_fd.setText(_format_indian_currency(proj['fd_interest']))
        self.proj_savings.setText(_format_indian_currency(proj['savings_interest']))
        self.proj_gross.setText(_format_indian_currency(proj['gross_total_income']))
        self.proj_taxable.setText(_format_indian_currency(proj['taxable_income']))
        self.proj_tax.setText(_format_indian_currency(proj['projected_tax']))

        slab = proj["slab"]
        rate = slab["current_rate"]
        if slab["is_top_slab"]:
            self.proj_slab_label.setText(f"Top slab — {rate}% marginal rate")
            self.proj_slab_label.setProperty("textrole", "metric")
            self.proj_slab_label.setProperty("color", "danger")
            self.proj_slab_sub.setText("Projected income is in the highest New Regime bracket.")
        else:
            to_next = slab["amount_to_next_slab"] or 0
            next_rate = slab["next_rate"]
            self.proj_slab_label.setText(f"{rate}% slab  ·  {_format_indian_currency(to_next)} to the {next_rate}% slab")
            # Less headroom before the next bracket → warmer colour.
            if to_next <= 50000:
                color_role = "danger"
            elif to_next <= 150000:
                color_role = "warning"
            else:
                color_role = "success"
            self.proj_slab_label.setProperty("textrole", "metric")
            self.proj_slab_label.setProperty("color", color_role)
            ceiling = slab["slab_ceiling"] or 0
            self.proj_slab_sub.setText(
                f"Cross {_format_indian_currency(ceiling)} taxable income and your marginal rate rises to {next_rate}%.")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _spin(self, readonly=False) -> QDoubleSpinBox:
        s = QDoubleSpinBox()
        s.setRange(-0.01, 99_999_999.99)
        s.setDecimals(2); s.setGroupSeparatorShown(True); s.setPrefix("₹ ")
        s.setSpecialValueText("₹ — (not entered)")
        s.setValue(-0.01)  # Default to "not entered" state
        s.setMaximumWidth(Theme.INPUT_CURRENCY_MAX_WIDTH)
        if readonly:
            s.setReadOnly(True)
            s.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        return s

    def _wrap_left_align(self, widget) -> QWidget:
        """Wrap a widget in a left-aligned layout container."""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(widget)
        layout.addStretch()
        return container

    def _result_lbl(self, bold=False) -> QLabel:
        l = QLabel("—")
        if bold:
            l.setProperty("textrole", "emphasis-lg")
        else:
            l.setProperty("textrole", "body-md")
        return l

    def _connect_signals(self):
        for spin in [self.gross_salary, self.exemption_10, self.deduction_16ii, self.deduction_16iii,
                     self.pension_income, self.stcg_normal, self.stcg_111a, self.ltcg_20, self.ltcg_112a,
                     self.presumptive_income, self.manufacturing_income, self.other_business_income,
                     self.savings_interest_input, self.fd_interest_input, self.other_interest,
                     self.dividend_income, self.rental_income, self.lottery_winnings,
                     self.online_game_winnings, self.other_income_input]:
            spin.valueChanged.connect(self._update_gross)

    def _on_source_changed(self):
        self.data_source = "ais" if self.source_combo.currentIndex() == 0 else "app"
        self._update_context_panel()
        self.refresh()

    def _update_gross(self):
        """Display gross income calculated by the same function the engine uses."""
        salary = max(0, max(0, self.gross_salary.value()) - max(0, self.exemption_10.value()) -
                     max(0, self.deduction_16ii.value()) - max(0, self.deduction_16iii.value()))

        # Use the same function as the engine to ensure displayed gross matches calculated gross
        gross, _ = calculate_gross_total_income(
            salary_income=salary,
            pension_income=max(0, self.pension_income.value()),
            business_income=max(0, self.manufacturing_income.value()) + max(0, self.other_business_income.value()) +
                           max(0, self.presumptive_income.value()),
            house_property_income=0,
            capital_gains_normal=max(0, self.stcg_normal.value()),
            capital_gains_stcg_111a=max(0, self.stcg_111a.value()),
            capital_gains_ltcg_112=max(0, self.ltcg_20.value()),
            capital_gains_ltcg_112a=max(0, self.ltcg_112a.value()),
            interest_income=max(0, self.savings_interest_input.value()) + max(0, self.fd_interest_input.value()) + max(0, self.other_interest.value()),
            dividend_income=max(0, self.dividend_income.value()),
            other_income=(max(0, self.rental_income.value()) + max(0, self.lottery_winnings.value()) +
                         max(0, self.online_game_winnings.value()) + max(0, self.other_income_input.value())),
        )
        self.gross_income_label.setText(_format_indian_currency(gross))

        # Expand section if it has a value
        # Find the "Other Income Sources" group and expand it
        for group in self._section_groups:
            title = group.title() if hasattr(group, 'title') else (
                group.title_text if isinstance(group, CollapsibleSection) else ""
            )
            if "Other Income Sources" in title:
                if isinstance(group, CollapsibleSection):
                    group.set_expanded(gross > 0)
                else:
                    group.setChecked(gross > 0)

    def refresh(self):
        pid = session.selected_person_id
        fy  = session.selected_fy
        self._update_context_panel()
        self._update_projection()
        if not pid:
            self.person_label.setText("Select a person")
            self.person_label.setProperty("textrole", "emphasis-sm")
            self._clear_inputs()
            self.advance_tax_banner.clear()
            return
        person = get_person(pid)
        if person:
            ay = get_assessment_year(fy)
            self.person_label.setText(f"Tax Estimator for {person['full_name']}  ·  FY {fy}")
            self.person_label.setProperty("textrole", "emphasis-sm")
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
            self.tds_salary.setValue(profile.get("tds_deducted", 0))
            self.tcs_collected.setValue(profile.get("tcs_collected", 0))
            self.advance_tax.setValue(profile.get("advance_tax_paid", 0))
            self.self_assessment_tax.setValue(profile.get("self_assessment_tax", 0))

            # Recompute fresh from the stored income figures
            gross_total_income = profile.get("gross_total_income", 0)
            salary_income = profile.get("salary_income", 0)
            new = calculate_new_regime_tax(gross_total_income, salary_income=salary_income, financial_year=fy)
            taxes_paid = (
                profile.get("tds_deducted", 0) + profile.get("tcs_collected", 0)
                + profile.get("advance_tax_paid", 0) + profile.get("self_assessment_tax", 0)
            )
            self._display_waterfall(new, gross_total_income, salary_income, taxes_paid, pid, fy)

    def _clear_income_fields(self):
        for s in [self.gross_salary, self.exemption_10, self.deduction_16ii, self.deduction_16iii,
                  self.pension_income, self.stcg_normal, self.stcg_111a, self.ltcg_20, self.ltcg_112a,
                  self.presumptive_income, self.manufacturing_income, self.other_business_income,
                  self.other_interest, self.dividend_income, self.rental_income, self.lottery_winnings,
                  self.online_game_winnings, self.other_income_input]:
            s.setValue(0)

    def _clear_inputs(self):
        self._clear_income_fields()
        for s in [self.fd_interest_input, self.savings_interest_input,
                  self.tds_salary, self.tds_other, self.tcs_collected, self.advance_tax, self.self_assessment_tax]:
            s.setValue(0)
        for row in [self.waterfall_gross, self.waterfall_std_ded, self.waterfall_taxable,
                    self.waterfall_slab_tax, self.waterfall_special_tax, self.waterfall_base_tax,
                    self.waterfall_rebate, self.waterfall_marginal, self.waterfall_after_rebate,
                    self.waterfall_surcharge, self.waterfall_cess, self.waterfall_total,
                    self.waterfall_taxes_paid, self.waterfall_net]:
            row.set_value(None)
        self.waterfall_itr.setText("—")

    def _on_calculate(self):
        pid = session.selected_person_id
        if not pid:
            show_danger("Please select a person from the top bar.")
            return

        # Salary section: gross minus exemptions and deductions
        salary = max(0, max(0, self.gross_salary.value()) - max(0, self.exemption_10.value()) -
                     max(0, self.deduction_16ii.value()) - max(0, self.deduction_16iii.value()))

        # Capital gains: separate by special rate
        capital_gains_normal = max(0, self.stcg_normal.value())
        capital_gains_stcg_111a = max(0, self.stcg_111a.value())
        capital_gains_ltcg_112 = max(0, self.ltcg_20.value())
        capital_gains_ltcg_112a = max(0, self.ltcg_112a.value())

        # Business / Profession: presume + regular
        business_income = max(0, self.manufacturing_income.value()) + max(0, self.other_business_income.value())
        presumptive_income = max(0, self.presumptive_income.value())

        # Other income: interest, dividend, rental, lottery, games, misc
        other_income = (max(0, self.other_interest.value()) + max(0, self.dividend_income.value()) +
                        max(0, self.rental_income.value()) + max(0, self.lottery_winnings.value()) +
                        max(0, self.online_game_winnings.value()) + max(0, self.other_income_input.value()))

        result = calculate_and_save_tax(
            person_id=pid, financial_year=session.selected_fy,
            salary_income=salary,
            pension_income=max(0, self.pension_income.value()),
            business_income=business_income,
            presumptive_income=presumptive_income,
            house_property_income=0,
            capital_gains_normal=capital_gains_normal,
            capital_gains_stcg_111a=capital_gains_stcg_111a,
            capital_gains_ltcg_112=capital_gains_ltcg_112,
            capital_gains_ltcg_112a=capital_gains_ltcg_112a,
            fd_interest=max(0, self.fd_interest_input.value()),
            savings_interest=max(0, self.savings_interest_input.value()),
            other_interest=max(0, self.other_interest.value()),
            dividend_income=max(0, self.dividend_income.value()),
            other_income=other_income,
            tds_deducted=max(0, self.tds_salary.value()) + max(0, self.tds_other.value()),
            tcs_collected=max(0, self.tcs_collected.value()),
            advance_tax_paid=max(0, self.advance_tax.value()),
            self_assessment_tax=max(0, self.self_assessment_tax.value()),
        )
        self._display_waterfall(result["new_regime"], result["gross_total_income"],
                               salary, result["taxes_paid"], pid, session.selected_fy)
        if self.parent_window:
            self.parent_window.refresh_overview()
        show_success(f"Tax calculated for FY {session.selected_fy}")

    def _display_waterfall(self, new: dict, gross_total_income: float, salary_income: float,
                          taxes_paid: float, pid: int, fy: str):
        """Populate waterfall widgets from the New Regime calculation dict."""
        # Collect all values for max calculation
        values = [
            abs(gross_total_income),
            abs(new.get("standard_deduction", 0)),
            abs(new['taxable_income']),
            abs(new['slab_tax']),
            abs(new.get('special_rate_tax', 0)),
            abs(new.get('rebate_87a', 0)),
            abs(new.get('surcharge', 0)),
            abs(new.get('cess', 0)),
            abs(new['total_tax']),
            abs(taxes_paid),
        ]
        max_value = max(values) if values else 1
        if max_value == 0:
            max_value = 1

        # Display waterfall with visual bars
        self.waterfall_gross.set_value(gross_total_income, max_value)
        self.waterfall_std_ded.set_value(-new.get("standard_deduction", 0), max_value)
        self.waterfall_taxable.set_value(new['taxable_income'], max_value)
        self.waterfall_slab_tax.set_value(new['slab_tax'], max_value)

        # Show special rate tax only if present
        if new.get('special_rate_income', 0) > 0:
            self.waterfall_special_tax.set_value(new['special_rate_tax'], max_value)
            self.waterfall_special_tax.show()
        else:
            self.waterfall_special_tax.hide()

        self.waterfall_base_tax.set_value(new['slab_tax'] + new.get('special_rate_tax', 0), max_value)
        self.waterfall_rebate.set_value(-new.get('rebate_87a', 0), max_value)

        # Marginal relief is computed within the engine but not returned separately.
        # We can infer it, but for now just hide it if zero
        self.waterfall_marginal.hide()

        self.waterfall_after_rebate.set_value(
            new['slab_tax'] + new.get('special_rate_tax', 0) - new.get('rebate_87a', 0), max_value)
        self.waterfall_surcharge.set_value(new.get('surcharge', 0), max_value)
        self.waterfall_cess.set_value(new.get('cess', 0), max_value)
        self.waterfall_total.set_value(new['total_tax'], max_value)
        self.waterfall_taxes_paid.set_value(-taxes_paid, max_value)

        net_new = new["total_tax"] - taxes_paid
        self.waterfall_net.set_value(net_new, max_value)

        # Get ITR recommendation
        itr_form, itr_reason = get_recommended_itr_form(
            salary_income=salary_income,
            business_income=self.manufacturing_income.value() + self.other_business_income.value(),
            presumptive_income=self.presumptive_income.value(),
            interest_income=self.savings_interest_input.value() + self.fd_interest_input.value() + self.other_interest.value(),
            dividend_income=self.dividend_income.value(),
            other_income=self.rental_income.value() + self.lottery_winnings.value() +
                        self.online_game_winnings.value() + self.other_income_input.value(),
        )
        self.waterfall_itr.setText(f"{itr_form} — {itr_reason}")

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

        # Use the new regime's tax
        tax_new = profile.get("total_tax_new", 0)

        gross_income = profile.get("gross_total_income", 0)
        tds = profile.get("tds_deducted", 0)
        advance_paid = profile.get("advance_tax_paid", 0)

        result = calculate_advance_tax(
            financial_year=fy,
            gross_income=gross_income,
            annual_tax=tax_new,
            tds_deducted=tds,
            advance_tax_paid=advance_paid,
        )

        self.advance_tax_banner.update_reminder(result)
