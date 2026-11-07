# FD Planner and real-data testing handoff

**Updated:** 2026-11-07. Read this guide, then `tools/real_ui_tests/REBUILD_PLAN.md` before continuing the rebuild.
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
The P3.12 final run passed 38 checks, including the focused clipped-target case (group 4 to 6), actual plan/result,
and unchanged database fingerprint. S00 passed on a fresh scratch copy; its S report is `P3_00_overview_S.json`.
S01 Accounts passed 26/26 checks on scratch (`P3_01_accounts_S.json` and
`P3_01_accounts_S_passcheck_20261107.out`). Independent checks confirmed live IDs 4/507/28 and scratch IDs 5/507/28
for accounts/transactions/FDs, with database integrity `ok`; three click-point tests passed. S02 is next/in progress,
S02 Transactions passed 41/41 checks on fresh scratch (`P3_02_transactions_S.json` and
`P3_02_transactions_S_final_20261107.out`). Product commit `249691a` keeps the transaction dialog footer visible on
short screens with a scrollable form; its geometry tests passed 2/2. The date field still required the recorded
non-OS `setDate()` fallback, so physical date-entry coverage remains incomplete. S03 is next. Continue S03, S04, S05,
S06, S07, and S09 sequentially, with P3.11 hard refresh last; the full suite and P5 collection remain pending.

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
`run_on_scratch.py`. The runbook is authoritative for exact sequence and current pending status.

The P5 collector requires current P3 files with nonempty boolean-result lists and compares fingerprint row counts and
hashes across the full table set. A requested baseline that is missing, invalid, or mismatched fails collection.
Review policy: Sol medium for planning and review; Luna medium for implementation, with a focused collection test.
