# Family FD planner

Open **FD Planner** in the main sidebar. The button on **Fixed Deposits** opens the same full page. Restart an already-running app after updating the Python files. The original comparison, coverage and other-options components remain for compatibility. The superseded optimized dialog, manual-rate workflow and first optimizer have been removed.

## Simple page

The main inputs are **Keep available** (initially 15% of known eligible cash) and **Plan up to** (1, 2, 3 or 5 years). Select **Refresh my bank rates**, then **Build my plan**.

The default plan pools family cash, uses general-customer rates, limits household exposure to one bank to 20%, applies annual interest/income limits, and keeps each newly funded FD bucket within the modeled insurance limit. **Plan settings** contains these optional controls and stays collapsed initially. None of these limits is silently relaxed to produce a result.

The **Money flow** tree shows family funds → people → bank accounts → FD tenures and ready cash. Click a person to expand their accounts. Additional bank accounts are grouped until clicked. Moving dots show the planned flow; animation can be paused. Pan, zoom and reset controls are provided. Amounts and detail tables respect privacy mode.

- **My bank rates** shows each selected bank, exact savings bands and general retail FD slabs, effective dates, the actual check timestamp, and official source links.
- **Upcoming money** shows dated FD maturities and expected salary receipts separately from cash available today.
- **Plan details** gives principal, holder, bank, tenure, coupon, maturity and projected interest. Expand **Why these allocations** for financial-year estimates and assumptions.
- **Transfers** shows net account-to-account movements needed to fund the same allocation.

The page remains interactive during background rate refreshes and calculations. Changing a planning input invalidates the old result. Closing the app during an active planner task is guarded until the task finishes.

## Source data

The default source is `data/data/Data 26-27.xlsx`, read without modifying or exporting it. **Choose workbook** selects another file with the same layout. The source name is visible at the top of the page.

`engines/family_workbook.py` reads the Bank sheet's account summary and explicitly dated FD blocks, plus the Salary sheet's dated expected/actual income. Existing app people, complete active FD records and unmatched income expectations supplement the workbook. App salary expectations do not duplicate a month already provided by the workbook; matched expectations and bank-interest forecasts already modeled elsewhere are excluded. Workbook savings values take priority; an absent balance is filled from a uniquely matching app account if possible. Missing balances remain unknown and are excluded from spendable cash. They are never presented as confirmed zero balances.

FD aggregate balances do not become invented contracts or maturity dates. Incomplete FD terms are flagged, conservatively retained in exposure, and excluded from new insured FD funding in that holder/bank bucket. Income/TDS estimates remain provisional when existing interest or future income is incomplete. Joint capacities require review and are excluded from automated funding.

Family cash can move between eligible accounts belonging to different people. The resulting holder is a **conditional tax attribution scenario**: an internal transfer does not establish beneficial ownership or remove spouse/minor clubbing or HUF rules. Future salary and maturity receipts are not invested before they arrive. The planner executes no transfers or FD bookings.

The family planner uses general rates for everyone; it does not apply a senior-citizen premium.

## Official bank publications

`engines/official_bank_rates.py` fetches public bank-hosted HTTPS documents only. No family balances, names, account numbers or workbook contents are sent. TLS uses Windows system trust when available; certificate verification is never disabled.

The source registry covers the eleven legal banks present in the workbook. Jana, Ujjivan, HDFC, SBI and IDFC FIRST have semantic HTML adapters. Unity's current combined interest-rate disclosure is located from its official page and its retail PDF section is parsed separately from bulk and senior tables.

On the 26 October 2026 check, usable publications were obtained for these six banks. Equitas, AU and Bank of India blocked or failed automated requests; YES Bank and RNSB did not expose a usable verified table through their current adapters. These failures are shown explicitly. Search snippets, comparison sites and older PDFs are not substituted as current confirmed rates.

Unity's published savings bands are displayed, but the progressive-versus-whole-balance calculation basis could not be established from that disclosure. Its savings return is therefore excluded from optimization until confirmed. Ambiguous Unity FD tenure entries are also excluded with a visible explanation. The parser uses the retail effective date even when a bulk section has a newer date.

The local cache is `data/family_bank_rates.json`. Entries retain official URLs, download time, effective dates and source hashes. Rates expire after 24 hours. A failed refresh replaces that bank's confirmation with an error rather than silently retaining the previous rate as current. A fresh download date and an effective date are different: an older effective date can still be the current official publication.

Only the general, callable retail column is used. Bulk, FD Plus/non-callable, recurring-deposit, senior and annualized-yield columns are not mixed with retail FD coupons. Minimum tickets and explicit published day counts are respected. Calendar months are converted using the booking date. Final bank booking terms and rounding still need checking before placing a deposit.

## Optimization

`engines/family_fd_engine.py` solves a mixed-integer linear model with SciPy/HiGHS. Integer variables choose principal in ₹1,000 steps for every usable rate/account/tenure candidate. The full model enumerates each allowed day up to the chosen horizon, with a 60,000-candidate guard.

FD principal, destination cash and progressive savings interest are optimized together. The objective is projected contractual FD interest plus static-balance savings interest, less incremental ordinary income tax over the common planning period. Savings rates are assumed constant; this is a scenario, not a rate forecast. Early FD maturities earn no invented renewal return. Future receipts are shown but do not fund today's plan.

Constraints include:

- Cash conservation across the pool, or separate owner budgets when family transfers are disabled.
- The requested liquid reserve, rate-card ticket limits and general-customer eligibility.
- Maximum household exposure to each legal bank, including recorded existing FDs, new maturity values and projected retained savings. If locked existing FDs already exceed the cap, no additional money is allocated there and the pre-existing breach is explicitly reported; contracts are not broken automatically.
- Conditional insurance checks for newly funded FD buckets, including retained savings and existing deposits within the same holder/bank bucket. Existing uninsured money elsewhere is not described as protected.
- Annual bank FD interest headroom after known existing FD interest, using ₹50,000 for these non-senior holders.
- Financial-year taxable-income caps of ₹12 lakh for modeled resident individuals and ₹4 lakh for HUF when tax limits are enabled. HUF has no individual rebate.
- Piecewise ordinary new-regime tax, including the individual rebate, marginal relief, slabs and cess when calculating incremental tax. The supported income range is ₹0–₹50 lakh; special-rate income, deductions and ownership adjustments require review.

Calendar coupon compounding and simple broken periods produce financial-year accrual coefficients that reconcile to the modeled maturity. Bank-specific rounding and payout products can differ.

Large models first obtain an audited feasible plan using slab endpoints, common calendar tenures and financial-year boundaries. The complete daily-tenure model is then searched within the remaining solver budget. The better feasible result is retained. The page reports **Best found plan** and a bound-based search gap if the time limit prevents proof of optimality. A frontier-only result is never labelled a proven optimum. Every published result is checked for integer feasibility, constraints, cash conservation and transfer funding.

The solver's time budget applies to its search phases; parsing, interest-curve construction and result auditing add processing time. Optimality is relative to the supplied data, modeled products, horizon and allocation step. Missing rates or income prevent a claim of a universally best realized return.

## Interest limits and declarations

₹50,000 is a withholding threshold, not a tax-free interest allowance. ₹12 lakh is a conditional individual new-regime rebate threshold, not an FD principal limit. HUF uses a separate tax calculation without that rebate. Future years currently assume the same ordinary-income rules continue.

For tax year 2026–27, **Form 121** replaces Forms 15G/15H. For a person below 60, nil estimated tax alone does not satisfy all declaration conditions: aggregate relevant declaration income also has to meet the applicable basic-exemption condition. The family page does not certify declaration eligibility or file a declaration.

Official references:

- [Income Tax Department: Form 121 guidance](https://www.incometaxindia.gov.in/documents/d/guest/fn-121)
- [Income Tax Department: tax rates and computation](https://www.incometaxindia.gov.in/w/tax-rates-and-computation)
- [DICGC FAQs](https://www.dicgc.org.in/FAQs)

The legacy comparison and other-options tabs remain informational. Their comparison snapshots are not promoted to official inputs for this family optimizer. No investment is purchased by the app.

## Validation

Install `requirements.txt`, then launch `python main.py` normally. Added runtime dependencies include SciPy, Beautiful Soup and truststore.

```powershell
.venv/Scripts/python.exe -m pytest tests/test_family_workbook.py tests/test_family_fd_engine.py tests/test_official_bank_rates.py tests/test_family_planner_screen.py -q
```

The new tests cover workbook immutability, missing versus zero balances, incomplete FD terms, pooled and individual budgets, reserves, exhaustive small-case optima, savings competing with FDs, insurance including retained cash, HUF tax, solver-timeout fallback, official source parsing, stale rates, full-page navigation, interactive tree branches, background callbacks and privacy. Tests use temporary databases and synthetic fixtures. A separate local check reconciled the actual workbook plan and verified that the workbook's hash did not change.
