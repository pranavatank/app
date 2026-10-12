# FD Planner

## Overview
The FD Planner helps decide **where to put spare savings**. It shows current bank FD rates and suggests how to split an amount across banks so that:

- the money earns the highest available rate, and
- no person ever holds more than the **DICGC insured limit (₹5,00,000 per depositor per bank)** at any one bank, counting savings, FDs and interest together.

Money that doesn't fit safely into insured bank FDs is pointed to **government-backed schemes** (Post Office, NSC, SCSS, RBI bonds), which have no insurance cap.

Open it from **Fixed Deposits → FD Planner** (header button). It is a dialog with three tabs: **Split Savings**, **My Coverage** and **Other Safe Options**.

## Features

### Split Savings tab

**Current FD rates**
- Table of banks with their highest rate, 1-year, 3-year and 5-year rates, and the extra rate for senior citizens.
- The best rate for each tenure is highlighted in green. Click any column header to sort.
- **Use** checkbox: untick banks you don't want to use (no account, don't trust them, etc.). The choice is remembered.
- **Refresh Rates** fetches the latest table from the web (runs in the background). **Open Source** opens the page in the browser. **Change Source…** points the app at a different page.
- The line above the table shows the source, the date of the rates, and a warning when they are a built-in snapshot or older than 30 days.

**Plan your split**

| Input | Default | Meaning |
|---|---|---|
| Person | Selected person, or *All family members* | *All family members* splits across everyone; each person gets their own ₹5 lakh cover per bank |
| Amount to invest | — | The amount to place in FDs |
| Use My Savings | — | Fills the amount with savings balances minus *Keep aside* |
| Keep aside | ₹1,00,000 | Emergency money to leave in savings |
| Tenure | 1 year | 1, 3 or 5 years |
| Max banks per person | 5 | Upper limit on how many banks each person uses |
| Min per bank | ₹10,000 | Banks with less insured room than this are skipped |
| Insured limit per bank | ₹5,00,000 | DICGC cover; change only if the official limit changes |
| Senior citizen rates | From date of birth | Adds the bank's senior premium. In family mode it is applied per person automatically |
| Include small finance banks | On | Small finance banks are DICGC-insured but some people prefer to avoid them |
| Count my existing deposits | On | Subtracts savings and FDs already held at each bank from the room left |
| Keep interest within insured limit | On | Caps the principal so the **maturity value** stays within the limit |

**Results**
- KPI tiles: amount invested, weighted rate, total interest, and extra interest compared with the average listed rate.
- Table: Person, Bank, Rate, Invest, Interest, Maturity Value, Matures On, Already at Bank, Insured After, Note.
- Notes flag **TDS likely — submit Form 15G/15H** when a bank's yearly interest for that person would cross the TDS threshold (₹50,000, or ₹1,00,000 for senior citizens), and **Above insured limit** if that ever happens.
- Warning banner when part of the amount could not be placed, listing skipped banks and the best government-backed scheme for the rest.
- **Copy Plan** copies the split (tab-separated, with a total line) to paste into a note or spreadsheet.

### My Coverage tab
For each person and bank: savings, FDs (at maturity value), total, room left, % used and a status:

- **Over limit** (red): above the insured limit; the summary shows how much is uninsured.
- **Near limit** (amber): 90% or more used; put new deposits elsewhere.
- **Within limit** (green).

### Other Safe Options tab
Government-backed alternatives with their rate, lock-in, eligibility, maximum, tax treatment, and the projected interest for the amount entered on the Split Savings tab:

| Scheme | Rate | Lock-in | Limit | Notes |
|---|---|---|---|---|
| Senior Citizens Savings Scheme (SCSS) | 8.20% | 5 years | ₹30 lakh | 60+ only; quarterly payout; 80C |
| Sukanya Samriddhi Yojana (SSY) | 8.20% | 21 years | ₹1.5 lakh/yr | Daughter under 10; tax-free |
| RBI Floating Rate Savings Bond | 8.05% | 7 years | No limit | Resets every 6 months (NSC + 0.35%) |
| National Savings Certificate (NSC) | 7.70% | 5 years | No limit | Compounds yearly; 80C |
| Post Office Time Deposit – 5 years | 7.50% | 5 years | No limit | 80C |
| Kisan Vikas Patra (KVP) | 7.50% | 9 years 7 months | No limit | Money doubles |
| Post Office Monthly Income Scheme | 7.40% | 5 years | ₹9 lakh single | Monthly payout |
| Post Office Time Deposit – 3 / 2 / 1 year | 7.10 / 7.00 / 6.90% | 3 / 2 / 1 years | No limit | |
| Public Provident Fund (PPF) | 7.10% | 15 years | ₹1.5 lakh/yr | Tax-free; 80C |

Rates are for the **Oct–Dec 2026** quarter. SCSS is shown only when a senior citizen is selected. Schemes that beat the best bank FD rate for the chosen tenure are highlighted. Select a row to see how it pays out.

## How the split is calculated
`suggest_household_allocation` in `engines/fd_allocation_engine.py`:

1. **Candidates.** Every (person, bank) pair where the bank has a rate for the chosen tenure, is ticked, and passes the small-finance filter. Each person's rate includes the senior premium if they are 60+.
2. **Order.** Highest rate first; ties go to the earlier person, then bank name. So the best bank is used for every family member before moving to the next bank.
3. **Room at each bank** = insured limit − what that person already holds there (savings + FDs at maturity value).
4. **Cap.** With *Keep interest within insured limit* on, the principal is reduced so that principal plus interest at maturity (quarterly compounding) stays within the room. Example: at 7.5% for 3 years, ₹5 lakh of room allows about ₹4 lakh of principal. The cap is rounded down to the nearest ₹1,000.
5. **Fill.** Skip the pair if the cap is below *Min per bank* or the person already uses *Max banks*; otherwise place `min(cap, amount left)`.
6. **Leftover.** Anything not placed is reported, together with the highest-rate government scheme whose limit can take the leftover and whose lock-in is no longer than the chosen tenure (`best_overflow_option`).

Because every placement has the same tenure and the only limits are per-bank caps, filling the highest rates first gives the maximum total interest.

Banks are matched to your accounts by a normalised name (`normalize_bank_key`), so "HDFC Bank Ltd", "HDFC Bank" and "HDFC" are the same bank, and "SBI" matches "State Bank of India".

## Data sources and storage

| Data | Source | Stored in |
|---|---|---|
| Bank FD rates | [Paisabazaar scheduled banks table](https://www.paisabazaar.com/fixed-deposit/scheduled-banks-fd-interest-rates/) (default; changeable) | `data/fd_rates_cache.json`; a dated snapshot is built into `engines/fd_rate_source.py` for first run and offline use |
| Rates source URL | User setting | `data/settings.json` → `fd_rates_source_url` |
| Unticked banks | User setting | `data/settings.json` → `fd_planner_excluded_banks` |
| Government scheme rates | [India Post](https://www.indiapost.gov.in/Financial/Pages/Content/Post-Office-Saving-Schemes.aspx), [RBI](https://www.rbi.org.in/scripts/BS_PressReleaseDisplay.aspx?prid=63065) | Constants in `engines/investment_options.py` |
| Insured limit | DICGC | `DICGC_INSURANCE_LIMIT` in `config.py` |
| Existing savings and FDs | App database (read-only) | Existing `BankAccount` and `FixedDeposit` tables |

- No database schema changes. The planner only reads accounts and FDs.
- The network is used **only** when *Refresh Rates* is clicked. Parsing uses the standard library (`urllib`, `html.parser`); no new dependencies.
- The rate parser finds the first HTML table with a "bank" column and at least one "1-year", "3-year" or "5-year" column, matching by header text, so another page with a similar table can be used via *Change Source…*.

## Keeping it current

| When | What to update |
|---|---|
| Every quarter (next: 1 Jan 2027) | Government scheme rates, `SCHEMES_PERIOD` and `SCHEMES_VALID_UNTIL` in `engines/investment_options.py`. The tab warns once the quarter has passed |
| Every 6 months (Jan, Jul) | RBI Floating Rate Savings Bond rate (= NSC rate + 0.35%) |
| Occasionally | Refresh `_BUNDLED_SNAPSHOT` in `engines/fd_rate_source.py` so first-run rates are recent |
| If the DICGC limit changes | `DICGC_INSURANCE_LIMIT` in `config.py` |
| If TDS thresholds change | `FD_TDS_THRESHOLD` / `FD_TDS_THRESHOLD_SENIOR` in `config.py` |
| If Refresh Rates starts failing | The source page layout probably changed; check its table headers, or switch source with *Change Source…* |

## Limitations
- The default source lists the ~19 highest-rate banks. Large banks such as SBI, HDFC and ICICI are not in it.
- Aggregator rates can lag the bank's own site. Always confirm the rate with the bank before booking.
- Existing balances come from the app's stored `current_balance`, so they are only as fresh as the last statement import.
- A joint account counts fully against each holder. This is conservative: DICGC actually treats joint accounts by holder order.
- Market-linked options (liquid or arbitrage funds, Treasury Bills) are mentioned but not projected, because their returns are not fixed.
- Reading a third-party page can break if the page is redesigned; the planner then keeps showing the last saved rates.

## Code map

| File | Responsibility |
|---|---|
| `engines/fd_rate_source.py` | Fetch, parse, cache and date the bank rate table; bundled snapshot |
| `engines/fd_allocation_engine.py` | Existing exposure per bank, insured-cap maths, household split, savings total, coverage report |
| `engines/investment_options.py` | Government scheme data, projections, best scheme for leftover money |
| `ui/dialogs/fd_planner_dialog.py` | `FDPlannerDialog`: tabs, rates table, inputs, results, Copy Plan |
| `ui/dialogs/fd_coverage_tab.py` | `CoverageTab`: My Coverage tab |
| `ui/dialogs/investment_options_tab.py` | `InvestmentOptionsTab`: Other Safe Options tab |
| `ui/fixed_deposits_screen.py` | *FD Planner* header button (`_on_open_planner`) |
| `config.py` | `DICGC_INSURANCE_LIMIT` |

## Tests
```
.venv/Scripts/python.exe -m pytest tests/test_fd_rate_source.py tests/test_fd_allocation_engine.py tests/test_investment_options.py tests/test_fd_planner_dialog.py tests/test_fd_coverage_tab.py tests/test_investment_options_tab.py -q
```
The tests cover HTML parsing, caching, staleness, cap maths, greedy order, family splits, senior rates, exclusions, TDS flags, coverage statuses, scheme projections and the dialog's behaviour. Network calls are mocked, and tests never write to the real `data/` folder.
