# Personal Offline Financial Management System

## Overview
A fully offline desktop application for managing personal and family financial data with comprehensive features for tracking income, expenses, investments, and tax calculations. User credentials (bank statement passwords and Income Tax portal passwords) are encrypted; the SQLite database itself is stored as plaintext and should be kept on an encrypted volume (BitLocker, FileVault, LUKS) if privacy from file-system access is important.

## ✨ Features

### Core Financial Management
- 👥 Multi-person financial management (family members)
- 🏦 Multi-bank account tracking
- 💰 Income & expense monitoring with categories
- 📊 Running balance calculations
- 🔄 Transaction management (add/edit/delete)

### Investment & Interest
- 🏦 Fixed Deposit (FD) management
- 📈 FD interest calculation (Monthly/Quarterly/Annual compounding)
- 💵 Savings interest estimation
- 📅 Financial year-wise (and quarter-wise) interest allocation
- 🔮 Maturity projections
- ⚠️ FD interest TDS-threshold reminder — flags, per bank and per quarter, when yearly FD interest crosses the ₹50,000 limit and which form to file to avoid deduction

### Tax Calculation
- 🇮🇳 Indian income tax calculation (New Regime)
- 🧾 87A rebate + 4% Health & Education cess
- 💳 Net payable / refund due — total liability minus TDS, TCS, advance tax and self-assessment tax already paid
- 📈 Next-year income projection vs tax slab — projected gross income (income expectations + real next-FY FD interest + carried-forward savings) and the ₹ headroom to the next tax bracket

### Statement Import
- 📄 PDF bank statement import
- 📊 Excel statement import
- 🤖 Automatic transaction extraction (rule-based parser + optional local AI, see below)
- 🏦 Automatic FD detection — booking and maturity/redemption transactions are recognised and turned into FD records
- 🔍 Duplicate detection
- 🏷️ Smart category suggestions

### AIS/TIS Import
- 📑 Import Annual Information Statement (AIS) from Income Tax portal
- 📋 Import Tax Information Statement (TIS) from Income Tax portal
- 🔄 Auto-extract salary, interest, dividend, rental income
- ⚖️ Compare actual (IT portal) vs expected (app) income data
- 📊 Visual comparison with difference highlighting
- 💡 Identify income discrepancies for tax filing

### Reports & Analytics
- 📈 Income vs Expense charts
- 🥧 Category-wise expense breakdown
- 🏦 Bank-wise balance distribution
- 📊 Interest earnings trends
- 📅 Multi-year comparisons

### Security & Privacy
- 🔐 Master password authentication (PBKDF2, 100K iterations)
- 🔒 Encrypted credential fields (bank statement & Income Tax portal passwords)
- 📱 Device binding
- 🔑 Optional TOTP (2FA)
- 👁️ Privacy mode (mask all amounts)
- 💾 Backup & restore (plaintext copy of database)

## 🛠️ Technology Stack

- **Language**: Python 3.10+
- **UI Framework**: PyQt6
- **Database**: SQLite (plaintext, recommended on encrypted volume)
- **PDF Parsing**: pdfplumber
- **Excel Parsing**: pandas / openpyxl
- **Charts**: matplotlib
- **Security**: cryptography, pyotp

## 📦 Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd "Financial App"
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**
   ```bash
   python main.py
   ```

## 🚀 First Run Setup

On first launch, you'll be prompted to:
1. Create a master password (minimum 8 characters)
2. Optionally enable TOTP (2FA)
3. The app will automatically create the database

## 📁 Project Structure

```
Financial App/
├── core/                    # Core functionality
│   ├── auth.py             # Authentication & security
│   ├── database.py         # Database initialization (plaintext SQLite)
│   ├── encryption.py       # Field-level AES-256 encryption for credentials
│   └── session.py          # Session management
│
├── models/                  # Data access layer (10 tables)
│   ├── person.py
│   ├── bank_account.py
│   ├── transaction.py
│   ├── fixed_deposit.py
│   ├── fd_interest_record.py
│   ├── savings_interest.py
│   ├── tax_profile.py
│   ├── statement_import_log.py
│   ├── ais_tis_import.py
│   └── auth_security.py
│
├── engines/                 # Business logic
│   ├── interest_engine.py  # FD & savings interest
│   ├── tax_engine.py       # Tax calculations
│   ├── statement_parser.py # Statement import
│   ├── ais_tis_parser.py   # AIS/TIS JSON parser
│   └── balance_engine.py   # Balance calculations
│
├── ui/                      # User interface
│   ├── login_screen.py
│   ├── dashboard_screen.py
│   ├── accounts_screen.py
│   ├── transactions_screen.py
│   ├── income_management_screen.py
│   ├── fixed_deposits_screen.py
│   ├── statement_import_screen_modern.py
│   ├── tax_documents_screen.py
│   ├── tax_screen.py
│   ├── settings_screen.py
│   └── widgets/
│       ├── summary_panel.py
│       ├── chart_widget.py
│       └── toast_utils.py
│
├── data/                    # Database (auto-created, plaintext SQLite)
├── backups/                 # Backup copies (plaintext)
├── main.py                  # Application entry point
├── config.py               # Configuration & constants
└── requirements.txt        # Dependencies
```

## 🎯 Usage Guide

### Navigation
1. **🏠 Overview** - Dashboard with financial summary
2. **💼 Accounts** - Manage bank accounts
3. **💸 Transactions** - Manage income/expenses
4. **📈 Income & Expectations** - Track expected income
5. **🏦 Fixed Deposits** - Track FDs and interest
6. **📄 Statement Import** - Import bank statements
7. **📋 Tax Documents** - View AIS/TIS import data
8. **🧮 Tax** - Calculate taxes
9. **⚙️ Settings** - Security & preferences

### Key Workflows

#### Adding a Transaction
1. Go to Transactions screen
2. Click "+ Add Transaction"
3. Select person, account, date, type, amount
4. Add category and description
5. Save

#### Creating a Fixed Deposit
1. Go to Fixed Deposits screen
2. Click "+ Add FD"
3. Enter principal, rate, tenure, compounding type
4. Maturity amount is auto-calculated
5. Save (interest is automatically allocated to FYs)

#### Importing Bank Statements
1. Go to Statement Import screen
2. Follow 2-step wizard:
   - **Select**: Choose person, account, and PDF/Excel file
   - **Preview**: Review extracted transactions and confirm import

#### Offline AI Statement Extraction (Local)
The importer now supports a local AI parsing mode through Ollama.

1. Install Ollama
   - `winget install -e --id Ollama.Ollama --source winget --accept-package-agreements --accept-source-agreements`
2. Pull a free local model
   - `"%LOCALAPPDATA%\\Programs\\Ollama\\ollama.exe" pull qwen2.5vl:7b`
3. Enable parser mode (PowerShell)
   - `$env:STATEMENT_PARSER_MODE = "auto"` (rule parser first, then AI fallback)
   - Optional: `$env:OLLAMA_MODEL = "qwen2.5vl:7b"`
   - Optional: `$env:OLLAMA_ENDPOINT = "http://127.0.0.1:11434"`
   - Optional: `$env:OLLAMA_KEEP_ALIVE = "-1"` keeps the model loaded while the app runs

Modes:
- `auto`: try the rule-based parser first, then fall back to local AI when rule parsing finds no transactions
- `ai`: use only the local AI parser (rule parsers are skipped entirely)
- `rule`: use only the regex/column rule-based parser

Both parser paths share the same FD detection and reference-number extraction, so FD booking/maturity transactions are recognised whichever parser runs.

Optional tuning:
- `$env:OLLAMA_TIMEOUT_SECONDS = "60"` — request timeout (default 60s; raise it if a cold model load is slow)
- Use the **Warm Up AI** button on the Statement Import screen to pre-load the model before parsing, so the first run in `ai`/`auto` mode doesn't hit a cold-start timeout.

The app unloads the configured Ollama model when the desktop window closes.

#### Calculating Tax
1. Go to Tax screen
2. Enter salary and other income
3. FD/savings interest auto-loads
4. Enter taxes already paid (TDS, TCS, advance tax, self-assessment)
5. Click "Estimate Tax"
6. Review the results:
   - **Tax Summary** — taxable income, slab tax, 87A rebate, cess, total liability
   - **Net Payable / Refund** — what you still owe or are owed after taxes already paid
   - **Next Year Projection** — projected income and where it lands in the tax slabs

#### Importing AIS/TIS from Income Tax Portal
1. Download AIS/TIS JSON from Income Tax e-filing portal
   - Login to https://www.incometax.gov.in/
   - Go to "Annual Information Statement (AIS)" or "Tax Information Statement (TIS)"
   - Download JSON file for the financial year
2. Go to AIS/TIS Import screen in the app
3. Select person from top bar
4. Click "Import JSON"
5. Select downloaded JSON file
6. View comparison table:
   - **Actual (AIS/TIS)**: Income reported to IT department
   - **Expected (App)**: Income tracked in your app
   - **Difference**: Highlights discrepancies
   - **Status**: ✓ Match / ⚠ Minor Diff / ✗ Mismatch
7. Use this data to:
   - Verify all income is tracked in app
   - Identify missing transactions
   - Ensure accurate tax filing

## 🔒 Security

**What IS protected:**
- Master password: Hashed with PBKDF2 (100,000 iterations) with per-user salt.
- Bank statement passwords and Income Tax portal passwords: Encrypted with AES-256 in the `statement_password_enc` and `ais_tis_password_enc` columns.
- Device binding: App records a hash of the device ID at first login.
- Optional 2FA: Time-based one-time passwords (TOTP) can be enabled.

**What is NOT protected:**
- The SQLite database file (`data/financial.db`) is stored in **plaintext**. Anyone with read access to the file can see all balances, transactions, fixed deposits, tax records, and income data.
- Backup files are plaintext copies of the database; restores overwrite the live database.
- All other fields (transaction amounts, interest earned, tax calculations, deductions, etc.) are readable to anyone with file-system access.

**Recommendation:**
If the privacy of your financial data from file-system access is important, store the database and backups on an encrypted volume (BitLocker on Windows, FileVault on macOS, LUKS on Linux). This prevents casual inspection if someone gains access to your device.

**Offline Operation:**
The app does not connect to the internet and does not send data anywhere. All computation and storage is local to your device.

## 📊 Database Schema

The application uses the following tables:
1. **AuthSecurity** - Authentication data
2. **Person** - Family members
3. **Bank** - Bank master (name, nickname, TAN)
4. **BankAccount** - Bank accounts
5. **Transactions** - All transactions
6. **FixedDeposit** - FD records
7. **FDInterestRecord** - FD interest by FY / quarter
8. **SavingsInterestRecord** - Savings interest by FY
9. **TaxProfile** - Tax calculations by person/FY (income, deductions, rebate, cess, TDS/TCS/advance/self-assessment tax paid)
10. **IncomeSource** - Income source master
11. **IncomeExpectation** - Expected/recurring income tracking
12. **StatementImportLog** - Import history
13. **AISTISImport** - AIS/TIS import data
14. **Form26AS** - Form 26AS import data

## 🎨 UI Theme

The app ships **4 themes** with a fully token-driven styling system — every
screen reads colours from `Theme.*` tokens, so switching a theme re-colours the
whole app **live, with no restart**.

- **Light themes**: Aurora (default), Slate Light
- **Dark themes**: Nova (default), Midnight Pro

Change the theme in **Settings → Color Theme** (each card shows a live preview).
Icons come from a unified registry (Fluent / Material Design, with emoji
fallback) rather than being hardcoded per screen. Tables support Excel-style
keyboard shortcuts (see below); read-only tables support Ctrl+C copy.

To add a new theme, copy an existing `ui/theme/theme_*.py`, adjust its colour
constants, and register it in `ui/theme/theme_manager.py`.

# Keyboard Shortcuts Guide

## Excel-Like Table Shortcuts

All table screens in the Financial App now support the following keyboard shortcuts:

### Selection Shortcuts

| Shortcut | Action | Description |
|----------|--------|-------------|
| **Ctrl+A** | Select All | Selects all cells in the table |
| **Click** | Select Cell | Click on a cell to select it |
| **Shift+Click** | Range Selection | Hold Shift and click to select a range of cells |
| **Ctrl+Click** | Multi-Selection | Hold Ctrl and click to select multiple non-contiguous cells |
| **Drag** | Drag Selection | Click and drag to select multiple cells |

### Clipboard Shortcuts

| Shortcut | Action | Description |
|----------|--------|-------------|
| **Ctrl+C** | Copy | Copy selected cells to clipboard (TSV format) |
| **Ctrl+V** | Paste | Paste clipboard content to selected cells |
| **Ctrl+X** | Cut | Copy selected cells and clear their content |

### Editing Shortcuts

| Shortcut | Action | Description |
|----------|--------|-------------|
| **Double-Click** | Edit Cell | Double-click on an editable cell to edit it |
| **F2** | Edit Mode | Press F2 to enter edit mode for selected cell |
| **Enter** | Confirm Edit | Press Enter to save changes and move to next row |
| **Esc** | Cancel Edit | Press Esc to cancel editing |
| **Delete** | Delete Rows | Delete selected rows (with confirmation) |

### Navigation Shortcuts

| Shortcut | Action | Description |
|----------|--------|-------------|
| **Arrow Keys** | Navigate | Move between cells using arrow keys |
| **Tab** | Next Cell | Move to next cell (right) |
| **Shift+Tab** | Previous Cell | Move to previous cell (left) |
| **Home** | First Column | Jump to first column in current row |
| **End** | Last Column | Jump to last column in current row |
| **Ctrl+Home** | First Cell | Jump to first cell in table |
| **Ctrl+End** | Last Cell | Jump to last cell in table |
| **Page Up** | Scroll Up | Scroll one page up |
| **Page Down** | Scroll Down | Scroll one page down |

## Screen-Specific Features

### Transactions Screen
- **Editable Columns**: Category, Mode, Reference No, Description, Amount, Balance After
- **Read-Only Columns**: Date, Type, Account, Person
- **Checkbox**: Select transactions for bulk operations
- **Stats Bar**: Shows sum and average of selected amounts

### Fixed Deposits Screen
- **Editable Columns**: FD No, Principal, Rate %, Tenure, Compounding, Start Date, Actual Interest
- **Read-Only Columns**: Person, Bank, Maturity Date, Maturity Amount, Expected Interest, Method, Status
- **Recalculate Button**: Click "📊 Recalculate Selected" to auto-calculate maturity for checked FDs
- **Auto-Calculation**: After pasting values, select FDs and click Recalculate to update maturity amounts
- **Checkbox**: Select FDs for recalculation or bulk operations

### AIS/TIS Import Screen
- **Comparison Table**: All columns are copyable (read-only)
- **Breakdown Table**: All columns are copyable (read-only)
- **No Checkboxes**: These are view-only tables
- **Stats Bar**: Shows sum and average of selected amounts

### Statement Import Screen
- **Preview Table**: All columns are copyable (read-only)
- **Checkbox**: Select transactions to import
- **Stats Bar**: Shows sum and average of selected amounts

## Advanced Features

### Multi-Cell Paste
- Copy a range from Excel (e.g., 10 rows × 5 columns)
- Click on starting cell in app
- Press Ctrl+V
- All cells will be pasted maintaining structure

### Selective Column Paste
- Copy single column from Excel
- Click on first cell of target column
- Press Ctrl+V
- Only that column will be filled

### Cross-Table Copy
- Copy cells from one table screen
- Navigate to another table screen
- Paste cells
- Works across all table screens

## Keyboard Shortcut Summary

```
Selection:
  Ctrl+A     - Select All
  Shift+Click - Range Selection
  Ctrl+Click  - Multi-Selection

Clipboard:
  Ctrl+C     - Copy
  Ctrl+V     - Paste
  Ctrl+X     - Cut

Editing:
  Double-Click - Edit Cell
  F2          - Edit Mode
  Enter       - Confirm
  Esc         - Cancel
  Delete      - Delete Rows

Navigation:
  Arrow Keys  - Move
  Tab         - Next Cell
  Shift+Tab   - Previous Cell
  Home/End    - First/Last Column
  Ctrl+Home   - First Cell
  Ctrl+End    - Last Cell
  Page Up/Down - Scroll
```

---

**Note**: All shortcuts work across Windows, macOS, and Linux. On macOS, use Cmd instead of Ctrl.

## 🔧 Configuration

Edit `config.py` to customize:
- Financial year start (default: April 1)
- Transaction categories
- Account types
- Compounding types

## 💾 Backup & Restore

### Creating Backup
1. Go to Settings → Backup & Restore
2. Click "Create Backup"
3. Backup saved to `backups/` folder

### Restoring Backup
1. Go to Settings → Backup & Restore
2. Click "Restore Backup"
3. Select backup file
4. App will restart with restored data

## 🐛 Troubleshooting

### Database Issues
- Delete `data/financial.db` and restart (creates fresh DB)

### Import Errors
- Ensure PDF/Excel files are not password-protected
- Check file format compatibility
- For AI mode, ensure Ollama is running and model is installed

### Display Issues
- Ensure screen resolution is at least 1100x700

## 📝 License

This project is for personal use only.

## 🤝 Contributing

This is a personal project. Feel free to fork and customize for your needs.

## ⚠️ Disclaimer

- This software is provided as-is without warranty
- Always keep backups of your financial data
- Tax calculations are estimates - consult a tax professional
- Not responsible for any financial decisions made using this software

## 📞 Support

For issues or questions, please refer to the documentation in the `docs/` folder.

---

**Version**: 2.0.0  
**Status**: Production Ready ✅  
**Last Updated**: 2026
