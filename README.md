# Personal Offline Financial Management System

## Overview
A fully offline, encrypted desktop application for managing personal and family financial data with comprehensive features for tracking income, expenses, investments, and tax calculations.

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
- 📅 Financial year-wise interest allocation
- 🔮 Maturity projections

### Tax Calculation
- 🇮🇳 Indian income tax calculation (2024-25 slabs)
- ⚖️ Old vs New regime comparison
- 💡 Automatic regime recommendation
- 📋 Deductions support (80C, 80D, HRA, home loan)
- 📊 Assessment year projections

### Statement Import
- 📄 PDF bank statement import
- 📊 Excel statement import
- 🤖 Automatic transaction extraction
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
- 🔐 Master password authentication
- 🔒 AES-256 database encryption
- 📱 Device binding
- 🔑 Optional TOTP (2FA)
- 👁️ Privacy mode (mask all amounts)
- 💾 Encrypted backup & restore

## 🛠️ Technology Stack

- **Language**: Python 3.10+
- **UI Framework**: PyQt6
- **Database**: SQLite (encrypted with AES-256)
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
3. The app will automatically create the encrypted database

## 📁 Project Structure

```
Financial App/
├── core/                    # Core functionality
│   ├── auth.py             # Authentication & security
│   ├── database.py         # Database initialization
│   ├── encryption.py       # AES-256 encryption
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
│   ├── transactions_screen.py
│   ├── fixed_deposits_screen.py
│   ├── statement_import_screen.py
│   ├── ais_tis_import_screen.py
│   ├── tax_screen.py
│   ├── reports_screen.py
│   ├── settings_screen.py
│   └── widgets/
│       ├── summary_panel.py
│       ├── chart_widget.py
│       └── privacy_overlay.py
│
├── data/                    # Database (auto-created)
├── backups/                 # Encrypted backups
├── main.py                  # Application entry point
├── config.py               # Configuration & constants
└── requirements.txt        # Dependencies
```

## 🎯 Usage Guide

### Navigation
1. **🏠 Overview** - Dashboard with financial summary
2. **💸 Transactions** - Manage income/expenses
3. **🏦 Fixed Deposits** - Track FDs and interest
4. **📄 Statement Import** - Import bank statements
5. **📑 AIS/TIS Import** - Import Income Tax portal data
6. **📋 Tax** - Calculate taxes
7. **📊 Reports** - View analytics
8. **⚙️ Settings** - Security & preferences

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
2. Follow 5-step wizard:
   - Select person
   - Select bank account
   - Choose PDF/Excel file
   - Preview extracted transactions
   - Review Import Debug Panel for skipped rows and parse issues
   - Confirm import

#### Offline AI Statement Extraction (Local)
The importer now supports a local AI parsing mode through Ollama.

1. Install Ollama
   - `winget install -e --id Ollama.Ollama --source winget --accept-package-agreements --accept-source-agreements`
2. Pull a free local model
   - `"%LOCALAPPDATA%\\Programs\\Ollama\\ollama.exe" pull qwen2.5:3b`
3. Enable parser mode (PowerShell)
   - `$env:STATEMENT_PARSER_MODE = "auto"` (AI first, fallback to rule parser)
   - Optional: `$env:OLLAMA_MODEL = "qwen2.5:3b"`
   - Optional: `$env:OLLAMA_ENDPOINT = "http://127.0.0.1:11434"`

Modes:
- `auto`: try local AI parser first, fallback to existing parser if AI is unavailable
- `ai`: use only local AI parser
- `rule`: use only existing regex/column parser

#### Calculating Tax
1. Go to Tax screen
2. Enter salary and other income
3. FD/savings interest auto-loads
4. Add deductions (80C, 80D, etc.)
5. Click "Calculate Tax"
6. View old vs new regime comparison

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

## 🔒 Security Features

- **Encryption**: All data encrypted with AES-256
- **Master Password**: Required for all access
- **Device Binding**: App tied to specific device
- **TOTP Support**: Optional 2FA
- **Privacy Mode**: Mask all financial amounts
- **Secure Backups**: Encrypted backup files

## 📊 Database Schema

The application uses 10 tables:
1. **AuthSecurity** - Authentication data
2. **Person** - Family members
3. **BankAccount** - Bank accounts
4. **Transactions** - All transactions
5. **FixedDeposit** - FD records
6. **FDInterestRecord** - FD interest by FY
7. **SavingsInterestRecord** - Savings interest by FY
8. **TaxProfile** - Tax calculations by person/FY
9. **StatementImportLog** - Import history
10. **AISTISImport** - AIS/TIS import data

## 🎨 UI Theme

Dark theme with Catppuccin-inspired colors:
- Background: `#1e1e2e`
- Primary: `#89b4fa` (blue)
- Success: `#a6e3a1` (green)
- Warning: `#fab387` (orange)
- Danger: `#f38ba8` (red)

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

**Version**: 1.0.0  
**Status**: Production Ready ✅  
**Last Updated**: 2024