# Personal Financial Manager — Audit & Rebuild Plan

**Audit date:** 3 September 2026
**Audited against:** the owner's real data in `data/PersonalData/Pranav/`
(`26AS.pdf`, `AIS.pdf`, `TIS.pdf`, `Data 26-27.xlsx`, and four bank statements:
Equitas, IDFC, Jana, Ujjivan).
**Current FY:** 2026-27 (AY 2027-28). The tax documents on hand are FY 2025-26 (AY 2026-27).

> **How to use this document.**
> It is written to be executed by an AI coding agent.
> Sections 1-3 are context you must read before changing code.
> Section 4 is the reference specification of the Indian tax and banking rules — treat it as authoritative.
> Sections 5-6 are the target architecture and UI.
> Section 7 is the ordered task backlog; each task has **Goal / Files / Change / Acceptance test**.
> Do not reorder tasks across phases — later phases depend on earlier ones.
>
> **Golden rule:** the four PDFs and the XLSX in `data/PersonalData/Pranav/` are the
> regression suite. A change is done when the numbers it produces match those
> documents — not when the code merely runs without error.

---

## 1. Executive summary

The architecture is sound: a clean `core / models / engines / ui` split, token-driven
theming, a sensible SQLite schema. The problems are concentrated in the **numerical
and extraction layers** — the code that decides what a number *means*.

Measured against the owner's real documents:

> ## ▶ The executable plan is [`REBUILD_PLAN.json`](REBUILD_PLAN.json)
>
> **This markdown file is the reasoning. The JSON is the plan.**
> An agent should execute `REBUILD_PLAN.json` — it merges the engine-layer findings below
> with a second audit pass (4 Sep 2026) that covered the **frontend** by rendering the real
> app offscreen under PyQt6 6.11 and screenshotting all 11 screens.
>
> The two were merged into one file because the dependency graph is interleaved: screen
> rebuilds are views of engine output and cannot be sequenced independently of it.
> It contains 60 tasks in a verified topological order, 27 reproducible measurements,
> the Indian tax/banking specification, and the design system.
> Section 9 below summarises the frontend findings; the task backlog in section 7 is
> superseded by the JSON.

| Area | Measured result | Should be |
|---|---|---|
| **Login** | **Crashes with `ImportError`** — the app is unusable after sign-in | Works |
| Transaction direction (income vs expense) | **27%–59% wrong** across the four banks | ~0% |
| FD detection from statements | Works for Jana only; **0% for Equitas / Ujjivan / IDFC** | All banks |
| AIS income extraction | Misses **₹60,091** of ₹4,10,549 (14.6%) | Exact |
| AIS TDS extraction | **₹19,194** vs true ₹13,367 (**+43%**) | Exact |
| TIS extraction | Reports **₹27,05,069** "other income" (true: ₹1,05,069) | Exact |
| 26AS TDS extraction | **₹1,847** vs true ₹13,367 (**−86%**) | Exact |
| Tax slabs | FY 2023-24 slabs; 87A rebate ₹25,000 | FY 2026-27 slabs; 87A ₹60,000 |
| Tax screen inputs | **~20 of ~30 fields silently discarded** on calculate | All used |
| FD "Bank Style" maturity | **Identical to Formula** (short-circuited) — the toggle does nothing | Distinct; matches bank |
| FD financial-year split | **₹789 in the wrong FY** on a single 501-day FD | Accrual-correct |
| Savings interest | Engine **never called anywhere** — always ₹0 | Daily-product, quarterly |
| DB encryption | README claims AES-256; **the DB is plaintext SQLite** | Fix the code, or fix the claim |

Two changes carry most of the value:

1. **Switch statement parsing from regex-over-text to coordinate-based column
   extraction.** Nearly every direction error, lost FD number and mangled narration
   traces back to flattening a table into a line of text and then guessing which
   number came from which column.
2. **Treat TIS as the source of truth for income and 26AS as the source of truth for
   tax credit**, instead of summing regex matches out of AIS.

---

## 2. Evidence — what the current code actually produces

Every figure below came from running this repository's own code against the owner's
real files. Task 0.5 makes these runs permanent.

### 2.1 Statement import is dead

```
>>> import engines.statement_parser
ImportError: cannot import name '_extract_reference_no' from partially
initialized module 'engines.statement_parser' (most likely due to a circular import)
```

**Cause.** `engines/statement_parser.py:20` runs `from engines.bank_parsers import parse_sbi_pdf`.
`engines/bank_parsers/__init__.py` then imports `yes_bank_statement_parser`, whose
**line 19** does `from engines.statement_parser import _extract_reference_no, ...` at
module top level. `_extract_reference_no` is defined at line ~41 of `statement_parser.py`
— *after* line 20 — so it does not exist yet.

`engines.bank_parsers` is imported from **exactly one place in the entire repo**
(`statement_parser.py:20`), so nothing ever pre-loads it to break the cycle.

**Severity correction (runtime-verified 4 Sep 2026).** An earlier draft of this document
said the app launches and only fails when "Statement Import" is clicked. That is wrong.
`DashboardScreen._build_content_area()` (`ui/dashboard_screen.py:516–565`) **eagerly
constructs all 11 screens** at login, `StatementImportScreen` among them
(line 541), and that module imports `engines.statement_parser` at its own module top
level (`ui/statement_import_screen_modern.py:39`). None of the four screens built before
it touches `engines.bank_parsers`, so the cycle is never pre-broken.

The failure therefore happens inside `LoginScreen._finish_login()` → `DashboardScreen()`.
**The app is unusable immediately after entering the correct password.** Confirmed by
running the real module under PyQt6 6.11:

```
>>> from ui.statement_import_screen_modern import StatementImportScreen
ImportError: cannot import name '_extract_reference_no' from partially
initialized module 'engines.statement_parser' (most likely due to a circular import)
```

**Introduced by** commit `9107bf0` *"feat: added hdfc and yes bank parser and fixies
import staement"* (23 Aug 2026), which added the YES parser.
`sbi_statement_parser.py:140` performs the same import **inside a function**, which is
why SBI never triggered it.

### 2.2 Transaction direction is wrong 27–59% of the time

Method: parse each statement with `GenericPDFParser`, then compare each row's assigned
type against the sign of the change in the statement's **own running balance** (which
the parser itself extracted). Rows whose balances do not tie out are excluded, so this
is a conservative floor.

```
Statement             Rows  Checkable  DirWrong    Err%     Parser Inc/Exp
--------------------------------------------------------------------------
Equitas.pdf             42         31        16   51.6%         9/33
IDFC.pdf               377        371       100   27.0%        14/363
Jana - Pranav.pdf       65         64        30   46.9%        12/53
Ujjivan - Pranav.pdf    27         22        13   59.1%         0/27
```

Ujjivan produced **zero** income rows, though its statement is almost entirely FD
closure credits. IDFC's own header reads Total Debit ₹4,80,013.35 vs Total Credit
₹4,67,264.82 — near parity — yet the parser returned 14 income against 363 expense.

Concrete misreads:

| Statement row | Truth | Parser said |
|---|---|---|
| IDFC `IMPS/509317380481/LOTUSINVESTMENT` ₹12,000 (bal 13,331→25,331) | Income | **Expense** |
| Ujjivan `4483130330001450 : Closure Proceeds` ₹97,651 | Income / FD Maturity | **Expense / Other Expense** |
| Jana `CREDIT INTEREST CAPITALISED` ₹1,504 | Income / Savings Interest | **Expense / Other Expense** |
| Equitas `INT AUTO REDEEM …` ₹5,389 | Income / FD Interest | **Expense / Other Expense** |
| Equitas `PRINC AND INT AUTO REDEEM` ₹50,000 | Income / FD Maturity | **Expense / Other Expense** |

**Why.** In `GenericPDFParser._parse_line`, the two-date branch (used by IDFC, Ujjivan
and Equitas) ends with:

```python
txn_type = _infer_txn_type_from_desc(remainder.upper()) or \
           _infer_txn_type_from_desc(upper) or "Expense"
```

There is **no balance-delta fallback in this branch** — it exists only in the one-date
branch — so any credit whose narration lacks a hard-coded keyword such as `"NEFT CR"`
silently defaults to **Expense**.

Worse, the three-number branch that *does* look at columns:

```python
if first_val > 0 and second_val == 0:
    amount = first_val            # sets amount and balance...
elif second_val > 0 and first_val == 0:
    amount = second_val           # ...but never sets txn_type
```

determines which of the Debit/Credit columns was populated and then **throws that
information away**. That is the most reliable signal in the whole document.

### 2.3 Narration and FD account numbers are destroyed

`_clean_pdf_description()` strips `\b\d{10,}\b` — any run of 10+ digits. That deletes
exactly the identifier which links a statement row to AIS and to an FD record:

| Original | After cleaning |
|---|---|
| `4483130330001450 : Closure Proceeds` | `: Closure Proceeds` |
| `UPI/MOB/509149175752/UPI` | `UPI/MOB//UPI` |
| `IMPS/509317380481/LOTUSINVESTMENT/…` | `IMPS//LOTUSINVESTM ENT/…` |

The Ujjivan number `4483130330001450` appears verbatim in AIS carrying interest of
₹3,387. Deleting it forfeits automatic FD-to-AIS reconciliation.

Also observed: header and footer text bleeding into transactions
(`UPI/MOB//UPI REGISTERED OFFICE: IDFC FIRST BANK LIMITED, K`); an invented row dated
`2022-11-15` for ₹13,631.64 assembled from the *account opening date* and the *opening
balance*; and a balance of `0.76` scraped out of the Equitas footer address
"No.769, Anna Salai".

### 2.4 Multi-line rows are reassembled wrongly

Jana prints one logical row across **three** physical lines, with the amounts line in
the middle:

```
CASA CREDIT INTEREST          CHBATCH4522010044796      <- narration + ref, part 1
01/04/2026    9.00   0.00   1,506.80                    <- date + amounts
CAPITALIZED                   705C260331                <- narration + ref, part 2
```

Line-based merging cannot recover this. The parser produced descriptions such as
`TD. GENERIC PAYIN DEBIT 40ef1bd7224 a75df1578e834c44888be` — reference fragments
belonging to **two different transactions** glued onto one row.

Jana also prints **newest-first**. The parser carries `prev_balance` forward assuming
ascending order, so its balance-delta logic is inverted for Jana.

### 2.5 FD keyword rules are incomplete and mis-ordered

`_guess_fd_category()` tests `"AUTO REDEEM"` **before** `"INT AUTO REDEEM"`:

```python
if any(w in desc_upper for w in ["PRINC AND INT AUTO REDEEM", "AUTO REDEEM", ...]):
    return "FD Maturity"      # <- "INT AUTO REDEEM" matches here first
if any(w in desc_upper for w in ["INT AUTO REDEEM", "FD INTEREST"]):
    return "FD Interest"      # <- unreachable
```

So Jana's `INT AUTO REDEEM PRANAV 4522030015435122/1` (₹8,511 of **interest**) is booked
as **FD Maturity**. Interest is taxable income; return of principal is not. This
corrupts the tax figure directly.

Missing vocabulary for the owner's actual banks:

| Bank | Real narration | Meaning | Detected today? |
|---|---|---|---|
| Equitas | `INITIAL PAYIN … FD300014105382` | FD booking | **No** |
| Equitas | `TD/00671929` | FD reference | **No** |
| Ujjivan | `<acct> : Closure Proceeds` | FD maturity | **No** |
| Jana | `CREDIT INTEREST CAPITALISED` | Savings interest | **No** |
| Jana | `TD. GENERIC PAYIN DEBIT` | FD booking | Yes |
| Jana | `PRINC AND INT AUTO REDEEM` | FD maturity | Yes |
| Jana | `INT AUTO REDEEM` | FD interest | **Mis-mapped to Maturity** |

### 2.6 AIS / TIS / 26AS extraction

Ground truth, taken from the TIS document itself (TIS is the department's own
de-duplicated summary):

| Category | Truth (TIS, FY 2025-26) |
|---|---|
| Dividend | 2,655 |
| Interest from savings bank | 46,183 |
| Interest from deposit (FD) | 2,56,642 |
| Business receipts (194J) | 1,05,069 |
| **Total income** | **4,10,549** |
| Purchase of time deposits (**not income**) | 13,00,000 |
| TDS actually deducted (26AS) | 13,367 |

**`parse_ais_pdf_text` output:**

| Field | Parsed | Truth | Error |
|---|---|---|---|
| FD interest | 2,45,389 | 2,56,642 | **−11,253** |
| Savings interest | **0** | 46,183 | **−46,183** |
| Dividend | **0** | 2,655 | **−2,655** |
| Business receipts | 1,05,069 *(as `other_income`)* | 1,05,069 | wrong bucket |
| TDS deducted | **19,194** | 13,367 | **+5,827 (+43%)** |

*Causes.* (a) `summary_re` only matches rows whose code begins `TDS-`, so every **SFT**
row is invisible — that is all savings-bank interest, all dividend, and the FD interest
of AU (₹9,710) and IDFC (₹1,543), which carry no TDS entry because Form 15G was filed.
(b) `detail_re` matches **Active and Inactive rows alike** and sums TDS from both; AIS
rows 60–102 for Jana are superseded `Inactive` entries that must be ignored.

**`parse_tis_pdf_text` output** — the worst of the three:

| Field | Parsed | Truth |
|---|---|---|
| other_interest | 3,49,008 | 0 |
| dividend | 5,310 | 2,655 *(counted twice)* |
| **other_income** | **27,05,069** | 1,05,069 |

`27,05,069 = 13,00,000 × 2 + 1,05,069`. The **"Purchase of time deposits"** SFT-005 line
— money the owner *invested*, not income — is counted as income, **twice**. Left
unfixed, this fabricates ₹26 lakh of taxable income.

**`parse_form26as_pdf` output** — 6 records from a document containing 200+ detail rows:

```
sum tds_deducted : 1,847.00     (truth 13,367)      -86%
name             : 'AZIPT9702H Assessee Name'
sections seen    : {'194J': 1, '194A': 4, '194B': 1}   <- 194B = lottery winnings
dates            : ''  (all empty)
deductor name    : '1 ENLIGHTVISION TECHNOLOGIES PRIVATE LIMITED  105069.00 10508.00 10508'
```

*Causes.* It searches for the literal strings `"PART A"` / `"PART B"`, but 26AS uses
`PART-I`, `PART-II`, … so the section state machine never exits and ingests the legend
pages. It requires a TAN on the line, so **detail rows are never read**. It parses dates
as `dd/mm/yyyy` while 26AS prints `31-Mar-2026`. `re.search(r"19[0-9][A-Z]?")` matched
`194BA` in the legend and recorded section `194B`. **Part II (15G/15H) is not handled at
all** — that is ₹2,23,133 of the owner's interest income. Reversal entries (Remarks `B`
or `G`, negative amounts) are never netted.

### 2.7 FD mathematics diverges from the owner's own spreadsheet

The `Data 26-27.xlsx` "Bank" sheet keeps **two** maturity calculations per FD, and the
app mirrors them with `maturity_amount_formula` / `maturity_amount_bank`. Running the
app's engine on the sheet's own four Jana FDs:

```
FD                          Sheet H  app flexible  Sheet Z  app bankStyle
---------------------------------------------------------------------------
2026-02-24 +201d              4,455      4,458.54    4,496       4,458.54
2026-02-24 +501d             11,482     11,485.52   11,545      11,485.52
```

**`calculate_fd_maturity_bank_style` returns exactly the same number as
`calculate_fd_maturity_flexible`.** The "Bank Style" option in the UI is inert for
day-tenure FDs — which is every FD the owner holds — because of this short-circuit:

```python
if tenure_days > 0 and tenure_years == 0 and tenure_months == 0:
    return calculate_fd_maturity_flexible(...)     # bank-style never runs
```

The spreadsheet's genuine bank method (columns U–Z) is: compound quarterly for
**completed** quarters, then **simple** interest on the accumulated balance for the
leftover days —
`W = P(1+r/4)^q − P`, `X = P(1+r/4)^q × (d/365) × r`, `Z = round(W + X)`.

**Financial-year allocation is materially wrong.** For the 501-day FD
(₹1,00,000 @ 8%, 24-Feb-2026 → 10-Jul-2027, total interest ₹11,482):

```
FY             sheet (accrual)   app (credit-event)      diff
2025-26                    789                 0.00      -789
2026-27                  8,279             8,219.09       -60
2027-28                  2,414             3,262.91      +849
TOTAL                   11,482            11,482.00
```

The app assigns a whole compounding quarter to the FY in which the quarter *ends*. The
first quarter (24-Feb-2026 → 23-May-2026) **straddles 31 March**, so all of it lands in
FY 2026-27 and FY 2025-26 receives ₹0. The total is preserved, but a financial-year
application is judged entirely on *which year* a number falls in. Across the four FDs
in the sheet this misplaces roughly ₹3,156 in a single year — and it is the number that
feeds the tax screen and the TDS-threshold warning.

Note also that `interest_engine.py` contains **three mutually inconsistent FY-allocation
methods**: `calculate_fd_interest_for_fy` (straight-line by days),
`calculate_fd_interest_quarterly_for_fy` (straight-line into quarters), and
`calculate_fd_quarterly_credit_breakdown` (credit events). Only the last is used by
`allocate_fd_interest_to_fy`.

### 2.8 The tax engine is two budgets out of date

`engines/tax_engine.py` still encodes FY 2023-24:

```python
NEW_REGIME_SLABS = [(300000,0),(600000,5),(900000,10),(1200000,15),(1500000,20),(inf,30)]
rebate_87a = min(base_tax, 25000) if taxable_income <= 700000
standard_deduction: float = 75000     # applied unconditionally
```

Correct for FY 2025-26 **and** FY 2026-27 (unchanged between them): slabs
`4L / 8L / 12L / 16L / 20L / 24L`, 87A rebate **₹60,000** up to taxable income
**₹12,00,000**, with **marginal relief** above that point.

Missing entirely: **surcharge**, **marginal relief**, the rule that **87A does not apply
to special-rate income** (111A / 112 / 112A), and the rule that the **₹75,000 standard
deduction applies only against salary or pension**. The owner has *no* salary — his
income is professional fees under 194J — so the app grants him a ₹75,000 deduction he
is not entitled to.

### 2.9 The tax screen discards most of its own inputs

`ui/tax_screen.py` builds roughly 30 input fields and sums them into the on-screen
"Gross Income" label in `_update_gross()` (line 590). But `calculate_and_save_tax`
accepts only 8 income/deduction arguments. Fields that are collected, displayed in the
gross total, and then **silently dropped** at calculate time:

- `presumptive_income` (44AD / 44ADA) — **the owner's entire professional income**
- `manufacturing_income`, `other_business_income`
- `stcg_normal`, `stcg_111a`, `ltcg_20`, `ltcg_112a`, `ltcg_other`
- `annual_rent`, `municipal_tax`, `unrealized_rent`, `letout_interest`, `self_occupied_interest`
- `deduction_80tta`, `deduction_80ttb`

The "Gross Income" shown on screen and the gross income actually taxed are two different
numbers on the same screen.

### 2.10 Savings interest is never computed

```
$ grep -rn "allocate_savings_interest_to_fy\|calculate_savings_interest_for_fy" --include=*.py .
engines/interest_engine.py:  (definitions only)
```

Both functions are **dead code**. `SavingsInterestRecord` is never populated by the
engine, so `get_total_savings_interest()` — used by the tax projection — always returns
0. For the owner that is ₹46,183 of real, taxable income.

The algorithm is wrong in any case: `_average_monthly_balance` averages the
`balance_after` of *transactions* within each month, then averages those monthly
averages. A month holding one ₹5,00,000 transaction and 29 quiet days at ₹1,000 averages
to ₹5,00,000. Since 1 April 2010 the RBI has required savings interest on the **daily
closing balance**, credited quarterly or more frequently.

### 2.11 Other defects

- **`config.py`: `FD_TDS_FORM_NAME = "Form 121"` — no such form exists.** It is
  **Form 15G** (under 60) / **Form 15H** (senior citizen). The owner has in fact filed
  15G: 26AS Part II shows ₹2,23,133 of interest with nil TDS.
- **README claims "AES-256 database encryption"; `core/database.py` opens a plaintext
  SQLite file.** Only two *fields* are encrypted (`statement_password_enc`,
  `ais_tis_password_enc`). Either adopt SQLCipher or correct the claim — do not leave a
  false security promise in the README.
- **`advance_tax_engine`**: `total_paid` never accumulates across instalments, so all
  four rows show the same paid figure; 234C interest is hard-coded to 3 months (the
  15-March instalment attracts **1**); the statutory safe harbours are **12% / 36%**,
  not 15% / 45%; and the **44ADA single-instalment rule** (100% by 15 March) is not
  implemented — precisely the owner's case, so the app would wrongly flag him overdue
  for Q1–Q3.
- **`BankAccount.person_id` is a single FK, but the owner's spreadsheet has joint
  accounts** (`B+P+Pranav`, `A+B+P`, `A+P+Pranav`, `Pranav+B`) and an **HUF** — a
  separate tax entity with its own PAN and its own return.
- `Form26ASImport` / `Form26ASRecord` / `IncomeSource` / `AISTISImportLine` /
  `AISTISImportRecord` are created ad hoc inside model modules rather than in
  `initialise_database()`. All table creation belongs in one place.
- `_extract_reference_no`'s pattern `\b[A-Z0-9]{12,}\b` matches long hex narration
  fragments, so it often returns noise rather than a real UTR.

---

## 3. What the owner's data tells us about the domain

Read this before designing anything. The spreadsheet and the tax documents together
define what the app is supposed to be.

### 3.1 `Data 26-27.xlsx` — the mental model to reproduce

**Sheet "Bank"** has three blocks.

*Block 1 — per-person roll-up (rows 7–11).* Columns: Saving Balance, Saving Int,
FD Maturity Amount, Expected Int, Actual Interest, Expected Salary, Actual Salary,
Total. Entities: **BAT, PAT, Pranav, HUF**.

*Block 2 — the bank × person matrix (rows 16–55).* Banks: Unity, Jana, Ujjivan,
Equitas, IDFC, HDFC, SBI, YES, AU, BOI, RNSB. Holders include joint combinations
(`B+P+Pranav`, `A+B+P`, `A+P+Pranav`, `Pranav+B`). Per account: Saving Balance,
FD Maturity Amount, Expected Interest, Actual Interest.

*Block 3 — the FD engine (rows 65–73).* This is the heart of the workbook.

| Col | Meaning | Formula |
|---|---|---|
| C | Start date | — |
| D | Tenure in **days** | — |
| E | Maturity date | `= C + D` |
| F | Principal | — |
| G | Rate % | — |
| H | **Total interest (formula method)** | `ROUNDUP(F*(1+G/400)^(4*(E−C)/365),0) − F − 4` |
| I | Maturity amount | `= F + H` |
| K | FD account number | — |
| M | Days before 1 Apr 2026 | `IF(C<=FYstart, FYstart−C, 0)` |
| N | Days from start to FY end | `IF(E>=FYstart, IF(E>=FYend, FYend−C, D), 0)` |
| P | Interest in FY 2025-26 | `INT(IF(M<=183, F*G/100*M/365, …compound…))` |
| Q | Interest in FY 2026-27 | `INT(compound to FY end) − P` |
| R | Interest in FY 2027-28 | `IF(E>=nextFYstart, H, 0) − Q − P` |
| U–Z | **Bank-style interest** | quarters `U=INT(days/30.433/3)`; `W=(1+G/400)^U*F−F`; `X=(1+G/400)^U*F*(V/365)*(G/100)`; `Z=ROUND(W+X,0)` |

Four things to carry into the app:

1. **Tenure is expressed in days**, and maturity date is `start + days`.
2. **The ≤183-day rule**: short deposits earn **simple** interest, not compound. This is
   real Indian banking practice and the app has no notion of it.
3. **FY allocation is accrual-by-difference**: compute cumulative interest to each
   31 March, then subtract the prior year. This is the correct method and it is *not*
   what the app does (see §2.7).
4. **Two maturity figures are kept side by side** (formula and bank-style) because banks
   round differently. The `− 4` in column H is an empirical calibration to match the
   bank's actual figure; it should become a **per-bank calibration setting**, not a
   hard-coded constant.

*Known defects in the workbook itself* (worth fixing when the app supersedes it):
the `Q$23` reference in column Q is stale and always false; the two branches of the
inner `IF` in column Q are identical; and the `M<=365` branch of column P charges a
full year of compounding for tenures between 184 and 365 days.

**Sheet "Salary"** — expected vs actual salary per person per month for FY 2026-27:
BAT ₹41,600/month (₹4,99,200), PAT ₹31,600/month (₹3,79,200), Pranav ₹21,500 for
Apr–Jul then ₹25,000 for Aug–Mar (₹2,86,000). Note the **mid-year change** — expectations
must be stored per occurrence, not as a single annual figure. `IncomeExpectation` already
supports this.

### 3.2 What the tax documents reveal

**Pranav's income is professional fees under section 194J, not salary.** The deductor is
ENLIGHTVISION TECHNOLOGIES PRIVATE LIMITED (TAN `AHME02369D`), ₹1,05,069 paid with
₹10,508 TDS at 10%. AIS files it under the heading **"Business receipts"**. Consequences:

- He files **ITR-3**, or **ITR-4** if he opts for presumptive taxation under **44ADA**.
- He gets **no ₹75,000 standard deduction** — that is a salary-only relief.
- Because he has business/professional income, the **one-time** new-regime switch rule
  genuinely applies to him (Form 10-IEA). His statement that there is no way back to the
  old regime is correct *for him*. (For a purely salaried person the choice is annual —
  worth remembering if BAT or PAT are salaried.)

**Form 15G has been filed.** 26AS **Part II** — a part the parser ignores entirely —
shows ₹90,745 (Jana) + ₹53,311 (Equitas) + ₹79,077 (Ujjivan) = **₹2,23,133** of interest
carrying **nil TDS**. This is why `FD_TDS_FORM_NAME` matters and why it must say
**Form 15G**.

**The three documents nest cleanly, and that is exploitable:**

```
AIS per-bank total = 26AS Part I (with TDS) + 26AS Part II (15G/15H, nil TDS)
   Jana    93,604 =  2,859 + 90,745   ✓
   Equitas 72,708 = 19,397 + 53,311   ✓
   Ujjivan 79,077 =      0 + 79,077   ✓
TIS category total = sum of AIS SFT rows, with TDS duplicates removed
   Interest from deposit 2,56,642 = 93,604 + 79,077 + 72,708 + 9,710 + 1,543  ✓
```

**TIS de-duplicates; AIS does not.** In AIS the same FD interest is reported twice — once
as `TDS-194A` (Part B1) and once as `SFT-016(TD)` (Part B2). TIS keeps the SFT figure and
marks the TDS duplicate `-`. **Any importer that adds Part B1 and Part B2 together will
roughly double the interest income.**

**AIS gives per-FD-account interest.** `SFT-016(TD)` lists each deposit account number
with its interest — e.g. Jana `45220300154351221` → ₹3,726, Ujjivan `4483130330001450` →
₹3,387, Equitas `3000108323941` → ₹6,395. And those numbers appear in the statements:

| Bank | Statement narration | AIS account number | Rule |
|---|---|---|---|
| Jana | `4522030015435122/1` | `45220300154351221` | remove `/` |
| Ujjivan | `4483130330001450 : Closure Proceeds` | `4483130330001450` | exact |
| Equitas | `FD300014105382` | `3000141053821` | strip `FD`, prefix match |

**This is the reconciliation key the whole app should be built around**: statement row →
FD record → AIS-reported interest, matched on deposit account number.

**Only `Active` rows count.** AIS marks superseded entries `Inactive`; the summary
`COUNT` equals the number of Active rows exactly (Jana: 59 Active, COUNT 59, AMOUNT
₹93,604).

**26AS contains reversal pairs.** Its own legend states *"Figures in brackets represent
reversal (negative) entries"*, with Remarks `B` (rectification by deductor) and `G`
(reprocessing). Jana's Part I has +93 / −93, +186 / −186 pairs that net out. **The
deductor-level total row is authoritative — sum the header, never the details.**

**SFT-005 "Purchase of time deposits" ₹13,00,000 is not income.** It is a
reportable-transaction disclosure. It must be surfaced as a compliance flag and
**excluded from every income total**.

**A refund of ₹3,880 for FY 2024-25 was received 04/10/2025** (AIS Part B4) — the app
should track refunds.

### 3.3 The owner's FY 2025-26 position, computed correctly

| Line | Amount |
|---|---|
| Professional receipts (194J) | 1,05,069 |
| Presumptive profit @ 50% u/s 44ADA | 52,535 |
| Interest from deposits | 2,56,642 |
| Interest from savings bank | 46,183 |
| Dividend | 2,655 |
| **Total income** | **3,58,015** |
| Standard deduction | **nil** (no salary) |
| Basic exemption, new regime | 4,00,000 |
| **Tax payable** | **nil** |
| TDS already deducted | 13,367 |
| **Refund due** | **13,367** |

Total income sits below the ₹4,00,000 basic exemption, so the 87A rebate is not even
reached. The app must be able to produce this result and the resulting refund figure.

---

## 4. Reference specification — Indian rules the app must encode

### 4.1 New regime slabs, FY 2025-26 and FY 2026-27 (identical)

| Taxable income | Rate |
|---|---|
| Up to ₹4,00,000 | Nil |
| ₹4,00,001 – ₹8,00,000 | 5% |
| ₹8,00,001 – ₹12,00,000 | 10% |
| ₹12,00,001 – ₹16,00,000 | 15% |
| ₹16,00,001 – ₹20,00,000 | 20% |
| ₹20,00,001 – ₹24,00,000 | 25% |
| Above ₹24,00,000 | 30% |

- **Section 87A rebate:** lower of tax on normal income or **₹60,000**, where total
  income **excluding special-rate income** is ≤ **₹12,00,000**. Applied **before**
  surcharge and cess.
- **Marginal relief** above ₹12,00,000: tax payable is capped so that it never exceeds
  the income earned above ₹12,00,000.
- **87A is not available against special-rate income** — sections 111A (STCG on equity),
  112 and 112A (LTCG) — regardless of total income. Finance Act 2025 made this explicit.
- **Standard deduction ₹75,000** — against **salary or pension income only**.
- **Health & Education Cess 4%** on (tax − rebate + surcharge).
- **Surcharge** (new regime): 10% above ₹50 lakh, 15% above ₹1 crore, 25% above ₹2 crore;
  capped at 15% for income under 111A/112A. Surcharge has its own marginal relief.

Store slabs **per financial year** in a table keyed by FY. Never hard-code a single set.

### 4.2 TDS and Form 15G

- **Section 194A** (interest other than securities): TDS **10%** with PAN, **20%**
  without. Threshold from FY 2025-26: **₹50,000** for non-seniors, **₹1,00,000** for
  senior citizens — applied **per bank**, aggregating all branches.
- **Section 194J** (professional or technical fees): **10%**.
- **Form 15G** (under 60) / **Form 15H** (60+): self-declaration filed with each bank
  when total income is below the taxable limit, to prevent deduction. File at the start
  of the financial year. `config.FD_TDS_FORM_NAME` must say **Form 15G**, and the app
  should choose 15G vs 15H from the person's date of birth.

### 4.3 Presumptive taxation — section 44ADA

- Eligible: resident individual or firm (not LLP) in a specified profession.
- Gross receipts limit **₹50 lakh**, raised to **₹75 lakh** when cash receipts are ≤5%.
- Deemed profit **50%** of gross receipts (a higher figure may be declared).
- File **ITR-4**.
- **Advance tax may be paid in a single instalment by 15 March** — this overrides the
  normal four-instalment schedule and must be honoured by `advance_tax_engine`.

### 4.4 Advance tax (non-44ADA)

| Due | Cumulative | 234C safe harbour |
|---|---|---|
| 15 Jun | 15% | 12% |
| 15 Sep | 45% | 36% |
| 15 Dec | 75% | 75% |
| 15 Mar | 100% | 100% |

234C interest is 1% per month for **3 months** on the first three shortfalls and
**1 month** on the 15-March shortfall. No advance tax is due if net liability after TDS
is under ₹10,000. Resident senior citizens without business income are exempt.

### 4.5 Bank interest mathematics

**Fixed deposits.**
- Tenure **under 6 months (≤183 days): simple interest** — `P × r × d / 365`.
- Tenure **6 months and above: quarterly compounding** — `P(1 + r/4)^q` for completed
  quarters, then **simple interest on the accumulated balance** for the broken period:
  `P(1+r/4)^q × d/365 × r`.
- Use a 365-day denominator (366 in a leap year for the days falling in it).
- **FY allocation for tax is on an accrual basis**: cumulative interest to 31 March,
  minus cumulative interest to the previous 31 March. Banks report accrued interest per
  FY in AIS on this basis.

**Savings accounts.**
- **Daily closing balance ("daily product") basis**, mandatory since 1 April 2010.
- Credited **quarterly or more frequently**.
- `interest = Σ(daily closing balance) × rate / days_in_year`, accumulated per quarter.
- The app already stores `balance_after` per transaction, so the daily balance series
  can be reconstructed by carrying the last known balance forward across quiet days.

### 4.6 The three documents

| | **Form 26AS** | **AIS** | **TIS** |
|---|---|---|---|
| Source | TRACES | Compliance Portal | Compliance Portal |
| Contains | TDS/TCS credit, advance tax, refunds | Every reported transaction, per source | De-duplicated category summary |
| Use for | **Claiming tax credit** | **Per-source detail & feedback** | **Income figures for the ITR** |
| Duplicates? | No | **Yes** (TDS and SFT both report the same interest) | **No** |
| Authority | Wins on TDS credit | Detail | Wins on income totals |

Structure the importer accordingly: **TIS drives income, 26AS drives credit, AIS supplies
the per-account detail that lets you reconcile against FD records.**

26AS parts to handle: **Part I** (TDS), **Part II** (TDS for 15G/15H — nil TDS but real
income), Part III–V, **Part VI** (TCS), **Part VII** (refunds paid), Part VIII–IX,
**Part X** (defaults). Status codes: `F` Final, `U` Unmatched, `M` Matched, `P`
Provisional, `O` Overbooked, `Z` Mismatch. Only `F`/`M` should be treated as reliable
credit.

---

## 5. Target architecture

### 5.1 Statement parsing — replace text regex with column geometry

The new pipeline, in `engines/statement/`:

```
extract.py    pdfplumber .extract_words() -> words with x0, x1, top, bottom
rows.py       cluster words into visual rows by `top` (tolerance ~3px)
columns.py    detect the column header row; derive x-ranges per column;
              assign every word to a column by x-midpoint
schema.py     map detected headers to canonical fields via a synonym table
assemble.py   merge continuation rows (rows with no date and no amount) into
              the preceding logical row, per column
validate.py   walk the running balance; assert bal[n] == bal[n-1] ± amount[n]
```

Design rules, each answering a specific failure in §2:

1. **Direction comes from the column, never from keywords.** A value in the
   Debit/Withdrawal column is an Expense; a value in the Credit/Deposit column is
   Income. Keywords are used only for *category*, never for direction.
2. **Balance validation is the acceptance test.** After parsing, walk the running
   balance. Every row must satisfy `balance[n] − balance[n−1] == ±amount[n]`. Report a
   confidence score, and refuse to import below a threshold rather than importing
   wrong data silently.
3. **Detect statement ordering** by comparing the first and last dates; normalise to
   ascending before any balance-delta reasoning (Jana prints newest-first).
4. **Never delete digits from the narration.** Keep `description_raw` verbatim.
   Extract identifiers *additively* into `reference_no` and a new
   `deposit_account_no` field. Losing `4483130330001450` costs the AIS match.
5. **Reconcile against the statement's control totals** where printed (IDFC gives
   Opening Balance / Total Debit / Total Credit / Closing Balance). A parse that does
   not tie to those totals is a failed parse.
6. **Bank profiles are data, not code.** One YAML/JSON per bank holding column
   synonyms, date formats, ordering, narration vocabulary and calibration constants.
   Adding a bank should not require a new Python module.

### 5.2 Bank narration vocabulary (seed from the real statements)

```yaml
fd_booking:      ["TD. GENERIC PAYIN DEBIT", "INITIAL PAYIN", "PAYIN DEBIT",
                  "FIXED DEPOSIT", "TERM DEPOSIT", "FD BOOKING"]
fd_maturity:     ["PRINC AND INT AUTO REDEEM", "CLOSURE PROCEEDS", "FD CR",
                  "MATURITY", "MATURED", "REDEMPTION", "REDEEMED"]
fd_interest:     ["INT AUTO REDEEM", "FD INTEREST", "INTEREST ON DEPOSIT"]
savings_interest:["CREDIT INTEREST CAPITALISED", "CASA CREDIT INTEREST",
                  "CREDIT INTEREST CAPITALIZED"]
bank_charges:    ["SMS ALERTS CHARGES", "GOODS AND SERVICES TAX", "AMB CHARGES"]
```

**Match longest-pattern-first.** `INT AUTO REDEEM` must be tested before
`AUTO REDEEM`, and `PRINC AND INT AUTO REDEEM` before both. Encode this as an ordered
list with explicit priority, so the §2.5 shadowing bug cannot recur.

### 5.3 Tax document importers — one module per document

```
engines/taxdocs/form26as.py   Parts I–X; nets reversal entries; deductor totals authoritative
engines/taxdocs/ais.py        Part B1 (TDS) + B2 (SFT); Active only; per-account detail
engines/taxdocs/tis.py        category totals from the "Accepted by taxpayer" column
engines/taxdocs/merge.py      TIS income + 26AS credit + AIS detail -> one FY position
```

Non-negotiable rules:

- **Active-only.** Skip every AIS row whose status is `Inactive`. Verify with the
  summary `COUNT`.
- **Never add Part B1 to Part B2.** They describe the same money. Prefer the SFT figure;
  fall back to TDS only where no SFT row exists for that source.
- **Maintain an explicit non-income code list** — `SFT-005` (purchase of time deposits),
  `SFT-004`, `SFT-012` and similar. These are compliance disclosures. Surface them on a
  "Reported transactions" panel and exclude them from every income total.
- **Net reversals in 26AS**: sum signed amounts, and prefer the deductor header total.
- **Parse dates as `dd-MMM-yyyy`** for 26AS and `dd/mm/yyyy` for AIS.
- Use **table extraction**, not line regex — these are real ruled tables and pdfplumber
  handles them.
- **Store the parse, not just the totals**: one row per source per section, keeping TAN,
  account number, quarter, amount and status, so the UI can drill down and so FD
  matching has something to join against.

### 5.4 Data model changes

```sql
-- Joint accounts and the HUF (the spreadsheet already needs this)
CREATE TABLE AccountHolder (
    account_id INTEGER NOT NULL REFERENCES BankAccount(account_id),
    person_id  INTEGER NOT NULL REFERENCES Person(person_id),
    is_primary INTEGER NOT NULL DEFAULT 0,       -- primary holder declares the interest
    PRIMARY KEY (account_id, person_id)
);
ALTER TABLE Person ADD COLUMN entity_type TEXT DEFAULT 'Individual';  -- Individual | HUF
ALTER TABLE Person ADD COLUMN date_of_birth TEXT;   -- drives 15G vs 15H

-- The AIS reconciliation key
ALTER TABLE FixedDeposit  ADD COLUMN deposit_account_no TEXT;
ALTER TABLE Transactions  ADD COLUMN deposit_account_no TEXT;
CREATE INDEX idx_FD_deposit_account ON FixedDeposit(deposit_account_no);

-- Per-FY tax parameters, so no slab is ever hard-coded again
CREATE TABLE TaxSlabConfig (
    financial_year TEXT NOT NULL,
    regime         TEXT NOT NULL,      -- 'New'
    upper_limit    REAL,               -- NULL = infinity
    rate           REAL NOT NULL,
    sort_order     INTEGER NOT NULL
);
CREATE TABLE TaxParams (
    financial_year        TEXT PRIMARY KEY,
    rebate_87a_limit      REAL, rebate_87a_max REAL,
    standard_deduction    REAL,
    cess_rate             REAL,
    fd_tds_threshold      REAL, fd_tds_threshold_senior REAL
);

-- Savings interest on a daily-product basis
ALTER TABLE SavingsInterestRecord ADD COLUMN quarter TEXT;
ALTER TABLE SavingsInterestRecord ADD COLUMN daily_product REAL;
ALTER TABLE SavingsInterestRecord ADD COLUMN calculation_basis TEXT DEFAULT 'DailyBalance';

-- Per-bank FD calibration (replaces the spreadsheet's hard-coded "-4")
CREATE TABLE BankFDConvention (
    bank_id             INTEGER PRIMARY KEY REFERENCES Bank(bank_id),
    compounding         TEXT DEFAULT 'Quarterly',
    simple_below_days   INTEGER DEFAULT 183,
    day_count           TEXT DEFAULT 'Actual/365',
    rounding_adjustment REAL DEFAULT 0
);
```

Move **all** `CREATE TABLE` statements into `core/database.py`.

### 5.5 Interest engine — one method, not three

Delete `calculate_fd_interest_for_fy` and `calculate_fd_interest_quarterly_for_fy`.
Keep a single accrual function that mirrors the spreadsheet:

```python
def fd_interest_accrued_to(fd, as_of: date) -> float:
    """Cumulative interest from start_date to as_of, using the bank's convention."""

def fd_interest_for_fy(fd, fy: str) -> float:
    """Accrual basis, matching Data 26-27.xlsx columns P/Q/R."""
    fy_start, fy_end = fy_date_range(fy)
    return (fd_interest_accrued_to(fd, min(fy_end, maturity))
            - fd_interest_accrued_to(fd, min(fy_start - 1day, maturity)))
```

`fd_interest_accrued_to` must implement §4.5: simple interest below the bank's
`simple_below_days`, otherwise quarterly compounding for completed quarters plus simple
interest on the broken period.

---

## 6. UI / UX plan

### 6.1 Navigation — remove one screen, add one

Current `_NAV_ITEMS` in `ui/dashboard_screen.py:33`:

```
Overview · Accounts · Transactions · Income Management · Fixed Deposits ·
Statement Import · AIS/TIS Import · Tax · 26AS vs AIS · Reports · Settings
```

Target:

```
Overview · Accounts · Transactions · Income & Expectations · Fixed Deposits ·
Statement Import · Tax Documents · Tax · Reports · Settings
```

- **Remove "26AS vs AIS".** As the owner asked, and because it compares two documents
  that measure different things (26AS is credit, AIS is income), which is why it never
  produced a useful answer. Delete `ui/reconciliation_screen.py` and
  `engines/reconciliation_engine.py`.
- **Merge "AIS/TIS Import" into "Tax Documents"**, which imports 26AS, AIS and TIS
  together and shows one reconciled FY position.
- **Rename "Income Management" to "Income & Expectations"** and make it the new
  expected-income screen described below.

### 6.2 The new "Income & Expectations" screen

This replaces the reconciliation screen with what the owner actually asked for:
*"my actual data expected income these year visualisation"*. It is the Excel workbook,
made live.

**Header strip** — FY selector, person selector (including HUF and "All"), and four
KPI tiles:

```
Expected income      Received to date      Still expected      Projected tax
₹ 12,45,000          ₹ 4,10,200 (33%)      ₹ 8,34,800          ₹ 0
```

**Panel 1 — Expected vs Actual by month** (grouped bar chart, 12 months).
Expected from `IncomeExpectation`, actual from matched `Transactions`. This is the
"Salary" sheet, visualised — and it handles Pranav's mid-year ₹21,500 → ₹25,000 step
because expectations are stored per occurrence.

**Panel 2 — Income composition** (stacked bars by FY, or a donut for one FY).
Segments: Professional/Business receipts · FD interest · Savings interest · Dividend ·
Salary · Other. Colour must stay consistent with the rest of the app.

**Panel 3 — FD interest runway** (the workbook's P/Q/R columns as a chart).
Interest accruing per FY across all live FDs, with a marker on the current FY. Answers
"how much interest lands in which year" at a glance.

**Panel 4 — Per-bank TDS threshold gauges.**
One horizontal gauge per bank showing FY interest against the ₹50,000 (or ₹1,00,000)
threshold, coloured green / amber / red, labelled with the quarter in which the running
total crosses. Where a 15G is on file, badge it — the owner has filed 15G with Jana,
Equitas and Ujjivan and the app should show that rather than warn pointlessly.

**Panel 5 — Expectation ledger** (table). Columns: Month · Type · Source · Expected ·
Actual · Variance · Status · Matched transaction. Inline edit; "Auto-match" button.

Follow the `dataviz` guidance for all charts: currency axes in ₹ with Indian digit
grouping, no more than 6 categorical colours, direct labels rather than legends where
a chart has ≤4 series, and readable in both light and dark themes.

### 6.3 The "Tax Documents" screen

Three drop zones (26AS · AIS · TIS), each showing parse status, then one reconciled view:

```
Category                    TIS        AIS      26AS    In app    Status
Interest from deposit    2,56,642   2,56,642      —    2,51,180   ⚠ short 5,462
Interest from savings       46,183     46,183     —          0    ✗ missing
Business receipts (194J)  1,05,069   1,05,069  1,05,069  1,05,069  ✓
Dividend                     2,655      2,655     —          0    ✗ missing
─────────────────────────────────────────────────────────────────────────
TDS credit claimable                             13,367            ✓ 26AS
Reported (not income): purchase of time deposits ₹13,00,000        ⓘ SFT-005
```

Then a **per-FD drill-down** matching AIS `SFT-016(TD)` account numbers to FD records —
the feature the owner's data makes possible and which nothing in the app currently
exploits:

```
Deposit account        Bank      AIS interest   App interest   Δ
45220300154351221      Jana            3,726          3,726    ✓
4483130330001450       Ujjivan         3,387              —    ✗ FD not in app
3000108323941          Equitas         6,395          6,340    ⚠ 55
```

### 6.4 Tax screen — new regime only

- Delete every old-regime field and the old-vs-new comparison, per the owner's
  instruction. Keep the `*_old` DB columns so historical rows still load.
- Delete 80C / 80D / 80TTA / 80TTB / HRA / home-loan inputs — none are available in the
  new regime.
- Group what remains: **Salary · Business/Professional · Capital gains · Other sources ·
  Taxes paid**.
- Show the computation as a **visible waterfall**, so the number can be audited:
  `Gross → deductions → Taxable → Slab tax → 87A rebate → Marginal relief → Surcharge → Cess → Total → less TDS → Payable/Refund`.
- **The gross shown must be the gross computed.** Wire every field through to the engine
  (§2.9) or remove the field.
- Add an **ITR form hint**: business/professional income present → ITR-3, or ITR-4 if
  44ADA is elected; interest and dividend only → ITR-1.

### 6.5 General UI notes

- The app has ten themes and a token system already — keep using `Theme.*` tokens and do
  not introduce new hard-coded colours.
- Add **empty states** to every screen ("No FDs yet — import a statement or add one").
- Statement import should end on a **confidence summary**: rows parsed, balance
  validation pass rate, rows needing review — and block a low-confidence import.
- Use ₹ with Indian digit grouping (`₹ 2,56,642`) consistently; there is already a
  `session.mask()` helper for privacy mode.

---

## 7. Task backlog

Execute in order. Each task states its acceptance test; do not mark a task done until
its test passes against the files in `data/PersonalData/Pranav/`.

### Phase 0 — Unblock and build the safety net

**Task 0.1 — Fix the circular import.** *(blocker; nothing else can be tested)*
- **Files:** `engines/bank_parsers/yes_bank_statement_parser.py`
- **Change:** move `from engines.statement_parser import _extract_reference_no, _append_issue, _guess_fd_category` (line 19) **inside** the functions that use it, matching the pattern already used at `sbi_statement_parser.py:140`. Better still, extract those three helpers into a new `engines/parser_utils.py` that both modules import, and remove the cycle entirely.
- **Accept:** `python -c "import engines.statement_parser"` succeeds from a clean interpreter, and the Statement Import screen opens.

**Task 0.2 — Add a dependency check on startup.**
- **Files:** `main.py`
- **Change:** verify `pdfplumber`, `pandas`, `openpyxl`, `pypdf`, `dateutil` are importable and show a clear dialog naming what to `pip install` if not.
- **Accept:** running with a missing dependency shows a readable message, not a traceback.

**Task 0.3 — Centralise table creation.**
- **Files:** `core/database.py`, `models/form26as.py`, `models/income_source.py`, `models/ais_tis_import.py`, `models/income_expectation.py`
- **Change:** move every `CREATE TABLE` into `initialise_database()`; delete the ad-hoc creators.
- **Accept:** deleting `data/financial.db` and starting the app creates all tables; `grep -rn "CREATE TABLE" models/` returns nothing.

**Task 0.4 — Correct `config.py`.**
- **Change:** `FD_TDS_FORM_NAME = "Form 15G"`; add `FD_TDS_FORM_NAME_SENIOR = "Form 15H"` and `FD_TDS_THRESHOLD_SENIOR = 100_000`.
- **Accept:** no occurrence of "Form 121" remains in the repo.

**Task 0.5 — Build the regression harness.** *(everything after this depends on it)*
- **Files:** new `tests/fixtures/` and `tests/test_real_documents.py`
- **Change:** add tests that parse the four statements and the three tax PDFs and assert against the known-correct figures in §2 and §3.3. Passwords: AIS/TIS `azipt9702h08032004`, Equitas statement `0803PRA` — read them from an environment variable or a local untracked file, **never commit them**.
- **Accept:** the suite runs and currently **fails** with the deltas listed in §2 — that failure is the baseline.

> ### ⚠ Do Task 0.6 first — real credentials are already committed to git
>
> **Task 0.6 — Remove personal data from version control.** *(urgent; do before any push)*
>
> `git ls-files data/PersonalData/` confirms these files are **tracked and committed**:
>
> ```
> data/PersonalData/Pranav/26AS.pdf          <- PAN, address, all TDS detail
> data/PersonalData/Pranav/AIS.pdf           <- PAN, partial Aadhaar, 65 deposit a/c numbers
> data/PersonalData/Pranav/TIS.pdf
> data/PersonalData/Pranav/Data 26-27.xlsx
> data/PersonalData/Pranav/Statement/*.pdf   <- 4 full bank statements
> data/PersonalData/Pranav/password.txt      <- AIS/TIS and statement passwords in cleartext
> ```
>
> `.gitignore` has `data/*.pdf`, which does **not** match a subdirectory, so nothing here is excluded.
> `git check-ignore data/PersonalData/Pranav/password.txt` returns "not ignored".
>
> - **Change:** add `data/PersonalData/` to `.gitignore`; `git rm --cached -r data/PersonalData/`;
>   keep the files on disk as the regression fixtures. Because they are already in history,
>   also purge them (`git filter-repo --path data/PersonalData --invert-paths`, or BFG) and,
>   if this repo was ever pushed anywhere, **rotate the AIS/TIS and statement passwords**.
> - **Accept:** `git check-ignore data/PersonalData/Pranav/password.txt` succeeds;
>   `git log --all --name-only -- data/PersonalData/` returns nothing; the files still exist locally.

### Phase 1 — Statement parsing rebuilt

**Task 1.1 — Coordinate-based extraction.**
- **Files:** new `engines/statement/` package (§5.1)
- **Change:** use `page.extract_words()`; cluster into rows by `top`; detect the header row; derive per-column x-ranges; assign words by x-midpoint.
- **Accept:** for each of the four statements, every parsed row's amount comes from an identified Debit or Credit column.

**Task 1.2 — Direction from columns.**
- **Change:** Debit/Withdrawal column → `Expense`; Credit/Deposit column → `Income`. Use keywords for category only. Remove `_infer_txn_type_from_desc` from the direction path.
- **Accept:** the §2.2 harness reports **0 direction errors** on all four statements (was 27–59%).

**Task 1.3 — Balance-walk validation.**
- **Change:** after parsing, assert `balance[n] − balance[n−1] == ±amount[n]`; detect and normalise statement ordering first; emit a confidence score.
- **Accept:** all four statements validate ≥99%; IDFC's parsed totals match its printed Total Debit ₹4,80,013.35 and Total Credit ₹4,67,264.82.

**Task 1.4 — Preserve narration; extract identifiers additively.**
- **Change:** stop stripping `\d{10,}` from the description. Keep `description_raw`. Add `deposit_account_no` to `Transactions`, populated from patterns such as `4522030015435122/1`, `4483130330001450`, `FD300014105382`.
- **Accept:** the Ujjivan row retains `4483130330001450` and populates `deposit_account_no`; no description contains a bank footer or page header.

**Task 1.5 — Multi-line assembly.**
- **Change:** merge continuation rows per column using x-ranges, so Jana's three-line records reassemble correctly.
- **Accept:** Jana yields `CASA CREDIT INTEREST CAPITALIZED` as one description with reference `CHBATCH4522010044796705C260331`; no description mixes two transactions' references.

**Task 1.6 — Bank profiles as data.**
- **Files:** new `engines/statement/profiles/{jana,ujjivan,equitas,idfc,hdfc,yes,sbi}.yaml`
- **Change:** move column synonyms, date formats, row ordering, narration vocabulary (§5.2) and FD conventions into profiles. Keep a generic fallback profile.
- **Accept:** adding a bank requires only a new YAML file; all four statements parse via profiles.

**Task 1.7 — Fix FD categorisation.**
- **Change:** ordered longest-match-first rules from §5.2.
- **Accept:** Jana `INT AUTO REDEEM` → **FD Interest** (not Maturity); Ujjivan `Closure Proceeds` → FD Maturity; Equitas `INITIAL PAYIN` → FD Principal; Jana `CREDIT INTEREST CAPITALISED` → Savings Interest.

### Phase 2 — Tax document import

**Task 2.1 — Rewrite the 26AS parser.**
- **Files:** new `engines/taxdocs/form26as.py`; delete `engines/form26as_parser.py`
- **Change:** table extraction; handle `PART-I` … `PART-X`; parse `dd-MMM-yyyy`; net reversal entries (Remarks `B`/`G`, negative amounts); treat the deductor header row as authoritative; **parse Part II (15G/15H)** separately; capture Part VII refunds; record booking status.
- **Accept:** total TDS = **₹13,367**; four deductors (Enlightvision ₹1,05,069/₹10,508; Jana ₹2,859; Equitas ₹19,397/₹0; and Part II Jana ₹90,745, Equitas ₹53,311, Ujjivan ₹79,077); no section `194B`; name = `PRANAV ARVINDBHAI TANK`.

**Task 2.2 — Rewrite the AIS parser.**
- **Files:** new `engines/taxdocs/ais.py`
- **Change:** parse Part B1 (`TDS-*`) **and** Part B2 (`SFT-*`); **skip every `Inactive` row**; validate against the summary `COUNT`; capture per-account detail from `SFT-016(SB)` and `SFT-016(TD)`; keep an explicit non-income code list (`SFT-005`, …); map `TDS-194J` to a `business_receipts` bucket.
- **Accept:** FD interest **₹2,56,642**, savings **₹46,183**, dividend **₹2,655**, business receipts **₹1,05,069**, TDS **₹13,367**; SFT-005 ₹13,00,000 flagged non-income; per-account rows recovered for all 65 deposit accounts.

**Task 2.3 — Rewrite the TIS parser.**
- **Files:** new `engines/taxdocs/tis.py`
- **Change:** read the five category totals from the **"Accepted by taxpayer"** column on page 1 only; do not re-add the annexure; exclude non-income categories.
- **Accept:** exactly `{dividend: 2,655, savings: 46,183, deposits: 2,56,642, business: 1,05,069}` and `purchase_of_time_deposits: 13,00,000` flagged non-income. **No value of ₹27,05,069 or ₹3,49,008 anywhere.**

**Task 2.4 — Merge into one FY position.**
- **Files:** new `engines/taxdocs/merge.py`
- **Change:** income from TIS, credit from 26AS, detail from AIS; per-category variance against the app's own figures; never sum AIS B1 and B2.
- **Accept:** produces the §3.3 table and a refund of **₹13,367**.

**Task 2.5 — Match AIS deposit accounts to FD records.**
- **Change:** join `AIS SFT-016(TD)` account numbers to `FixedDeposit.deposit_account_no`, normalising `/`, an `FD` prefix, and a trailing check digit (§3.2).
- **Accept:** Jana `4522030015435122/1` matches AIS `45220300154351221`; unmatched AIS accounts are listed as "FD not in app".

**Task 2.6 — Delete the reconciliation feature.**
- **Files:** delete `ui/reconciliation_screen.py`, `engines/reconciliation_engine.py`; remove `("26AS vs AIS", "reconciliation")` from `_NAV_ITEMS`.
- **Accept:** no import of either module remains; navigation renders without a gap.

### Phase 3 — Interest engines

**Task 3.1 — One correct FD accrual function.**
- **Files:** `engines/interest_engine.py`
- **Change:** implement `fd_interest_accrued_to()` per §4.5 (simple below 183 days; quarterly compounding plus simple broken-period above); implement `fd_interest_for_fy()` by difference; **delete** `calculate_fd_interest_for_fy` and `calculate_fd_interest_quarterly_for_fy`.
- **Accept:** the 501-day FD splits **789 / 8,279 / 2,414** across FY 2025-26 / 26-27 / 27-28, matching the spreadsheet exactly.

**Task 3.2 — Make Bank Style real.**
- **Change:** remove the `tenure_days > 0` short-circuit; implement the spreadsheet's U–Z method; add `BankFDConvention.rounding_adjustment` to replace the hard-coded `− 4`.
- **Accept:** the 201-day FD returns **4,496** bank-style and **4,455** formula (currently both return 4,458.54).

**Task 3.3 — Savings interest, daily-product basis.**
- **Change:** rewrite `calculate_savings_interest_for_fy` to reconstruct the daily closing balance from `balance_after`, carrying the last balance across quiet days; accumulate per quarter; **call it** from statement import and from the FY refresh. Delete `_average_monthly_balance`.
- **Accept:** the function is invoked from at least one non-test caller; Jana savings interest for FY 2025-26 lands within a few rupees of the AIS figure **₹4,010**, against credits of ₹2,495 (01-Oct) and ₹1,504 (01-Jan).

**Task 3.4 — Correct the TDS threshold check.**
- **Change:** use `FD_TDS_THRESHOLD_SENIOR` when the person is 60+ at any point in the FY; report **Form 15G / 15H** by age; suppress the warning where a 15G is already recorded as filed.
- **Accept:** Jana/Equitas/Ujjivan show "15G on file" rather than a TDS warning for FY 2025-26.

### Phase 4 — Tax engine

**Task 4.1 — FY-driven slabs and parameters.**
- **Change:** create and seed `TaxSlabConfig` / `TaxParams` for FY 2025-26 and FY 2026-27 per §4.1; read them by FY; delete the hard-coded constants.
- **Accept:** taxable income ₹15,00,000 in FY 2026-27 gives slab tax **₹1,05,000** (₹0 on the first ₹4L + ₹20,000 on ₹4–8L + ₹40,000 on ₹8–12L + ₹45,000 on ₹12–15L), plus 4% cess = **₹1,09,200**. The current code returns **₹1,50,000** (verified by running `calculate_tax_by_slabs(1500000, NEW_REGIME_SLABS)`).
- **Also accept:** a salaried gross of **₹12,75,000** — the headline tax-free figure for this regime — must come out at **₹0**. The current code charges **₹93,600** (verified: it computes taxable ₹12,00,000, base tax ₹90,000, and applies **no** 87A rebate because its threshold is still ₹7,00,000).

**Task 4.2 — 87A, marginal relief, surcharge, cess.**
- **Change:** 87A = min(tax on normal income, ₹60,000) when non-special income ≤ ₹12,00,000; marginal relief above ₹12,00,000; exclude 111A/112/112A from the rebate; surcharge with its own marginal relief; 4% cess last.
- **Accept:** taxable ₹12,00,000 → nil tax; ₹12,10,000 → about ₹10,000 (marginal relief); ₹12,00,000 including ₹2,00,000 of 111A gains → rebate applies only to the non-special part.

**Task 4.3 — Standard deduction only against salary.**
- **Change:** `standard_deduction = min(75_000, salary_income + pension_income)`.
- **Accept:** the owner's FY 2025-26 position yields the §3.3 table — total income ₹3,58,015, tax nil, refund **₹13,367** — with **no** ₹75,000 deduction applied.

**Task 4.4 — Remove the old regime.**
- **Change:** delete old-regime calculation, fields and comparison from the engine and `ui/tax_screen.py`; keep the `*_old` DB columns for historical rows.
- **Accept:** no old-regime input remains in the UI; existing saved profiles still load.

**Task 4.5 — Wire every input through.**
- **Change:** extend `calculate_and_save_tax` to accept business/presumptive income, capital gains at their special rates, and house property; make `_update_gross()` and the engine share one function.
- **Accept:** entering ₹52,535 of 44ADA presumptive income changes the computed tax; the on-screen "Gross Income" always equals the gross the engine used.

**Task 4.6 — Advance tax corrections.**
- **Change:** accumulate payments per instalment; 234C safe harbours 12% / 36% / 75% / 100%; 1 month of interest on the 15-March shortfall; implement the **44ADA single-instalment** rule; exempt resident seniors without business income.
- **Accept:** a 44ADA taxpayer shows one instalment due 15 March, not four overdue ones.

**Task 4.7 — ITR form guidance.**
- **Change:** derive the suggested ITR form from the income mix (§3.2).
- **Accept:** the owner's profile suggests **ITR-4 (44ADA)** or ITR-3, never ITR-1.

### Phase 5 — Data model

**Task 5.1 — Joint accounts and HUF.** Add `AccountHolder`, `Person.entity_type`, `Person.date_of_birth`; migrate existing `BankAccount.person_id` rows into `AccountHolder` as primary; update the account dialog for multiple holders.
**Accept:** the spreadsheet's `B+P+Pranav` account can be represented, and HUF appears as a separate tax entity.

**Task 5.2 — Deposit account numbers.** Add the columns and index from §5.4; backfill from existing descriptions.
**Accept:** Task 2.5's matching works on existing data.

**Task 5.3 — Per-bank FD conventions.** Add `BankFDConvention`; seed Jana, Ujjivan, Equitas, IDFC.
**Accept:** Task 3.2 reads its calibration from this table.

### Phase 6 — UI

**Task 6.1 — "Income & Expectations" screen** per §6.2 (five panels).
**Accept:** with the spreadsheet's data loaded, the monthly chart reproduces the Salary sheet including Pranav's Aug step from ₹21,500 to ₹25,000.

**Task 6.2 — "Tax Documents" screen** per §6.3, replacing AIS/TIS Import.
**Accept:** importing the three real PDFs produces the §6.3 comparison table and the per-FD drill-down.

**Task 6.3 — Tax screen rebuild** per §6.4 (new regime only, waterfall).
**Accept:** every step of the computation is visible and reproduces §3.3.

**Task 6.4 — Statement import confidence summary** per §6.5.
**Accept:** importing a deliberately corrupted statement is blocked with a reason.

**Task 6.5 — Navigation and empty states** per §6.1.
**Accept:** every screen has a useful empty state; no dead nav entries.

### Phase 7 — Security and honesty

**Task 7.1 — Resolve the encryption claim.** Either integrate SQLCipher (`sqlcipher3`) keyed from the master password, or amend the README to state that field-level encryption protects stored passwords while the database file itself is not encrypted. **Do not leave the current claim standing.**
**Accept:** the README matches what the code does.

**Task 7.2 — (moved)** Protecting the sample data is now **Task 0.6** in Phase 0; the files are already committed, so it cannot wait until Phase 7.

---

## 8. Priority order if time is limited

0. **Task 0.6** — real PAN, account numbers and cleartext passwords are committed to git.
1. **Task 0.1** — the app's statement import is currently dead.
2. **Tasks 1.1–1.3** — direction from columns plus balance validation removes the 27–59% error.
3. **Tasks 2.1–2.3** — correct income and TDS figures; stops ₹26 lakh of phantom income.
4. **Tasks 4.1–4.3** — current slabs and the correct standard-deduction rule.
5. **Tasks 3.1–3.2** — FD interest in the right financial year.
6. **Task 6.2 / 6.1** — the screens the owner asked for.

Everything else is refinement on top of a correct core.

---

## 9. Frontend audit summary (4 Sep 2026)

Method: the real application was rendered offscreen under PyQt6 6.11 with a seeded
database, all 11 screens screenshotted, and theme switching timed. Full detail and the
executable task list are in **[`REBUILD_PLAN.json`](REBUILD_PLAN.json)**.

> **Caveat on the screenshots.** The offscreen platform plugin exposed **zero font
> families**, so Qt fell back to a capitals-only stub face. All text in the captures
> renders uppercase with odd punctuation. That is an artefact of the harness, **not** of
> the app — no typography or letterform conclusions were drawn from those images. Layout,
> spacing, density, colour and widget behaviour are unaffected and were assessed.

| Finding | Measurement |
|---|---|
| **Ghost widgets on the dashboard** | `SummaryPanel.clear_stats()` calls `deleteLater()` without re-parenting, so cleared rows keep painting. Unit test: 3 clear+add cycles leave **3** copies. Visible as overlapping, garbled text in the Bank Accounts panel |
| **WCAG AA contrast: 56 of 140 checks fail (40%)** | Every one of the 10 themes fails ≥4 checks. `TEXT_MUTED` fails in **all 10** (1.51–2.80). `BORDER` vs `SURFACE` fails in **all 10** (1.10–1.45, needs 3.0), so field outlines are nearly invisible |
| **Tooltips unreadable in all 4 dark themes** | QSS sets `background: TEXT_PRIMARY; color: #FFFFFF`; dark themes' `TEXT_PRIMARY` is near-white (Nova `#E4E1F0`) → ratio **1.29** |
| **Button labels fail on 6 of 10 themes** | Hard-coded `#FFFFFF` over pastel dark-theme primaries (`#A78BFA` → **2.72**) |
| **Theme switch blocks the UI for ~1.5–1.8 s** | `ThemeManager._deep_refresh()` walks **1,079** live widgets twice. `settings_screen.py:465` shows an "Applying theme…" loader that cannot animate, because the work runs on the same thread |
| **469 inline `setStyleSheet()` calls** | Styling lives outside QSS where Qt cannot re-polish it; each screen hand-maintains bespoke `refresh_theme()` code (`tax_screen.py` re-styles ~11 of its 58) |
| **Parsing freezes the window** | `parse_statement_with_debug`, `parse_ais_pdf_text`, `parse_form26as_pdf` all run on the UI thread. `Loader.run()` (threaded) exists but is used **once**; the AIS screen uses the *blocking* `with Loader(...)` |
| **171 blocking `QMessageBox` popups** | 84 warning + 54 information + 19 question + 14 critical |
| **Floating "AI" button covers the primary action** | `_position_chat_launcher()` pins a 58 px button to the window's bottom-right and `raise_()`s it — directly over "Parse Statement" |
| **11 unlabelled sidebar icons** | Sidebar defaults collapsed at 76 px; only 3 tooltips exist in the whole dashboard, **none on nav**. Icons carry ~96 hard-coded hex colours in `ui/icons.py`, so they never follow the theme |
| **`qfluentwidgets` undeclared** | It is the *primary* icon source in `ui/icons.py` but is absent from `requirements.txt`, so a clean install always silently falls back |
| **No `:focus` style on any button** | Only text inputs show focus. Keyboard navigation is invisible (WCAG 2.4.7) |
| **Nav items are monkey-patched `QWidget`s** | `container.mousePressEvent = lambda …` activates on *press* not release; no button role for assistive tech |
| **Scrollbars are 7 px** | Below the WCAG 2.2 SC 2.5.8 24×24 px target minimum |
| **Redundant screens** | Reports (5 chart tabs) overlaps Overview and the planned Income screen; the 1,152-line chatbot is generic Ollama chat with **no access to financial data** |

Two claims from the first pass are **retracted**: `current_balance` *is* seeded by
`add_account()` (the ₹0 in an early capture was a fault in the test harness, not the
app), and the login failure is more severe than first described (see §2.1).
`engines/balance_engine.py` is nonetheless never called from anywhere, so balances do
not re-derive from imported transactions.

---

## Sources

Tax and banking rules cited in §4 were verified against:

- [Income Tax Slabs FY 2025-26 and FY 2026-27 — ClearTax](https://cleartax.in/c/income-tax-slab-rates)
- [Income Tax Slabs for Tax Year 2026-27 (AY 2027-28) — Bajaj Housing Finance](https://www.bajajhousingfinance.in/income-tax-slab)
- [Section 87A Rebate FY 2025-26 — Tax2win](https://tax2win.in/guide/section-87a)
- [Section 87A Marginal Relief FY 2026-27: the ₹12L cliff and the capital-gains carve-out — CAclubindia](https://www.caclubindia.com/articles/section-87a-marginal-relief-fy-2026-27-the-rs-12l-cliff-the-capital-gains-carve-out-and-6-worked-examples-56062.asp)
- [Section 194A: TDS on Interest Other than Interest on Securities — ClearTax](https://cleartax.in/s/section-194a-tds-on-interest-other-than-interest-on-securities)
- [Section 44ADA – Presumptive Tax Scheme for Professionals — ClearTax](https://cleartax.in/s/section-44ada)
- [File ITR-4 (Sugam) Online FAQs — Income Tax Department](https://www.incometax.gov.in/iec/foportal/help/e-filing-itr4-form-sugam-faq)
- [Form 26AS vs AIS vs TIS: Pre-Filing Reconciliation Guide — Tax Garden](https://taxgarden.in/blog/ais-vs-form-26as-vs-tis-itr-prep-guide-ay-2026-27)
- [AIS vs TIS vs Form 26AS: What to Check Before Filing ITR — Finnovate](https://www.finnovate.in/learn/blog/ais-vs-tis-vs-form-26as-before-filing-itr)
- [Interest calculation on Deposits — ICICI Bank (PDF)](https://www.icici.bank.in/content/dam/icicibank/managed-assets/docs/personal/general-links/interest-calculation-of-deposit.pdf)
- [FD Interest Calculation: Simple vs Compound — IndusInd Bank](https://www.indusind.bank.in/iblogs/fixed-deposit/fixed-deposit-interest-calculation-simple-vs-compound-interest/)
- [RBI circular on payment of interest on savings accounts on a daily product basis — TaxGuru](https://taxguru.in/rbi/rbi-circular-on-payment-of-interest-on-savings-bank-account-on-a-daily-product-basis-ucbs.html)

---

# Appendix Z — Open issues found during execution

Recorded as they were hit, so the plan stays the source of truth and these get
decided deliberately rather than absorbed silently. Nothing here is fixed.

## Z1. Gradient buttons fail contrast in every theme (from T037)
The token contract's 17 required pairs cover flat `PRIMARY`, but every filled
button is painted with a GRADIENT, and each gradient starts at a light
300/400-level stop. White label contrast against the light end:
  Aurora  primary 4.47 · success 1.92 · danger 2.69 · warning 1.67 · info 1.81
  Nova    primary 1.85 · success 1.52 · danger 1.89 · warning 1.25 · info 1.45
  Midnight primary 2.98 · success 1.52 · danger 1.90 · warning 1.25 · info 1.67
No single text colour clears 4.5 across a stop that spans light to dark, so
this cannot be fixed by choosing a better label colour — the gradient START
stops have to be darkened, or filled buttons have to become flat fills.
DECISION NEEDED: darken every gradient start, or drop gradients on filled
buttons. Either is a visual change beyond what T037 authorised.

## Z2. FOCUS_RING was unsatisfiable as specified (resolved, but by changing themes)
`FOCUS_RING` must clear 3.0 against both SURFACE and PRIMARY. With a near-black
SURFACE and a 400-level pastel PRIMARY that is algebraically impossible: Nova
needed a ring luminance >= 0.1185 and <= 0.0786 simultaneously.
Resolved by darkening Nova's PRIMARY #A78BFA -> #7D54F8 and Midnight Pro's
#818CF8 -> #5563F6, which also fixed M16 (white labels at 2.72 / 2.98).
FLAGGED because it changed two themes' identity colours, which no task asked for.

## Z3. The "56 violations" baseline is pair-set dependent (reconciled, no action)
M14's 56-of-140 is measured over the audit's own 14-pair set. The token
contract's 17-pair set replaces 5 of those pairs (DANGER, SUCCESS, WARNING,
INFO on SURFACE, and BORDER_FOCUS on SURFACE) with *_TEXT and FOCUS_RING
variants, moving exactly 19 failures into a "missing token" bucket:
56 - 19 = 37. Both numbers are correct. Quoting "56" against the new contract
will look like a regression when it is not.

## Z4. Jana's direction bug is not what M3 diagnosed (resolved)
M3 attributes the direction errors to the two-date branch defaulting to
"Expense". True for three banks. Jana is different: it populates BOTH the
Deposits and Withdrawal columns on every row, with `0.00` in the unused one.
So "whichever column is present" picks debit on every Jana row, and "reject
rows where both are present" drops all 65. The rule has to be that the
non-zero column decides. Worth knowing before writing any future parser.

## Z5. Jana's measured error rate is 36.0%, not 46.9% (no action)
M3 records 46.9%. Measured today: 25 balance-tied rows, 9 wrong = 36.0%.
Equitas, IDFC and Ujjivan reproduce to 0.1%, and Jana's row count matches
exactly at 65, so this is a methodology difference in the original harness,
not codebase drift.

## Z6. IDFC's header is stacked, and its control-totals row is a near-miss (resolved)
IDFC's transaction header spans two physical lines (`Transaction | Value Date |
Particulars | Cheque | Debit | Credit | Balance` then `Date | No`). Separately
its page-1 `Opening Balance | Total Debit | Total Credit | Closing Balance` row
scores 3 against the same synonym table. A match threshold below 4 silently
picks the control-totals row as the header. Do not lower it.

## Z7. Statement Import depended on the deleted chatbot module (resolved)
T009 says to delete ui/chatbot_screen.py. It also held OllamaModelStartWorker,
imported by ui/statement_import_screen_modern.py — a screen being KEPT. Moved
to ui/ollama_worker.py before deleting. T009 did not mention this.

## Z8. Git history still contains the secrets (OPEN — needs a human)
T001's untracking is done; the history purge is not, and requires explicit
approval because it is irreversible and breaks every clone. If this repo was
ever pushed anywhere, the AIS/TIS and Equitas passwords must be rotated too.

## Z9. T014 continuation-row merging is DISABLED (OPEN)
Jana prints one logical transaction across three physical rows with the amounts
row in the middle, so its narration and reference arrive split:
description `CREDIT INTEREST CAPITALISED` instead of
`CASA CREDIT INTEREST CAPITALIZED`, and `reference_no` None instead of
`CHBATCH4522010044796705C260331`.
Three attempts to enable the merge all destroyed real transactions — row counts
fell from 38/376/65/27 to 28/344/57/25 and IDFC's parsed credits came up
102,324.00 short against its own printed control totals. Each attempt was
reverted. The merge code is present but switched off, and the anchor-count
invariant (anchors in == transactions out) is the check that must hold before
it can be turned on.
IMPACT: narration quality on Jana only. Direction, amounts, balances and totals
are all correct and verified. No financial figure is affected.
Guarded by tests/test_statement_package.py, which pins the row counts, zero
direction errors, and IDFC's control totals so this cannot regress unnoticed.

## Z10. deposit_account_no is only populated for Ujjivan (OPEN)
21 of 27 Ujjivan rows carry it. Equitas, IDFC and Jana yield 0, because their
narrations reference deposits in formats the current extractor does not match
(Equitas prints `FD300014105382`, Jana `4522030015435122/1`). The
normalisation rules and `deposit_account_matches()` are implemented and unit-
correct; what is missing is the narration patterns that find the number in the
first place for those three banks.
IMPACT: FD-to-statement linking works for Ujjivan only.

## Z11. T018's "TDS 13,367" is not obtainable from AIS (plan error)
T018 requires the AIS parser to produce tds = 13,367. It cannot: that figure
is 26AS's, not AIS's.
Measured from AIS.pdf, all 67 detail rows across all three detail tables:
    TDS DEDUCTED total   12,073   (Active 6,246 + Inactive 5,827)
    TDS DEPOSITED total  12,073
The strings "13,367", "10,508" and "2,859" do not appear anywhere in AIS.pdf.
They are 26AS figures — T017's own acceptance lists them as deductor rows
(Enlightvision 10,508 + Jana 2,859 = 13,367).
The plan's suggested fix ("skip every Inactive row") reaches 6,246, which is
further from the target than summing everything.
RESOLUTION TAKEN: the AIS parser reports what AIS actually says (12,073) and
26AS remains the authority on tax credit. The 1,294 difference between the two
documents is a real reconciliation finding about the owner's data, not a
parser bug, and the Tax Documents screen should surface it rather than hide it.

## Z12. 26AS detail-row count is 49, not the "200+" M8 implies (no action)
M8 says the document has "200+ detail rows" against 6 recovered. The rewritten
parser returns 49 PART-I detail records. The difference is that the raw page
count includes PART-II detail rows (now correctly held separately), the legend
tables, and matched reversal pairs. Every acceptance figure that matters is
exact: total TDS 13,367, PART-II 2,23,133, deductor totals, dates, no 194B.
The row count itself was never an acceptance criterion.

## Z13. Marginal relief at 12,10,000 yields 10,400, not 10,000 (no action)
T028 expects "approximately 10,000". Marginal relief caps the TAX at the 10,000
of income earned above the 12,00,000 threshold; the 4% cess then applies on top,
giving 10,400. That ordering is what the plan itself specifies (cess last, on
tax - rebate + surcharge), so 10,400 is correct and the plan's figure was the
pre-cess number.

## Z14. Tests were running against the owner's real database (fixed)
config.DB_PATH defaults to data/financial.db, and nothing in the test suite
redirected it, so any test touching the database was operating on the owner's
real financial data. tests/conftest.py now redirects the whole session to a
temp database, seeds it, and asserts DB_PATH does not resolve to
data/financial.db. Verified by mtime/size before and after a full run.

## Z15. deposit_account_no had no migration (fixed)
T013 added the column to the CREATE TABLE statements only. CREATE TABLE IF NOT
EXISTS is a no-op on an existing database, so the column was never added there,
and the new index on it made initialise_database() raise
"no such column: deposit_account_no" — on a FRESH database everything worked,
so this only broke machines that already had data. The owner's. Guarded
ALTER TABLE migrations now run before the index is created.

## Z16. A FOURTH defect in the owner's workbook — inconsistent FY boundaries
domain_spec.owner_spreadsheet_model lists three known workbook defects. There is
a fourth, and it changes a tax figure.
The FY boundaries live in cells Q66 and Q67 of the "Bank" sheet:
    Q66 = 2026-04-01   (the START of FY2026-27)
    Q67 = 2027-03-31   (the END of FY2026-27)
Columns M and N are plain date differences from those, so the first boundary is
one day later than it should be. That single day is the entire reason the sheet
shows 789 of FY2025-26 interest on the 501-day FD: with a correct 31 March
boundary the count is 35 days, not 36, and the accrual is 767.

T023's acceptance asks for 789 / 8,279 / 2,414 "matching the owner's spreadsheet
exactly". The app instead uses 31 March consistently for every boundary and
produces 767 / 8,301 / 2,414, which still re-adds to the 11,482 maturity total
exactly. Reproducing 789 would mean reproducing the workbook's off-by-one.
DECISION NEEDED: keep the app correct (current behaviour), or make the app
bug-compatible with the spreadsheet so the owner's own cross-checks tie out.
Recommendation: keep the app correct and fix the workbook.
