# Project Handoff & Testing Guide

**Read this file first and read it fully. It is written to be sufficient on its own** —
you should not need to read source files to understand what this project is, what
state it is in, what has been verified, what is broken, or how to test it.

**Last updated:** 2026-09-23.
**Audience:** an AI agent (or human) picking this project up with zero prior context.

---

## 1. What this app is

A **personal financial manager** for one real user (Pranav). Offline-first, local
SQLite, PySide6 desktop UI on Windows.

Its purpose is not bookkeeping. It is **tax planning**: predict this financial
year's taxable income early enough to *act* — to stay under the ₹12,00,000 rebate
limit and to prevent TDS from being deducted at source.

### The single most important concept in this codebase

There are **two kinds of data and they must never be conflated**:

| | **OUR DATA** | **ITR-SIDE DATA** |
|---|---|---|
| What | Bank statements, Fixed Deposits, Income Expectations | 26AS, AIS, TIS |
| Source | The user's own records, imported by this app | The Income Tax department |
| Mutable? | Yes — this is our model of reality | **No. Extract and accept.** |
| Purpose | **PREDICT** the current FY so the user can act | **COMPARE** against our prediction |

**Our predicted figure being LOWER than AIS is EXPECTED, not a bug.** Most FD
interest is credited *inside the FD* and never appears as a savings-account
transaction, so our statement-derived data legitimately under-reports.
In any comparison UI the words **"gap", "mismatch" and "error" must not appear.**
Use neutral framing: *"Our data under-reports this bank."*

The owner's own words: *"our fd data and statement data and our expectation data
is our data which will help us to predict these current year income so i can
prevent tds deductions and keep in 12L limit. but 26AS, AIS and TIS are real data
coming from ITR side, we can not change it."*

---

## 2. THE TRAP THAT WILL BITE YOU — read before touching income figures

The `Transactions` table books **₹64,95,691** as Income for FY 2025-26.
**Almost none of it is taxable income.**

| category | rows | amount | taxable? |
|---|---|---|---|
| `Other Income` | 166 | ₹52,58,725 | **NO** — the user's own transfers between his 4 banks |
| `FD Maturity` | 11 | ₹11,41,366 | **NO** — principal returning |
| `FD Interest` | 9 | ₹91,590 | **YES** |
| `Savings Interest` | 3 | ₹4,001 | **YES** |

**Genuinely taxable: ₹95,591.**

- `is_internal_transfer` is **0 on all 506 rows** — it is useless as a filter.
- You **must** classify by the `category` column.
- A naive `SUM(amount) WHERE transaction_type='Income'` reports ₹64.9 lakh against
  a ₹12 lakh limit and makes any prediction screen worse than useless.

`tools/test_prediction_engine.py` has a permanent assertion guarding this
(`non_taxable > 5_000_000` and `taxable < 200_000`). **Do not weaken it.**

---

## 3. Current state of the real database

`data/financial.db` is **REAL USER DATA**, not a fixture. It is gitignored
(`.gitignore:2` → `data/*.db`). Back it up before any writing operation.

| table | rows | note |
|---|---|---|
| Person | 1 | person_id 1, PAN and DOB set |
| BankAccount | 4 | `Test Bank` deleted 2026-09-23 — see below |
| Transactions | 506 | imported from the 4 real statements; categories backfilled 2026-09-23 |
| FixedDeposit | 19 | **all 19 are `Pending Details`** — no rate, no maturity (the one known FD lived on the deleted Test Bank) |
| IncomeExpectation | 0 | never populated |
| Form26ASImport / Form26ASRecord | 1 / 158 | 26AS imported 2026-09-21 (FY 2025-26, total TDS ₹13,367) |
| AISTISImport | 2 | AIS + TIS imported 2026-09-21 (`tools/taxdoc_import.py` or the Tax Documents screen) |
| Bank | 0 | |

Accounts: `38` Jana Small Finance Bank, `39` IDFC FIRST Bank,
`40` Ujjivan Small Finance Bank, `41` Equitas Small Finance Bank.
`1` Test Bank (leftover junk, owned the only "known"-rate FD and all 6
`FDInterestRecord` rows) was deleted 2026-09-23 via `tools/delete_account.py`
after `models/bank_account.py::delete_account` was fixed to detach/cascade
`AccountHolder`, `IncomeExpectation`, `StatementImportLog` and transaction FK
references first (it previously raised `IntegrityError` on any account with an
`AccountHolder` row, since `PRAGMA foreign_keys=ON`).

### Income reclassification (2026-09-23)
`tools/backfill_transactions.py` recategorised 39 "Other Income" rows using
`_guess_fd_category` plus explicit rules for known counterparties, and flagged
3 rows `is_internal_transfer=1` via a new `find_internal_transfers()` in
`models/transaction.py`. Real, taxable income sources that were sitting under
the non-taxable "Other Income" bucket are now correctly categorised as
**Commission Income** (Kevision Systems, Lotus Investment — note the source
description has a stray mid-word space, `"LOTUSINVESTM ENT"`), **Professional
Fees** (Enlightvision, matches the 26AS 194JB deductor) and **Salary** (Prasad
M). `TAXABLE_INCOME_CATEGORIES` in `engines/prediction_engine.py` was extended
with these three category names.

**Taxable income moved from ₹95,591 to ₹2,54,784** (FY 2025-26, as of
2026-03-31). This is a genuine change to the user's real tax figures, not a
bug — reviewed and approved by the owner before running. The `tools/test_prediction_engine.py`
CRITICAL GUARD threshold was correspondingly raised from `< 200_000` to
`< 500_000` (still far below the ~₹64.9L naive-full-sum bug signature it
exists to catch).

**`is_internal_transfer` pairing is deliberately conservative.** A candidate
debit/credit pair is only accepted if it is the *unique* match for that
amount within a ±2-day window, across every account — not just cross-account
candidates. An early version of this check excluded same-account candidates
before counting, which caused a real false pair: a 2025-05-03 ₹2,00,000 cheque
paid to a third party ("SATELLI") got linked to a ₹2,00,000 NEFT credit *from
the user's mother* (a gift, not a transfer) — see §9. Caught before it reached
the real DB by independently querying the DB rather than trusting the
implementer's report. Fixed by counting all debits/credits of that amount+date
regardless of account when checking for ambiguity.

The Transactions screen's "Transfer" type filter now actually works — it maps
to `is_internal_transfer=1` in `_fetch_and_display()` rather than a literal
`transaction_type='Transfer'` (which never matched anything, since the schema
only has `Income`/`Expense`).

**FD rates are the biggest data gap.** 19 of 20 FDs came from statements carrying
only principal + start date. They are projected at a **7.5% default**
(`DEFAULT_FD_RATE` in `engines/prediction_engine.py`) — the owner's explicit
choice — and every derived figure is flagged `is_estimated`. Entering the real
rates is the highest-value accuracy improvement available.

---

## 4. The real documents

All under `data/PersonalData/Pranav/` — **gitignored** (`.gitignore:15`). Never
commit them, never print the PAN or a full account number into a committed file.

| file | state | extraction |
|---|---|---|
| `Statement/Jana - Pranav.pdf` | plain | 65 txns, confidence 1.000 |
| `Statement/IDFC.pdf` | plain | 376 txns, confidence 1.000 |
| `Statement/Ujjivan - Pranav.pdf` | plain | 27 txns, confidence 1.000 |
| `Statement/Equitas.pdf` | **encrypted** | 38 txns |
| `26AS.pdf` | plain | 86 Part-I + 72 Part-II records |
| `AIS.pdf`, `TIS.pdf` | **encrypted** | see below |

**Passwords are already on disk** at `data/PersonalData/Pranav/password.txt`
(gitignored): one line for AIS/TIS, one for Equitas. The PAN is also inside the
26AS. Read them at runtime (`read_ais_tis_password` in `tools/taxdoc_import.py`, or
`$AIS_TIS_PASSWORD`). **Do not ask the user for these. Do not hardcode or write them
into any committed file, including this guide.**

### Verified ground truth — 26AS
Measured from the raw PDF, independently of the parser:
- 6 deductor summary rows; **211 line items** (194A ×206, 194JB ×4, 194JA ×1)
- flags: 177 normal, **25 `B` + 9 `G` reversals** (negative — must be netted)
- **Net TDS ₹13,367.00**, net gross ₹3,50,458
- Per deductor: Enlightvision ₹1,05,069/₹10,508 · Jana ₹2,859/₹2,859 ·
  Equitas ₹19,397/₹0 · Jana 15G/H ₹90,745/₹0 · Equitas 15G/H ₹53,311/₹0 ·
  Ujjivan 15G/H ₹79,077/₹0
- 194A = bank interest. **194JB/194JA = professional fees, NOT interest.**

### Verified — AIS / TIS (they agree with each other)
Dividend ₹2,655 · Savings interest ₹46,183 · **FD interest ₹2,56,642** ·
total interest ₹3,02,825 · business receipts ₹1,05,069 · AIS TDS ₹12,073.

### The interest comparison (this is the expected shape, not a defect)
| bank | 26AS 194A incl Part-II | our transactions |
|---|---|---|
| Equitas | ₹54,816 | ₹92,257 |
| Jana | ₹34,469 | ₹4,001 |
| **Ujjivan** | **₹79,077** | **₹0** |
| IDFC | — | ₹244 |

Ujjivan showing ₹0 on our side is the clearest illustration of section 1: its
interest is credited inside FDs and never lands in a statement row.
**TDS never appears in transactions at all** — it is deducted before credit, so it
can only come from the tax documents. That is correct behaviour, not a bug.

---

## 5. How to test — read this before writing any test

### 5.1 The environment
- Repo `D:\Pranav\app`, branch `main`. Always run from the repo root.
- Python: `.venv\Scripts\python.exe`. **PySide6 6.11.2** (migrated from PyQt6 this
  session — see §7).
- Windows, display scaling **125%** (`devicePixelRatio == 1.25`). Never hardcode
  1.25; read it live.

### 5.2 Non-negotiable rules
1. **UTF-8 stdout.** A rupee sign kills a cp1252 Windows console mid-run. Every
   script must start with:
   ```python
   for _s in (sys.stdout, sys.stderr):
       try: _s.reconfigure(encoding="utf-8", errors="replace")
       except Exception: pass
   ```
   This has bitten three times.
2. **Never pipe a long run through `| tail`** — the pipe buffers everything and you
   see nothing until it exits. Redirect to a file and read the file.
3. **Real DB safety.** Back up to the scratchpad before any write. Any test that
   creates rows must delete them in an always-runs path. Prefix test rows `RUIH_`.
4. **Never commit** `data/PersonalData/**` or `data/financial.db`.
5. **Report real output.** A failure is a finding. Fabricating a pass wastes more
   time than the bug does — this happened repeatedly this session (§9).

### 5.3 Real-UI testing (the harness)
`tools/real_ui_test_harness.py` → `RealUIHarness`. Launches a **real, visible,
maximized** window. Never `QT_QPA_PLATFORM=offscreen` for UI behaviour tests.

API: `launch(factory, maximized=True)`, `click(root, "Accessible Name")`,
`type_into(...)`, `key(...)`, `find(root, name)`, `find_dialog(cls, title, timeout)`,
`scroll_into_view(w)`, `settle(sec)`, `shot(name)`, `to_physical(pt)`,
`click_via_os(w)`, `find_via_uia(...)`.

**Hard-won gotchas — each cost hours:**
- **§A DPI.** Qt geometry is logical px; `pyautogui` is physical px. Multiply by
  `devicePixelRatio` or clicks land up-and-left. `to_physical()` does it.
- **§B Window off-screen.** A fixed `resize(1600,900)` becomes 2000×1125 physical
  at 125% and hangs off a 1920×1080 screen; Qt still returns valid coordinates.
  **Launch maximized.**
- **§C Focus stealing.** Windows silently refuses `SetForegroundWindow` for
  script-launched windows. The harness forces it via pywin32 and warns — **heed
  the warning.**
- **§D Scroll.** `mapToGlobal()` returns coordinates for widgets scrolled out of
  view. Clicking hits whatever is actually there. The harness calls
  `ensureWidgetVisible()` first.
- **§E Repaint lag.** Script-driven `processEvents()` lags the compositor by
  1-2s. **A screenshot alone is never proof** — always cross-check widget state
  (`label.text()`, `.isChecked()`, a DB query).
- **§F `QTest.mouseDClick` does not fire `doubleClicked`** at all, on any platform.
  Any past "verified" double-click test using it tested nothing. Use
  `pyautogui.doubleClick()` or the keyboard equivalent, and say which.
- **§G Modal `.exec()` blocks `QTest.mouseClick`.** The click call sits on the
  stack inside the modal's nested event loop. **Pre-arm
  `QTimer.singleShot(0, cb)` BEFORE clicking anything that opens a modal.**
  `PersonDialog`, `BankDialog`, `AccountDialog` are all `.exec()`-modal.
- **§H Blind coordinate clicks misclick.** Prefer accessible-name lookup + QTest
  over OS coordinates; `click_via_os()` is the opt-in escape hatch.
- **§I PySide6 `findChildren()` takes ONE type**, not a tuple. PyQt6 allowed the
  tuple form.

### 5.4 Testing colour / theme problems
**Grep cannot find them.** Twice this session a file was grep-clean of hex
literals and still rendered wrong. The cause is *when* a widget is built, not what
the source says.

**Method that works:** render the widget offscreen, sample pixels, count how many
are bright. See §7's chart bug for the exact failure mode.

### 5.5 What to run

```
# engine assertions (52, read-only, ~15s) - never run while something else
# writes the real DB; a throwaway FD row makes the FD-count checks fail
.venv\Scripts\python.exe tools/test_prediction_engine.py

# charts vs direct DB aggregates (reads data/financial.db read-only)
.venv\Scripts\python.exe -m pytest tests/test_chart_db_agreement.py -q

# import 26AS/AIS/TIS into the DB (backs up first; --dry-run writes nothing;
# password comes from $AIS_TIS_PASSWORD or the gitignored password file)
.venv\Scripts\python.exe tools/taxdoc_import.py --dry-run

# statement extraction quality, modern vs legacy parser
.venv\Scripts\python.exe tools/extraction_audit.py

# 26AS per-record extraction + reconciliation
.venv\Scripts\python.exe tools/taxdoc_audit.py data/PersonalData/Pranav/26AS.pdf

# 26AS vs bank transactions, bank by bank
.venv\Scripts\python.exe tools/tax_reconcile.py

# real-window UI flows — ONE AT A TIME, each takes over the screen
.venv\Scripts\python.exe tools/real_ui_tests/test_add_person_flow.py
.venv\Scripts\python.exe tools/real_ui_tests/test_add_bank_flow.py
.venv\Scripts\python.exe tools/real_ui_tests/test_add_account_flow.py
.venv\Scripts\python.exe tools/real_ui_tests/test_statement_import_flow.py
.venv\Scripts\python.exe tools/real_ui_tests/test_tax_documents_flow.py
.venv\Scripts\python.exe tools/real_ui_tests/test_button_size_audit.py
.venv\Scripts\python.exe tools/real_ui_tests/test_excel_table_interactions.py   # writes RUIH_ rows, always cleans up
.venv\Scripts\python.exe tools/real_ui_tests/test_dark_theme_sweep.py          # read-only
.venv\Scripts\python.exe tools/real_ui_tests/test_transactions_scale.py        # read-only

# pytest (statement package)
.venv\Scripts\python.exe -m pytest tests/test_statement_package.py -q

# account deletion (fixes cascade, requires --expect-name match; --dry-run first)
.venv\Scripts\python.exe tools/delete_account.py --account-id <id> --expect-name "<bank_name>" --dry-run

# income recategorisation + internal-transfer detection (--dry-run first)
.venv\Scripts\python.exe tools/backfill_transactions.py --dry-run --person-id 1
```

**§J Full-suite pytest is fragile on this Windows/Qt/matplotlib stack.**
Running all of `tests/` in one process segfaults partway through (access
violation during garbage collection of matplotlib/Qt objects, or occasionally
a `unittest.mock` teardown) — this is pre-existing and not caused by any
particular test. `tests/test_dashboard_lazy.py`, `tests/test_chart_relocation.py`
and `tests/test_money_label.py` are the most likely to trigger it. Each passes
cleanly when run alone (`pytest tests/test_X.py -q`); a segfault at the very
end of a file (after `[100%]`) is teardown/GC, not a real test failure. If you
need a full-suite signal, run each file as its own process rather than one
combined `pytest tests -q` invocation.

**Two real-UI tests can never run concurrently** — they fight over screen focus.

---

## 6. Architecture you need to know

### Navigation (10 screens, `ui/dashboard_screen.py`)
`0` Overview · `1` Accounts · `2` Transactions · `3` Income & Expectations ·
`4` Fixed Deposits · `5` Statement Import · `6` Tax Documents · `7` Tax ·
`8` **Income Prediction** · `9` Settings

Adding a screen means **five** edits, and missing any one fails silently:
`_NAV_ITEMS`, the `screen_key_map`, the lazy page builder, `ui/icons.py` `_R`
registry, and `Theme.SCREEN_ACCENTS` — **plus** the page-name tuple in the
theme-refresh loop (~line 403).

### Two statement parsers exist
- **Modern** — `from engines.statement import parse_statement_pdf`. Confidence
  1.000 on all statements. **This is what the UI now uses.**
- **Legacy** — `engines.statement_parser.parse_statement_with_debug`. Confidence
  0.41–0.73. Still present; do not wire it back in.

The modern engine calls `normalise_order()` before balance reasoning. The legacy
one does not, which is why its confidence scores were wrong — transactions come out
**reverse-chronological** and a naive balance walk on a descending list fails.

### Prediction engine — `engines/prediction_engine.py`
Pure calculation, no Qt imports, no DB writes, plain dicts, every money figure
carries `is_estimated`. Single UI entry point:
`get_prediction_summary(person_id, financial_year=None, as_of=None)` →
keys `financial_year, as_of, realised_income, projected_fd_interest,
projected_savings_interest, expected_income, fy_income, tds_risk, timeline,
advisory`. Designed so the owner's future **advisory/strategy layer** ("where
should I invest to stay under the limit") can build on it without rework.

Added 2026-09-21: `itr_actuals()` and `compare_our_data_to_itr()` (ITR-side stored
figures and the neutral side-by-side; both new keys `itr_actuals` and `comparison`
are in the summary), and `build_strategies()` (declaration 15G/15H, redistribution,
new bank, defer maturity, headroom, data quality; surfaced in `build_advisory()` as
`strategies` + `context`). `engines/taxdocs/persist.py` maps parsed 26AS/AIS/TIS
onto `models/form26as.py` / `models/ais_tis_import.py`.

**Test hazard:** `tests/conftest.py` repoints `config.DB_PATH` to an empty temp DB
for every test. A test that must see real data has to point it back at
`data/financial.db` (see `tests/test_chart_db_agreement.py`), and a screen that
starts its own async `load_data()` must have it patched out or it overwrites the
data under test.

Engine hazards it works around — **do not undo these**:
- `interest_engine.fd_interest_for_fy()` **raises TypeError on a NULL
  maturity_date**, i.e. on 19 of 20 FDs. Use `fd_interest_accrued_to()` on a
  *synthesised copy*.
- `interest_engine.fd_tds_threshold_status()` reads `FDInterestRecord`, which only
  contains leftover Test Bank rows. Do not reuse it.
- `_get_tax_params()` / `_get_tax_slabs()` are the **only** accessors for
  TaxParams/TaxSlabConfig. Private by necessity. Never hardcode ₹12,00,000 or
  ₹50,000 — read them.

### Threading — the bug that froze the app
`Loader.run(parent, fn, message, on_done=, on_error=)` is the ONLY correct way to
run slow work. It now marshals callbacks to the GUI thread via a `_GuiRelay`
QObject with an explicit `QueuedConnection`.

**Why this matters:** a plain Python callable has **no thread affinity**, so Qt
invoked `on_done` directly on the *worker* thread. All GUI follow-up ran
off-thread, and constructing a `QMessageBox` there **deadlocked the process** —
window "Not Responding", no dialog visible, no error. **Never open a dialog from a
worker thread. Never revert this.**

### Theme
All colour via `Theme` tokens (`ui/theme/theme.py`). **No raw hex outside
`ui/theme/`.** Four themes: Aurora, Slate (light), Nova, Midnight Pro (dark).
Contrast measured — all pass WCAG AA 4.5:1 (Aurora `TEXT_MUTED` was 4.36:1 on
`BG`; fixed 2026-09-21 to `#6F6B89` = 4.75:1, and `("TEXT_MUTED","BG",4.5)` is now
in `tests/test_theme_contrast.py`).

**Any screen holding charts MUST define `refresh_theme()`** covering every chart
and table it owns. See §7.

---

## 7. Fixed this session — do not regress these

| # | Bug | Root cause |
|---|---|---|
| 1 | **App deadlocked on statement import** | `Loader.run` ran callbacks on the worker thread; `QMessageBox` there froze the process |
| 2 | "Update Account Details" modal froze import | `AccountMetadataDialog.exec()` fired mid-parse-result. Disabled via `SHOW_METADATA_DIALOG = False`. **The owner asked for it skipped**; restore only when non-modal or deferred |
| 3 | **26AS extracted ₹0.00 TDS** | Per-record parse broken — 49 records, `tax_deducted` None on all. Now 86+72 records, TDS sums to **exactly ₹13,367**, 27 reversals netted |
| 4 | **Encrypted AIS/TIS could never be imported** | `password=None` hardcoded, no prompt. `get_ais_tis_password()` existed in `models/person.py` but was called from nowhere. Now wired |
| 5 | Statements scored 0.41–0.73 confidence | UI used the legacy parser. Switched to modern → **1.000, zero balance failures** |
| 6 | Ujjivan detected **0 income rows** | Legacy misclassification — every interest credit typed as expense |
| 7 | References dropped | Continuation lines put the ref in the *description* column. Jana 34→46/65, IDFC 343→**358/376** |
| 8 | **Charts stayed white in dark mode** | `ChartWidget` bakes facecolor at construction. `IncomeManagementScreen` never defined `refresh_theme()`, and `dashboard_screen` calls it inside `except Exception: pass` → **AttributeError swallowed silently**. 69.6% bright → 0.0% |
| 9 | Navigation left pages at opacity 0 | A `fade_in()` on page change; a starved event loop left the page invisible. Removed |
| 10 | Test windows survived failures | `harness.close()` only ran on the success path. Now always-runs teardown |
| 11 | Prediction screen showed ₹0 | `_refresh_all_sections()` was a stub (`pass`) — data loaded then discarded; and it bailed when `selected_person_id` was None (the default) |

**PyQt6 → PySide6 migration** (66 files) also landed. Enum access was already
fully-scoped Qt6 form; no `sip`, no `QVariant`, no `QAction`. `QT_API=pyside6` is
pinned in `main.py`, `tests/conftest.py`, `tools/real_ui_test_harness.py` and
guarded in `chart_widget.py`, because matplotlib and qtawesome both bind at import
time.

## 7a. Fixed 2026-09-23 (plan-then-build session) — do not regress these

| # | Bug | Root cause |
|---|---|---|
| 12 | Button heights/widths ignored `height=`/`min_width=` args | `Theme.btn`'s QSS `min-height`/`max-width` (content-box) overrode `setFixedHeight`/`setMaximumWidth`. Rewrote sizing to snap to `HEIGHT_SM/MD/LG` (28/36/44) and bake exact geometry into the QSS itself |
| 13 | Tax Documents "Add" button did nothing | `EmptyState` default `action_text="Add"`, never connected to a handler. Now "Browse Form 26AS", wired to the 26AS zone |
| 14 | 6 Fixed Deposits buttons clipped their labels after fix #12 | Their `min_width=` args were sized for the *old* forced-320px-minimum behaviour; once real sizing applied, labels like "Recalculate Selected" no longer fit. Bumped `min_width` per button to fit the measured `sizeHint()` |
| 15 | Savings-interest projection was hardcoded `0.0` | `project_savings_interest` now projects unrealised interest per-account from statement-coverage-end to FY-end, basis current-FY or prior-FY daily rate |
| 16 | `is_internal_transfer` was 0 on all rows, unused | New `find_internal_transfers()` in `models/transaction.py`; `reprocess_internal_transfers` no longer overwrites `category` (previously it did, corrupting classification); used in `realised_income_to_date` alongside category |
| 17 | `Test Bank` (account_id 1) — phantom 15G strategy, deletion raised `IntegrityError` | `delete_account` didn't detach `AccountHolder`/`IncomeExpectation`/transaction FK refs before deleting, and FK enforcement is on. Fixed and deleted via `tools/delete_account.py` |
| 18 | ~₹1.59L of real taxable income booked as non-taxable "Other Income" | Commission/professional-fee/salary credits (Kevision, Lotus Investment, Enlightvision, Prasad M) were never classified. Backfilled via `tools/backfill_transactions.py`, reviewed and approved by the owner (see §3) |
| 19 | ExcelTable checkbox indicator click didn't reliably select the row | Checkbox cell only synced on `cellClicked`, which the `QCheckBox` widget itself consumes. Added `setCheckboxCell()` connecting the checkbox's own `toggled` signal |
| 20 | Double-click / Enter on a transaction row opened both an inline editor and the modal edit dialog | `setEditTriggers` included `DoubleClicked`, which raced against the `doubleClicked → _edit_transaction` modal handler. Narrowed triggers to `EditKeyPressed` only |
| 21 | Amount/Balance columns sorted lexicographically ("1,234" < "500") | Plain `QTableWidgetItem`. Added `_AmountSortItem` (mirrors the existing `_DateSortItem` pattern) |
| 22 | Transactions screen "Transfer" type filter always showed 0 (or stale) rows | Filtered by literal `transaction_type='Transfer'`, which never exists in the schema. Now filters by `is_internal_transfer=1` in Python after fetch |

---

## 8. What is PENDING — start here

### Done 2026-09-23 (see §10 for detail; §7a for the bug list)
- Items 2, 3, 5, 6, 7, 8, 9, 11, 12 below (from the 2026-09-21 pending list) are
  done — button sizing, savings projection, ExcelTable/dark-theme/transactions-scale
  testing, Test Bank deletion, `is_internal_transfer` population and use.
- Plus: real taxable-income recategorisation (₹1.59L, owner-approved), 3 new
  real-UI test files, checkbox/double-click/numeric-sort fixes on the
  Transactions screen, and the "Transfer" filter now works.
- Item 10 (`test_screen_render.py` slow) is superseded by §J — full-suite pytest
  is fragile on this stack for reasons unrelated to that one file's runtime.

### Done 2026-09-21 (see §10 for detail)
- 26AS/AIS/TIS stored in the DB, persisted from the Tax Documents screen and via
  `tools/taxdoc_import.py`; the prediction screen shows the ITR-side panel and a
  neutral comparison table.
- Strategy layer (`build_strategies`) and a Strategies section on the screen.
- Bulk FD rate-entry dialog (Fixed Deposits screen, "Enter Real Rates").
- Charts-vs-DB test, engine suite extended to 52 assertions.
- Fixed: Overview income/expense chart (`"credit"` vs `Income`), Settings button
  widths, Aurora `TEXT_MUTED` contrast, scrollbar radius token, 8 buttons at 40px,
  hardcoded passwords removed from `tools/tax_reconcile.py` and
  `tools/pipeline_import.py`.

### High value (still pending)
1. **Enter the real FD rates.** The dialog exists but has not been used on real
   data: all 19 remaining FDs are `Pending Details` and every projection is still
   an estimate at the 7.5% default. **Needs the user's real rates and tenures.**
   After entering them, the engine-suite FD expectations (`estimated_fd_count`,
   `known_fd_count`, FD interest `total` — currently 19 / 0 / ₹80,291.00) must be
   re-baselined from measured output, not loosened.
4. **Strategy quality.** Redistribution never fires today because no bank has
   spare room; `build_strategies` uses the 7.5% default for principal maths until
   real rates exist.
13. **~₹22.2L of "Other Income" (27 Jana rows described only as `"Transaction"`)
    and ~₹17.4L of family NEFT/UPI credits are still unclassified/non-taxable.**
    Not touched this session — the owner only approved the specific Kevision /
    Lotus Investment / Enlightvision / Prasad M rows (§3). Worth a manual review
    pass if more of it turns out to be taxable.
14. **Live theme switching is broadly incomplete.** Applying a theme to an
    *already-built* window (`test_dark_theme_sweep.py` Pass B) leaves most
    screens with bright, unthemed elements — `import_page`, `tax_documents_page`,
    `tax_page` and `settings_page` have no `refresh_theme()` at all, and even
    pages that do (`transactions_page`, `income_page`, `fd_page`,
    `prediction_page`) still show bright filter bars, buttons, charts and
    `CollapsibleSection` headers after a switch. Building a window fresh in the
    target theme (Pass A) is fully clean — 0 offenders across all 10 screens.
    This is a large, pre-existing gap (consistent with the already-known
    `Theme.btn` baked-QSS and `ChartWidget` baked-facecolor issues); fixing it
    properly is a design-system-level pass across every screen, out of scope for
    a single session. Screenshots: `tools/real_ui_tests/screenshots/*_darkB_*.png`.
15. **The Transactions screen has no pagination** — it loads the entire FY
    (505+ rows) into the table at once. Works today; flagged for if/when FY
    row counts grow much larger.

### Known open defects (recorded, unfixed)
9. **`Theme.btn` sizing bug (fixed 2026-09-23, see §7a #12)** — kept here as a
   pointer since item 9 numbering is referenced elsewhere; no longer open.
10. **Full-suite `pytest tests -q` is fragile**, see §5.5 §J. Not specific to
    `test_screen_render.py`'s runtime — several files individually pass but
    segfault when run back-to-back with hundreds of other Qt/matplotlib tests
    in one process (GC-time access violations). Confirmed pre-existing (not
    caused by 2026-09-23 changes) by checking `git diff` showed no changes to
    the affected files, and that each one passes 100% of its own assertions
    when run alone. Two pre-existing test failures also found this way, both
    unrelated to this session's changes: `test_dashboard_lazy.py`'s nav-button
    count (expects 9, dashboard now has 10 screens) and sidebar-collapse-width
    assertions are stale/failing independent of any 2026-09-23 edit.

---

## 9. How to work on this project

**Verify everything against disk.** Multiple sub-agents this session reported
detailed success for work that was never written, or was written and then
clobbered. One suggested `git checkout HEAD -- <dirs>` as a "fix", which would
have destroyed verified work. **Trust `git diff` and re-running the command; not a
report.**

**Grep-clean does not mean correct.** Two visual bugs survived grep audits because
they depended on *when* a widget was constructed. Render and measure.

**Measure before diagnosing.** An "amounts are off by one row" bug was confidently
diagnosed here and was **wrong** — it was an artifact of reverse-chronological
ordering. The real issue was a different parser entirely. Reproduce with numbers
before changing code.

**Use `faulthandler.dump_traceback_later(N, exit=True)`** to find hangs. It is how
the worker-thread deadlock was located when there was no exception and no visible
dialog.

**Never run two real-UI tests at once.**

---

## 10. Findings log

Append dated entries below. Do not delete prior ones. This section was rewritten
on 2026-09-19 to fold ~900 lines of session-by-session history into the structured
guide above; the detail that still mattered is preserved in §2–§9, and the full
narrative remains in git history.

### 2026-09-19 — full pipeline verified on real data
506 transactions imported across 4 real accounts; 20 FDs (₹27,00,000 principal).
Taxable income **₹95,591** vs the naive ₹64,95,691. Projected FY 2025-26 total
₹2,17,098 against the ₹12,00,000 limit — **headroom ₹9,82,902**. For the current
FY (2026-27) all three real banks are projected to cross the ₹50,000 TDS threshold
(Jana ₹1,00,268 est., Equitas ₹69,419 est., Test Bank ₹61,677) — the actionable
signal for 15G/15H or redistribution. All figures marked `(Est.)` because of the
7.5% default rate.

Income Prediction screen shipped at nav index 8 with headroom / TDS-risk /
timeline views, a rules-based advisory, and the two-sided OUR-DATA vs ITR-SIDE
comparison. 28/28 engine assertions pass with zero DB writes.

### 2026-09-21 — pending §8 work built via plan-then-build (Opus plan/verify, Haiku build)
**Built:** ITR document persistence (`engines/taxdocs/persist.py`, `tools/taxdoc_import.py`,
Tax Documents screen); `itr_actuals` / `compare_our_data_to_itr` / `build_strategies`
in the prediction engine; ITR panel, comparison table and Strategies section on the
Income Prediction screen; `apply_fd_details` + `FDBulkRateDialog` + "Enter Real Rates"
button; `tests/test_chart_db_agreement.py`; engine suite 28 -> 52 assertions.
Real DB after import: 26AS 158 records, total TDS ₹13,367.00; AIS FD interest
₹2,56,642 / savings ₹46,183 / TDS ₹12,073; TIS interest figures identical.
Our-side vs ITR (FY 2025-26): FD interest ₹1,21,507 vs ₹2,56,642; savings ₹4,001 vs
₹46,183; TDS ₹0 vs ₹13,367. Our side is lower everywhere - the expected shape.

**Bugs the independent verification caught (all passed the implementer's own checks):**
- `FDBulkRateDialog` used column indexes 4-8 but `ExcelTableWithStats(show_checkboxes=True)`
  adds a checkbox at column 0, so real columns are 5-9. Manual entry parsed the *Start
  Date* as the rate and saved nothing; "Apply to Checked" overwrote the start date.
- Compounding default `fd.get("k", "Quarterly")` returns `None` when the key exists as
  `None`; use `fd.get("k") or "Quarterly"`.
- `apply_fd_details` passed the FD's *old* tenure to `update_fd`, saving 0/0/0.
- `tests/test_chart_db_agreement.py` first ran against conftest's empty temp DB and
  passed vacuously (guards nested behind `if x > 0`). Then it raced the screen's own
  async `load_data()` (values changed run to run). Both fixed; three consecutive
  stable runs.
- E2's invariants were first written as prints, not counted assertions.
- A throwaway `RUIH_` FD in the real DB makes `test_prediction_engine.py` report FD-count
  failures while it exists; never run the suite concurrently with a DB-writing test.

**Also fixed:** Overview "Income vs Expense" chart compared `transaction_type == "credit"`
(column only holds `Income`/`Expense`), booking all 506 rows as expense; scrollbar
`border-radius: 4px` literals now use `RADIUS_CONTROL` (fixes `test_theme_radius`); real
AIS/TIS and Equitas passwords removed from `tools/tax_reconcile.py` and
`tools/pipeline_import.py` (read at runtime from `$AIS_TIS_PASSWORD` / the gitignored
password file). **The old passwords remain in git history and in earlier docs
(`docs/AUDIT_AND_REBUILD_PLAN.md`, `docs/PIPELINE_AUDIT_PLAN.md`, `docs/REBUILD_PLAN.json`,
`tests/test_form26as_parser.py`, `tests/test_taxdocs_merge.py`); consider treating them
as exposed and rotating them if they matter.**

**Tax Documents real-UI test:** used to stall at the encrypted AIS file because
`_on_ais_selected` opens a modal password dialog on `is_pdf_encrypted` alone (the saved
password only prefills it) and the test never answered it (gotcha G). Pre-existing, not a
regression from persistence. Fixed: the test now pre-arms a `QTimer.singleShot` that fills
and accepts the `PasswordDialog` (password read at runtime, never hardcoded), backs up the
DB first, and checks afterwards that a re-import replaced rows (158 26AS records, 1 AIS +
1 TIS import). Ran once end to end on 2026-09-21: all checks passed.

### 2026-09-23 — §8 pending items built via plan-then-build (Opus plan/verify, Haiku build)

**Built:** button-sizing fix across the design system; real `project_savings_interest`;
`find_internal_transfers`/`reprocess_internal_transfers` rewrite; `delete_account` cascade
fix + `tools/delete_account.py`; `tools/backfill_transactions.py`; 3 new real-UI tests
(`test_excel_table_interactions.py`, `test_dark_theme_sweep.py`,
`test_transactions_scale.py`); checkbox-sync, double-click/Enter dialog conflict, and
numeric-sort fixes on the Transactions screen; "Transfer" filter now works. Full bug list
in §7a.

**Real DB changes (all backed up first, all reviewed before running for real):**
`Test Bank` (account_id 1) deleted; 39 "Other Income" transactions recategorised
(₹1.59L moved to taxable categories, owner-approved — see §3); 3 transactions flagged
`is_internal_transfer=1`. Engine suite re-baselined from measured output: taxable
₹95,591 → ₹2,54,784, non-taxable ₹64,00,091.21 → ₹62,40,898.21, FD total
₹1,21,507 → ₹80,291.00 (known FD lost with Test Bank), `fy_income.projected_total`
₹2,17,098 → ₹3,35,075, headroom ₹9,82,902 → ₹8,64,925. 52/52 engine assertions and
`test_chart_db_agreement.py` pass.

**A data-loss incident happened and was caught and fixed — read this before trusting
any real-UI test's self-reported pass/fail.** While testing
`test_excel_table_interactions.py`'s delete-selected step, an earlier (buggy) version
of the test deleted 2 real transactions (ids 571, 598 — both legitimate, just
recategorised to Savings Interest that same session) instead of only its own `RUIH_`
rows. The test's own final report claimed a clean run (`total_before = 504`, cleanup
"successful") — **504 was itself wrong (should have been 506)**, and the report never
flagged the discrepancy. It was caught only by independently diffing the live DB's
`transaction_id` set against a `backups/*.db` snapshot taken minutes earlier — the
mismatch (`missing: [571, 598]`) was the tell. Restored from
`backups/pre_ruih_test_20260923_213106.db` (the last backup where both rows were still
intact) with the user's explicit approval, using their exact original field values.
Root cause of the deletion itself was never fully isolated (the test file was rewritten
under time pressure rather than bisected) — if `test_excel_table_interactions.py`'s
delete-selected step is touched again, verify against a fresh backup diff afterwards, not
just the test's own printed counts. **This is exactly the failure mode §9 already warns
about ("trust `git diff` and re-running the command, not a report") — it just took a
transaction-id diff instead of a `git diff` to catch it.**

**Also found and fixed on the way:** `backup_database()` in `core/database.py` has no
return statement (always returns `None`), so any caller checking `if backup_path:` gets a
false "FAILED" even on a successful backup — check `os.path.exists()`/`getsize()` instead.
The Transactions screen filters by `session.selected_fy`; any test/tool that inserts rows
into a specific FY must also set `dashboard.fy_combo` to that FY before checking table
state, or rows are invisible regardless of search/filter text.
`test_dark_theme_sweep.py`'s brightness measurement used the old PyQt-era
`img.constBits(); ptr.setsize(...)` pattern, which doesn't exist on PySide6's memoryview —
rewritten with `np.frombuffer` + `bytesPerLine()`. `ThemeCard` intentionally paints a
fixed preview of its *own* theme's colours regardless of the active theme (so an Aurora
preview card is supposed to look bright even under Midnight Pro) — excluded from the
brightness-offender check, not a bug.
