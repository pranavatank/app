# Income Prediction Screen — Plan

## The mental model (the owner's, and the whole design rests on it)
TWO kinds of data, never conflated:
- **OUR DATA** (statements, FDs, expectations) — PREDICTS this FY's income so the
  owner can ACT: prevent TDS and stay under the 12,00,000 rebate limit.
- **ITR-SIDE DATA** (26AS/AIS/TIS) — immutable facts. Extract and accept. Only
  ever COMPARED against our prediction.
Our number being LOWER than AIS is EXPECTED, not an error: most FD interest is
credited inside the FD and never appears as a savings-account transaction.
The words "gap", "mismatch" and "error" must not appear in that comparison UI.

## MEASURED facts (verified on the real DB, 2026-09-19)
Income rows, FY 2025-26, by category:
| category         | rows | amount        | taxable? |
|------------------|------|---------------|----------|
| Other Income     | 166  | 5,258,725.21  | NO - self-transfers between the owner's own 4 banks |
| FD Maturity      | 11   | 1,141,366.00  | NO - principal returning |
| FD Interest      | 9    | 91,590.00     | YES |
| Savings Interest | 3    | 4,001.00      | YES |

**Genuinely taxable income: 95,591.00, not 6,495,691.**
`is_internal_transfer` is 0 on ALL 506 rows, so it is USELESS as a filter.
Classification MUST be by category. A naive SUM(Income) reports 64.9L against a
12L limit and makes the screen worse than useless.

FDs: 20 rows, 2,700,000 principal. 19 are status 'Pending Details' (no rate, no
maturity, no tenure) - Jana 14, Equitas 5. The 20th (fd_id 1) belongs to a
leftover 'Test Bank' account, has rate 8.0, and owns all 6 FDInterestRecord rows.
Owner's decision: use DEFAULT_FD_RATE = 7.5 for FDs with no rate, and VISIBLY MARK
every figure derived from it.

ITR-side DB tables (Form26ASImport, Form26ASRecord, AISTISImport,
AISTISImportRecord) are ALL EMPTY. The 26AS/AIS/TIS numbers quoted elsewhere came
from parsing the PDFs directly. So the ITR panel's correct default is
"Not imported yet - import on the Tax Documents screen." Do NOT parse PDFs here.

Tax config lives in the DB, do not hardcode: TaxParams rebate_87a_limit 1200000,
fd_tds_threshold 50000, standard_deduction 75000, cess 4%. TaxSlabConfig has the
new-regime slabs per FY.

## Engine hazards found by inspection
- `fd_interest_for_fy()` CRASHES on a NULL maturity_date (19 of 20 FDs).
  Use `fd_interest_accrued_to()` on a SYNTHESISED COPY of the FD with rate and
  maturity filled in. Never mutate the original dict.
- `interest_engine.fd_tds_threshold_status()` reads FDInterestRecord, which only
  has Test Bank rows. Do not reuse it; compute per-bank from FixedDeposit and
  mirror only its output shape.

## Units
| # | Unit | Mode | Window | Depends |
|---|---|---|---|---|
| 1 | engines/prediction_engine.py | SEQUENTIAL (first) | No | - |
| 2 | tools/test_prediction_engine.py | PARALLEL w/ 3 | No | 1 |
| 3 | ui/income_prediction_screen.py | PARALLEL w/ 2 | No | 1 |
| 4 | Nav wiring (dashboard_screen, icons, theme) | SEQUENTIAL | No | 3 |
| 5 | Verify in the running app + dark theme | SEQUENTIAL (last) | YES | 4 |

## Nav wiring specifics
Insert "Income Prediction" BETWEEN Tax and Settings -> Tax 7, Income Prediction 8,
Settings becomes 9. Required edits:
- ui/icons.py `_R`: "income_prediction": ("mdi6.chart-timeline-variant", "default", emoji)
- ui/theme/theme.py SCREEN_ACCENTS: "income_prediction" (else screen_accent silently
  falls back to PRIMARY)
- ui/dashboard_screen.py: _NAV_ITEMS, the screen_key map, the lazy page builder
  (renumber Settings), AND add the new page to the theme-refresh tuple (~line 403).
  Omitting that last one is the SILENT dark-mode bug: dashboard calls
  page.refresh_theme() inside `except Exception: pass`.
- tests/test_dashboard_lazy.py may assert nav counts and will need updating.

## Screen requirements
Three views: (1) headroom to 12L, (2) per-bank projected interest vs the 50,000
FD TDS threshold, (3) month-by-month timeline. Plus the two-sided
"OUR PREDICTION" vs "ITR-SIDE ACTUALS" comparison. Estimated figures marked
consistently. MUST define refresh_theme() covering every chart and table.
setAccessibleName on every interactive control. All work via Loader.run.
Architecture must leave room for a later advisory/strategy layer; a simple
rules-based advisory is in scope now, clearly labelled as guidance.
