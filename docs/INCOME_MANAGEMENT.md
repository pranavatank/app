# Income Management Feature

## Overview
The Income Management screen allows you to track expected income (salary, dividends, etc.) and link them to actual transactions when received.

## Features

### Expected Income Tracking
- Set expected income with:
  - Income type (Salary, Dividend, Interest, Rental, Business, Other)
  - Expected amount
  - Expected date
  - Frequency (Monthly, Quarterly, Half-Yearly, Yearly, One-Time)
  - Target account
  - Notes

### Expected vs Actual Comparison
- View expected and actual amounts side-by-side
- Calculate variance (difference between expected and actual)
- Track status:
  - **Pending**: Expected date not yet reached, not received
  - **Received**: Linked to actual transaction
  - **Overdue**: Expected date passed, not received

### Summary Dashboard
- **Expected Total**: Sum of all expected income
- **Actual Received**: Sum of all received income
- **Pending**: Sum of income not yet received
- **Variance**: Difference between actual and expected (excluding pending)

### Link Actual Transactions
- Link expected income to actual income transactions
- Prevents duplicate linking
- Shows only unlinked transactions
- Unlink if needed

### Filters
- Filter by person
- Filter by financial year
- Filter by income type
- Filter by status (All, Pending, Received, Overdue)

## Usage

### Adding Expected Income
1. Click "＋ Add Expected Income"
2. Select person and account
3. Choose income type
4. Enter expected amount and date
5. Select frequency
6. Add optional notes
7. Click "Add"

### Linking Actual Transaction
1. Select an expected income entry
2. Click "🔗 Link Actual"
3. Select the matching transaction from the list
4. Click "OK"

### Editing Expected Income
1. Double-click an entry or select and click "✏ Edit"
2. Modify details
3. Click "Save"

### Deleting Expected Income
1. Select an entry
2. Click "🗑 Delete"
3. Confirm deletion

## Database Schema

### IncomeExpectation Table
- `expectation_id`: Primary key
- `person_id`: Foreign key to Person
- `account_id`: Foreign key to BankAccount
- `income_type`: Type of income
- `expected_amount`: Expected amount
- `expected_date`: Expected date
- `frequency`: Frequency of income
- `financial_year`: Financial year
- `actual_transaction_id`: Foreign key to Transactions (nullable)
- `notes`: Optional notes
- `created_at`: Creation timestamp

## Navigation
Access via: Dashboard → 💰 Income Management (4th item in sidebar)
