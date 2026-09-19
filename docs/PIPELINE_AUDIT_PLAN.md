# Pipeline Audit Plan — extraction quality, linkage, reconciliation, charts

All numbers below were MEASURED on the real documents/DB, not assumed.

## Verified ground truth (2026-09-19)

### Two statement parsers exist; the UI uses the worse one
| statement | modern `engines.statement.parse_statement_pdf` | legacy `engines.statement_parser.parse_statement_with_debug` (USED BY UI) |
|---|---|---|
| Jana     | rows 65,  conf **1.000**, badbal 0, refs **0/65**  | conf 0.640, badbal 39, refs 61/65 |
| IDFC     | rows 376, conf **1.000**, badbal 0, refs 343       | rows 377, conf 0.730, badbal 5, refs 358 |
| Ujjivan  | rows 27,  conf **1.000**, badbal 0, refs 22        | conf 0.409, badbal 4 |

The earlier "amounts off by one row" diagnosis was WRONG — it was an artifact of
walking a reverse-chronological list. Modern calls `normalise_order()` first;
legacy does not, and `ui/statement_import_screen_modern.py` re-runs
`confidence()`/`balance_walk()` on a descending list, which is why the 0.9 import
gate misfires.

Modern is NOT a drop-in swap: it loses `reference_no` on Jana (0/65 vs 61/65),
one IDFC row, and some balances. The work is to port legacy's ref/balance
extraction onto modern, then point the UI at modern.

### Passwords are on disk — do not prompt, do not brute-force
`data/PersonalData/Pranav/password.txt` (gitignored): AIS/TIS `azipt9702h08032004`,
Equitas `0803PRA`. PAN `AZIPT9702H` (confirmed inside 26AS). Never commit these.

### 26AS extraction is badly broken — this is the number the owner wants
Ground truth measured from the real PDF text:
- 6 deductor summary rows; 211 line items (194A x206, 194JB x4, 194JA x1)
- status flags: 177 normal, 25 `B` reversals, 9 `G` reversals
- NET gross 350458.00, **NET TDS 13367.00**; positive-TDS rows 50 summing 17710.00
- Per deductor: Enlightvision 105069/10508 · Jana 2859/2859 · Equitas 19397/0 ·
  Jana(15G/H) 90745/0 · Equitas(15G/H) 53311/0 · Ujjivan 79077/0

`engines/taxdocs/form26as.py` returns: `total_tds` **13367.0 (CORRECT)**, but only
**49 records** of 211, and every record has `tax_deducted=None`, `deductor_name=''`,
`tan=None`. Sum of per-record tax_deducted = **0.00**. Header (pan/name/AY) is fine.
So: header good, per-line detail broken.

### Real DB state
person_id=1 'Soon-to-be Senior', dob 1965-04-15, **pan_number NULL**;
1 BankAccount ('Test Bank'), 1 FD, 0 Transactions, 0 Bank rows, no tax imports.
No real accounts exist for Jana/IDFC/Ujjivan/Equitas.

`data/PersonalData/` and `data/*.db` are BOTH gitignored — verified.

## Units

| # | Unit | Mode | Window | Depends |
|---|---|---|---|---|
| 1 | Statement parser convergence (port refs/balances to modern, point UI at it) | PARALLEL | No | — |
| 2 | 26AS per-record fix + encrypted AIS/TIS/Equitas password path | PARALLEL | No | — |
| 3 | Dark-theme static audit of the two base screens | PARALLEL | No | — |
| 4 | Real accounts + real imports + FD/income linkage | SEQUENTIAL | **Yes** | 1,2,3 |
| 5 | Tax reconciliation vs 26AS/AIS/TIS | SEQUENTIAL | **Yes** | 4 |
| 6 | Charts + Transactions/FD screens vs DB aggregates | SEQUENTIAL | **Yes** | 5 |
| 7 | Consolidation | SEQUENTIAL | No | 1-6 |

Units 4-6 each take over the screen and MUST NOT run concurrently.

## Ground rules
- Back up `data/financial.db` before any writing unit; restore = copy back, app closed.
- Never commit `data/PersonalData/**`, `data/financial.db`, the passwords or the PAN.
- UI tests: `tools/real_ui_test_harness.py`; read `docs/VISUAL_TESTING_GUIDE.md`
  (§3.4 scroll, §3.5 cross-check widget state not screenshots, §3.8 pre-arm
  `QTimer.singleShot(0, cb)` before a modal, §6 new-test rules). Real maximized
  window, UTF-8 stdout, always-runs teardown. `findChildren()` takes ONE type.
- Do not regress: `_GuiRelay`/QueuedConnection in `ui/widgets/loader.py`;
  `SHOW_METADATA_DIALOG = False`; no page-fade on navigation.
- Every parser fix must cite PDF evidence and be RE-MEASURED after the change.
