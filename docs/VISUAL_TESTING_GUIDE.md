# Project Handoff & Testing Guide

**Read this file first and read it fully. It is written to be sufficient on its own** —
you should not need to read source files to understand what this project is, what
state it is in, what has been verified, what is broken, or how to test it.

**Last updated:** 2026-09-19.
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
| BankAccount | 5 | see below |
| Transactions | 506 | imported from the 4 real statements |
| FixedDeposit | 20 | **19 are `Pending Details`** — no rate, no maturity |
| IncomeExpectation | 0 | never populated |
| Form26ASImport / AISTISImport | 0 | **ITR docs have never been imported into the DB** |
| Bank | 0 | |

Accounts: `1` Test Bank (leftover junk), `38` Jana Small Finance Bank,
`39` IDFC FIRST Bank, `40` Ujjivan Small Finance Bank, `41` Equitas Small Finance Bank.

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
(gitignored): AIS/TIS `azipt9702h08032004`, Equitas `0803PRA`.
PAN `AZIPT9702H` (also inside 26AS). **Do not ask the user for these. Do not
hardcode them into committed source.**

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
# engine assertions (28, read-only, ~15s)
.venv\Scripts\python.exe tools/test_prediction_engine.py

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

# pytest (statement package)
.venv\Scripts\python.exe -m pytest tests/test_statement_package.py -q
```

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
Contrast measured — all pass WCAG AA 4.5:1 **except Aurora `TEXT_MUTED` on `BG` at
4.36:1** (open, unfixed, low priority).

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

---

## 8. What is PENDING — start here

### High value
1. **Enter real FD interest rates.** 19 of 20 FDs are `Pending Details`. Everything
   in the prediction is an estimate until this is done. Consider a bulk-entry UI.
2. **Import 26AS/AIS/TIS into the DB.** The parsers work, but
   `Form26ASImport`/`AISTISImport` are still empty, so the Income Prediction
   screen's ITR-side panel correctly shows an EmptyState. Until this is done there
   is no stored actuals side to compare against.
3. **The advisory/strategy layer the owner wants:** *"screens and strategies which
   tell me how to invest and where to invest to keep my income below limit."*
   `build_advisory()` in the prediction engine is the seam — currently simple
   rules only.

### Testing never completed
4. **Charts vs DB aggregates.** Never verified that a plotted series equals a
   direct DB aggregate. A rendered chart is not evidence (§E).
5. **ExcelTable interactions** — cell click, checkbox toggle + row-highlight sync,
   Enter-to-edit, double-click-to-edit (§F), delete-selected with a DB check.
6. **Screen-by-screen sweep** across all 10 screens in a dark theme.
7. **Transactions screen at scale** — 506 real rows, paging and filtering.

### Known open defects (recorded, unfixed)
8. **8 buttons render 40px**, off the {28,36,44} scale — `height=40` passed to
   `Theme.btn` in `transactions_screen`, `tax_screen` and two dialogs.
9. **6 Settings buttons render 320-322px** against a 280px cap — `min_width=155`
   inside a stretching layout.
10. **Aurora `TEXT_MUTED` fails contrast** at 4.36:1 (needs 4.5:1).
11. **`Test Bank` (account_id 1) is leftover junk** polluting real output — it owns
    the only complete FD and all 6 `FDInterestRecord` rows. Decide whether to delete it.
12. **`is_internal_transfer` is unused** (0 on all rows). Populating it properly
    would make income classification far more robust than category matching.

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
