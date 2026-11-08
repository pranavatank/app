# Fresh rebuild and real-UI runbook

**Updated:** 2026-11-08. Read `docs/VISUAL_TESTING_GUIDE.md` first for product purpose, FD Planner limits, expected source
figures, and safety rules. This file is the current execution checklist. Do not rely on prior run claims unless a matching
log or independent measurement exists.

## Current status

| Work | Status |
|---|---|
| Live `data/financial.db` | Full P2 rebuild and independent postflight passed. Do not reset again. |
| P0 document preflight | **Passed, exit 0.** `screenshots/rebuild/P0_repair_20261105.out`. Fixed PDF row grouping recovers one Equitas debit; Ujjivan blank balances reconcile between printed anchors. |
| Focused checks | Private sources 3, password readers 7, preflight 46, FD provenance 34, PDF rows 5, real statement package 10, P5 collection 22 passed. Collection log: `screenshots/rebuild/collection_verified.out`. Other logs: `resume_focused/`, `password_review_verified.out`, `row_repair_verified/`. |
| Tax imports and postflight | 26AS, AIS, TIS, and `rebuild_postflight.py` passed; zero postflight failures. |
| Phase 3 | Eleven R-mode reports pass (283/283 assertions). S00 Overview passed; S01 Accounts passed 26/26; S02 Transactions passed 41/41. S03 Income passed 58/58 (`P3_03_income_S.json`, `P3_03_income_S_final_20261107.out`); focused edit/link/unlink/delete passed 15/15 (`P3_03_income_dialogs_S_pickerfix_20261107.out`), and picker/geometry checks passed 3/3. S04 Fixed Deposits passed 19/19; see `P3_04_fixed_deposits_S.json` and `P3_04_fixed_deposits_S_verified_20261107.out`. Independent checks confirmed original FD/transaction ID sets 28/507 restored after scratch and integrity `ok`. S05 Statement Import passed 53/53, exit 0, in `P3_05_statement_import_S_settingsfix_20261107.out`. Nov 8 native S-mode: S06 tax documents 9/9 after the header fix (`P3_06_tax_documents_S_headerfix_20261108.out`); S07 tax 10/10 (`P3_07_tax_S_expanded_20261108.out`); S09 settings 33/33 (`P3_09_settings_S_20261108.out`). The focused source-year test file passed 13 tests (`taxdoc_header_20261108/test_taxdoc_source_year.py.log`); its wrapper also invoked a nonexistent file, so do not count the entire runner as passing. Real AIS+TIS parser FY2025 passed (`S06_parser_fixed_20261108.out`). S06 now excludes historical body-page FY mentions based on first-page metadata while still rejecting conflicting header years. Sol review found no blocker. Live DB fingerprint matched baseline (`tax_milestone_compare_20261108.out`). Next: S13 fresh-scratch run, then R11. Full suite and P5 remain pending; S13 is an unverified draft. UX notifications and focus completed Nov 7; see the UX checkpoint below. |
| Unity seven-row mini statement | Explicitly deferred; no opening/running balances. |
| S03 Income | **Passed 58/58**, plus focused dialogs 15/15 and picker/geometry tests 3/3. |
| S04 Fixed Deposits | **Passed 19/19.** `P3_04_fixed_deposits_S_verified_20261107.out`; exact original IDs restored after scratch. |
| S05 Statement Import | **Passed 53/53, exit 0.** `P3_05_statement_import_S_settingsfix_20261107.out`. |
| S06 FY behavior | **Native S passed 9/9**, `P3_06_tax_documents_S_headerfix_20261108.out`; parser FY2025 passed for AIS+TIS. Historical body-page year mentions are excluded using first-page metadata; conflicting header years still reject. |
| S07 Tax | **Native S passed 10/10**, `P3_07_tax_S_expanded_20261108.out`. |
| S09 Settings | **Native S passed 33/33**, `P3_09_settings_S_20261108.out`. |
| S13 People/DOB | Draft test added; unverified. |
| Hard refresh (R11) | Pending. Reproduce suspected session-key loss; keep key/FY preservation assertions. |

### Nov 7 UX checkpoint — completed

Toast tests passed 13/13 (`notifications_final_20261107.out`); focus tests passed 9/9
(`ux_finish_20261107/test_theme_qss.py.log`); broader theme checks passed 26/26
(`ux_theme_checks_20261107.out`). Native Windows Aurora/Nova checks passed for timer expiry, worker-thread delivery,
click-through outside the toast, and modal handoff (`ux_native_integration_20261107.out`). The final Aurora/Nova
Windows previews verify full short danger-message wrapping at a 38px viewport with no scrollbar. Accepted previews are
`ux_notifications_aurora_final.png`, `ux_notifications_nova_final.png`, and `ux_modal_*_final.png` under
`screenshots/rebuild/`. Notifications use FIFO queues, natural height, 3/5/7-second durations, hover pause, and modal
handoff. Simple acknowledgement message boxes use notifications; confirmations and TOTP remain modal. Focus uses
rounded outer borders with no inner native rectangle and remains keyboard accessible. Independent final review
approved the repaired queue; no UX blockers remain. This is UX-specific verification, not completion of the full
product test plan. Final audit confirmed all 13 private source hashes unchanged, theme preferences byte-identical,
and AST parsing passed for all 11 changed Python files. The live database fingerprint matched before and after UX
work (`ux_complete_compare_20261107.out`).

P0 and the reviewed parser repair passed before deletion. Run logs, screenshots, expectation files, fingerprints, and progress records live under the ignored
`tools/real_ui_tests/screenshots/` tree. Preserve any existing contents. Before starting, inspect `git status --short` and
leave unrelated or staged work untouched.

### Completed rebuild milestone

The ignored audit `screenshots/rebuild/banks_checkpoint_20261106.json` passed for all four statements: Jana 65,
IDFC FIRST 376, Ujjivan 27, Equitas 39 (507 total). Every date/type/amount/balance matches its source and each
account's closing balance matches. FD provenance passed for 19 openings and 9 redemptions. The 28 FDs are Jana:
14 Pending Details / INR 1,300,000; Equitas: 5 Pending Details / INR 500,000 and 9 Matured / INR 850,000 principal /
INR 91,590 interest. SQLite integrity is `ok`, foreign-key violations are 0, and all 13 private hashes are unchanged.
The P2.4 logs are `screenshots/rebuild/P2_4_*20261106.out`; P2.8 log is
`screenshots/rebuild/P2_8_banks_20261106.out`. Latest snapshot:
`backups/rebuild_20261106T101846Z_P2_5_7.db` (UTC filename). The P2.5_7 tax import log,
`screenshots/rebuild/P2_taxdocs_20261106.out`, exited 0: 26AS has 158 FY 2025-26 records with INR 13,367 net TDS;
AIS and TIS both identify FY 2025-26 and match expected amounts. The saved password decrypts successfully. The full
read-only `rebuild_postflight.py` audit exited 0 with zero failures, verifying all 507 strict transaction row
multisets, accounts, and tax records; see `screenshots/rebuild/postflight_20261106.out` and `postflight.json`.
Do not reset or repeat completed imports.

Eleven R-mode reports pass all 283 recorded assertions. The accounts R run includes the verified actual OS close
assertion; the destroyed-widget helper log was fixed. P3.12 passed 38 checks, including the clipped-target case (group
4 to 6), actual plan/result, and unchanged database fingerprint. The family-tree unit check passes (1), recorded in
`screenshots/rebuild/tree_interaction_verified_20261106.out`. These reports cover read-only checks only.

P3.00 S passed on fresh scratch; its report is `P3_00_overview_S.json`. The wide checkbox now uses the indicator
center and guarded OS hit-testing; three click-point tests passed. P3.01 Accounts passed 26/26 and P3.02 Transactions
passed 41/41; transaction dialog geometry passed 2/2, with a recorded non-OS date-entry fallback. S03 Income passed
58/58 (`P3_03_income_S_final_20261107.out`), its focused dialog flow passed 15/15
(`P3_03_income_dialogs_S_pickerfix_20261107.out`), and picker/geometry checks passed 3/3. S04 Fixed Deposits passed
19/19 (`P3_04_fixed_deposits_S_verified_20261107.out`); original FD/transaction ID sets 28/507 were restored and
integrity was `ok`. S05 Statement Import passed 53/53 (`P3_05_statement_import_S_settingsfix_20261107.out`). The Nov 8
S06/S07/S09 and parser milestones, test-runner caveat, and live DB fingerprint check are recorded in Current status
above. S13 People/DOB remains an unverified draft; the next command is its fresh-scratch run.

Next command — S13 People/DOB on fresh scratch:

```powershell
.venv\Scripts\python.exe tools\real_ui_tests\run_on_scratch.py --fresh tools\real_ui_tests\rebuild_p3_13_people.py --env S *> tools\real_ui_tests\screenshots\rebuild\P3_13_people_S_20261108.out
```

| R-mode report | Result | JSON |
|---|---:|---|
| P3.10 topbar | 80/80 | `screenshots/rebuild/P3_10_topbar_R.json` |
| P3.00 overview | 48/48 | `screenshots/rebuild/P3_00_overview_R.json` |
| P3.01 accounts | 10/10 | `screenshots/rebuild/P3_01_accounts_R.json` |
| P3.02 transactions | 13/13 | `screenshots/rebuild/P3_02_transactions_R.json` |
| P3.03 income | 9/9 | `screenshots/rebuild/P3_03_income_R.json` |
| P3.04 fixed deposits | 7/7 | `screenshots/rebuild/P3_04_fixed_deposits_R.json` |
| P3.06 tax documents | 10/10 | `screenshots/rebuild/P3_06_tax_documents_R.json` |
| P3.07 tax | 12/12 | `screenshots/rebuild/P3_07_Tax_R.json` |
| P3.08 income prediction | 30/30 | `screenshots/rebuild/P3_08_Income Prediction_R.json` |
| P3.09 settings | 26/26 | `screenshots/rebuild/P3_09_Settings_R.json` |
| P3.12 FD Planner | 38/38 | `screenshots/rebuild/P3_12_FD Planner_R.json`; log `screenshots/rebuild/P3_12_R_final_20261106.out` |

## Fixed inputs and acceptance facts

- Private source resolver: `tools/private_sources.py` prefers `data/data/Pranav/`, with
  `data/PersonalData/Pranav/` as a legacy fallback. There are 13 protected private files; read only and compare their
  hashes before/after. The workbook is `data/data/Data 26-27.xlsx`; do not
  import it in this rebuild.
- Statements in order: Jana, IDFC FIRST, Ujjivan, Equitas. Corrected transaction counts are 65, 376, 27, 39 (507 total).
  Verify ledger balances independently; P0 validates chronology, required fields, and running-balance reconciliation.
- 26AS: FY 2025-26, AY 2026-27, 158 records, net TDS INR 13,367. Import 26AS, then AIS, then TIS in one screen instance.
  AIS JSON and Form16A files are not imported by this flow. AIS/TIS PDFs identify FY 2025-26. Password readers handle labels without
  exposing the values.
- Person DOB: 2004-03-08. Master credential is the generated local value in ignored `credentials.local.json` unless
  `FINMGR_MASTER_PASSWORD_FILE` is configured; source labels are fallback. Never reveal credentials.
- Expected FD provenance: Jana 14 openings / INR 1,300,000; Equitas 5 openings / INR 500,000. Historical redemption expectations were
  9 matured placeholders / INR 850,000 principal / INR 91,590 interest. Measure the
  actual DB; these figures are acceptance checks, not data to force into place.
- Unity mini statement has seven credits and a footer balance but no opening or running balances. Do not import it.

## Safety gates

1. Never run `tools/backfill_transactions.py`. No schema, authentication-policy, or tax-policy redesign is in scope.
2. The authorized reset is complete. Keep the pre-reset backup referenced by `screenshots/rebuild/before_fresh_backup.json`
   (`backups/rebuild_20261104T132227Z_before_fresh.db`) and the latest rebuilt snapshot. Both are private and ignored.
   Do not reset again when resuming this checkpoint.
3. Run GUI scripts sequentially, no parallel UI or heavy pytest load. Check process exit codes and inspect each
   script's `.log`/`.json` output. Confirm key results with independent read-only SQL and fingerprints.
4. P0 is read-only. R mode is read-only on the live DB. Every S-mode mutation runs through
   `run_on_scratch.py --fresh`; never pass `--real` or run a mutator directly against the live DB.
5. Do not modify `data/data/`, `data/PersonalData/`, the verified backup, or the original theme preferences. Keep
   artifacts in ignored `screenshots/`; do not stage or commit anything. Owner requested commits be batched by the
   coordinating agent.
6. Credentials must never appear in command arguments, logs, source, or screenshots. Keep `pyautogui.FAILSAFE` on.

## Phase 0: preflight, backup, reset, and build

From repo root in PowerShell; use `.venv\Scripts\python.exe`. Run one command at a time and stop at the first failure.

```powershell
.venv\Scripts\python.exe tools\real_ui_tests\rebuild_p0_expectations.py --defer-unity
```

Check P0 exit status and `screenshots/rebuild/P0_expectations.json`: all four statements parse, counts match, balances
reconcile, 26AS year fields match, master credential is available, and the Unity source is recorded as deferred. Do not
reset if any check fails. Confirm the backup and hash manifest before deleting the four literal DB/sidecar paths.
The first 2026-11-05 attempt failed; the repaired run passed. Row/preflight/package checks then passed 61 tests with child exit 0.

Historical P2 build sequence (completed; do not rerun):

```text
rebuild_p2_0_setup.py
rebuild_p2_1_person.py
rebuild_p2_2_banks.py
rebuild_p2_3_accounts.py
rebuild_p2_4_statement.py --bank "Jana"
rebuild_p2_4_statement.py --bank "IDFC FIRST"
rebuild_p2_4_statement.py --bank "Ujjivan"
rebuild_p2_4_statement.py --bank "Equitas"
rebuild_p2_5_7_taxdocs.py
rebuild_p2_8_fd_origin.py
```

P2 steps created snapshots and updated ignored progress records. The completed imports and P2.8 provenance are covered
by the milestone audit above; postflight passed with zero failures.

## Phase 3: UI walkthrough

Run one script at a time. Each P3 script launches/bootstrap/login itself through `main_wrapper`; do not call `p.start()`
again from a script. R means read-only against real data; S means mutating against a fresh scratch copy.

```powershell
# R mode example
.venv\Scripts\python.exe tools\real_ui_tests\rebuild_p3_00_overview.py --env R *> tools\real_ui_tests\screenshots\rebuild\P3_00_R.out

# S mode example (fresh scratch copy per run)
.venv\Scripts\python.exe tools\real_ui_tests\run_on_scratch.py --fresh tools\real_ui_tests\rebuild_p3_01_accounts.py --env S *> tools\real_ui_tests\screenshots\rebuild\P3_01_S.out
```

Check each exit code and its `P3_<nn>_<screen>_<env>.log` and `.json`. Run relevant scripts in this order, adapted to
their supported environments and parts:

| Script | What to inspect |
|---|---|
| `rebuild_p3_10_topbar.py` | Run first in R mode: navigation, person/account/FY selectors, logout/relogin |
| `rebuild_p3_00_overview.py` | KPI and chart values vs SQL, account filter, privacy mode |
| `rebuild_p3_01_accounts.py` | account cards/details; S add, edit, validation, delete |
| `rebuild_p3_02_transactions.py` | filters, sort, transfer linking; S add/edit/move/delete |
| `rebuild_p3_03_income.py` | income/expectations controls; S03 income-contract behavior |
| `rebuild_p3_04_fixed_deposits.py` | FD rows/actions and data quality |
| `rebuild_p3_05_statement_import.py` | S import flow and balance-validation block |
| `rebuild_p3_06_tax_documents.py` | persisted 26AS display and S06 FY behavior |
| `rebuild_p3_07_tax.py` | saved profile, estimate, tax vectors |
| `rebuild_p3_08_income_prediction.py` | prediction and comparison values |
| `rebuild_p3_09_settings.py` | settings and theme preference behavior |
| `rebuild_p3_12_fd_planner.py` | planner navigation, data sourcing, plan view, transitions/partial coverage |
| `rebuild_p3_11_hard_refresh.py` | R only and last; explicitly reproduce suspected AES session-key loss |

Purpose-built UI scripts can mix OS mouse/keyboard input with direct Qt widget setup. In particular, P2.2 Banks and P2.3
Accounts scripts use tab navigation, `combo.setCurrentIndex`, and `openingbalance.setValue`; record these as GUI-flow
coverage, not proof that every field was independently entered through physical input. P2.1 also has this limitation.

Run S scripts only through `run_on_scratch.py --fresh`. For any legacy mutating flow, including `test_add_person_flow.py`,
`test_add_bank_flow.py`, `test_add_account_flow.py`, `test_statement_import_flow.py`, `test_tax_documents_flow.py`, and
`test_excel_table_interactions.py`, use scratch isolation. Do not run legacy tests against the rebuilt DB.

Useful runner and verification tools:

```powershell
.venv\Scripts\python.exe tools\rebuild_verify.py --fingerprint --out after_p3
.venv\Scripts\python.exe tools\rebuild_verify.py --compare before_p3 after_p3
.venv\Scripts\python.exe tools\real_ui_tests\rebuild_p5_collect.py
```

Also use `tools/real_ui_tests/rebuild_common.py` for secrets, modal handling, snapshots, fingerprints and checks;
`rebuild_p3_common.py` for navigation/SQL/a11y observations; and `run_on_scratch.py` for DB and theme isolation.
`rebuild_verify.py` supports `--engines` and `--tempdb` for read-only engine checks.

## Phase 4 and handoff update

After GUI checks, run focused tests individually, then the isolated full runner if the session owner requests it. The
focused results above do not count as rebuild or GUI verification. Check S03
contract expectations and S06 year handling, then update the table above with observed counts, exact log paths, exits,
and independent SQL results. Re-run the relevant failed scenario after a fix.

Finally run `rebuild_p5_collect.py`, compare live DB fingerprints around all R scripts, verify private source hashes,
check theme preferences, and ensure the real DB passes integrity check. Record unresolved findings with reproduction
evidence. Keep the hard-refresh result provisional until the key-loss suspicion is reproduced or ruled out and the
known DOB/People-tab coverage gap is directly addressed.
