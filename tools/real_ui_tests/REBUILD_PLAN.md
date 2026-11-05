# Fresh rebuild and real-UI runbook

**Updated:** 2026-11-05. Read `docs/VISUAL_TESTING_GUIDE.md` first for product purpose, FD Planner limits, expected source
figures, and safety rules. This file is the current execution checklist. Do not rely on prior run claims unless a matching
log or independent measurement exists.

## Current status

| Work | Status |
|---|---|
| Live `data/financial.db` | **Paused at owner's request after Jana.** Setup, person, four banks/accounts, and Jana import passed (exit 0). Do not reset again. |
| P0 document preflight | **Passed, exit 0.** `screenshots/rebuild/P0_repair_20261105.out`. Fixed PDF row grouping recovers one Equitas debit; Ujjivan blank balances reconcile between printed anchors. |
| Focused checks | Private sources 3, password readers 7, preflight 46, FD provenance 34, PDF rows 5, real statement package 10, P5 collection 22 passed. Collection log: `screenshots/rebuild/collection_verified.out`. Other logs: `resume_focused/`, `password_review_verified.out`, `row_repair_verified/`. |
| Remaining imports | IDFC FIRST, Ujjivan, Equitas, then 26AS/AIS/TIS are pending. All Phase 3 runs remain pending. |
| Unity seven-row mini statement | Explicitly deferred; no opening/running balances. |
| S03 income contract and S06 FY behavior | Harness repaired and source-reviewed; GUI verification pending. |
| Hard refresh | Pending. Reproduce suspected session-key loss; keep key/FY preservation assertions. |

P0 and the reviewed parser repair passed before deletion. Run logs, screenshots, expectation files, fingerprints, and progress records live under the ignored
`tools/real_ui_tests/screenshots/` tree. Preserve any existing contents. Before starting, inspect `git status --short` and
leave unrelated or staged work untouched.

### Exact pause checkpoint and next command

Independent audit `screenshots/rebuild/checkpoint_20261105.json` passed: Person 1, Bank 4, BankAccount 4,
AccountHolder 4, BankFDConvention 4, Transactions 65, FixedDeposit 14, StatementImportLog 1, tax imports 0.
Every Jana date/type/amount/balance matches the freshly parsed source; closing balance is INR 1,506.80.
All 14 FD opening links validate. SQLite integrity is `ok`, foreign-key violations 0, all 13 private hashes match,
and original theme preferences were restored. Each completed GUI log is `screenshots/rebuild/P2_*_20261105.out`.
Latest rebuilt snapshot: `backups/rebuild_20261104T192018Z_P2_4_Jana.db` (filename uses UTC).

On resume, check this checkpoint, source hashes, and absence of another app process. **Do not delete the DB or
repeat setup.** Continue with the next command, then Ujjivan, Equitas, tax documents, and P2.8 in order:

```powershell
$env:QT_QPA_PLATFORM='windows'
$env:PYTHONUTF8='1'
.venv\Scripts\python.exe -u tools\real_ui_tests\rebuild_p2_4_statement.py --bank "IDFC FIRST" *> tools\real_ui_tests\screenshots\rebuild\P2_4_IDFC_resume.out
```

Full `rebuild_postflight.py` is prepared for all four statements and tax imports; it intentionally cannot pass this
partial checkpoint. It and the revised P3 scripts have not been run end to end. The full isolated suite and final
P5 collection after the remaining imports and UI runs are pending. The collector's focused tests passed (22); the
master is retained in ignored `screenshots/rebuild/credentials.local.json`.

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

Full sequence for reference follows; setup through Jana is **already complete**. Resume at IDFC FIRST:

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

The P2.5_7 script imports 26AS, AIS, and TIS. P2 steps create snapshots and update ignored progress records. After P2.8, check
transaction counts, account balances, tax-document rows, FD `source_transaction_id` provenance, and SQLite integrity
independently. Save a post-build fingerprint. Compare all 13 protected-file hashes with the prepared manifest and
restore the prior theme preferences if a script changed them.
Run `.venv\Scripts\python.exe tools\real_ui_tests\rebuild_postflight.py` after all imports; it is a read-only
row-by-row ledger/tax audit. FD provenance remains the P2.8 check.

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
| `rebuild_p3_10_topbar.py` | navigation, person/account/FY selectors, logout/relogin |
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
