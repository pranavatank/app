# Terminology Reference

This document establishes a single term for each concept in the application, ensuring consistent messaging across the user interface.

## Money In / Money Out

### Income (was: Credit)
- **Used for**: Transaction type representing money coming in
- **Where**: All transaction UI, filter dropdowns, charts, badges
- **Why**: "Income" is clearer and more universally understood than "Credit" (which has accounting/banking connotations). The database already stores this concept as "Income" transaction_type.

### Expense (was: Debit)
- **Used for**: Transaction type representing money going out
- **Where**: All transaction UI, filter dropdowns, charts, badges
- **Why**: "Expense" is clear and direct. The database already stores this concept as "Expense" transaction_type.

**Exception**: Bank statement columns during import (e.g., parsing a CSV with literal "Credit" / "Debit" column headers) may display the raw source column names as-is during column mapping previews.

## The Human

### Person (was: Family Member)
- **Used for**: A single individual being tracked
- **Where**: Form labels, dialogs, combo boxes, headings
- **Why**: "Person" is simpler, shorter, and more inclusive. Avoids outdated "family" framing.

### People (was: Family Members)
- **Used for**: Plural or collective reference to individuals
- **Where**: Section titles, button labels, dialog titles
- **Why**: Grammatically correct plural of "Person"; replaces "Family Members" everywhere except documented exceptions.

### Manage People (was: Manage Family / Manage Family Members)
- **Used for**: Action label for the person management interface
- **Where**: Settings screen, button labels
- **Why**: Consistent with "Person" terminology.

**Exception**: "Taxpayer" is retained only in `ui/tax_screen.py` (e.g., "Name of Taxpayer", "Taxpayer Category") where it is a legal term of art for tax reporting.

## Running Balance

### Balance (was: Balance After)
- **Used for**: The account balance at a point in time (typically after a transaction)
- **Where**: Transaction table headers, form labels, dialogs
- **Why**: "Balance" is concise and unambiguous; "Balance After" is redundant and verbose.

### Current Balance
- **Used for**: The present/latest account balance
- **Where**: Account details, account cards, summary screens
- **Why**: Clearly distinguishes from historical transaction balances; already consistently used in accounts_screen.py.

## Fixed Issues

### "Salary & Pension Income" (fixed from: Salary_Pension Income)
- Already corrected; uses ampersand (&) instead of underscore for display.

### "Link Transfers" (was: Reprocess Data)
- **Used for**: The button that detects and links matching transfers between accounts
- **Tooltip**: "Detect and link matching transfers between accounts"
- **Why**: "Link Transfers" accurately describes the function (establishing transfer links). The old label "Reprocess Data" was vague and did not communicate intent to users.

---

## Test Coverage

The suite `tests/test_terminology.py` validates that retired terms do not appear in user-facing strings within `ui/**/*.py` files, with documented exceptions:
- Retired terms in `ui/tax_screen.py` matching the "Taxpayer" legal-term exception are excluded.
- Bank statement column headers during import are excluded (raw source data).
