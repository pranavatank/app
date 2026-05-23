# Form 26AS Import & Income Source Management

## Overview

The system now supports importing Form 26AS (TDS statement) alongside AIS/TIS data, with intelligent TAN matching and income source management.

---

## Key Features

### 1. **Dual Tab Interface**
- **Tab 1: Form 26AS** - Import TDS records from PDF
- **Tab 2: AIS/TIS** - Import comprehensive income data from JSON

### 2. **Income Source Management**
- Centralized database of all income sources (employers, banks, companies, brokers, etc.)
- Automatic TAN-based matching
- Smart handling of new sources during import

### 3. **Intelligent Import Process**
- Checks existing data before importing
- Updates only missing fields
- Prevents duplicate entries
- Links income sources automatically

---

## Income Source Types

The system supports the following source types:

1. **Employer** - Salary paying companies
2. **Bank** - Banks paying interest
3. **Company** - Companies paying dividends
4. **Broker** - Stock brokers
5. **Mutual Fund** - Mutual fund houses
6. **Tenant** - Rental income payers
7. **Other** - Any other income source

---

## Database Schema

### IncomeSource Table

```sql
CREATE TABLE IncomeSource (
    source_id INTEGER PRIMARY KEY,
    source_type TEXT NOT NULL,
    source_name TEXT NOT NULL,
    tan TEXT UNIQUE,
    pan TEXT,
    address TEXT,
    contact_person TEXT,
    phone TEXT,
    email TEXT,
    notes TEXT,
    created_date TEXT
)
```

**Purpose**: Store all entities that pay income or deduct TDS

**Key Fields**:
- `tan`: Tax Deduction Account Number (unique identifier)
- `source_type`: Category of income source
- `source_name`: Display name

---

## Import Workflows

### Form 26AS Import

**Step 1: Select PDF**
- Click "📤 Import Form 26AS PDF"
- Select PDF downloaded from Income Tax portal

**Step 2: Automatic Parsing**
- Extracts TDS records from PDF
- Identifies deductor name, TAN, section, amounts
- Parses transaction dates and certificate numbers

**Step 3: TAN Matching**
- For each TDS record, system checks if TAN exists in database
- If TAN exists → Links to existing income source
- If TAN is new → Shows dialog to categorize

**Step 4: New Source Dialog**
- Lists all new TANs found
- User selects source type for each (Employer/Bank/Company/etc.)
- System creates income source records

**Step 5: Save**
- Saves all TDS records to Form26ASRecord table
- Links to income sources via TAN

### AIS/TIS Import

**Step 1: Select JSON**
- Click "📤 Import AIS/TIS JSON"
- Select JSON downloaded from Income Tax portal

**Step 2: Parse JSON**
- Extracts salary, interest, dividend, rental income
- Extracts TDS records with source details

**Step 3: Merge with Existing**
- Checks if AIS data already exists for person + FY
- Updates only missing fields
- Preserves manually entered data

**Step 4: TAN Matching**
- Same as Form 26AS import
- Links income sources automatically

**Step 5: Save**
- Saves aggregated income data
- Saves detailed records with TAN links

---

## TAN Matching Logic

```python
def match_income_source(tan: str):
    # 1. Search by TAN (exact match)
    source = get_income_source_by_tan(tan)
    
    if source:
        # TAN found - use existing source
        return source
    else:
        # TAN not found - prompt user
        return prompt_new_source_dialog(tan)
```

**Benefits**:
- No duplicate entries
- Consistent naming across imports
- Easy reconciliation
- Better reporting

---

## Usage Examples

### Example 1: Salary Income

**Scenario**: Import Form 26AS with employer TDS

1. PDF contains: `ABC Company Ltd | ABCD12345E | 192 | ₹50,000`
2. System checks TAN `ABCD12345E`
3. Not found → Shows dialog
4. User selects: **Employer**
5. System creates:
   ```
   IncomeSource:
     source_type: Employer
     source_name: ABC Company Ltd
     tan: ABCD12345E
   ```
6. Links TDS record to this source

**Result**: Future imports with same TAN auto-link to "ABC Company Ltd"

### Example 2: Bank Interest

**Scenario**: Import AIS with bank interest

1. JSON contains: `HDFC Bank | HDFC00001A | Interest | ₹12,000`
2. System checks TAN `HDFC00001A`
3. Found → Links to existing "HDFC Bank" source
4. No dialog needed

**Result**: Seamless import, no user intervention

### Example 3: Dividend Income

**Scenario**: Import AIS with dividend from multiple companies

1. JSON contains:
   - `Reliance Industries | RELI12345A | Dividend | ₹5,000`
   - `TCS Ltd | TCSL67890B | Dividend | ₹3,000`
2. System checks both TANs
3. Not found → Shows dialog with both
4. User selects: **Company** for both
5. System creates two income sources

**Result**: Dividend income properly categorized

---

## Income Management Screen (Future)

The income source database enables a future "Income Management" screen:

**Features**:
- View all income sources
- Edit source details
- Link to bank accounts
- Track payment history
- Generate income reports by source

**Example View**:
```
Income Sources
├── Employers
│   ├── ABC Company Ltd (ABCD12345E)
│   │   └── Salary: ₹50,000/month → HDFC Salary A/c
│   └── XYZ Corp (XYZC98765F)
│       └── Salary: ₹75,000/month → ICICI Salary A/c
├── Banks
│   ├── HDFC Bank (HDFC00001A)
│   │   └── Interest: ₹12,000/year
│   └── SBI (SBIB00002C)
│       └── Interest: ₹8,000/year
└── Companies
    ├── Reliance Industries (RELI12345A)
    │   └── Dividend: ₹5,000
    └── TCS Ltd (TCSL67890B)
        └── Dividend: ₹3,000
```

---

## Benefits

### 1. **Data Consistency**
- Single source of truth for all income sources
- No duplicate entries
- Consistent naming

### 2. **Automatic Linking**
- TAN-based matching eliminates manual work
- Future imports auto-link to existing sources

### 3. **Better Reconciliation**
- Easy to match Form 26AS vs AIS
- Clear visibility of all income sources
- Identify missing entries

### 4. **Tax Compliance**
- Complete TDS tracking
- Source-wise income breakdown
- Ready for ITR filing

### 5. **Reporting**
- Income by source type
- TDS by deductor
- Year-over-year comparisons

---

## Technical Details

### Form 26AS Parser

**File**: `engines/form26as_parser.py`

**Functions**:
- `parse_form26as_pdf(pdf_text)` - Main parser
- `parse_form26as_text_simple(text)` - Fallback parser
- `extract_financial_year_from_ay(ay)` - Convert AY to FY

**Extraction Logic**:
1. Identify Part A section (TDS deducted at source)
2. Extract TAN using regex: `[A-Z]{4}[0-9]{5}[A-Z]`
3. Extract section code: `19[0-9][A-Z]?`
4. Extract amounts: `[\d,]+\.\d{2}`
5. Extract dates: `\d{2}/\d{2}/\d{4}`
6. Group by deductor

### Income Source Model

**File**: `models/income_source.py`

**Key Functions**:
- `save_income_source()` - Create/update source
- `get_income_source_by_tan()` - Find by TAN
- `get_all_income_sources()` - List all sources
- `search_income_sources()` - Search by name/TAN

**Unique Constraint**: TAN must be unique

---

## Future Enhancements

1. **Auto-categorization**
   - ML-based source type prediction
   - Learn from user selections

2. **Bank Account Linking**
   - Link income sources to bank accounts
   - Track which account receives which income

3. **Payment Tracking**
   - Track expected vs actual payments
   - Alert on missing income

4. **Multi-year Analysis**
   - Compare income sources across years
   - Identify trends

5. **Export Features**
   - Export income source list
   - Generate ITR annexures

---

## Troubleshooting

### Issue: TAN not extracted from PDF

**Solution**: 
- Check PDF quality
- Try OCR if PDF is scanned
- Manually add income source

### Issue: Duplicate sources created

**Solution**:
- TAN should be unique
- If duplicate, delete one and update TAN in remaining

### Issue: Wrong source type selected

**Solution**:
- Edit income source from management screen
- Update source type

---

## API Reference

### Save Income Source

```python
from models.income_source import save_income_source

source_id = save_income_source(
    source_type="Employer",
    source_name="ABC Company Ltd",
    tan="ABCD12345E",
    pan="ABCDE1234F",
    address="123 Business Park, Mumbai",
    contact_person="HR Manager",
    phone="+91-22-12345678",
    email="hr@abc.com",
    notes="Monthly salary on 1st"
)
```

### Get Income Source by TAN

```python
from models.income_source import get_income_source_by_tan

source = get_income_source_by_tan("ABCD12345E")
if source:
    print(f"Found: {source['source_name']}")
```

### Search Income Sources

```python
from models.income_source import search_income_sources

results = search_income_sources("HDFC")
for source in results:
    print(f"{source['source_name']} - {source['tan']}")
```

---

## Conclusion

The Form 26AS import and income source management system provides a robust foundation for comprehensive income tracking and tax compliance. By centralizing all income sources and using TAN-based matching, the system eliminates duplicates, ensures consistency, and simplifies reconciliation.
