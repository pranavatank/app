# Project Handoff & Testing Guide

**Read this file first and read it fully. It is written to be sufficient on its own** —
you should not need to read source files to understand what this project is, what
state it is in, what is pending, or how to test it.

**Last updated:** 2026-09-23 (second pass).
**Audience:** an AI agent (or human) picking this project up with zero prior context.
This guide keeps only what is pending and what you need to know to avoid repeating
past mistakes — not a changelog. Full history is in git log / commit messages.

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

The `Transactions` table books **₹64,95,682** as Income for FY 2025-26.
**Most of it is not taxable income.**

- You **must** classify by the `category` column, not by a naive
  `SUM(amount) WHERE transaction_type='Income'` (that reports ₹64.9L against a
  ₹12L limit and makes any prediction screen worse than useless).
- `category IN TAXABLE_INCOME_CATEGORIES` (`engines/prediction_engine.py`) is
  taxable: `FD Interest`, `Savings Interest`, `Commission Income`,
  `Professional Fees`, `Salary`. Everything else counts as non-taxable UNLESS
  `is_internal_transfer=1` is also false and the category is unrecognized
  (then it's `unclassified`, not counted either way).
- `is_internal_transfer` is now populated (3 rows currently) and is used
  alongside category in `realised_income_to_date` — but it's a *small, very
  conservative* flag (see §3), not a general-purpose filter. Most non-taxable
  rows are non-taxable by category (`Other Income`, `FD Maturity`), not by
  this flag.
- **Currently taxable: ₹2,54,784** (FY 2025-26, as of 2026-03-31). This is a
  real, owner-approved figure, not the original ₹95,591 — see §3 for what
  changed and why, before assuming any number you see elsewhere is stale.

`tools/test_prediction_engine.py` has a permanent CRITICAL GUARD assertion
(`non_taxable > 5_000_000` and `taxable < 500_000`) that exists purely to
catch a "summed everything as taxable" regression. **Do not weaken it** — but
also don't be surprised the threshold isn't ₹200,000 anymore; it was
deliberately raised to sit above the current legitimate taxable figure. If a
future income recategorisation pushes taxable income close to ₹500,000
legitimately, raise the threshold again (with the same reasoning), don't just
delete the guard.

---

## 3. Current state of the real database — READ THIS, it changed recently

`data/financial.db` is **REAL USER DATA**, not a fixture. It is gitignored
(`.gitignore:2` → `data/*.db`). Back it up before any writing operation — see
§5.2 rule 3 and the `tools/delete_account.py` / `tools/backfill_transactions.py`
pattern (dry-run first, `core.database.backup_database()`, verify counts).

| table | rows | note |
|---|---|---|
| Person | 1 | person_id 1, PAN and DOB set |
| BankAccount | 4 | `38` Jana, `39` IDFC FIRST, `40` Ujjivan, `41` Equitas. `Test Bank` (account_id 1, leftover junk) was deleted — do not expect it to exist |
| Transactions | 506 | imported from the 4 real statements; categories backfilled |
| FixedDeposit | 19 | **all 19 are `Pending Details`** — no rate, no maturity. Every FD projection is an estimate at the 7.5% default (`DEFAULT_FD_RATE`). **Entering the real rates is the highest-value accuracy improvement available** — the bulk-entry dialog exists (Fixed Deposits screen, "Enter Real Rates") but needs the user's real rates/tenures |
| IncomeExpectation | 0 | never populated |
| Form26ASImport / Form26ASRecord | 1 / 158 | FY 2025-26, total TDS ₹13,367 |
| AISTISImport | 2 | AIS + TIS imported (`tools/taxdoc_import.py` or the Tax Documents screen) |
| Bank | 0 | |

### Income classification is not fully clean — know this before trusting any total
`TAXABLE_INCOME_CATEGORIES` now includes `Commission Income`, `Professional
Fees`, `Salary` (added when real income sources — Kevision Systems, Lotus
Investment, Enlightvision, Prasad M — were found misclassified as non-taxable
`Other Income` and recategorised, owner-approved). **Not exhaustively
reviewed**: ~₹22.2L of "Other Income" (27 Jana rows described only as
`"Transaction"`, unidentifiable from the description alone) and ~₹17.4L of
family NEFT/UPI credits are still sitting under non-taxable `Other Income`,
unreviewed. If you're asked to improve income-classification accuracy, this
is where the remaining value is — but changing it changes the user's real tax
figures, so confirm with the owner first, the way the Commission/Professional
Fees/Salary reclassification was confirmed.

`LOTUSINVESTM ENT` (note: literal stray space mid-word in the source bank
statement text) — if you ever grep for "LOTUSINVESTMENT" or "LOTUS
INVESTMENT" and get zero matches, that's why; strip whitespace before
matching, or match `LOTUSINVESTM.?ENT`.

### `is_internal_transfer` — deliberately conservative, read before extending it
Populated via `find_internal_transfers()` in `models/transaction.py`. A
candidate debit/credit pair is accepted only if it is the *unique* match for
that amount within a ±2-day window, **counted across every account, not just
cross-account candidates** — an early version excluded same-account rows from
the ambiguity count and produced a real false positive (a cheque paid to a
third party got linked to a gift from the user's mother, because it looked
"unique" once same-account candidates were wrongly excluded). If you touch
this function, re-verify against a fresh DB diff (see §9), not just the
function's own reported pair count.

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
into any committed file, including this guide.** (Old passwords were previously
committed in earlier docs/tests and remain in git history — if you ever need to
know which files, `git log -p` on `tools/tax_reconcile.py` and
`tools/pipeline_import.py` will show; rotate them if it matters.)

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

Ujjivan showing ₹0 on our side is the clearest illustration of §1: its
interest is credited inside FDs and never lands in a statement row.
**TDS never appears in transactions at all** — it is deducted before credit, so it
can only come from the tax documents. That is correct behaviour, not a bug.

---

## 5. How to test — read this before writing any test

### 5.1 The environment
- Repo `D:\Pranav\app`, branch `main`. Always run from the repo root.
- Python: `.venv\Scripts\python.exe`. PySide6 6.11.2.
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
2. **Never pipe a long run through `| tail`** — the pipe buffers everything and you
   see nothing until it exits. Redirect to a file and read the file.
3. **Real DB safety.** Back up (`core.database.backup_database()`, WAL-safe —
   `shutil.copy2` is NOT safe on a WAL-mode DB) before any write. Any test that
   creates rows must delete them in an always-runs (`finally`) path. Prefix
   test rows `RUIH_`.
4. **Never commit** `data/PersonalData/**` or `data/financial.db` or anything
   under `backups/` (check `.gitignore` covers `.db`, `.db-shm` AND
   `.db-wal` — a WAL sidecar file was once nearly committed because the
   gitignore only listed `.db`).
5. **Report real output.** A failure is a finding. Fabricating a pass wastes
   more time than the bug does. **A test's own self-reported pass/fail is not
   proof — verify against the actual DB/disk state independently, every
   time** (see §9; this is not a hypothetical, it caught a real bug).

### 5.3 Real-UI testing (the harness)
`tools/real_ui_test_harness.py` → `RealUIHarness`. Launches a **real, visible,
maximized** window. Never `QT_QPA_PLATFORM=offscreen` for UI behaviour tests.

API: `launch(factory, maximized=True)`, `click(root, "Accessible Name")`,
`type_into(...)`, `key(...)`, `find(root, name)`, `find_dialog(cls, title, timeout)`,
`scroll_into_view(w)`, `settle(sec)`, `shot(name)`, `to_physical(pt)`,
`click_via_os(w)`, `click_at_via_os(widget, local_point, double=False)`,
`find_via_uia(...)`. `double_click()` uses `pyautogui`, not `QTest.mouseDClick`
(see gotcha F).

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
  Use `pyautogui.doubleClick()` or the keyboard equivalent, and say which.
- **§G Modal `.exec()` blocks `QTest.mouseClick`.** The click call sits on the
  stack inside the modal's nested event loop. **Pre-arm
  `QTimer.singleShot(0, cb)` BEFORE clicking anything that opens a modal.**
  `PersonDialog`, `BankDialog`, `AccountDialog`, `TransactionDialog` are all
  `.exec()`-modal.
- **§H Blind coordinate clicks misclick.** Prefer accessible-name lookup + QTest
  over OS coordinates; `click_via_os()` is the opt-in escape hatch.
- **§I PySide6 `findChildren()` takes ONE type**, not a tuple. PyQt6 allowed the
  tuple form.
- **§J A screen/test that inserts rows into a specific FY must also set
  `dashboard.fy_combo` to that FY** before checking table state — the
  Transactions screen filters by `session.selected_fy`, which defaults to the
  *current* FY, not whatever FY your test data is in. Rows will silently not
  appear otherwise, and every downstream assertion cascades into wrong
  failures that look unrelated to the real cause.
- **§K `backup_database()` in `core/database.py` returns `None` on success**
  (no return statement) — checking `if backup_path:` on its return value
  always looks like failure. Check `os.path.exists(dest)` /
  `os.path.getsize(dest) > 0` instead.

### 5.4 Testing colour / theme problems
**Grep cannot find them.** A file can be grep-clean of hex literals and still
render wrong. The cause is *when* a widget is built, not what the source says.

**Method that works:** render the widget offscreen/onscreen, sample pixels
(`np.frombuffer(img.constBits(), ...)` — PySide6's `constBits()` returns a
memoryview, the old PyQt `ptr.setsize(img.byteCount())` pattern doesn't
apply), count how many are bright (luminance > 216).

**Known false positive:** `ThemeCard` (Settings screen) intentionally paints a
fixed preview of its *own* theme's colours regardless of the active theme —
a bright Aurora preview card under a dark theme is correct, not a bug.
Exclude `type(w).__name__ == "ThemeCard"` from any brightness-offender scan.

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

**Full-suite `pytest tests -q` is fragile on this Windows/Qt/matplotlib
stack — use `tools/run_full_tests.py` instead.** Running all of `tests/` in
one process segfaults partway through (access violation during garbage
collection of matplotlib/Qt objects). `tools/run_full_tests.py` runs each
`tests/test_*.py` file in its own subprocess for real isolation:
```
.venv\Scripts\python.exe tools/run_full_tests.py
# specific files, and pass extra pytest flags after --:
.venv\Scripts\python.exe tools/run_full_tests.py tests/test_kpi_tile.py -- -v
```
Current baseline: **35 PASS, 2 CRASH** (`test_chart_relocation.py`,
`test_money_label.py`) — both pre-existing, both an interpreter-teardown
segfault that happens *before* pytest's own summary line is written (all
their own assertions pass — the log shows `...` / `[100%]` then nothing). The
tool's classifier reports these as `CRASH` rather than `PASS (crashed after
summary)` because it can't find a summary line at all in this specific crash
timing; read the log in `%TEMP%\finmgr_test_logs\` to confirm it's this
known-benign case before treating a CRASH as a regression.

`test_dashboard_lazy.py`'s two previously-stale-failing tests (nav-button
count, sidebar-collapse-width) are now fixed and pass.

**Two real-UI tests can never run concurrently** — they fight over screen focus.

---

## 6. Architecture you need to know

### Navigation (10 screens, `ui/dashboard_screen.py`)
`0` Overview · `1` Accounts · `2` Transactions · `3` Income & Expectations ·
`4` Fixed Deposits · `5` Statement Import · `6` Tax Documents · `7` Tax ·
`8` **Income Prediction** · `9` Settings

Adding a screen means edits in several places, and missing any one fails
silently: `_NAV_ITEMS` (its second element is the screen key, used both for
nav routing and as the key into `Theme.SCREEN_ACCENT_FILL`/`SCREEN_ACCENT_TINT`
— add a matching entry to those dicts in **all 4** theme files, not just one),
the lazy page builder, `ui/icons.py`'s icon registry, and
`self._screen_pages` (consumed by `_refresh_shared_widgets`). There is no
`screen_key_map` anymore — nav buttons carry their screen key directly via
`setProperty("screen", ...)`.

### Two statement parsers exist
- **Modern** — `from engines.statement import parse_statement_pdf`. Confidence
  1.000 on all statements. **This is what the UI uses.**
- **Legacy** — `engines.statement_parser.parse_statement_with_debug`. Still
  present; do not wire it back in — its confidence scores are wrong because it
  never calls `normalise_order()`, so transactions come out
  reverse-chronological and a naive balance walk fails.

### Prediction engine — `engines/prediction_engine.py`
Pure calculation, no Qt imports, no DB writes, plain dicts, every money figure
carries `is_estimated`. Single UI entry point:
`get_prediction_summary(person_id, financial_year=None, as_of=None)` →
keys `financial_year, as_of, realised_income, projected_fd_interest,
projected_savings_interest, expected_income, fy_income, tds_risk, timeline,
advisory, itr_actuals, comparison`. `build_strategies()` (declaration 15G/15H,
redistribution, new bank, defer maturity, headroom, data quality) surfaces in
`build_advisory()` as `strategies` + `context`. `engines/taxdocs/persist.py`
maps parsed 26AS/AIS/TIS onto `models/form26as.py` / `models/ais_tis_import.py`.

`project_savings_interest(person_id, financial_year, as_of=None)` projects
unrealised interest per-account from statement-coverage-end to FY-end (basis:
current-FY daily rate if any realised this FY, else prior-FY daily rate, else
zero) — not a hardcoded 0.0 anymore. Returns
`{total, realised, full_year, per_bank, is_estimated}`.

**Test hazard:** `tests/conftest.py` repoints `config.DB_PATH` to an empty temp DB
for every test. A test that must see real data has to point it back at
`data/financial.db` (see `tests/test_chart_db_agreement.py`), and a screen that
starts its own async `load_data()` must have it patched out or it overwrites the
data under test.

Engine hazards it works around — **do not undo these**:
- `interest_engine.fd_interest_for_fy()` **raises TypeError on a NULL
  maturity_date**, i.e. on all 19 of the remaining FDs. Use
  `fd_interest_accrued_to()` on a *synthesised copy*.
- `interest_engine.fd_tds_threshold_status()` reads `FDInterestRecord`, which
  is now empty (its only rows lived on the deleted Test Bank). Do not rely on
  it having data.
- `_get_tax_params()` / `_get_tax_slabs()` are the **only** accessors for
  TaxParams/TaxSlabConfig. Private by necessity. Never hardcode ₹12,00,000 or
  ₹50,000 — read them.

### Threading — do not revert
`Loader.run(parent, fn, message, on_done=, on_error=)` is the ONLY correct way to
run slow work. It marshals callbacks to the GUI thread via a `_GuiRelay`
QObject with an explicit `QueuedConnection` — a plain Python callable has no
thread affinity, so without this Qt invokes `on_done` on the *worker* thread,
and constructing a `QMessageBox` there **deadlocks the process** (window "Not
Responding", no exception, no visible dialog). **Never open a dialog from a
worker thread.**

### Theme
All colour via `Theme` tokens (`ui/theme/theme.py`). **No raw hex outside
`ui/theme/`.** Four themes: Aurora, Slate (light), Nova, Midnight Pro (dark).

`Theme.btn()` height is snapped to `HEIGHT_SM/MD/LG` (28/36/44) and baked into
the button's own QSS (`min-height`/`max-height`), not left to
`setFixedHeight()` alone — Qt's stylesheet re-application overrides
`setFixedHeight`/`setMaximumWidth` on repolish, so geometry must live in the
QSS string itself.

**Accent system (added 2026-09-23).** Every screen has a colour identity via
`Theme.SCREEN_ACCENT_FILL`/`SCREEN_ACCENT_TINT` dicts (keyed by screen name,
defined per-theme in all 4 `ui/theme/theme_*.py` files — same 10 keys in
every file). `Theme.accent(name)` resolves either a screen key or a semantic
name (`"primary"`, `"success"`, `"danger"`, `"warning"`, `"info"`, `"teal"`,
`"purple"`, `"pink"` — see `ui.theme.components.ACCENT_TOKENS`) to a hex
colour; `Theme.screen_accent(key)`/`screen_accent_fill(key)` resolve just the
tint/fill pair. `KpiTile`, `SummaryPanel`, `CollapsibleSection`, `EmptyState`
all take an `accent=` kwarg and style themselves via QSS
`[accent="name"]`/`[screen="name"]` dynamic-property selectors (not inline
`setStyleSheet` calls) — so a live theme switch just needs the property
re-evaluated, not the widget rebuilt. Each also has a `refresh_theme()`
method; `DashboardScreen._refresh_shared_widgets()` walks every built page
and calls it on every instance of those 4 classes. **Two gotchas that will
bite you if you add new colour code:** (1) Qt reads an 8-digit hex string as
`#AARRGGBB` (alpha first), not `#RRGGBBAA` — a `f"{color}2E"` pattern
intending "add alpha" silently produces a wrong colour instead of erroring;
use `ui.theme.components.rgba(hex, alpha)` instead. (2) `border-radius: 999px`
does NOT clip a non-square/non-circular widget into a circle in Qt's QSS —
verified by direct offscreen render; use one of the real radius tokens
(`RADIUS_CONTROL`/`RADIUS_CARD`/`RADIUS_MODAL`/`RADIUS_PILL`) or a literal
that's actually been checked to look right at that widget's size.

**Any screen holding charts MUST define `refresh_theme()`** covering every
chart and table it owns, or a live theme switch leaves it visually stale.
**Charts and 4 full pages (`import_page`, `tax_documents_page`, `tax_page`,
`settings_page`) still don't** — see §7 pending item.

---

## 7. PENDING — start here

### High value
1. **Enter the real FD rates.** The bulk-entry dialog exists (Fixed Deposits
   screen, "Enter Real Rates") but has not been used on real data: all 19
   remaining FDs are `Pending Details`, every projection is an estimate at
   the 7.5% default. **Needs the user's real rates and tenures.** After
   entering them, re-baseline `tools/test_prediction_engine.py`'s FD
   expectations (`estimated_fd_count`, `known_fd_count`, FD interest `total`
   — currently 19 / 0 / ₹80,291.00) from measured output, not loosened.
2. **Strategy quality.** Redistribution never fires today because no bank has
   spare room; `build_strategies` uses the 7.5% default for principal maths
   until real rates exist (depends on item 1).
3. **~₹22.2L + ~₹17.4L of "Other Income" is still unclassified/non-taxable and
   unreviewed** — see §3 "Income classification is not fully clean". Confirm
   with the owner before recategorising any of it, the way the earlier
   reclassification was confirmed.
4. **Live theme switching is still incomplete, though better than before.**
   `KpiTile`/`SummaryPanel`/`CollapsibleSection` headers/`EmptyState` now
   re-theme correctly on a live switch (via `_refresh_shared_widgets()`) —
   Overview screen went from 3 brightness offenders to 0. What's still
   unthemed on a live switch: **charts** (`ChartWidget` bakes its facecolor
   at construction — matplotlib figure, not QSS-drivable the same way) and
   **4 full pages that have no `refresh_theme()` at all**:
   `import_page`, `tax_documents_page`, `tax_page`, `settings_page` (check
   with `has_refresh_theme=False` lines printed by
   `tools/real_ui_tests/test_dark_theme_sweep.py`). Building a window fresh
   in the target theme is fully clean — 0 offenders across all 10 screens
   (Pass A of that same test). Fixing charts + the 4 missing pages is a
   further design-system pass, not a quick patch.
5. **`tools/run_full_tests.py`'s crash classifier has a gap** (§5.5): a
   process that crashes *before* pytest's own summary line prints (rather
   than after) is reported as `CRASH` with "(no summary found)" instead of
   the more accurate "PASS (crashed after summary)" — currently affects
   `test_chart_relocation.py`/`test_money_label.py`. Not urgent (the log
   still shows the truth if you read it), but worth tightening if this
   pattern recurs on other files.

### Known, accepted limitations (not bugs to fix blindly)
6. **The Transactions screen has no pagination** — loads the entire FY
   (505+ rows) at once. Fine today; revisit if per-FY row counts grow much
   larger.
7. **`Test Bank` (account_id 1) is gone.** If you see references to it in old
   documents/plans, they're stale — don't try to "fix" an account that no
   longer exists.

---

## 8. How to work on this project

**A test's or agent's own self-reported pass/fail is not proof — verify
independently, every time.** This bit hard this session: a real-UI test's
delete-selected step deleted 2 real transactions instead of only its own
`RUIH_`-prefixed test rows, and the test's own final report still claimed a
clean run with a wrong "before" count that silently absorbed the loss. It was
only caught by diffing the live DB's row-id set against a timestamped backup
taken minutes earlier. If you write or run anything that deletes/modifies
real rows by id, **diff the actual id set against a backup afterwards** — do
not trust a printed count alone. Restoring lost rows needs the user's
explicit approval and their exact original field values from a backup; ask
before writing them back.

**Grep-clean does not mean correct.** Visual/theme bugs depend on *when* a
widget is constructed, not what the source says. Render and measure (§5.4).

**Measure before diagnosing.** Confidently-diagnosed bugs have turned out
wrong before (an "off by one row" bug was actually reverse-chronological
ordering from a different parser entirely). Reproduce with real numbers
before changing code.

**Use `faulthandler.dump_traceback_later(N, exit=True)`** to find hangs with
no exception and no visible dialog (this is how a worker-thread deadlock was
once located).

**Never run two real-UI tests at once** — they fight over screen focus.

**When Haiku sub-agents implement something, re-verify their claims yourself**
against real command output before trusting a "done"/"all passed" report —
several real bugs this session (a false transfer-pairing match, a broken
LOTUS-INVESTMENT category match, the data-loss incident above) were only
caught this way, not from the implementer's own self-check.
