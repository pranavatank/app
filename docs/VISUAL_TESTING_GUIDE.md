# FD Planner and real-data testing handoff

**Updated:** 2026-11-08. Read this guide, then `tools/real_ui_tests/REBUILD_PLAN.md` before continuing the rebuild.
This is a concise handoff for a fresh agent; old investigation history belongs in Git and ignored run logs.

## Product and data model

This is an offline-first PySide6 personal finance app backed by local SQLite. It helps the owner predict current-year
income early enough to plan around tax and TDS. The FD Planner is a full dashboard page opened from the sidebar or
Fixed Deposits page. It groups a planning tree by family, person, bank account, FD tenure, and ready cash; the user can
pause, pan, zoom, and use privacy mode. See [`FD_PLANNER.md`](FD_PLANNER.md) for implementation detail.

Keep the two data purposes distinct:

| App-owned records | ITR-side records |
|---|---|
| Statements, FDs, and income expectations describe the owner's model and support prediction. | 26AS, AIS, and TIS come from the Income Tax Department and are accepted as reported; use them for comparison. |

Statement-derived income can be lower than AIS because FD interest may stay in the deposit and never appear in a
savings statement. Describe that plainly as under-reporting in our inputs; do not call it an error or silently alter
ITR-side values. For taxable-income totals use `TAXABLE_INCOME_CATEGORIES` in `engines/prediction_engine.py`, not all
transactions with `transaction_type='Income'`. FD maturity principal and transfers are not automatically taxable.

## FD Planner behavior and limits

- Main code: `ui/fd_planner_screen.py`, `ui/widgets/family_money_tree.py`, `engines/family_workbook.py`,
  `engines/official_bank_rates.py`, `engines/family_fd_engine.py`, and `engines/fd_planner_math.py`.
- It reads the current workbook at `data/data/Data 26-27.xlsx`. Statement and tax PDFs are under
  `data/data/Pranav/`, with `data/PersonalData/Pranav/` as the tools' legacy fallback. All private sources are read-only.
- Bank quotes are fetched from official bank publications and cached locally for 24 hours. Missing or ambiguous rates
  must remain unavailable; never replace them with a comparison-site rate or an old quote. Unity savings bands have an
  unverified calculation basis and are excluded from optimization.
- The optimizer uses general-customer rates and the fixed ordinary new-regime parameters currently supported by the
  family model. It does not yet consume editable `TaxParams`/`TaxSlabConfig`; future tax years assume continuity.
  Family pooling, ownership, and HUF treatment are conditional. No declaration eligibility or tax result is certified.
- Reserve cash, bank concentration, modeled insurance, annual income/interest limits, and retained cash constrain the
  plan. Future income and FD maturities are shown separately from spendable cash today. Missing balances or FD terms
  remain visibly incomplete. A timed-out solve is best found with a gap, not a proven optimum.
- The 26-Oct actual-workbook audit found a 4.13% search gap and preserved the reserve; treat it as a historical
  scenario, not a current guarantee. Refresh rates and remeasure before relying on any plan.

## Rebuild facts and source expectations

The authorized fresh rebuild uses four statement PDFs, then 26AS, AIS, and TIS through their separate import flows.
Verified corrected parser counts are Jana 65, IDFC FIRST 376, Ujjivan 27, Equitas 39 (507 total). The row-grouping
repair recovered an omitted INR 100,000 Equitas debit. Two blank Ujjivan balances derive zero between printed anchors.
26AS has 158 records and net TDS INR 13,367 for FY 2025-26 / AY 2026-27. AIS/TIS identify FY 2025-26; both report
dividends 2,655, savings interest 46,183, FD interest 256,642, and business receipts 105,069; AIS TDS is 12,073.
AIS JSON and the two Form16A PDFs are not imported by the existing PDF flow. DOB is 2004-03-08.

Equitas source has 5 detected FD openings totaling INR 500,000. The historical redemption expectation was
9 matured placeholders with principal INR 850,000 and interest INR 91,590; remeasure it after import. Unity's
seven-row mini-statement has no opening or running balances, so it is deferred and must
not be imported into the ledger until reliable balances are available.

**Updated 2026-11-07.** The full rebuild is complete. The ignored bank checkpoint records every source row's date,
type, amount, and balance matching across Jana (65), IDFC FIRST (376), Ujjivan (27), and Equitas (39), with account
closing balances matching. All 19 FD openings and 9 redemption records pass provenance checks. The 28 FDs are: Jana
14 Pending Details / INR 1,300,000; Equitas 5 Pending Details / INR 500,000 and 9 Matured / INR 850,000 principal /
INR 91,590 interest. 26AS imported 158 FY 2025-26 records with INR 13,367 net TDS; AIS and TIS imported, both for
FY 2025-26, with expected amounts. The saved tax-document password decrypts successfully. `rebuild_postflight.py`
passed with zero failures, verifying all 507 strict transaction row multisets plus accounts and tax records. See
ignored `tools/real_ui_tests/screenshots/rebuild/postflight_20261106.out` and `postflight.json`. Integrity is `ok`,
foreign-key violations are 0, and all 13 private-file hashes match. Latest snapshot:
`backups/rebuild_20261106T101846Z_P2_5_7.db`. Do not reset. All eleven completed P3 read-only reports pass 283/283
recorded assertions; the runbook lists counts and paths. This records R-mode coverage only, not the mutating flows.
The P3.12 final run passed 38 checks, including the clipped-target case and unchanged database fingerprint. S00
Overview passed; S01 Accounts passed 26/26; S02 Transactions passed 41/41. S03 Income passed 58/58, its focused
edit/link/unlink/delete run passed 15/15, and the picker plus geometry tests passed 3/3. S04 Fixed Deposits passed
19/19 (`P3_04_fixed_deposits_S.json`, `P3_04_fixed_deposits_S_verified_20261107.out`). Independent checks confirmed
live FD/transaction IDs 28/507, exact ID sets restored after scratch, and integrity `ok`. S05 Statement Import passed
53/53 (`P3_05_statement_import_S_settingsfix_20261107.out`). Nov 8 native S-mode milestones: S06 tax documents
passed 9/9 after the header fix (`P3_06_tax_documents_S_headerfix_20261108.out`); S07 tax passed 10/10
(`P3_07_tax_S_expanded_20261108.out`); S09 settings passed 33/33 (`P3_09_settings_S_20261108.out`). The focused
source-year tests passed 13/13 (`full_suite_20261108/test_taxdoc_source_year.py.log`). The real AIS+TIS parser passed FY2025
(`S06_parser_fixed_20261108.out`). The S06 regression now excludes historical body-page FY mentions using first-page
metadata while still rejecting conflicting header years. The live DB fingerprint matched its baseline
(`tax_milestone_compare_20261108.out`). S13 People passed 10/10 on fresh scratch
(`P3_13_people_S_20261108.out`); its synthetic add/edit DOBs were 1994-03-08 and 1996-11-23, and independent SQL
confirmed the owner's DOB 2004-03-08 was unchanged. Native R11 hard refresh passed 55/55
(`P3_11_hard_refresh_R_preserved_20261108.out`) with its built-in live DB fingerprint guard unchanged. The refresh
preserves session identity, key, and FY while excluding venv dependencies. Session reload passed 1 test
(`session_reload_20261108.out`), selector/module eligibility passed 6 (`hard_refresh_modules_20261108.out`), and Sol
review found no blockers. The isolated baseline suite passed across 69 files: 735 passed and 8 skipped
(`full_suite_20261108.out`). The skips are 5 explicit full-DB/session-parity placeholders, 1 legacy 26AS interface
placeholder, and 2 statement-flow cases without a person fixture; the native S05 import flow already passed 53/53.
After the final formatter change, the affected regression set passed 23 tests (money 16, hard-refresh selector/module
6, session reload 1; `final_regressions_20261108.out`). This is a targeted rerun, not a post-change rerun of all 69
files. P4 engine/tempdb verification exited 0 with zero JSON failures (`P4_engine_tempdb_fixed_20261108.out`); H12's
deliberately tampered ciphertext remained unchanged and was skipped as expected. P5 exited 0 with 23 current reports,
zero failures, zero watchdog issues, 6 accessibility lookup observations (not confirmed defects), and 77 observations
(`P5_final_20261108.out`). The live DB and preferences matched the `resume_20261108_before` baseline. Final audit
confirmed all 13 private hashes, exact theme preference bytes, SQLite integrity and foreign keys, 507 transactions,
28 FDs, unchanged owner DOB, and syntax for changed files (`final_audit_20261108.out`). Full database fingerprints
matched between `resume_20261108_before` and `complete_20261108` (`final_compare_20261108.out`). Sol's final-delta
review found no blockers. Unity remains explicitly deferred; the bank-rate, tax-policy, and partial manual-coverage
limits described above still apply.

**Nov 7 UX work — completed.** Toast tests passed 13/13 (`notifications_final_20261107.out`) and focus tests passed
9/9 (`ux_finish_20261107/test_theme_qss.py.log`). Broader theme checks passed 26/26 (`ux_theme_checks_20261107.out`).
Native Windows checks passed for Aurora and Nova: timer expiry, worker-thread delivery, click-through outside the
toast, and modal handoff (`ux_native_integration_20261107.out`). Final Aurora/Nova Windows previews also verify
wrapping of the full short danger message at a 38px viewport without a scrollbar. Accepted previews are
`ux_notifications_aurora_final.png`, `ux_notifications_nova_final.png`, and `ux_modal_*_final.png` under
`tools/real_ui_tests/screenshots/rebuild/`. Toasts use FIFO queues, natural height, 3/5/7-second durations, hover pause,
and survive modal handoff. Simple acknowledgement message boxes use toasts; confirmations and TOTP remain modal.
Focus uses rounded outer borders without an inner native rectangle and remains keyboard accessible, including a
distinct focused-selected-tab state in light and dark themes. Independent final review approved the repaired queue;
there are no outstanding UX blockers. This completion is specific to the UX work and does not change the remaining
rebuild coverage listed above. Final audit confirmed all 13 private source hashes unchanged, theme preferences
byte-identical, and AST parsing passed for all 11 changed Python files. The live database fingerprint matched before
and after UX work (`ux_complete_compare_20261107.out`).

## Safety and working rules

- Work on `main` in this checkout. Preserve staged and unrelated changes. The owner authorized commits of completed
  batches; the coordinating agent owns staging and commits.
- Never run `tools/backfill_transactions.py`. Do not redesign schema, authentication policy, or tax policy as part of
  this rebuild. Do not modify source documents, `theme_prefs.original`, or the verified backup.
- Before resetting, confirm the recorded backup exists and is readable; only the explicitly named database files and
  sidecars may be removed. Never use wildcards. Rebuild steps and all mutating UI walkthroughs must be sequential.
- Real-UI scripts use the real mouse and keyboard. Do not run another UI process or heavy test workload alongside
  them. Check each exit code and independently inspect SQL/fingerprints; screenshots and script PASS lines alone are
  insufficient.
- R mode must not change the real DB. S mode must use
  `tools/real_ui_tests/run_on_scratch.py --fresh ... --env S`. Never pass `--real` or point a scratch test at the live DB.
- Secrets come from `FINMGR_MASTER_PASSWORD_FILE` when configured, then ignored `credentials.local.json`, then source
  labels through `rebuild_common.read_secret`. Never print, log, hardcode, or put credentials on a command line.
- Keep screenshots and logs under ignored `tools/real_ui_tests/screenshots/`. Do not commit `data/`, `backups/`, DB
  files, or screenshots. Keep `pyautogui.FAILSAFE` enabled.

## Useful commands and sources

Run from the repo root in PowerShell, one command at a time. The venv is `.venv\Scripts\python.exe`.

```powershell
# Read-only document preflight (required before reset)
.venv\Scripts\python.exe tools\real_ui_tests\rebuild_p0_expectations.py --defer-unity

# Focused tests: run individually to isolate Qt/native failures
.venv\Scripts\python.exe -m pytest tests\test_private_sources.py -q
.venv\Scripts\python.exe -m pytest tests\test_taxdoc_passwords.py -q
.venv\Scripts\python.exe -m pytest tests\test_rebuild_preflight.py -q
.venv\Scripts\python.exe -m pytest tests\test_rebuild_fd_provenance.py -q
.venv\Scripts\python.exe -m pytest tests\test_rebuild_collection.py -q

# Independent DB checks; use after rebuild or against a named backup as appropriate
.venv\Scripts\python.exe tools\rebuild_verify.py --engines --tempdb
.venv\Scripts\python.exe tools\rebuild_verify.py --fingerprint --out before_p3
```

The source resolver is `tools/private_sources.py`. Preflight and ledger/year validation are in
`tools/real_ui_tests/rebuild_preflight.py`; P0 parses expected source facts without importing into the DB. Rebuild
helpers are in `rebuild_common.py`, per-screen checks in `rebuild_p3_common.py`, and scratch isolation in
`run_on_scratch.py`. The runbook is authoritative for exact sequence and current checkpoint.

The P5 collector requires current P3 files with nonempty boolean-result lists and compares fingerprint row counts and
hashes across the full table set. A requested baseline that is missing, invalid, or mismatched fails collection.
Review policy: Sol medium for planning and review; Luna medium for implementation, with a focused collection test.
