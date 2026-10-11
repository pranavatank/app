# Rebuild + real-UI walkthrough: runbook and current state

**Last updated:** 2026-10-12. This file is the runbook and state record for two linked efforts:
(1) rebuilding `data/financial.db` from scratch through the real UI, and (2) walking every control of the app with
scripts that drive the real mouse and keyboard, then validating the backend.

## 0. Read order for a fresh agent

1. **`docs/VISUAL_TESTING_GUIDE.md` §1, §2, §4, §5.2, §8** (about 15 minutes): what the app is, the income-figure trap,
   the real documents and their verified figures, the non-negotiable test rules, and how to work. It is the product
   handoff; this file does not repeat it.
2. **This file** for everything about the rebuild, the Phase 3 scripts, current results, open decisions and next steps.
3. Only then open source files. The sections below list exactly which files matter.

If you only have time for one file, read this one: sections 1-5 and 9 are enough to run and extend the tests safely.

## 1. Current state (2026-10-12)

| Area | State |
|---|---|
| Fresh DB rebuild (Phases 0-2) | Done 2026-09-29, verified. DB counts below. |
| Phase 3 R-mode scripts (read-only on real DB) | **Run on the real UI.** 10 of 11 screens pass (see 4.3). `11_hard_refresh` has not been run. |
| Phase 3 S-mode scripts (mutating, scratch copy only) | Run once, failed on script bugs, **repaired but not re-run**: 03 income, 04 fixed deposits, 05 statement import, 09 settings. 01, 02, 07 have S parts that were never run. |
| Phase 4 headless checks | Run once on 2026-09-29 (results in the guide). Not re-run after the later bug fixes. |
| Phase 5 findings | `screenshots/rebuild/FINDINGS.md` (gitignored) exists; fix-claim ledger is still all "pending". `rebuild_p5_collect.py` has not been run since the R runs. |
| Device check in `core/auth.py` | **Temporarily commented out (lines ~82-83) and UNCOMMITTED** so the scripts can log in. See section 6, item D1. |

**Real DB contents** (`data/financial.db`, rebuilt through the real UI): Person 1 ("Pranav"), Bank 4 (Jana, IDFC FIRST,
Ujjivan, Equitas), BankAccount 4, Transactions 506 (65 / 376 / 27 / 38), FixedDeposit 23 (Jana 14 `Pending Details`,
Equitas 9 `Matured`, of which 5 are wrong until the Equitas repair), Form26ASImport 1 / Form26ASRecord 158,
AISTISImport 2 (AIS + TIS, both FY 2025-26), AccountHolder 4, StatementImportLog 4, TaxProfile 0, IncomeExpectation 0.
Taxable income measured on this DB is about ₹96,056, not the old ₹2,54,784, because the owner-approved Commission /
Professional Fees recategorisation lived in the deleted DB. **Never run `tools/backfill_transactions.py`** (owner rule:
the fresh-import pipeline is tested exactly as production runs it).

**Pending data repair (not code):** the pre-fix import wrongly marked Equitas FDs 15-19 as Matured and created placeholder
FDs 20-23 with NULL `start_date`. Repair = reset the Equitas account and re-import with the fixed matching:
`run_on_scratch.py --fresh rebuild_p2_4_reset_account.py --bank Equitas --expect-count 38`, then
`run_on_scratch.py rebuild_p2_4_statement.py --bank Equitas` (rehearsal), verify Pending=5 / Matured=9, then
`rebuild_p2_4_reset_account.py --real --confirm-account-id 4`. **`rebuild_p2_4_reset_account.py` has two known crash bugs**
(nonexistent `from services import engines`; `.issubset` called on a list) and does not delete the account's
`StatementImportLog` row: fix before use.

## 2. Hard rules (read before running anything)

- **One real-UI process at a time, and the user must not touch the mouse or keyboard** while it runs. Do not run heavy
  CPU work (pytest, other agents running tests) in parallel: it starved the UI once. Disable sleep and lock.
  `pyautogui.FAILSAFE` stays on: a mouse hit in a screen corner aborts the run.
- **Real DB is read-only for R scripts.** `P3Run` fingerprints every table before `bootstrap_app()` and again at the end
  (`R_ALLOWED` is empty). A mismatch is a FAIL. Mutating work goes only through `run_on_scratch.py`
  (a copy at `backups/phase3_scratch.db`; aborts with exit 3 if the real DB or real `theme_prefs.json` changed).
- **Secrets** (master password, AIS/TIS password, Equitas password) are read at runtime from
  `data/PersonalData/Pranav/password.txt` via `rebuild_common.read_secret("master"|"ais_tis"|"equitas")`. Never print,
  log, hardcode, or pass them as a command-line argument. Logs go through a redacting logger (secrets, PANs, long digit
  runs are masked). Screenshots contain PII: they stay under the gitignored `screenshots/`.
- **Verification is independent.** A script's own PASS and a screenshot are not proof: confirm with read-only SQL or widget
  state. After anything that deletes or edits rows by id, diff the id set against a backup (guide §8 data-loss incident).
- **Never commit** `data/`, `backups/`, `*.db*`, or `screenshots/`. They are gitignored; check `git status` before committing.
- **Do not edit `schema.prisma`/migrate/change schema** without an explicit owner request. Treat the current schema as the
  source of truth. Follow the repo's global rules (reuse existing helpers, simple code, minimal comments).
- **The device check bypass in `core/auth.py` is a test-only edit.** Do not commit it. Revert it or replace it with the
  owner-approved option (section 6, D1) before release.
- The harness runs commands through a permission classifier. Long unattended batches of real-UI scripts were allowed only
  after the owner granted permission; if a command is denied, stop and ask rather than working around it.

## 3. How to run

Environment: Windows, venv at `.venv\Scripts\python.exe`, repo root `D:\Pranav\app`, PowerShell. Check nothing else runs
`main.py` or the scripts first: `Get-CimInstance Win32_Process -Filter "name='python.exe'" | Select CommandLine`
(enumeration from an agent shell can be unreliable; cross-check log mtimes).

```
# R mode: read-only on the real DB
.venv\Scripts\python.exe tools\real_ui_tests\rebuild_p3_NN_<screen>.py --env R > tools\real_ui_tests\screenshots\rebuild\P3_NN_R.out 2>&1

# S mode: mutating, scratch copy only (use --fresh for a clean copy each time)
.venv\Scripts\python.exe tools\real_ui_tests\run_on_scratch.py --fresh tools\real_ui_tests\rebuild_p3_NN_<screen>.py --env S > ...P3_NN_S.out 2>&1
```
- Run scripts **sequentially and check each exit code**: do not chain blindly. Each script writes
  `screenshots/rebuild/P3_<nn>_<screen>_<env>.{log,json}` (the `.log`/`.json` survive a native crash; stdout does not) and
  appends a line to `screenshots/rebuild/PROGRESS.md`. `--part` re-runs a single block where a script supports it.
- Suggested order: `10_topbar`, `00_overview`, `01_accounts`, `02_transactions`, `03_income`, `04_fixed_deposits`,
  `06_tax_documents`, `07_tax`, `08_income_prediction`, `09_settings` (all `--env R`); then S scripts via `run_on_scratch`;
  `11_hard_refresh` (R only, **last**: it reloads every module and drops `session.aes_key`, and is refused on scratch);
  then `rebuild_verify.py --fingerprint --out X` / `--compare A B` and `rebuild_p5_collect.py`.
- Existing legacy flows must also go through scratch: `test_add_person_flow`, `test_add_bank_flow`, `test_add_account_flow`,
  `test_statement_import_flow`, `test_tax_documents_flow`, `test_excel_table_interactions` (they write and delete rows).
  `test_button_size_audit`, `test_dark_theme_sweep`, `test_transactions_scale` are read-only.
- Resume after any interruption: kill leftover app processes; if the DB fails `PRAGMA integrity_check`, restore the last
  `backups/rebuild_*.db` snapshot; re-run the failing script (every step is idempotent by construction).
- Login: scripts call `login_to_dashboard`, which needs a working `verify_login`. If it shows "Unauthorised device", the
  machine's MAC/hostname changed since setup (section 6, D1).

## 4. The tooling (all under `tools/real_ui_tests/` unless noted)

### 4.1 Shared helpers
- `rebuild_common.py`: `bootstrap_app`, `read_secret`, `redact`, `os_click(harness, root, accessible_name)` (name must be
  non-empty), `os_click_widget(harness, widget)`, `os_type`/`os_type_widget` (read-back verified; spin boxes compare
  `value()`), `os_select_combo`, `os_set_date`, `prearm`/`Prearm` (polls until a modal is active; **has a `match`
  predicate so a pending handler only takes its own dialog**), `answer_message_box(harness, app, button, expect_title)`,
  `answer_modal_dialog(harness, app, dialog_cls, title, fill_fn)`, `answer_password_dialog`, `native_file_dialog(opener, path)`
  (a subprocess types the path into the OS file dialog), `toast_texts()` (validation messages are toasts, not message boxes),
  `find_button`, `label_scan`, `parse_inr`, `login_to_dashboard(..., otp=None)`, `set_fy`, `wait_until`, `snapshot_db`,
  `fingerprint_real_db`/`diff_fingerprints`, `read/restore_theme_prefs`, `Checks`, `run_logged`, `start_modal_watchdog`.
- `rebuild_p3_common.py`: `P3Run` (`p.nav`, `p.sql`, `p.observe`, `p.a11y`, `p.checks.check`, `p.dashboard`, `p.harness`,
  `p.app`) and `main_wrapper(nn, screen, run_r, run_s)`. **`main_wrapper` already calls `p.start()` (bootstrap, login, FY
  2025-26)**: never call it again in a script. An exception in a run is logged and recorded as a FAIL check (never PASS).
- `run_on_scratch.py`: patches `config.DB_PATH`, `core.database.DB_PATH`, `core.backup_manager.DB_PATH` and both
  `_CONFIG_FILE`s; refuses `--real`, `--env R` scripts and hard-refresh; sets `FINMGR_SCRATCH=1`; optional `--from <db>`.
- `os_file_dialog_typer.py`, `rebuild_verify.py` (`--fingerprint [--out N]`, `--compare A B [--allow T1,T2]`, `--engines`,
  `--tempdb`; read-only), `rebuild_p5_collect.py` (writes `screenshots/rebuild/P5_collected.md`: failures, accessibility
  gaps, observations, integrity facts).
- `tools/real_ui_test_harness.py`: the lower-level `RealUIHarness` (click/type via the OS, screenshots, `find_dialog`).

### 4.2 Rebuild-from-scratch scripts (Phases 0-2)
`rebuild_p0_expectations.py` (headless: parses the real documents, writes `screenshots/rebuild/P0_expectations.json`,
**stop if any document figure differs from section 8**) then, after deleting `data/financial.db` (+ `-wal`, `-shm`,
`-journal`) by explicit literal path, in order: `rebuild_p2_0_setup.py` (first-run master password) ->
`rebuild_p2_1_person.py` -> `rebuild_p2_2_banks.py` -> `rebuild_p2_3_accounts.py` ->
`rebuild_p2_4_statement.py --bank Jana|"IDFC FIRST"|Ujjivan|Equitas` (in that order) -> `rebuild_p2_5_7_taxdocs.py`
(26AS -> AIS -> TIS in **one** screen instance; the AIS/TIS FY comes from the 26AS import, otherwise it falls back to the
top-bar FY) -> `rebuild_p2_8_fd_origin.py` (read-only). Prerequisites: a `master:` line in `password.txt`; an owner decision
on DOB (the dialog cannot be blank and defaults to today). Each step snapshots to `backups/rebuild_<UTC>_<tag>.db`.
`data/PersonalData/Pranav/Data 26-27.xlsx` is not part of the task: do not import it.

### 4.3 Phase 3 per-screen scripts and latest results
Screen indices: 0 Overview, 1 Accounts, 2 Transactions, 3 Income & Expectations, 4 Fixed Deposits, 5 Statement Import,
6 Tax Documents, 7 Tax, 8 Income Prediction, 9 Settings (Settings is **9**; old scripts that used 8 are fixed).

| Script | R result | S status |
|---|---|---|
| `rebuild_p3_10_topbar` (nav, person/account/FY combos, sidebar, logout/relogin) | 76/76 PASS | n/a |
| `rebuild_p3_00_overview` (KPIs, charts vs SQL, per-account balances; S: privacy mode) | 48/48 PASS | not run |
| `rebuild_p3_01_accounts` (cards, detail panel; S: add/validate/edit/delete) | 9/9 PASS | not run |
| `rebuild_p3_02_transactions` (filters, sort, pills, link-transfers; S: add/edit/move/delete/unsaved bar) | 13/13 PASS | not run |
| `rebuild_p3_03_income` | PASS (first run, before later fixes) | repaired, not re-run |
| `rebuild_p3_04_fixed_deposits` | PASS (first run) | repaired, not re-run |
| `rebuild_p3_05_statement_import` | n/a (S only) | repaired, not re-run (crashed first time: wrong file name) |
| `rebuild_p3_06_tax_documents` (R reads AIS/26AS figures from SQL; tables are empty in R by design) | 10/10 PASS | S (H3 FY test) not run |
| `rebuild_p3_07_tax` | 12/12 PASS | S (Estimate tax + vectors) not run |
| `rebuild_p3_08_income_prediction` | 30/30 PASS (first run) | n/a |
| `rebuild_p3_09_settings` | 26/26 PASS (first run) | repaired, not re-run |
| `rebuild_p3_11_hard_refresh` | **not run** | n/a (R only, last) |

R results for 03/04/08/09 predate several app fixes: re-run them. Expect the S `03` Salary standard-deduction check to
fail by design (the Tax screen reads the saved profile, not income expectations): decide whether the test or the product changes.

## 5. Gotchas that cost real time

- `os_click` with a button that has no accessible name used to click the dialog centre; it now raises. Unnamed controls
  are located by attribute and recorded with `p.a11y(...)` (a low-severity accessibility finding).
- Many accessible names repeat across screens (`Add account`, `File drop zone`): search under the page or dialog, not the
  dashboard. The three tax-document drop zones are `zone_26as`, `zone_ais`, `zone_tis`.
- Arm modal handlers **before** the click that opens the dialog, and end every fill by clicking a dialog button; a dialog
  left open is rejected by the 5 s watchdog and recorded as a failure. Native file dialogs are driven by
  `native_file_dialog`, and their titles must be in `p.expected_titles`.
- The Transactions table has a checkbox column 0, so every data column index is +1 (description 6, amount 7, id 11).
  `ExcelTableWithStats(show_checkboxes=True)` shifts columns everywhere: the income-expectations Edit/Delete bug came from this.
- Delete/Save/Recalculate on the Income, Fixed Deposits and Transactions screens act on **checked rows**, not the selection.
- Dashboard auto-selects the only person, so "All Persons" cannot stay selected with one person (by design, dashboard_screen ~791).
- Hard Refresh rebuilds in place and reloads app modules; the redaction patterns reset, so re-read the secrets after it.
- `uuid.getnode()`-based device fingerprint can change with network adapters/hostname (D1 below).
- Some pytest modules segfault when run together on this machine, before and after changes; run them one module at a time.
  Do not run `tests/test_chart_db_agreement.py` casually: it reads the real DB read-only and asserts the old baseline numbers.
- Sub-agents' self-reports (including "all passed") must be re-verified against real output before trusting them.

## 6. Open decisions for the owner

- **D1 Device-fingerprint lockout.** `get_device_fingerprint` = sha256(MAC + hostname). A change locks the owner out
  ("Unauthorised device.") with no recovery, and the binding adds no cryptographic protection (the AES key derives from the
  password and salt). Options: (A) keep strict and show an actionable message, (B) recommended: confirmed re-bind after a
  correct password/OTP, (C) remove the binding and fix the "cryptographically bound" texts in Settings/Login. `verify_login`
  and `verify_master_password` must behave identically. Until decided, `core/auth.py` stays uncommitted (it also holds the
  `change_password` error-handling fix, which should be committed on its own once D1 is settled).
- **D2** Privacy reveal: `ui/widgets/privacy_overlay.reveal_with_password` has no callers; privacy mode can be turned off
  without a password. Require the password (depends on D1) or delete the dead module.
- **D3** Full import rollback: updates to FDs that existed before a failed import (status, maturity) are not undone.
- **D4** `project_fy_income` ignores income expectations and may double-count payout-FD interest.
- **D5** Overview "Income (FY)" tile is a gross figure (includes FD maturity principal and unflagged self-transfers).
- **D6** Tax Documents uses `session.selected_person_id or 1` when "All persons" is selected.
- **D7** Tax-law gaps for a CA: basic-exemption shortfall adjustment for special-rate gains, s.112 LTCG rate (the "20%"
  field), lottery/online-game winnings (115BB), surcharge cap on special-rate income, FY-specific rates for FY2024-25.
  The Tax screen also recomputes tax from the saved profile without the capital-gains split (needs a schema change).
- **D8** Tax Documents ignores TIS salary.
- Also pending from the guide: enter real FD rates (bulk-rate dialog exists), re-baseline `tools/test_prediction_engine.py`
  and `tests/test_chart_db_agreement.py` from measured output (do not loosen the critical guard), the unclassified
  "Other Income" review, and incomplete live theme switching for charts and four pages.

## 7. Bugs found by this effort

Fixed and committed (see `git log`): first-run hang (toast before dashboard); FD-opening detection; `add_bank` did not seed
`BankFDConvention`; `ThemeManager._write_pref` dropped `sidebar_open`; toast container blocked clicks; FD redemption matching;
`add_account` creates the primary `AccountHolder`; balance-validation import block; dashboard refresh mapping +
`IncomePredictionScreen.refresh`; account details panel rebuilt its layout on every update (Close/Edit/Delete unreachable);
Western digit grouping replaced by Indian grouping on every screen (`session.mask` -> `format_inr`; `format_inr` no longer
returns "₹-0"); Tax Documents always showed the full TDS as "Refund Due" (now uses the tax engine); capital-gains rates for
FY2025-26 (20% s.111A, 12.5% s.112A above ₹1.25L) - **this changes saved tax figures**; failed-import rollback now removes
FDs created by redemption matching; savings interest after import runs once per FY after the balance recalculation;
`change_password` rolls back on error and reports undecryptable saved passwords; Shift Dates / Split Row used PySide6-invalid
keywords; bulk edit overwrote untouched fields; Excel column mapping was ignored; income-expectation Edit/Delete read the
wrong column; the Income dialog defaulted to FY 2020-21; editing a recurring expectation lost its month; FD maturity now
rounds up as the audit doc specifies (₹1,00,000 @ 7.10% 1y quarterly = 107288).

Not bugs / accepted: H13 (worker-thread widget access) is latent only (`_show_loader` has no callers); the single-person
auto-select above.

Hypotheses status (from the original review): H1/H2/H4/H6/H7/H11/H20 fixed; H9, H12, H23 fixed; H8 rates fixed, legal gaps open
(D7); H14 partly fixed (D3); H5, H15, H18 are decisions (D2, D4, D5); H3 (AIS/TIS FY depends on 26AS import order) is still
true and its S test has not run; H10 (DOB cannot be blank, two-digit year) and H16 (bank YAML profiles unused by the modern
parser) are unverified low-priority items; H22 (Hard Refresh drops the session key) and H24 (tax vectors include read-only
prefilled AIS interest) await the `11` and `07` S runs. `FINDINGS.md` holds the live ledger (all "pending").

## 8. Reference figures (must match exactly unless a parser/engine regression is the point)

- Statement parse counts: Jana 65, IDFC 376, Ujjivan 27, Equitas 38 (Equitas needs its password).
- 26AS: 158 records (86 Part-I + 72 Part-II), net TDS ₹13,367.00; 211 line items (194A x206, 194JB x4, 194JA x1), 25 B + 9 G
  reversals netted, net gross ₹3,50,458; per-deductor pairs in guide §4 (Equitas ₹54,816, Jana ₹34,469, Ujjivan ₹79,077).
- AIS/TIS: FD interest ₹2,56,642, savings interest ₹46,183, dividend ₹2,655, business receipts ₹1,05,069, AIS TDS ₹12,073.
- Tax engine vectors (new regime, FY2025-26, `calculate_new_regime_tax`, a pure function): non-salary ₹12,00,000 -> 0;
  ₹12,10,000 -> 10,400; ₹13,00,000 -> 78,000; salary ₹12,75,000 -> 0; ₹3,50,458 -> 0; ₹60,00,000 -> 15,78,720.
  With the new capital-gains rates: STCG ₹1,00,000 + LTCG ₹2,25,000 -> special-rate tax 32,500; LTCG ₹1,00,000 only -> 0.
- Seeded data: `TaxSlabConfig` 14 rows (7 x two FYs), `TaxParams` 2 rows, schema has 21 tables.

## 9. Next steps (in order)

1. Settle D1, then revert the temporary `core/auth.py` bypass or commit the chosen option.
2. Re-run the R scripts for 03, 04, 08, 09 (stale), then `11_hard_refresh` last.
3. Re-run the repaired S scripts (03, 04, 05, 09) and run the never-run S parts (00, 01, 02, 06, 07) with `run_on_scratch --fresh`;
   read the `.log`/`.json`, not stdout. Fix script bugs; record real app bugs in `FINDINGS.md` with file:line.
4. Run `rebuild_p5_collect.py`, then update the fix-claim ledger and hypotheses in `FINDINGS.md`.
5. Phase 4 headless checks again: `tools/run_full_tests.py` (baseline 35 PASS, 2 benign teardown CRASH), `tools/test_prediction_engine.py`
   (classify baseline-coupled vs invariant failures), `tools/extraction_audit.py`, `tools/taxdoc_audit.py`, `tools/tax_reconcile.py`,
   `tools/rebuild_verify.py --engines --tempdb`.
6. Equitas data repair (section 1) after fixing `rebuild_p2_4_reset_account.py`.
7. Final integrity statement: PersonalData hashes unchanged (compare with `P0_personaldata_hashes.json`), `git status` clean of
   data files, `theme_prefs.json` restored, real-DB fingerprint unchanged by R runs.
