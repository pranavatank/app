# Plan: rebuild `financial.db` from scratch through the real UI, then validate frontend and backend

## 0. Discoveries that change the brief

I checked each of these against the code before building the plan on it.

1. **Resetting the DB also deletes the login.** `AuthSecurity` (master password hash, device fingerprint, TOTP) lives in `financial.db`. After the reset, `main.py` → `core.auth.is_first_run()` sends the app to `ui/setup_screen.py:SetupScreen`, which asks for a new master password. The master password also derives `session.aes_key`, which encrypts the saved statement and AIS/TIS passwords (`models/bank_account.py:set_statement_password`, `models/person.py:set_ais_tis_password`; both silently do nothing when `aes_key` is None).
   - **Blocker:** the user must supply the master password. The agent must not invent it.
   - Recommended: the user adds a line `master: <pw>` to the gitignored `data\PersonalData\Pranav\password.txt`, and scripts read it at runtime like the other passwords.
   - Leave TOTP off for this pass. Automated logins cannot supply OTPs.
2. **FixedDeposit rows are not created by AIS import.** They come from statement import:
   - `ui/statement_import_screen_modern.py:_TransactionImportWorker.run` → `models/fixed_deposit.py:add_fd_from_statement` creates rows with status `Pending Details`. It fires when the description contains "fd accepted", "opening" or "fixed deposit".
   - `apply_statement_redemption_event` handles Income rows. It can mark FDs `Matured` or create new `Matured` rows.
   - AIS only shows a read-only match table (`engines/taxdocs/merge.py` section 7 → `find_fd_by_account_no`) and writes no FD rows.
3. **The owner-approved taxable figure of ₹2,54,784 will not come back from a fresh import.** The Commission Income / Professional Fees / Salary recategorisation was applied to existing rows by `tools/backfill_transactions.py` (ENLIGHTVISION, LOTUS INVESTMENT, KEVISION, PRASAD M rules). The import pipeline does not apply those rules. Expect realised taxable income to drop, probably towards the old ₹95,591. Re-applying the rules needs the user's approval (Phase 2.9).
4. **Figures that come from the documents must match exactly.** Commit e721005 did not touch `engines/statement/*` or `engines/taxdocs/*` (verified with `git show --stat`). So these must match the guide:
   - Statement parse counts: 65 / 376 / 27 / 38.
   - 26AS: 158 records (86 Part-I + 72 Part-II), net TDS ₹13,367.00, per-deductor figures.
   - AIS/TIS: FD interest ₹2,56,642, savings interest ₹46,183, dividend ₹2,655, business receipts ₹1,05,069, AIS TDS ₹12,073.

   Any difference there is a finding. Only figures derived from the DB may legitimately drift: FD count and status, categories, projections, `is_internal_transfer`.
5. **The existing real-UI scripts cannot be reused as they are.**
   - `test_add_person_flow.py`, `test_add_bank_flow.py` and `test_add_account_flow.py` click `dashboard._nav_buttons[8]` and assert "Settings is at nav index 8". Index 8 is now Income Prediction; Settings is 9. They then read `dashboard.settings_page`, which is never built, so they are broken.
   - Every script bypasses login (`DashboardScreen()` directly, so `aes_key` is None) and never calls `initialise_database()`. On a fresh DB they would crash.
   - `harness.click()` uses QTest, not the real OS mouse.
   - `test_statement_import_flow.py` and `test_add_account_flow.py` create data programmatically. File selection uses `zone.fileSelected.emit(...)`, not the file dialog.
   - `test_tax_documents_flow.py` writes to the real DB and never cleans up. It backs up with `core/backup_manager.create_backup`, which uses `shutil.copy2` and is not WAL-safe.
   - `test_excel_table_interactions.py` writes and deletes rows in the real DB. It is the script behind the earlier data-loss incident.
6. **The AIS/TIS FY fix only works in one order.** `ui/tax_documents_screen.py` saves AIS/TIS under `self._itr_financial_year or session.selected_fy`. `_itr_financial_year` is set only when 26AS was imported first in the same screen instance. The AIS/TIS parsers extract no FY. Otherwise the documents are saved under the top-bar FY, which defaults to the current FY, 2026-27 (wrong).
7. `data\PersonalData\Pranav\Data 26-27.xlsx` exists and is not in the task. Do not import it into the real DB. Ask the user what it is.

---

## Global execution rules (every phase)

- **Run one real-UI process at a time.** Before each launch, check that no other process is running `main.py` or `tools/real_ui_tests/*`:
  `Get-CimInstance Win32_Process -Filter "name='python.exe'" | Select CommandLine`.
  The user must not touch the mouse or keyboard during runs; `pyautogui.FAILSAFE` corner-abort stays on. Disable sleep/lock.
- **Secrets:** read from `password.txt` at runtime only. Use `tools/taxdoc_import.py:read_ais_tis_password` / `read_equitas_password`, plus a new reader for the `master` line.
  - Never print, log or write a secret, a PAN or a full account number.
  - Log a redaction filter: the 3 secret strings become `***`, `[A-Z]{5}[0-9]{4}[A-Z]` becomes `XXXXX9999X`, digit runs of 9+ are masked.
  - After typing a password, verify with an in-process `field.text() == secret` and print only True/False.
- **Every script:** the UTF-8 stdout header (guide §5.2), `faulthandler.dump_traceback_later(900, exit=True)`, output redirected to a log file (never `| tail`).
  - Logs and screenshots go to `tools\real_ui_tests\screenshots\rebuild\` (gitignored; screenshots contain PAN/PII, never commit).
  - Snapshots of the new DB go to top-level `backups\*.db`. Only top-level `backups/*.db` is gitignored, not subfolders.
- **Verification is always independent.** Use a read-only SQLite connection (`file:...financial.db?mode=ro`, `uri=True`) or direct widget state. A script's own PASS line is never proof (guide §8), and a screenshot is never proof (§E).
- **Do not commit anything.** New scripts stay untracked unless the user asks. End-of-run check: `git status --porcelain` shows no `data/`, `backups/` or `.db*` paths.

---

## Phase 0: Pre-flight (read-only; DB untouched)

**0.1 Environment.**
- `git -C D:\Pranav\app status --porcelain` is empty and HEAD is `e721005`.
- Nothing is running the app (process check above).
- Record `devicePixelRatio` (expected 1.25; read it live), screen size, and the keyboard layout (`win32api.GetKeyboardLayout(0) & 0xFFFF == 0x0409` means US). If the layout is not US, `pyautogui.write` may mistype symbols. Record this; per-field read-back verification still catches it.

**0.2 Integrity baseline.**
- SHA-256 of every file under `data\PersonalData\` → `screenshots\rebuild\P0_personaldata_hashes.json`.
- Record the exact contents of `data\theme_prefs.json` (currently `{"sidebar_open": false}`) and whether `data\onboarding_shown` exists (it does).

**0.3 Headless expectations** (new script `tools\real_ui_tests\rebuild_p0_expectations.py`; imports parsers only, never `core.database`). For each statement:
- Run `engines.statement.parse_statement_pdf(path, password=<equitas pw for Equitas.pdf>, debug={})`.
- Record the count, min/max date, Income sum, Expense sum, and first/last `balance_after`.
- Record the opening balance: the first row's `balance_after` minus its signed amount.
- Record the category histogram.
- Predict FD openings: apply the same substring rule as `_TransactionImportWorker._is_fd_opening_transaction`, recorded as the count plus (date, amount) pairs.
- Predict redemption candidates: Income rows.
- Call `engines.statement_metadata_extractor.extract_account_metadata(extract_statement_text(...))` and keep the masked account number (via `mask_account_number`) and the IFSC, if present, for Phase 2.3.

26AS:
- Run `engines.taxdocs.form26as.parse_form26as_pdf`. Record the record count, total TDS, per-deductor sums and TANs.
- Keep `name` and `pan` in memory only; log them masked.

AIS/TIS:
- Run `engines.taxdocs.ais.parse_ais_pdf` / `tis.parse_tis_pdf` with the password.
- Record fd_interest, savings_interest, dividend, business receipts and TDS, plus the SFT-016(TD) account-number count.

Write everything to `screenshots\rebuild\P0_expectations.json` (no secrets, PAN masked).

**STOP if:** any document figure differs from the guide §4 values (listed in §0.4 above). That would be a parser regression, and it must be reported before any reset.

**0.4 (Optional; the caller decides given the user's "not needed now")** Record aggregate-only facts from the current DB for the Phase 5 explanation: per-table counts, FY 2025-26 income sums by category, FD count by status. No rows, no copy. Skip this entirely if the caller prefers strict literalism.

**0.5 User inputs.** Stop and ask the user for:
- the master password (via the `password.txt` line);
- a DOB decision: enter it, or leave it at the dialog default and record that as a finding. The field cannot be blank; it defaults to today.
- confirmation that bank names should be the full legal names in 2.2.
- account interest rates, if known. Otherwise the 3.5% dialog default stays.
- whether Phase 2.9 recategorisation should be re-applied, and how.
- what `Data 26-27.xlsx` is.

**0.6 Build the shared tooling** (new files, detailed in the Appendix) before Phase 1, so the reset is followed immediately by a working driver.

**Checkpoint P0:** the expectations JSON and hashes exist, the tooling is written, and the user's answers are recorded in `screenshots\rebuild\PROGRESS.md`. Nothing has been modified; this phase is always safe to re-run.

---

## Phase 1: Reset

"Safe" means exactly this:
- Only `D:\Pranav\app\data\financial.db`, `financial.db-wal`, `financial.db-shm` (and `financial.db-journal` if present) are removed.
- Explicit literal paths only: no wildcards, no `-Recurse`, no directory deletes.
- `data\PersonalData\**`, `data\logo.png`, `data\onboarding_shown`, `data\theme_prefs.json` and `backups\` are untouched.
- The pre-reset DB is not backed up, per the user's instruction.

1. Confirm again that no python process holds the DB (process check). If one does, stop.
2. For each of the 4 literal paths: `if (Test-Path -LiteralPath $p) { Remove-Item -LiteralPath $p -Confirm:$false }`.
3. Verify:
   - none of the 4 paths exist;
   - `Get-ChildItem D:\Pranav\app\data` lists exactly `PersonalData`, `logo.png`, `onboarding_shown`, `theme_prefs.json`;
   - the `PersonalData` SHA-256 set equals P0.

   Do not launch anything that opens the DB between this step and P2.0. Any `get_connection()` would create an empty, schema-less file.

**Checkpoint P1:** the DB file is absent. Resume rule: if the DB exists and has an `AuthSecurity` row, Phase 1 is complete and P2.0 is done (go to P2.0's resume rule). If the file exists but has no tables, delete it again (step 2).

---

## Phase 2: Real-UI data entry (real DB; persists)

Each sub-step is its own script and process. Each one:
- starts by computing state from the DB, so it is idempotent;
- does its work with real OS mouse and keyboard, using the Appendix helpers;
- verifies independently;
- takes a WAL-safe snapshot `backups\rebuild_<UTC>_<step>.db` via `snapshot_db()` (checks exists, size > 0, `PRAGMA integrity_check`=ok on the copy, and counts equal the live DB);
- appends a line to `PROGRESS.md`.

To roll back a failed step, close the app, then restore the previous step's snapshot with `core.database.restore_database(path)`. Then verify the counts equal that snapshot and re-run the step.

Every script except P2.0 logs in through the real `LoginScreen` (`login_to_dashboard()`), then sets `dashboard.fy_combo` to `2025-26` via an OS combo selection (§J), and verifies `session.selected_fy == "2025-26"`.

### P2.0 First-run setup (`rebuild_p2_0_setup.py`)

**Precondition:** the DB is absent, or `SELECT COUNT(*) FROM AuthSecurity` = 0.

**Steps:**
1. `bootstrap_app()` runs `initialise_database()` and creates the schema.
2. Open `SetupScreen` with `harness.launch(..., maximized=False)`.
3. **Negative checks first** (these never write):
   - Type 5 characters into both fields and OS-click "Create account" → `is_first_run()` is still True.
   - Type mismatched values → still True.
4. **Real setup:**
   - `os_type` "Master password input" and "Confirm password input" (secret).
   - Verify "Enable two-factor authentication" `isChecked()` is False.
   - OS-click "Create account".
   - Wait for `setup.login.isVisible()`.
5. Log in through `setup.login` (see Appendix, `login_to_dashboard`) and adopt the dashboard window.

**Verify:**
- `AuthSecurity` has 1 row, `totp_secret IS NULL`, `privacy_mode_enabled=0`, and `device_id_hash == core.auth.get_device_fingerprint()`.
- In-process, `verify_login(pw)[0]` is True (print the bool only).
- All 22 `CREATE TABLE` tables exist (`sqlite_master`).
- `TaxSlabConfig` = 14 rows (7 × {2025-26, 2026-27}); `TaxParams` = 2 rows (`rebate_87a_limit`=1200000, `standard_deduction`=75000).
- `BankFDConvention` = 0.
- Dashboard: `len(_nav_buttons)` == 10 and `stack.count()` == 10; `person_combo` holds only "All Persons".

**Snapshot:** `P2_0`.

**Resume rule:** if `AuthSecurity`=1 but login with the stored password fails, **STOP and escalate**. The auth row has an unknown password; redo Phase 1.

### P2.1 Person (`rebuild_p2_1_person.py`)

**Precondition:** Person = 0. If Person = 1 and all fields match, skip.

**Steps:**
1. OS-click "Navigate to Settings".
2. Pre-arm a callback, then OS-click "Manage people". The Manage Data dialog is non-modal (`dlg.show()`); find it with `find_dialog(QDialog, "Manage Data")`.
3. Select the People tab by OS-clicking the tab bar: `tabs.tabBar().tabRect(0).center()`.
4. Pre-arm `QTimer.singleShot(0, fill)` (§G), then OS-click "Add person". Inside `fill`, on `PersonDialog` "Add Person":
   - `os_type` "Nickname" = `Pranav`.
   - "First name" / "Middle name" / "Last name" come from the 26AS `name` (first token / middle tokens / last token).
   - "PAN number" = the 26AS `pan`.
   - "Date of birth": `os_set_date` per the user's 0.5 decision.
   - OS-click "Save person".

**Verify (SQL):**
- `SELECT person_id, full_name, first_name, last_name, date_of_birth, pan_number FROM Person` → exactly 1 row, `person_id=1`, `full_name='Pranav'`.
- PAN equals the 26AS PAN (bool only).
- `date_of_birth` equals the intended ISO date. The DOB edit uses format `dd/MM/yy`. If the century is wrong (for example 2065), that is a finding: fall back to `dob_input.setDate()` and label it as a non-OS input.
- UI: `people_table.item(0,0).text()=='Pranav'`.
- After closing the dialog, check whether the top-bar `person_combo` contains "Pranav" without a restart. Record the result as observed behaviour.

**Snapshot:** `P2_1`.

### P2.2 Banks (`rebuild_p2_2_banks.py`)

**Precondition:** Bank = 0. If Bank = 4 and all rows match, skip.

**Steps:** In Manage Data, open the Banks tab. For each bank, pre-arm, OS-click "Add bank", `os_type` "Bank nickname", "Bank name", and optionally "Bank TAN", then OS-click "Save bank".

| Nickname | Bank name | TAN |
|---|---|---|
| `Jana` | `Jana Small Finance Bank` | From 26AS if there is exactly one TAN for deductors starting "JANA"; otherwise blank |
| `IDFC FIRST` | `IDFC FIRST Bank` | Blank |
| `Ujjivan` | `Ujjivan Small Finance Bank` | Same rule as Jana ("UJJIVAN") |
| `Equitas` | `Equitas Small Finance Bank` | Same rule as Jana ("EQUITAS") |

The first word of each name must match the 26AS deductor's first word. `tools/tax_reconcile.py` and `engines/statement/profiles.load_profile` key on the first word.

Also exercise the Cancel path once (type something, OS-click "Cancel bank dialog") and confirm the count is unchanged.

**Verify:**
- `SELECT bank_name, nickname, tan_code FROM Bank ORDER BY bank_id` → the 4 exact rows.
- `banks_table.rowCount()==4`.

**Snapshot:** `P2_2`.

### P2.3 Accounts (`rebuild_p2_3_accounts.py`)

At script start, verify `BankFDConvention` = 4. It is seeded at `initialise_database()` for existing banks; if it is 0, record a finding.

**Precondition:** BankAccount = 0. If it is 4 and all rows match, skip.

**Steps:** In Manage Data, open the Accounts tab. For each bank, in the order Jana, IDFC FIRST, Ujjivan, Equitas: pre-arm, then OS-click "Add account". On `AccountDialog` "Add Account":
- "Person selector" = Pranav (`os_select_combo`).
- "Bank selector": choose the list item (not typed text).
- "Account holder name" = the 26AS name.
- "Account type" = `Savings`.
- "Masked account number" = the P0 masked value, if available.
- "IFSC code" = the P0 IFSC, if valid.
- "Opening balance" = the P0 statement opening balance. Select all, then type digits.
- "Interest rate": the user-supplied rate, or leave 3.5.
- Leave the other fields at their defaults and record the stored `account_opening_date` (defaults to today).
- OS-click "Save account".

**Verify:**
- `SELECT account_id, person_id, bank_name, account_type, opening_balance, interest_rate FROM BankAccount ORDER BY account_id` → 4 rows, `person_id=1`, bank names exactly as in the Bank table, and opening balances equal to P0 to the paisa.
- `Bank` is still 4 (`get_or_create_bank` must not add a duplicate).
- `AccountHolder` rows as created.
- UI: `accounts_table.rowCount()==4`.

**Snapshot:** `P2_3`.

### P2.4a–d Statements (`rebuild_p2_4_statement.py --bank Jana|IDFC|Ujjivan|Equitas`)

Run once per statement in the order Jana → IDFC → Ujjivan → Equitas. Order matters: `reprocess_internal_transfers` runs after each import, across accounts.

**Precondition** (per account): `SELECT COUNT(*) FROM Transactions WHERE account_id=?`.
- 0 → run.
- Equal to the P0 count → skip.
- In between → **STOP and escalate.** The batch insert rolls back on failure, so a partial state should be impossible; if it happens, it is a finding.

**Steps:**
1. OS-click "Navigate to Statement Import".
2. OS-click "Select person: Pranav" and verify `isChecked()`.
3. OS-click "Select account: <bank_display_name> — Savings" and verify it is checked.
4. OS-click "Select PDF format" and verify `btn_format_pdf.isChecked()`.
5. **File selection by real OS input:** start `os_file_dialog_typer.py` as a subprocess (Appendix), then OS-click the "File drop zone". This opens `QFileDialog.getOpenFileName`; the helper types the full path and presses Enter. Assert the helper exits 0 and the screen's `selected_file` equals the path.
6. **Equitas only:** pre-arm a handler for `PasswordDialog`, then OS-click "Next button". In the handler: `os_type` "Password input" (secret), OS-click "Save password toggle" so it is checked, then OS-click "Confirm password". For the other statements, OS-click "Next button" directly.
7. Wait (up to 180 s) until `preview_table.rowCount() > 0` or an error is captured by the watchdog.
8. **Preview checks:**
   - Row count equals the P0 count.
   - No confidence block warning.
   - The duplicate count is 0; the DB was empty for this account.
   - Spot-check column mapping (commit fix "off-by-one column mapping"): for rows 0, mid and last, compare the preview cells' date, amount and description against the P0 parse at the same index.
9. OS-click "Select all new transactions", then OS-click "Next button" (Import).
10. Wait (up to 180 s) until `person_cards_container.isVisible()` and the loader is hidden.

**Verify (SQL, against P0):**
- `COUNT(*)`, `MIN/MAX(transaction_date)`, and `SUM(amount)` by `transaction_type` for the account equal P0 exactly.
- Every row has `source='Statement Import'`.
- **Balance fix:** in `ORDER BY transaction_date, transaction_id` order, each `balance_after` equals the P0 parsed `balance_after`, and `BankAccount.current_balance` equals the last parsed balance.
- `StatementImportLog`: 1 new row, `records_imported` = count, `status='Success'`.
- `SELECT fd_id, status, principal_amount, start_date, source_transaction_id FROM FixedDeposit WHERE account_id=?`: the count matches the P0 FD-opening prediction. Each `source_transaction_id` points to a same-account transaction with `amount = principal_amount` and `transaction_date = start_date`. Record the status breakdown (`Pending Details` / `Matured`).
- `SELECT COUNT(*) FROM Transactions WHERE is_internal_transfer=1`: record it after each import.
- `SavingsInterestRecord` rows exist for the FYs covered.
- **Equitas:** `statement_password_enc IS NOT NULL`, differs from the plaintext, and decrypts under `session.aes_key` to the password (bool only).
- UI: the dashboard "Total Balance" KPI text equals `SUM(current_balance)` formatted.

**Snapshot:** `P2_4_<bank>`.

### P2.5–P2.7 Tax documents (`rebuild_p2_5_taxdocs.py`, one process for all three)

The order is fixed at 26AS → AIS → TIS, in one `TaxDocumentsScreen` instance (§0.6). On resume, always re-drop 26AS first. That is idempotent: `save_form26as_import` deletes and re-inserts per (person, FY).

**Steps:**
1. Set the FY combo to 2025-26 (belt and braces), then OS-click "Navigate to Tax Documents".
2. Each drop zone (`zone_26as`, `zone_ais`, `zone_tis`; all share the accessible name "File drop zone", so use the attributes) is driven by the file-dialog typer plus an OS click.
3. AIS and TIS open a `PasswordDialog` modal *before* the background parse. Pre-arm a handler for it: type the secret, tick "Save password toggle", then "Confirm password".
4. After each drop, wait up to 180 s for `zone.pdf_data is not None` or an error status.
5. After TIS, `_on_all_loaded` renders three tables.

**Verify (SQL):**
- `SELECT financial_year, total_tds FROM Form26ASImport` → 1 row: `2025-26`, 13367.00.
- `SELECT COUNT(*) FROM Form26ASRecord` → 158.
- The per-deductor sums (GROUP BY `deductor_name`) equal guide §4.
- `SELECT source_type, financial_year FROM AISTISImport` → 2 rows (AIS, TIS), **both `2025-26`**. Any other FY confirms the FY-ordering bug.
- The stored payload figures equal P0/§4.
- `Person.ais_tis_password_enc` is not NULL and decrypts under `aes_key` (bool only).
- `core.backup_manager` was not invoked. The Tax Documents screen does not back up; only `taxdoc_import.py` does.

**UI:**
- `position_table` rows for FD Interest, Savings Interest and TDS show the §4 values.
- `fd_table` rows: record the "Matched" versus "Not in App" counts. This tests the "AIS FD matching never matching" fix: with statement-derived FDs present, at least one match is expected if `fd_reference_no` formats align. Zero matches is a finding to characterise: compare AIS account numbers against `fd_reference_no` using the last 4 digits only in the log.
- Confirm the words gap, mismatch and error do not appear in any label on the screen. "TDS Difference" and "Merge failed" are present in the code; note them.

**Snapshot:** `P2_7`.

### P2.8 FD origin confirmation (no UI entry)

`SELECT status, COUNT(*) FROM FixedDeposit GROUP BY status`, per account. Explain every FD by its source transaction (description snippet with 6+ digit runs masked).

Compare with the old baseline of 19 `Pending Details`. Differences are explained by redemption events (`Matured`) or by new-rule effects. None is created by AIS.

### P2.9 (gated on user approval) Owner-approved recategorisation

1. Run `.venv\Scripts\python.exe tools\backfill_transactions.py --dry-run --person-id 1` and show the user the list of proposed changes.
2. If the user approves, prefer re-applying through the UI: Transactions screen, FY 2025-26, edit the Category cell in the Excel table for each listed transaction_id, then OS-click Save. The dialog cannot pick Commission Income or Professional Fees, because they are not in `config.INCOME_CATEGORIES` (a finding). Alternatively, if the user prefers, run the script without `--dry-run`.
3. **Verify:** diff the transaction_id→category map against the dry-run list, ensuring exactly those rows changed and nothing else.

**Snapshot:** `P2_final`.

**Phase 2 exit criteria:**
- Counts are Person 1, Bank 4, BankAccount 4, Transactions = the sum of P0 counts (expected 506), Form26ASImport 1 / Form26ASRecord 158, AISTISImport 2.
- FixedDeposit is explained per P2.8.
- `PersonalData` hashes are unchanged.

---

## Phase 3: Walkthrough of every control on all 10 screens

**Environments:**
- **R (real DB), non-mutating only.** A content fingerprint is taken before and after: per table, row count plus the SHA-256 of `SELECT * ORDER BY rowid`. Allowed deltas: `TaxProfile` (from Estimate tax) and nothing else. `privacy_mode_enabled` must end at its original value.
- **S (scratch copy), for anything that creates, edits or deletes.**
  - Create `backups\phase3_scratch.db` from the `P2_final` snapshot with the SQLite backup API.
  - Run each script through `tools\real_ui_tests\run_on_scratch.py <script>`. Before any app import, it patches `config.DB_PATH` and `core.database.DB_PATH`, plus `core.session._CONFIG_FILE` and `ui.theme.theme_manager._CONFIG_FILE`, pointing them at the scratch paths. It does **not** patch `DATA_DIR`, because the PersonalData paths depend on it. It asserts the patched path is not the real one.
  - Around every S run, the real DB fingerprint must be unchanged. If it changes, **STOP**.
  - Re-create the scratch copy whenever a script leaves it inconsistent.
- Snapshot `theme_prefs.json` before each script and restore it byte-for-byte afterwards.

Each script is split per screen, `rebuild_p3_<nn>_<screen>.py`, so each is independently resumable. `PROGRESS.md` marks per-screen completion; a failed screen re-runs alone.

The top-bar FY is 2025-26 unless noted. For each control:
- Controls with an accessible name are located by it.
- Controls without one are located by attribute (for example `tax_page.btn_calc`). Record each such control as a low-severity accessibility finding. Examples: `transactions_screen` buttons, `fd_dialog` / `transaction_dialog` fields, tax inputs, `ThemeCard`s.

**Top bar and sidebar (R):**
- **Nav:** OS-click "Navigate to X" for X in all 10. Verify `stack.currentIndex()`, `page_title_lbl.text()`, `_screen_errors == {}`, and no error page.
- **Person combo:** "All Persons" ↔ Pranav. Verify `session.selected_person_id`.
- **Account combo:** each of the 4 accounts plus "All". Verify `session.selected_account_id` and that the Total Balance KPI equals that account's `current_balance`.
- **FY combo:** 2024-25 / 2025-26 / 2026-27. Verify `session.selected_fy`.
- **Sidebar toggle:** verify the width change and `theme_prefs.json.sidebar_open` toggling.
- **Logout:** pre-arm the QMessageBox and click "No" first (still logged in), then "Yes". Verify `LoginScreen` is visible and `session.aes_key is None`. Re-log in by OS: first with a wrong password (the error label is shown), then the real one.
- **Hard Refresh:** in its own final run, because it reloads modules and invalidates widget references. Verify the dashboard is rebuilt and nav works.

**Overview (R):**
- The 5 KPI tile texts versus independent SQL for FY 2025-26, person 1:
  - `SUM(current_balance)`;
  - Income / Expense sums by `transaction_type` within 2025-04-01..2026-03-31;
  - FD interest plus savings interest from `get_total_fd_interest` / `get_total_savings_interest` versus `FDInterestRecord` / `SavingsInterestRecord` SUM for the FY.

  Where a figure differs, read the model's SQL and classify the difference as an intentional filter or a bug. Note that "Income (FY)" is the naive ₹64.9L gross credit figure (guide §2 trap) and whether that is appropriate for a headline tile.
- **Charts:** 12 monthly bars equal SQL monthly sums (`ChartWidget` axes data; reuse the `tests/test_chart_db_agreement.py` approach). The pie slices equal the positive account balances.
- **Panels:** the interest and tax panel stat texts. The tax panel shows "No data" until P3 Tax writes a `TaxProfile`, and the value after.
- **Privacy mode:** toggling on (Settings) turns all tiles into "₹ ****". Restore it afterwards.

**Accounts (1):**
- R: "Toggle account view" switches views and the card count is 4. OS double-click each "Account card for …" opens the details dialog; verify the fields equal the DB; close it.
- S: "Add account" from this screen (RUIH_ holder); edit it (change IFSC; also test invalid IFSC, MICR, email, phone and TAN, each blocking Save); delete it. Verify via SQL at each step.

**Transactions (2):**
- R: with FY 2025-26, `table.rowCount()` equals the SQL count for the FY.
  - Type filter (`f_type`) Income / Expense; the search box `f_search` with a known substring. Verify the row count against the equivalent SQL.
  - Clear the filters.
  - Header-click sort on date and amount; verify monotonic order through `item().text()` parsing.
  - The income / expense / net pill texts equal SQL.
  - Charts are present.
  - "Link Transfers": click "No" at the confirm; the count is unchanged.
  - Edit dialog opened on a real row, then Cancel: the DB is unchanged (fingerprint).
- S: run `test_excel_table_interactions.py` through `run_on_scratch.py` (it covers paste, cut, Delete key and Enter). Then:
  - "Add Transaction": `TransactionDialog`, with the date typed in `dd/MM/yy`.
  - "Edit" on an Other Income row whose category is not in the dropdown. **Fix check:** the category and mode survive Save unchanged.
  - Move a transaction to another account (new feature). Check whether both accounts' `current_balance` values are recalculated (hypothesis H20).
  - Single delete and multi-select delete. Afterwards, diff the transaction_id set against the pre-run set; exactly the intended ids should be gone (guide §8 incident).
  - Unsaved-changes bar: edit a cell, try to navigate away, and check the prompt. Test both Discard and Save.
  - "Link Transfers" → Yes: record pairs and marked, and diff `is_internal_transfer` ids.

**Income & Expectations (3):**
- R: the ledger, the TDS threshold table and the expectations table render; the expectations table is empty. Verify against SQL.
- S: CRUD for each of the 7 income types (Salary, Rent, Interest, Dividend, Business, Freelance, Other) × a representative mix of the 5 frequencies:
  - Add via "Add income expectation": all fields by OS, notes `RUIH_<type>`.
  - Verify the `IncomeExpectation` row.
  - Edit via "Edit selected income expectation": change the amount and verify.
  - Link and unlink an actual transaction ("Link actual transaction" / "Unlink transaction" / "Link selected transaction"); verify the link column.
  - "Auto-match income expectations": record the matches.
  - Delete via "Delete selected income expectation", with its confirm.
  - After adding a Salary and a non-Salary expectation, check the fix "salary standard deduction applied to non-salary": on the Tax screen (source "App Actual Data") the standard deduction applies only when a Salary expectation exists.
  - Record whether `project_fy_income().projected_total` changes when expectations exist (hypothesis H15).

**Fixed Deposits (4):**
- R: the table row count equals `SELECT COUNT(*) FROM FixedDeposit`; the status colours are shown. Open "Enter real fixed deposit rates": exercise "Bulk interest rate", the years / months / days spins and the compounding combo, then **Cancel**. The fingerprint is unchanged.
- S:
  - **Bulk dialog Save** for 2 Pending FDs: 7.10%, 1 y, Quarterly. Verify `interest_rate`, the tenure fields, `maturity_date` = start + 1 y, status → `Active`, and `maturity_amount` equal to an **independently computed** value using the `BankFDConvention` rules (quarterly compounding, Actual/365, simple interest below 183 days) within ₹1.
  - `FDInterestRecord` rows for the FYs spanned.
  - `get_prediction_summary(1,'2025-26')['projected_fd_interest']['known_fd_count']` goes up by 2.
  - "Save fixed deposit changes" on a Pending FD edited in-table (fix: no crash with no rate).
  - "Recalculate selected fixed deposits": `actual_interest_amount`, `linked_transaction_id` and `status` are preserved (fix).
  - "Link transaction to fixed deposit" and "Auto-link fixed deposit transactions": verify the link columns.
  - "Add fixed deposit" through `fd_dialog` (RUIH reference number).
  - "Delete selected fixed deposit": the row is gone and linked transactions are unaffected.

**Statement Import (5):**
- S only. The re-import idempotency test: re-drop Jana. The preview shows every row as a duplicate and the import adds 0 (fix "breaking duplicate detection on re-import").
- Then run with a new RUIH account (Jana file) and, in the preview, do the following with the rows selected by OS click and shift-click on "Select transaction row N":
  - "Merge selected transactions" on 2 rows;
  - "Split selected transaction" on 1;
  - "Shift selected transaction dates";
  - "Bulk edit selected transactions";
  - delete a row;
  - "Clear transaction selection".

  After each action, verify `preview_transactions` / the table cells change for **exactly the selected rows** (fix: uses the table selection, not the checked rows). Then import and verify the DB reflects the edited preview.
- "Copy debug report": the clipboard is non-empty.
- "Export debug report": the typer types a scratchpad path; the file exists.
- "Back button" at each stage.
- Excel path: "Select Excel format" and "Map Excel columns" with a synthetic `.xlsx` in the session scratchpad (RUIH rows). Use the user's xlsx only if they say so.
- Also run the nav-fixed `test_statement_import_flow.py` through `run_on_scratch`.

**Tax Documents (6):**
- R: re-drop is not needed. Leave the screen, change the FY, come back: `ais_tis_page` is never refreshed (hypothesis H1), so record what is shown. Hover and scroll the 3 tables.
- S: a fresh session with the FY combo at **2026-27**, dropping **AIS only**. Check which FY `AISTISImport` stores (hypothesis H3). Then run `test_tax_documents_flow.py` through `run_on_scratch`.

**Tax (7):**
- R: "Tax person selector" = Pranav; "Tax data source selector" = "AIS/TIS Data". Verify the prefilled inputs equal the AIS figures, with no double-counting of other interest or dividends (fix). Then "App Actual Data": the inputs equal the engine's realised figures.
  - Switch person and FY and back: no stale values (fix).
  - OS-click "Estimate tax" once. Verify each waterfall row value (`waterfall_*` rows' values) equals `calculate_new_regime_tax(gross, …, financial_year='2025-26')` called independently in the verifier, and that the `TaxProfile` row was written with the same totals. This is the allowed R delta.
- S: all 27 input spins, via OS click, select-all and type. Use the Phase 4 tax vectors; the waterfall must equal the independent expected values.

**Income Prediction (8):**
- R: with the FY at 2025-26, `prediction_page._prediction_data['financial_year']=='2025-26'` and the header label matches.
  - The headroom / limit / projected texts equal `get_prediction_summary(1,'2025-26')` values called independently.
  - The TDS risk table rows equal `tds_risk` per bank.
  - The comparison table (FD / Savings / Total / TDS rows) matches.
  - No "gap", "mismatch" or "error" strings (`findChildren(QLabel)` text scan).
  - **FY-change test:** while on this screen, switch the FY combo to 2026-27. Check whether `_prediction_data['financial_year']` follows. The code suggests it will not: `_on_refresh_all`'s list maps index 8 to `settings_page.refresh` and the screen has no `refresh()` (hypothesis H1/H2). Also navigate away and back.

**Settings (9):**
- R:
  - **Themes:** OS-click each `ThemeCard` (`settings_page._theme_cards[name]`: Aurora, Slate, Nova, Midnight Pro). Verify `ThemeManager.current_name()`, then run the §5.4 pixel-brightness scan per screen, excluding `ThemeCard` (reuse the `test_dark_theme_sweep.py` logic). Check `theme_prefs.json` after each switch; hypothesis H6 is that `_write_pref` drops `sidebar_open`. Restore the original JSON at the end.
  - **Change password, validation only:** empty fields → warning; mismatch → warning; fewer than 8 characters → warning; a wrong *current* password with a valid new pair → "Old password is incorrect". This returns before any write; verify the `AuthSecurity` hash is unchanged. **Never** submit the correct current password.
  - **Privacy mode:** on → Overview masked → off; the DB flag is back to its original value.
  - "Quick backup" / "Create database backup": the new `backups\backup_*.db` exists, size > 0, `integrity_check`=ok.
  - "Restore database from backup": click **No** at the confirm only.
  - "Check AI availability" / "Warm up local AI model": record the graceful message if Ollama is absent; install nothing.
  - "Manage people", "Manage bank accounts" and "Manage banks (master)" open the dialog.
- S:
  - Enable TOTP: `totp_secret` is set. Log in with an OTP computed from the scratch secret in memory, then disable TOTP.
  - A full restore from a scratch backup.
  - Edit and delete of a RUIH person and bank.

**Also, in R:** `test_button_size_audit.py`, `test_dark_theme_sweep.py` and `test_transactions_scale.py` as-is (read-only). Fingerprint before and after, and restore `theme_prefs.json`.

**Phase 3 exit criteria:** every control above is exercised, or logged with the reason it was not. The real DB fingerprint delta is exactly `TaxProfile`, and the PersonalData hashes are unchanged.

---

## Phase 4: Backend verification (headless; after Phase 3; nothing else running)

Run each command with output redirected to `screenshots\rebuild\P4_<name>.log`.

1. `.venv\Scripts\python.exe tools\run_full_tests.py`.
   - Baseline: 35 PASS, 2 CRASH (`test_chart_relocation.py`, `test_money_label.py`). Read `%TEMP%\finmgr_test_logs\` to confirm those two are the benign teardown crash.
   - `test_chart_db_agreement.py` reads the real DB. It will fail its hard-coded 254784.00 / 6240898.21 asserts unless P2.9 was applied. Classify that as baseline drift; its SQL==engine asserts must pass.
2. `.venv\Scripts\python.exe tools\test_prediction_engine.py`. Classify each FAIL:
   - **Baseline-coupled** (realised taxable 254784, non-taxable 6240898.21, `estimated_fd_count` 19, `known_fd_count` 0, FD total 80291, projected 335075, headroom 864925): explain from the P2.8/P2.9 facts. Do not edit the numbers without user approval (guide §7.1).
   - **Invariant** (critical guard, FD-count sum == DB, `is_estimated`, idempotency, zero-side-effect, ITR stored values, limit 1200000, threshold 50000): these must pass. A failure is a bug.
3. `tools\extraction_audit.py`: modern parser, 3 statements, confidence 1.000 and counts equal P0. Plus Equitas through the P0 script (the audit omits it).
4. `tools\taxdoc_audit.py data\PersonalData\Pranav\26AS.pdf`: 211 line items (194A ×206, 194JB ×4, 194JA ×1), 25 B + 9 G reversals netted, net ₹13,367.00, net gross ₹3,50,458, and the 6 per-deductor pairs from §4. **Exact.**
5. `tools\tax_reconcile.py`:
   - The 26AS side equals §4 exactly (Equitas ₹54,816, Jana ₹34,469, Ujjivan ₹79,077).
   - The "our transactions" side is compared with the §4 table (Equitas ₹92,257, Jana ₹4,001, Ujjivan ₹0, IDFC ₹244). Explain any difference by category effects. Ujjivan at ₹0 is expected (§1).
6. **New independent verifier** (`tools\rebuild_verify.py --engines`, read-only on the real DB). It recomputes each figure with its own SQL and formulas, not the engine functions, and compares:
   - **`realised_income_to_date(1,'2025-26',date(2026,3,31))`:** taxable, non-taxable and unclassified from `SUM(amount) … GROUP BY category` using `TAXABLE_INCOME_CATEGORIES`, excluding `is_internal_transfer=1` as documented. Must be equal to the paisa.
   - **`project_fd_interest`:** read `_synthesise_fd` for its synthesis rules (default rate `DEFAULT_FD_RATE` 7.5%, tenure assumption). Compute interest per FD with your own formula, limited to the FY window and maturity (fix). Tolerance ₹1 per FD. `estimated_fd_count + known_fd_count` equals the Active + Pending FD count.
   - **`project_bank_tds_risk`:** per bank, projected FD plus realised interest versus the threshold. The threshold is 50,000, or 1,00,000 with `Form 15H` if the DOB makes the person 60 or older (fix check).
   - **`compare_our_data_to_itr`:** ITR values equal the stored AIS values (FD 2,56,642, savings 46,183) and TDS equals 13,367.
   - **Tax engine vectors** (`calculate_new_regime_tax(..., financial_year='2025-26')`, a pure function; never `calculate_and_save_tax` on the real DB). Expected values under the seeded new-regime slabs:

     | Case | Expected tax |
     |---|---|
     | Non-salary ₹12,00,000 | 0 (slab 60,000, rebate 60,000) |
     | ₹12,10,000 | 10,400 (slab 61,500, marginal relief caps it at 10,000, plus 4% cess) |
     | ₹13,00,000 | 78,000 (no relief) |
     | Salary ₹12,75,000 | 0 (standard deduction 75,000 → 12,00,000) |
     | ₹3,50,458 | 0 |
     | ₹60,00,000 | 15,78,720 (slab 13,80,000, 10% surcharge 1,38,000, 4% cess 60,720) |

     Special-rate probes, reported as legal-verification items for the owner or a CA, not asserted as bugs:
     - normal ₹5,00,000 plus STCG-111A ₹1,00,000: statute for FY 2025-26 gives 20,800 (20%); the engine uses 15%.
     - LTCG-112A ₹2,00,000 on top of ₹5,00,000 normal: statute gives 12.5% on (2,00,000 − 1,25,000) = 9,375 plus cess = 9,750; the engine uses a single 15% on everything.
   - **`calculate_advance_tax`** with a ₹1,00,000 liability: the instalments are cumulative 15 / 45 / 75 / 100%, i.e. incremental 15k / 30k / 30k / 25k (fix check). Read the function's doc for which of the two it returns.
   - **Savings interest opening balance** (fix): for an account whose statement spans two FYs, the opening balance used for the second FY equals the last `balance_after` before 1 April.
   - **`change_password` re-encryption**, in a throwaway temp DB in the session scratchpad (never the real or scratch DB):
     - `initialise_database` → `setup_master_password('Tmp#Pass123')` → set an encrypted statement password and an AIS password with the derived key → `change_password` → both decrypt with the new key and fail with the old one.
     - Then corrupt one ciphertext and re-run: confirm the silent-skip behaviour (hypothesis H12).
   - **Formatters:** `ui/dashboard_screen._format_indian_number` and `money_label` with 0.005, 1234567.899, −1,00,000.10 and 99.999. Compare against a hand-written Indian-grouping reference (fix: digit scrambling).
7. **Chart and KPI agreement:** the widget texts captured in Phase 3 versus the SQL in step 6 (already covered by the Phase 3 R checks; list the results here).

**Checkpoint P4:** every log exists and every FAIL is classified as regression, baseline drift, or legal-verification item.

---

## Phase 5: Findings

Write `screenshots\rebuild\FINDINGS.md` and hand the list to the caller; do not commit it.

**Severity:**
- **Critical:** data loss or corruption, wrong tax or TDS figures, secrets exposed, a crash or deadlock.
- **High:** a committed fix does not hold under real use; wrong FY or person attribution; a figure shown to the user that is wrong.
- **Medium:** stale UI that misleads; a validation gap; a threading violation that has not yet crashed.
- **Low:** accessibility names, wording, cosmetic.

Each finding needs: repro steps (the script and step), the expected value, the observed value, the evidence (SQL output, widget-state line, log path; a screenshot only as a supplement), and the file and line.

**Fix-claim ledger.** A table of all 27 bullets in the e721005 commit message. Status for each:
- Held (with evidence);
- Failed;
- Partly held (for example the income-prediction FY fix is first-build only);
- Not reachable from the UI (for example the privacy-reveal fix: `ui/widgets/privacy_overlay.reveal_with_password` has no callers);
- Not exercised (with the reason).

**Seeded hypotheses** from code reading. Each must be confirmed or refuted with evidence; none is to be reported as fact without it:

- **H1.** `ui/dashboard_screen.py:_on_refresh_all` has 9 entries for 10 screens:
  - index 6 uses `self.ais_tis_page`, but the attribute is `tax_documents_page`;
  - index 8 calls `settings_page.refresh`, but screen 8 is Income Prediction;
  - Settings (9) is never refreshed.
- **H2.** `IncomePredictionScreen` loads only in `__init__`; it has no `refresh()`.
- **H3.** AIS/TIS FY depends on 26AS being imported first in the same session; otherwise the top-bar FY is used (default 2026-27).
- **H4.** `tax_documents_screen` hard-codes `person_id=1` for get/set of the AIS password; persistence uses `selected_person_id or 1`.
- **H5.** `reveal_with_password` has no callers.
- **H6.** `ThemeManager._write_pref` overwrites `sidebar_open`.
- **H7.** `core/backup_manager.create_backup` uses `shutil.copy2` on a WAL-mode DB. It is used by the 24 h periodic backup, `taxdoc_import` and the tax-docs test.
- **H8.** Special-rate capital gains use a single rate and no 112A exemption (legal check).
- **H9.** `engines/taxdocs/merge.py` hard-codes `tax_payable=0`, `refund_due`=all TDS and standard deduction 0, and the Tax Documents screen shows "Refund Due" from this.
- **H10.** `PersonDialog` DOB cannot be left blank (defaults to today) and uses the two-digit `yy` format.
- **H11.** `TransactionDialog` cannot select Commission Income or Professional Fees (taxable categories missing from `config.INCOME_CATEGORIES`).
- **H12.** `change_password` silently skips ciphertexts it cannot decrypt, orphaning them.
- **H13.** The import worker connects `progress` to a plain callable. If `self._loader` is set, `_update_loader` touches widgets and calls `processEvents()` from the worker thread.
- **H14.** The import rollback does not undo `apply_statement_redemption_event` changes.
- **H15.** `project_fy_income` ignores `IncomeExpectation`.
- **H16.** The bank YAML profiles (`load_profile`) are unused by the modern parser.
- **H17.** Three real-UI scripts have the stale nav index 8.
- **H18.** The Overview "Income (FY)" tile is the naive gross sum.
- **H19.** The existing harness scripts bypass login and `initialise_database`.
- **H20.** Moving a transaction to another account does not recalculate either account's balance.

**Also report:**
- the Phase 2 numeric deltas against the old baseline, each with its cause;
- the list of controls without accessible names;
- a final integrity statement: PersonalData hashes unchanged, `git status` clean of data files, `theme_prefs.json` restored, and the real DB fingerprint delta limited to the allowed rows.

---

## Appendix: new tooling (write in Phase 0.6; do not commit)

All files go in `D:\Pranav\app\tools\real_ui_tests\` unless noted.

**`rebuild_common.py`**

- **`bootstrap_app()`:** mirrors `main.launch_app` minus `app.exec()`, in this order: `set_windows_app_user_model_id()`, `ensure_logo_assets()`, `QApplication`, `setStyle("Fusion")`, `QFont("Segoe UI",10)`, `install_copyable_error_dialogs()`, `ThemeManager.load_and_apply()`, `app.setStyleSheet(Theme.get_stylesheet())`, `os.makedirs(BACKUP_DIR)`, `initialise_database()`. Then build `RealUIHarness`, which reuses the existing `QApplication`.
- **`read_secret(kind)`:** kinds `master`, `ais_tis`, `equitas`; read from `password.txt`; raises without echoing the value.
- **`adopt_window(w)`:** `hwnd=int(w.winId())`, then the same `SetForegroundWindow` / `AttachThreadInput` fallback as `harness.launch`. `assert_foreground(w)` retries 3×, then raises a FOCUS failure.
- **`os_click(widget, local_pt=None, double=False)`:**
  1. `harness.scroll_into_view`; for table items, `scrollToItem` first.
  2. Assert the widget `isVisible()` and `isEnabled()`.
  3. Compute the global logical point.
  4. **Guard:** `QApplication.widgetAt(pt)` is the widget or a descendant, **and** `win32gui.WindowFromPoint(physical)` belongs to `os.getpid()`.
  5. `assert_foreground` on the widget's window.
  6. `harness.click_at_via_os` / `double_click_via_os`.
  7. Log the name and the logical and physical coordinates.
- **`os_type(w, text, secret=False)`:** `os_click` → `ctrl+a` → `backspace` → `pyautogui.write(text, interval=0.03)` → settle → assert the read-back (`text()` / `value()`) matches. For secrets, print the bool only.
- **`os_select_combo(combo, text)`:** `os_click(combo)` → `view=combo.view()`; `i=combo.findText(text)`; `view.scrollTo(idx)`; `os_click(view.viewport(), view.visualRect(idx).center())` → assert `currentText()`.
- **`os_set_date(dateedit, qdate)`:** `os_click` → `Home` → type the date in `displayFormat()` → assert `date()==qdate`. On mismatch, record a finding and fall back to `setDate` (labelled non-OS).
- **`prearm(cb)`:** a `QTimer.singleShot(0)` wrapper that captures exceptions and sets a done flag.
- **`wait_until(pred, timeout)`.**
- **`start_modal_watchdog()`:** a 500 ms `QTimer` that logs any visible `QMessageBox` / `QDialog` not in the expected set (title and redacted text). After 5 s it takes a screenshot, rejects the dialog and records a failure.
- **`login_to_dashboard(harness, login=None)`:**
  1. Assert `not is_first_run()`.
  2. Launch `LoginScreen` if not given.
  3. `os_type` "Master password" (secret) → OS-click "Unlock account".
  4. `wait_until(login.dashboard visible, 90)`, then `adopt_window`.
- **`snapshot_db(tag)`** and **`db_ro()`**: as described in Phase 2.
- **`fingerprint_real_db()`:** the per-table count plus the SHA-256 of `SELECT * ORDER BY rowid`.
- **`redacting_logger(script_name)`.**
- **Nav helper:** OS-click `"Navigate to <label>"` by accessible name, never `_nav_buttons[i]`.

**`os_file_dialog_typer.py`** runs as a separate process (no GIL dependence on the blocked Qt thread).
- Arguments: `--pid --path --timeout 30`.
- It polls `win32gui.EnumWindows` for a visible `#32770` window owned by the pid, foregrounds it, waits 0.7 s, presses `alt+n`, writes the path, presses `enter`, and exits 0; it exits 2 on timeout.
- The caller starts it *before* the OS click on the drop zone or "Export debug report", then asserts the exit code.

**`run_on_scratch.py <script> [args]`:**
- Patches `config.DB_PATH` and `core.database.DB_PATH` to `backups\phase3_scratch.db`, and the session and theme `_CONFIG_FILE` to scratch copies.
- Asserts the patched path is not the real one.
- Fingerprints the real DB, then `runpy.run_path(script, run_name="__main__")`, then fingerprints again. A mismatch means exit 3 and **STOP**.

**Script repairs:** in the 3 add_* scripts, replace `_nav_buttons[8]` with the "Navigate to Settings" accessible-name lookup, and change the index asserts to 9.

**`D:\Pranav\app\tools\rebuild_verify.py`** (read-only):
- `--state` prints the Phase 2 completion predicates, used for the resume decision.
- `--fingerprint`.
- `--engines` runs the Phase 4 step 6 checks.
- `--expect P0_expectations.json` compares Phase 2 against P0.

**Resume protocol after any interruption:**
1. Kill leftover app processes.
2. Run `rebuild_verify.py --state`. The first step whose predicate fails is the resume point.
3. If the DB fails `integrity_check`, restore the last snapshot.
4. Re-run that step's script. Every step is idempotent by construction.

### Critical files for implementation
- D:\Pranav\app\tools\real_ui_test_harness.py
- D:\Pranav\app\ui\statement_import_screen_modern.py (FD creation at `_TransactionImportWorker.run`, preview and import flow)
- D:\Pranav\app\ui\tax_documents_screen.py (26AS→AIS→TIS order, password dialogs, FD matching)
- D:\Pranav\app\ui\dashboard_screen.py (nav, `_on_refresh_all` mapping, FY combo)
- D:\Pranav\app\core\auth.py and D:\Pranav\app\ui\setup_screen.py (first-run setup and login after reset)
- Also: D:\Pranav\app\models\fixed_deposit.py, D:\Pranav\app\engines\prediction_engine.py, D:\Pranav\app\tools\backfill_transactions.py, D:\Pranav\app\tools\test_prediction_engine.py, D:\Pranav\app\tests\test_chart_db_agreement.py, D:\Pranav\app\tools\taxdoc_import.py (password readers)