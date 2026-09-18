
# Real UI Test Campaign — Execution Roadmap

**Status:** ready to execute. **Created:** 2026-09-18.
**Audience:** an implementation agent with NO other context. Read only this file plus the files each unit names.

## 0. Read this before executing ANY unit

### 0.1 What this campaign is
This is a **testing campaign against a PySide6 desktop app at `D:\Pranav\app`** that was just migrated from PyQt6 and given a UI/motion pass. The app has many known, pre-existing bugs. **Finding bugs is the POINT.** A unit that finds ten bugs has succeeded.

### 0.2 THE RECORD-DO-NOT-FIX RULE (applies to EVERY unit, no exceptions)
> **You must NOT modify any application code.** Not `ui/`, not `models/`, not `engines/`, not `core/`, not `config.py`. If a test reveals a bug in the app, **write it down in the findings log and move on to the next check in your unit.** Do not "just quickly fix" anything, even a one-liner, even if it is obviously wrong.
>
> **The only files you may create or modify are:**
> - new test scripts under `tools/real_ui_tests/`
> - your own test script, if the *script* is wrong (wrong accessible name, wrong assertion)
> - the "Findings log" section at the bottom of `docs/VISUAL_TESTING_GUIDE.md` (append only — never delete a prior entry)
> - `tools/real_ui_tests/screenshots/` (generated images)

### 0.3 THE DATABASE IS REAL USER DATA
This project's SQLite database contains the owner's **real financial records**. It is **not** a disposable fixture.
- Never call a bulk delete, never truncate, never "reset" anything.
- Any row your test creates, your test must delete, in a cleanup path that runs on **both** success and failure (see `report()` in `tools/real_ui_tests/test_add_person_flow.py`).
- For a **destructive** test (Delete Selected / delete a row): **create your own row first, record its ID, delete only that ID, and assert the total row count went back to exactly its pre-test value.** Never select an existing row and delete it.
- Prefix every test-created record with `RUIH_` so orphans from an interrupted run are identifiable by hand.

### 0.4 Mandatory setup snippet for every new test file
Copy this header into every new test script. It is taken from the working template.

```python
import os, sys
os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
# Do NOT set QT_QPA_PLATFORM=offscreen — the whole point is a REAL visible window.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
```

Then, exactly as in the template: build `SHOT_DIR`, a `failures` list, a `check(label, condition)` helper, `main()`, and a `report(harness, ...)` that does cleanup, prints a SUMMARY, closes every top-level widget, and returns `1 if failures else 0`.

### 0.5 Run command
```
.venv/Scripts/python tools/real_ui_tests/<your_test_file>.py
```
Run from `D:\Pranav\app`. Each test must exit on its own, leaving no window open.

### 0.6 The five harness hazards — memorize these

| # | Hazard | What it looks like | What you must do |
|---|---|---|---|
| §3.5 | **Repaint lag** | A screenshot shows the PREVIOUS screen even though `label.text()` already returns the new value. | Never conclude a bug from a screenshot alone. Always `harness.settle(1.5)` then cross-check widget state (`.text()`, `.isChecked()`, `stack.currentIndex()`, a DB query). Report "screenshot shows X, widget state says Y" — both. |
| §3.6 | **`QTest.mouseDClick` never fires `doubleClicked`** | A double-click test "fails" with zero app involvement. This is a QTest limitation, **not an app bug**. | `harness.double_click()` uses QTest and is unreliable. Use `harness.double_click_via_os(widget)` (real OS double-click) AND cross-check the keyboard path (select row + `Qt.Key.Key_Return`). If ambiguous, report it as **UNCONFIRMED**, never as "broken". |
| §3.8 | **Modal `.exec()` blocks `QTest.mouseClick`** | You click a button that opens a dialog and the call never returns; the dialog never appears in `allWidgets()`. | **Schedule the interact-with-the-dialog callback with `QTimer.singleShot(0, cb)` BEFORE clicking the opening button.** Then click, and let `harness.settle()` pump the nested loop. See `test_add_person_flow.py` lines 99-119. Every `PersonDialog`/`BankDialog`/`AccountDialog`/`FdDialog` is opened via `.exec()`. |
| §3.4 | **Scroll-into-view** | A widget below the fold reports valid geometry but isn't visible. | `harness.click()` calls `scroll_into_view()` automatically. Call `harness.scroll_into_view(w)` explicitly before any `harness.shot()` that must show a below-the-fold widget. |
| §3.1/3.2 | **DPI + geometry** | Only affects the OS-coordinate escape hatch. | Always `harness.launch(..., maximized=True)` (the default). Never pass `resize=`/`move=`. Log `harness.dpr` at the start of every run. |

**Extra hazard, discovered while planning this campaign — NATIVE FILE DIALOGS WILL HANG YOUR TEST.**
`ui/widgets/drop_zone.py` `_on_browse_click()` and `mousePressEvent()` both call `QFileDialog.getOpenFileName()`. That is a **native Windows modal** which QTest cannot close. **If you click a DropZone, your test hangs forever and you will have to kill it.** Never click a DropZone. Instead emit its signal directly: `screen.zone_26as.fileSelected.emit(r"D:\Pranav\app\data\PersonalData\Pranav\26AS.pdf")`. The same applies to any "Browse…" button.

**Extra hazard — background threads.** `ui/widgets/loader.py` `Loader.run()` executes work on a real `QThread` (PDF parsing, transaction import). A plain `harness.settle(2)` is not enough. Poll:
```python
import time
deadline = time.time() + 60
while time.time() < deadline and not <completion_condition>:
    harness.settle(0.5)
```

### 0.7 Discovering accessible names — DO NOT GUESS
Where this plan marks a name **(VERIFY)**, the name is a best guess. Before using it, print the real candidates:
```python
def dump_names(root, label=""):
    from PySide6.QtWidgets import QWidget
    print(f"--- accessible names under {label or root} ---")
    for w in [root] + root.findChildren(QWidget):
        n = w.accessibleName()
        if n:
            print(f"  {n!r:55} {type(w).__name__:22} visible={w.isVisible()} enabled={w.isEnabled()}")
```
Call `dump_names(screen, "SettingsScreen")` and read the output. If the guessed name isn't there, use the real one and note the correction in your findings entry. **A `LookupError` from `harness.find()` is a test-script bug, not an app bug** — fix your script (that is allowed) and re-run.

### 0.8 The findings-log entry format (MANDATORY — this is the durable artifact)
Every unit **appends** to the `## Findings log` section at the bottom of `docs/VISUAL_TESTING_GUIDE.md`. Append **below** all existing entries. Never delete or rewrite an earlier entry.

Use exactly this shape:

```markdown
### 2026-09-18 — Unit N: <unit name>

**Ran:** `tools/real_ui_tests/<file>.py` (theme: Aurora, dpr: <value>, maximized)
**Result:** <N> checks passed, <M> failed.

#### FINDING N.1 — <short title> [BUG | NOT-A-BUG | UNCONFIRMED | TEST-HARNESS-ONLY]
- **What I did:** <exact clicks/typing, in order, with the accessible names used>
- **Expected:** <what should have happened>
- **Observed (widget/DB state):** <exact values: stack.currentIndex()==0, page_title_lbl.text()=='Settings', DB row count 7 -> 7>
- **Observed (screenshot):** `tools/real_ui_tests/screenshots/NN_name.png` — <what is visible>
- **Repaint-lag ruled out?** <yes, because state disagreed after settle(2.0) / no, state and pixels agreed>
- **Suspected location:** `ui/<file>.py:<line>` — `<function name>` — <one sentence on the mechanism>
- **Severity:** <blocker | major | minor | cosmetic>
- **NOT FIXED** (per the campaign's record-do-not-fix rule).

#### FINDING N.2 — ...

**Nothing-to-report checks:** <one line listing what was verified working, so the next agent doesn't redo it>
```

If a unit finds **zero** bugs, it still appends an entry with the header, `**Result:**`, and the `**Nothing-to-report checks:**` line. An empty log entry is a campaign failure.

### 0.9 Parallelism rule — READ THIS
A real-UI test **opens a visible window and takes over screen focus and the screenshot surface**. Two of them running at once on this machine will corrupt each other's screenshots and interleave focus.

> **Only ONE test-RUNNING unit may execute at a time.** Units 1, 3, 4, 5, 6, 7 are write-and-run and are **SEQUENTIAL with respect to each other**.
> **Unit 2 is WRITE-ONLY (a pure code-reading audit, no window)** and can run in PARALLEL with anything.

---

## Unit summary table

| Unit | Name | Mode | Parallel/Sequential | Depends on |
|---|---|---|---|---|
| 1 | Navigation & Motion Triage | write-and-run | SEQUENTIAL — **must go first** | none |
| 2 | DPI-Scaling Code Audit | **write-only** (no window) | **PARALLEL** — any time | none |
| 3 | Add Bank + Add Account flows | write-and-run | SEQUENTIAL | Unit 1 |
| 4 | Statement Import end-to-end | write-and-run | SEQUENTIAL | Unit 3 (needs its DB knowledge; can use existing data if Unit 3 found blockers) |
| 5 | Tax Documents three drop zones | write-and-run | SEQUENTIAL | Unit 1 |
| 6 | Screen sweep + button size audit (9 screens, Aurora) | write-and-run | SEQUENTIAL | Unit 1 |
| 7 | ExcelTable interactions + Nova dark-theme repeat | write-and-run | SEQUENTIAL | Unit 6 |

Recommended order: **1 → 3 → 4 → 5 → 6 → 7**, with **2 running in parallel at any point**.

---

# UNIT 1 — Navigation & Motion Triage

**Mode:** write-and-run. **Sequencing:** SEQUENTIAL, **runs first**. **Depends on:** nothing.

## Why this unit exists
A screenshot from the last session (`tools/real_ui_tests/screenshots/02_01_settings.png`) showed two things that may or may not be bugs:
- (a) `page_title_lbl` read **"Settings"** but the visible body still showed the **Overview** screen's content (KPI cards, "Trends & Distribution", "No transaction data for this period").
- (b) The sidebar rendered **collapsed to icons only**.

Both must be disambiguated before any other unit trusts a screenshot. Every later unit depends on knowing whether screenshots from this harness are trustworthy.

**Two competing explanations for (a):**
1. **Repaint lag (§3.5)** — script-driven `processEvents()` lags the compositor. Test-harness-only, not an app bug.
2. **A real regression from the recent motion work.** `ui/dashboard_screen.py` `_navigate()` (around line 1003) calls `fade_in(screen)`. `ui/widgets/motion.py` `fade_in()` installs a `QGraphicsOpacityEffect` and **sets opacity to 0.0** before animating up to 1.0. If that animation is starved (script-driven event loop) or if `_opacity_effect()` returns `None` because a drop shadow is already installed, **the new page can genuinely sit at opacity 0**, letting stale pixels show through. That would be a real, user-visible bug.

**The likely explanation for (b):** `ui/dashboard_screen.py` line 149-150 does `self.sidebar_expanded = session.is_sidebar_open()` then `sidebar.setFixedWidth(248 if self.sidebar_expanded else 76)`. The collapsed render is probably **persisted session state, not a bug.** Confirm this — do not assume.

## File to create
`tools/real_ui_tests/test_navigation_and_motion.py`

## Exact steps

### Part A — baseline instrumentation
1. Use the §0.4 header. Import:
   ```python
   from PySide6.QtCore import Qt, QTimer
   from tools.real_ui_test_harness import RealUIHarness
   from ui.dashboard_screen import DashboardScreen
   from ui.theme.theme_manager import ThemeManager
   from ui.widgets import motion
   from core.session import session
   ```
2. Print and record `session.is_sidebar_open()` **before** constructing the window.
3. `ThemeManager.apply("Aurora", save=False, notify=False)`.
4. `harness = RealUIHarness(screenshot_dir=SHOT_DIR)`; print `harness.dpr`.
5. `dashboard = harness.launch(lambda: DashboardScreen(), maximized=True)`.
6. **Check the console for `WARNING: SetForegroundWindow fallback also failed`.** If it printed, note it in findings (screenshots may show the wrong window) but continue — `click()` does not need OS focus.
7. `harness.shot("00_launch")`. Record `dashboard.sidebar_expanded`.

### Part B — the navigation cross-check (motion ENABLED)
For **each** of the 9 nav indices `0..8` (`Overview, Accounts, Transactions, Income & Expectations, Fixed Deposits, Statement Import, Tax Documents, Tax, Settings`):
1. `harness.click(dashboard._nav_buttons[i])`
2. `harness.settle(2.0)` — a deliberately long settle to give the compositor every chance.
3. Capture and print ALL of the following into one dict:
   - `dashboard.stack.currentIndex()`
   - `type(dashboard.stack.currentWidget()).__name__`
   - `dashboard.stack.currentWidget().objectName()`
   - `dashboard.stack.currentWidget().isVisible()`
   - `dashboard.page_title_lbl.text()`
   - **The opacity of the page's graphics effect**, which is the crux:
     ```python
     from PySide6.QtWidgets import QGraphicsOpacityEffect
     eff = dashboard.stack.currentWidget().graphicsEffect()
     opacity = eff.opacity() if isinstance(eff, QGraphicsOpacityEffect) else None
     ```
   - `dashboard._screen_errors.get(i)` — if this is non-None the screen **failed to construct**; that is a serious BUG finding on its own, record the exception string verbatim.
4. `harness.shot(f"01_nav_{i}_motion_on")`
5. Assert with `check()`:
   - `stack.currentIndex() == i`
   - `page_title_lbl.text()` equals the expected nav title
   - `currentWidget().objectName()` does **NOT** start with `"placeholder_"` (a placeholder means the lazy swap in `_navigate()` failed — real BUG)
   - `currentWidget().isVisible()` is True
   - `opacity is None or opacity >= 0.99` — **if opacity is stuck below 1.0 after a 2-second settle, that is a REAL BUG**, the page is genuinely transparent on screen.

### Part C — the motion bisect (this is the disambiguator)
1. `motion.ENABLED = False`
2. Repeat the whole of Part B, screenshotting as `f"02_nav_{i}_motion_off"`.
3. Compare the two passes. Record the verdict explicitly:
   - **Body content correct with motion OFF, wrong with motion ON → REAL BUG in `fade_in()` usage in `_navigate()`.** Severity: major.
   - **Body content wrong in BOTH passes → not a motion bug**; the page swap itself is broken. Report with the `currentWidget()` type/objectName as evidence.
   - **Body content correct in both, only the original stale screenshot was wrong → repaint lag (§3.5), TEST-HARNESS-ONLY.** Record it as such so no later unit wastes time on it.
4. Restore `motion.ENABLED = True` at the end.

### Part D — sidebar expanded/collapsed under real rendering
1. Record `dashboard.sidebar_expanded` and `dashboard.findChild(QWidget, "sidebar").width()`.
2. Find the toggle button. Its accessible name is set dynamically to either `"Collapse sidebar"` or `"Expand sidebar"` (`_update_sidebar_toggle_btn`). **Do not hardcode** — use `dashboard._sidebar_toggle_btn` directly.
3. `harness.click(dashboard._sidebar_toggle_btn)`; `harness.settle(1.5)`; `harness.shot("03_sidebar_toggled")`.
4. Assert: `sidebar_expanded` flipped; sidebar width is now **248** (expanded) or **76** (collapsed) — **`animate_width()` connects `finished` to `setFixedWidth(target)`, so after a 1.5s settle the width must be exactly the target. A width stuck at an intermediate value is a REAL BUG** (the animation was starved and never finished, leaving the sidebar half-drawn).
5. Assert the nav labels' visibility matches: with the sidebar expanded, `btn._text_label.isVisible()` should be True for every button in `dashboard._nav_buttons`; collapsed, False. Report any mismatch.
6. Toggle back and assert it returns to the original width.
7. **Nav active accent bar:** with a screen selected, screenshot and record which button `_set_nav_active(index)` styled. Check via `dashboard._nav_buttons[i].isChecked()` (or the equivalent property found by reading `_set_nav_active` around line 319). Assert exactly one is active and it matches `stack.currentIndex()`.
8. Repeat steps 3-4 once with `motion.ENABLED = False` to confirm whether any width problem is motion-related.

### Part E — cleanup
This unit creates **no database rows**. Cleanup is just closing windows (the `report()` pattern's top-level-widget close loop). Restore `motion.ENABLED = True` and do **not** call `session.set_sidebar_open()` with a changed value — if your toggles left it changed, set it back to the value recorded in Part A step 2.

## Deliverables
- `tools/real_ui_tests/test_navigation_and_motion.py`
- Screenshots `00_*` through `03_*` in `tools/real_ui_tests/screenshots/`
- A findings-log entry in `docs/VISUAL_TESTING_GUIDE.md` per §0.8. **It must contain an explicit, unambiguous verdict sentence on the stale-Settings-screenshot question**, in one of these three forms: "REAL BUG in fade_in()", "REAL BUG in the page swap", or "TEST-HARNESS-ONLY repaint lag (§3.5)". And an explicit verdict on the sidebar: "persisted session state, NOT a bug" or the alternative.

## Hazards for this unit
§3.5 repaint lag is the whole subject — use `settle(2.0)`, never `settle()` default. Some screens may throw during lazy construction; `_get_screen_page()` swallows it into `_screen_errors` and shows an error page, so **check `_screen_errors` explicitly** or you will silently "pass" a screen that crashed. **Record, do not fix.**

---

# UNIT 2 — DPI-Scaling Code Audit (WRITE-ONLY, no window)

**Mode:** **write-only** — reads source code, opens no window, runs no test. **Sequencing:** **PARALLEL**, may run at any time alongside any other unit. **Depends on:** nothing.

## Why this unit exists
`docs/VISUAL_TESTING_GUIDE.md` §3.1 confirms this dev machine runs Windows display scaling at 125% (`devicePixelRatio == 1.25`). Qt widget geometry is in **logical** pixels; the physical screen is in **physical** pixels. §3.1 flags that **nobody has ever audited the app itself** for code that assumes a 1:1 mapping. If any app code does manual pixel math against screen coordinates, it misbehaves for a real user on a scaled display — a common laptop config, not an edge case.

## What to do
This is a **code-reading task**. Produce **no** test script; produce **only** a findings-log entry.

Search the whole of `ui/`, `core/`, and any other app package (not `tools/`, not `.venv/`) for these patterns and read every hit in context:

1. **Screen-coordinate math:** `mapToGlobal`, `mapFromGlobal`, `globalPos`, `globalPosition`, `QCursor.pos`, `screen().geometry`, `availableGeometry`, `primaryScreen`, `devicePixelRatio`, `logicalDotsPerInch`, `physicalDotsPerInch`.
2. **Manual positioning:** `.move(`, `.setGeometry(`, `.setFixedSize(`, `.setFixedWidth(`, `.setFixedHeight(` — especially any that computes from a screen dimension rather than from a fixed design constant.
3. **Custom painting:** any `paintEvent`, `QPainter`, `drawText`, `drawRect`, `drawPixmap`, `QPixmap(` with explicit sizes, `QIcon.pixmap(`, `.scaled(`.
4. **Pixel constants used against screen space** (as opposed to widget space, which is fine).
5. **Screenshot / image capture**: `grab()`, `render(`, `QScreen.grabWindow`.
6. **Anything using `pyautogui`, `win32gui`, `win32api` inside `ui/`** (there should be none — if there is, it is a strong candidate).

For each hit, classify it in the findings entry:
- **SAFE** — pure widget-local logical geometry, Qt handles scaling. (Most `.setFixedWidth(248)` calls are this.)
- **SUSPECT** — mixes a Qt logical coordinate with anything physical, or hardcodes a pixel value derived from a screen measurement, or paints at a fixed pixel size that would be blurry/wrong at dpr != 1.0.
- **CONFIRMED-RISK** — you can name a concrete scenario: "at 125% scaling, `<file>:<line>` computes X, which lands Y logical pixels off." A `QPixmap` created without `setDevicePixelRatio()` and drawn at a fixed size is a classic CONFIRMED-RISK (renders blurry / half-size on a HiDPI screen).

Also check whether the app sets any of the Qt HighDPI policy knobs at startup (look in `main.py` and `config.py` for `AA_EnableHighDpiScaling`, `AA_UseHighDpiPixmaps`, `QT_ENABLE_HIGHDPI_SCALING`, `HighDpiScaleFactorRoundingPolicy`). In Qt6 high-DPI scaling is on by default, and the rounding policy matters at **125%** specifically — the default `PassThrough`/`Round` behaviour differs and a 1.25 factor is exactly where rounding policies diverge. **Record which policy (if any) the app sets, and note that at 1.25 the default rounding can produce a 1-pixel layout difference.** This is a legitimate finding either way.

## Deliverables
- **No test script. No app code changes.**
- One findings-log entry in `docs/VISUAL_TESTING_GUIDE.md` per §0.8, listing every SUSPECT and CONFIRMED-RISK hit with `file:line`, the code snippet, and the concrete failure scenario at `dpr == 1.25`. Include a short "SAFE — audited and clear" list naming the files you read and cleared, so the next agent knows the audit was complete rather than shallow.
- Set `**Ran:**` to `code audit only — no window opened`.

## Hazards for this unit
None of the interaction hazards apply. The only hazard is **reporting a SAFE pattern as a bug** — Qt6 handles logical-pixel widget geometry correctly on its own, so `setFixedWidth(248)` is not a finding. Be specific about the mechanism or classify it SAFE. **Record, do not fix.**

---

# UNIT 3 — Add Bank + Add Account End-to-End Flows

**Mode:** write-and-run. **Sequencing:** SEQUENTIAL. **Depends on:** Unit 1 (you need its verdict on whether screenshots are trustworthy).

## Why this unit exists
These are flows 2 and 3 of the five the app owner explicitly asked for (`docs/VISUAL_TESTING_GUIDE.md` §5). Flow 1 (Add Person) already passes.

## Files to create
- `tools/real_ui_tests/test_add_bank_flow.py`
- `tools/real_ui_tests/test_add_account_flow.py`

Two separate files, per §6 rule 1 ("one file per flow"). Both follow `test_add_person_flow.py` exactly.

## Route to the dialogs (VERIFIED)
`ui/settings_screen.py` builds three buttons from titles `"People"`, `"Bank Accounts"`, `"Banks (Master)"` with `b.setAccessibleName(f"Manage {title.lower()}")`, so the accessible names are:
- `"Manage people"`
- `"Manage bank accounts"`
- `"Manage banks (master)"`

**All three call `_show_manage_data_screen()`** — the same `QDialog` titled `"Manage Data"` containing a `ManageDataScreen` with a `QTabWidget` whose tabs are `People` (0), `Banks` (1), `Accounts` (2). So the tab must be switched explicitly:
```python
mds = manage_dialog.findChild(ManageDataScreen)
mds.tabs.setCurrentIndex(1)   # Banks
harness.settle(1.0)
```

## test_add_bank_flow.py — exact steps

1. Constant: `TEST_BANK_NICKNAME = "RUIH_TestBank_01"`, `TEST_BANK_NAME = "Jana Small Finance Bank"` (a real bank name per `docs/AUDIT_AND_REBUILD_PLAN.md` §3 — Jana, Equitas, IDFC, Ujjivan).
2. `from models.bank import get_all_banks, delete_bank`. Snapshot `before = get_all_banks()` and print the count.
3. Launch exactly as in Part A of Unit 1 (Aurora, maximized, log `dpr`, check the focus warning).
4. `harness.click(dashboard._nav_buttons[8])` (Settings); `harness.settle(1.5)`; assert `dashboard.page_title_lbl.text() == "Settings"` and `dashboard.stack.currentIndex() == 8`.
5. `settings_screen = dashboard.settings_page`; `harness.click(settings_screen, "Manage banks (master)")` **(VERIFY with `dump_names(settings_screen, "SettingsScreen")` first)**.
6. `manage_dialog = harness.find_dialog(QDialog, "Manage Data")`; assert non-None; `harness.shot("01_manage_data_banks")`.
7. Switch to the Banks tab as shown above. Screenshot.
8. **Dump the names inside the dialog** — `dump_names(manage_dialog, "ManageDataScreen")` — and confirm `"Add bank"`, `"Bank list"`, `"Edit bank"`, `"Delete bank"` are present. Record any that are missing as a finding (a control with no accessible name is a real accessibility defect worth logging).
9. **§3.8 MODAL PATTERN — this is mandatory.** `BankDialog` is opened via `.exec()`. Schedule first, click second:
   ```python
   fill = {}
   def _fill_and_save_bank():
       from ui.dialogs.bank_dialog import BankDialog   # import at top of file, not here
       dlg = harness.find_dialog(BankDialog, timeout=2.0)   # title may vary — pass None and match by class
       fill["opened"] = dlg is not None
       if dlg is None: return
       harness.shot("02_bank_dialog_open")
       harness.type_into(dlg, "Bank nickname", TEST_BANK_NICKNAME)
       harness.type_into(dlg, "Bank name", TEST_BANK_NAME)
       fill["nickname_ok"] = ...   # read the widget back via harness.find(dlg,"Bank nickname").text()
       fill["name_ok"] = ...
       harness.shot("03_bank_fields_filled")
       save = harness.find(dlg, "Save bank")
       fill["save_found"] = save is not None
       if save: harness.click(save)
       fill["closed"] = not dlg.isVisible()
   QTimer.singleShot(0, _fill_and_save_bank)
   harness.click(harness.find(manage_dialog, "Add bank"), wait=1.5)
   ```
   Verified accessible names inside `ui/dialogs/bank_dialog.py`: `"Bank nickname"`, `"Bank name"`, `"Bank TAN"`, `"Save bank"`, `"Cancel bank dialog"`.
   **Note the trap:** `bank_dialog.py` defines `"Add bank"` / `"Bank list"` / `"Edit bank"` / `"Delete bank"` **too** (it also contains a manager view). Always scope your `harness.find()` to the right root — `manage_dialog` for the manager buttons, the `BankDialog` instance for the form fields — never to `dashboard`.
10. `harness.shot("04_after_bank_save")`.
11. **Cross-check both:**
    - **DB:** `after = get_all_banks()`; assert exactly one new row whose nickname or name matches; record its `bank_id`.
    - **Widget:** read every row of `mds.bank_table` (find it by `harness.find(manage_dialog, "Bank list")`, then iterate `rowCount()` / `item(r, 0).text()`) and assert the new bank appears **with no manual refresh**.
12. **Also test Cancel** (§5 checklist step 4 requires both Cancel and the primary action). Repeat the `QTimer.singleShot` pattern, but this time type a throwaway nickname `"RUIH_CancelBank"` and click `"Cancel bank dialog"`. Assert the dialog closed **and** `get_all_banks()` count is unchanged. Screenshot.
13. **Cleanup in `report()`:** `delete_bank(bank_id)` for every bank whose nickname or name starts with `RUIH_`. Assert the final `len(get_all_banks())` equals the `before` count exactly, and print both numbers.

## test_add_account_flow.py — exact steps

**Dependency:** an account needs a person and a bank. Create both yourself so cleanup is total:
1. Create the person and bank **programmatically** (not through the UI — the UI paths are already covered by Unit 3's bank test and the existing person test): `add_person("RUIH_AcctPerson_01")` and `add_bank("Equitas Small Finance Bank", "RUIH_AcctBank_01")`. Record both IDs. This keeps the test focused on the Account dialog and makes cleanup deterministic.
2. Launch, navigate to Settings, click `"Manage bank accounts"` **(VERIFY)**, get the `"Manage Data"` dialog, switch `mds.tabs.setCurrentIndex(2)` (Accounts).
3. `dump_names(manage_dialog, "ManageData-Accounts")` and confirm `"Add account"`, `"Bank accounts table"`, `"Edit account"`, `"Delete account"`.
4. **§3.8 pattern** around `"Add account"`, which opens `AccountDialog` via `.exec()`. Verified accessible names inside `ui/dialogs/account_dialog.py`: `"Person selector"` (a QComboBox), `"Bank selector"` (QComboBox), `"Account holder name"`, `"Account type"` (QComboBox), `"Masked account number"`, `"Full account number"`, `"Opening balance"`, `"Current balance"`, `"IFSC code"`, `"Branch name"`, `"Save account"`, `"Close account dialog"`, `"Account details tabs"` (a QTabWidget — **fields live on different tabs, so you must switch tabs to reach them**).
5. **Combo boxes cannot be filled with `type_into`.** For `"Person selector"` and `"Bank selector"`, do:
   ```python
   combo = harness.find(dlg, "Person selector")
   idx = combo.findText("RUIH_AcctPerson_01")     # may need findData; print combo items if -1
   check("Test person present in Person selector", idx >= 0)
   combo.setCurrentIndex(idx)
   ```
   **If the newly created person/bank is NOT in the combo, that is a real BUG finding** (the dialog isn't reloading its source lists) — record it and continue with whatever index is available so the rest of the flow still gets exercised.
6. Fill `"Account holder name"`, `"Masked account number"` (use something clearly fake like `XXXX1234`), `"Opening balance"` `"0"`. Switch `"Account details tabs"` as needed to reach any required field; use `dump_names(dlg, "AccountDialog")` and note which tab each is on.
7. Click `"Save account"`. Screenshot. Assert dialog closed.
8. **Cross-check:** `get_all_accounts()` contains a new row linked to the test `person_id` and the test bank; and the visible `"Bank accounts table"` shows it with no manual refresh.
9. **Statement Import cross-check (§5 flow 3's stated acceptance criterion):** close the Manage Data dialog, navigate to Statement Import (`dashboard._nav_buttons[5]`), `harness.settle(2.0)`, and assert:
   - a person card exists with accessible name `f"Select person: RUIH_AcctPerson_01"` (names are built as `f"Select person: {name}"` in `_create_person_card`)
   - clicking it (`harness.click(import_screen, "Select person: RUIH_AcctPerson_01")`) reveals an account card for the new account. Dump the account-card names with `dump_names(dashboard.import_page, "StatementImport")` — the account-card naming pattern is **(VERIFY)**; find it by reading the container `dashboard.import_page._account_cards` (a dict keyed by account_id) if the accessible name is ambiguous.
   - Screenshot.
   **If the new person/account does not appear, that is a real BUG** (`refresh()` not rebuilding cards) — record it.
10. **Cleanup in `report()`, in this order (FK order matters):** `delete_account(account_id)`, then `delete_bank(bank_id)`, then `delete_person(person_id)`. Wrap each in `try/except` and print the result, so a failure on one doesn't skip the others. Assert the final counts of `get_all_accounts()`, `get_all_banks()`, `get_all_persons()` all equal their pre-test values.

## Deliverables
Two test scripts, screenshots, and **one** findings-log entry covering both flows (per §0.8), including the Cancel-path results and the Statement-Import propagation result.

## Hazards for this unit
- **§3.8 is fatal if skipped** — `BankDialog`, `AccountDialog`, and `PersonDialog` are all `.exec()`. Schedule the callback **before** clicking.
- **Ambiguous accessible names.** `"Add bank"` / `"Bank list"` / `"Delete account"` etc. exist in **both** `manage_data_screen.py` and the dialog modules. Always scope `harness.find()` to the narrowest root.
- **Real DB.** Prefix everything `RUIH_`, delete in FK order, assert counts return to baseline.
- **Combo boxes** need `setCurrentIndex`, not typing.
- **Record, do not fix.**

---

# UNIT 4 — Statement Import End-to-End with a Real PDF

**Mode:** write-and-run. **Sequencing:** SEQUENTIAL. **Depends on:** Unit 3 (reuse its knowledge of account creation; if Unit 3 found the account flow blocked, this unit still runs using an **existing** account — see below).

## Why this unit exists
Flow 4 of the owner's five. Per §4 this card-based flow (person card → account card → format → browse → parse → preview → import) has **never** been driven with real clicks.

## File to create
`tools/real_ui_tests/test_statement_import_flow.py`

## Critical design decision — which account to import into
**Create your own person + bank + account programmatically** (`add_person`, `add_bank`, `add_account`) with `RUIH_` prefixes, exactly as Unit 3 does. **Do not import into one of the owner's real accounts** — importing real transactions into a real account and then deleting them risks corrupting real data. Importing into a throwaway account and deleting its transactions and then the account itself is clean.

The PDF to use: `data/PersonalData/Pranav/Statement/Jana - Pranav.pdf` (confirmed present). If parsing fails on that one, retry with `Equitas.pdf`, `IDFC.pdf`, or `Ujjivan - Pranav.pdf` and **record which files parse and which don't — that is itself a valuable finding.**

## Exact steps
1. Snapshot `len(get_all_persons())`, `len(get_all_banks())`, `len(get_all_accounts())`. Create `RUIH_ImportPerson_01`, a bank `"Jana Small Finance Bank"` nickname `RUIH_ImportBank_01`, and an account linking them. Record all three IDs.
2. Launch (Aurora, maximized). Navigate to Statement Import: `harness.click(dashboard._nav_buttons[5])`, `harness.settle(2.0)`. Assert `stack.currentIndex() == 5`, `page_title_lbl.text() == "Statement Import"`, and `dashboard._screen_errors.get(5) is None`. Screenshot.
3. `screen = dashboard.import_page`. Run `dump_names(screen, "StatementImport")` and **print the full dump into your findings entry** — this screen's card names are dynamic and the next agent will need them.
4. **Select the person card:** `harness.click(screen, f"Select person: RUIH_ImportPerson_01")`. Settle 1.5. Assert `screen._person_cards[person_id].isChecked()` is True. Screenshot.
5. **Select the account card.** The account cards live in `screen._account_cards` (a dict keyed by account_id). Assert your `account_id` is a key — **if it is not, that is a real BUG** (cards not rebuilt for the selected person). Then `harness.click(screen._account_cards[account_id])`. Settle. Assert it is checked. Screenshot.
6. **Select PDF format:** `harness.click(screen, "Select PDF format")` (verified name). Settle. Assert `screen.btn_format_pdf.isChecked()`.
7. **DO NOT CLICK THE BROWSE / DROP ZONE.** It opens `QFileDialog.getOpenFileName()`, a native modal that will hang your test permanently. Instead:
   - First run `dump_names` and read `ui/statement_import_screen_modern.py` around lines 320-430 to find how the file path is stored (look for a `DropZone` attribute, or a `self._selected_file` / `self.file_path` field).
   - If there is a `DropZone`, set the file by emitting its signal: `zone.fileSelected.emit(r"D:\Pranav\app\data\PersonalData\Pranav\Statement\Jana - Pranav.pdf")`.
   - **Record in findings that the browse button itself was NOT click-tested because it opens a native modal**, and note this as a permanent limitation of QTest-based testing for this control. (Optionally: verify the button exists, is enabled, and has a sane accessible name, without clicking it.)
8. Settle 1.5. Screenshot. Assert the screen now reflects a selected file (whatever label/status field holds it).
9. **Parse:** `harness.click(screen, "Next button")` — the primary button is `self.btn_next`, labelled `"Parse Statement →"`, accessible name `"Next button"` (verified).
10. **Parsing runs on a background `QThread` via `Loader.run()`.** You must poll, not settle once:
    ```python
    import time
    deadline = time.time() + 90
    while time.time() < deadline and screen.preview_table.rowCount() == 0:
        harness.settle(1.0)
    ```
    Find the preview table via `harness.find(screen, "Transaction preview table")` (verified name) or `screen.preview_table`.
11. Screenshot. **Cross-check:** `preview_table.rowCount() > 0`; print the first 3 rows' cell texts into the log. **If rowCount is 0 after 90 seconds, that is a BUG or a parse failure — capture whatever is in `screen.debug_output` (accessible name `"Import debug output"`, verified) verbatim into the findings entry.** That debug text is exactly what a fixer needs.
12. **Import:** click `"Select all new transactions"` (verified), settle, then find and click the Import button. Its accessible name is **(VERIFY)** — the same `btn_next` is reused on screen 2 with a changed label, so re-run `dump_names(screen, ...)` **after** reaching the preview step and use whatever is actually there.
13. Poll again (importing is also threaded). Screenshot.
14. **Cross-check the DB directly:** `from models.transaction import get_transactions_for_account` (or whatever the retrieval function is — read `models/transaction.py`) and assert transactions now exist for `account_id`. Record the count and the first row. **This is the acceptance criterion the owner asked for: "confirm the transactions actually land in the database for that account."**
15. **Cleanup in `report()`, in this order:** collect every transaction ID for `account_id` → `delete_transactions_by_ids(ids)` → `delete_account(account_id)` → `delete_bank(bank_id)` → `delete_person(person_id)`. Each in its own `try/except` with a printed result. Assert all four counts return to their pre-test baselines and **print before/after for each**. Also delete any FD rows the import may have auto-created (`get_all_fds(person_id=...)` → `delete_fd(...)`) — statement import can create FDs via `add_fd_from_statement`.

## Deliverables
One test script, screenshots of each of the 6+ steps, and a findings-log entry that includes: the full accessible-name dump of the Statement Import screen, the parse outcome per PDF attempted, the verbatim debug output if parsing failed, and the before/after DB counts proving clean cleanup.

## Hazards for this unit
- **NATIVE FILE DIALOG WILL HANG THE TEST.** Never click a browse button or DropZone. Emit the signal.
- **Background threads** — poll with a deadline; a single `settle()` is not enough.
- **Real DB + real money data.** This is the most destructive unit. Create your own person/bank/account, import into that only, and prove cleanup with before/after counts.
- **§3.5** — the preview table's *data* is the ground truth, not the screenshot.
- **Record, do not fix.**

---

# UNIT 5 — Tax Documents: Three Drop Zones with Real 26AS/AIS/TIS

**Mode:** write-and-run. **Sequencing:** SEQUENTIAL. **Depends on:** Unit 1.

## Why this unit exists
Flow 5 of the owner's five. Per §5: "click each of the three real drop zones for real, confirm each parses without the app hanging/crashing, confirm the reconciliation view populates."

## File to create
`tools/real_ui_tests/test_tax_documents_flow.py`

## THE CENTRAL CONSTRAINT — read this before writing a line
`ui/widgets/drop_zone.py` `mousePressEvent()` calls `_on_browse_click()` which calls `QFileDialog.getOpenFileName()`. **Clicking a DropZone opens a native Windows file dialog that QTest cannot close. Your test will hang forever.** Additionally, **all three DropZones have the identical accessible name `"File drop zone"`**, so `harness.find()` cannot distinguish them.

**Therefore this unit does NOT click the drop zones.** It drives them by their object attributes and signals, which is the genuine code path (`fileSelected` is what `dropEvent` and `_on_browse_click` both emit):
```python
screen = dashboard.tax_documents_page
screen.zone_26as.fileSelected.emit(r"D:\Pranav\app\data\PersonalData\Pranav\26AS.pdf")
```
**Record as a FINDING (severity: minor, category: accessibility/testability) that all three DropZones share `accessibleName() == "File drop zone"`**, which means a screen reader user cannot tell them apart and a test cannot address them individually. That is a genuine, reportable defect. Also record that the click path could not be exercised because of the native modal.

## Exact steps
1. Launch (Aurora, maximized). `harness.click(dashboard._nav_buttons[6])` (Tax Documents). Settle 2.0. Assert `stack.currentIndex() == 6`, `page_title_lbl.text() == "Tax Documents"`, `dashboard._screen_errors.get(6) is None`. Screenshot `01_tax_documents`.
2. `screen = dashboard.tax_documents_page`. `dump_names(screen, "TaxDocuments")` and print it.
3. Assert all three zones exist: `screen.zone_26as`, `screen.zone_ais`, `screen.zone_tis`, all visible and enabled. Record their rendered `.height()` (should be >= 120, per `setMinimumHeight(120)`).
4. **For each of the three, one at a time:**
   - Emit `fileSelected` with the corresponding real file:
     - `zone_26as` → `data/PersonalData/Pranav/26AS.pdf`
     - `zone_ais` → `data/PersonalData/Pranav/AIS.pdf`
     - `zone_tis` → `data/PersonalData/Pranav/TIS.pdf`
   - **Parsing is threaded via `Loader.run()`.** Poll with a deadline:
     ```python
     deadline = time.time() + 120
     while time.time() < deadline and zone.pdf_data is None:
         harness.settle(1.0)
     ```
     (`_on_26as_selected` sets `self.zone_26as.pdf_data = result` on success. On failure it calls `set_status(f"Error: ...", error=True)` and `pdf_data` stays None.)
   - Screenshot after each (`02_26as_parsed`, `03_ais_parsed`, `04_tis_parsed`).
   - **Cross-check:** `zone.pdf_data is not None` and `zone.pdf_path == <the path>`. **Also read the status label text** — find it by reading `ui/widgets/drop_zone.py` `set_status()` to see which attribute holds it. A `"Error: ..."` status is a **real, high-value BUG finding — copy the error text verbatim into the findings entry.**
   - **Also confirm the app did not hang**: if the poll hit its 120s deadline with `pdf_data` still None and no error status, that is a **hang** — a blocker-severity finding. Record it, screenshot, and move to the next zone rather than waiting longer.
5. **After all three are loaded, confirm the reconciliation view populates.** Verified table accessible names on this screen: `"Reconciled financial position table"`, `"Non-income items disclosure table"`, `"Fixed deposit reconciliation table"`. For each: `harness.find(screen, <name>)`, `harness.scroll_into_view(table)` (§3.4 — these are below the fold), `harness.settle(1.0)`, screenshot, and assert `rowCount() > 0`. Print the first 3 rows of each into the log. If a table is empty, record whether all three PDFs parsed (an empty table with a failed parse is expected; an empty table with three successful parses is a BUG).
6. **Scroll-below-the-fold check (§5 step 5):** scroll the screen to the bottom and screenshot. Note anything a user would not realize needs scrolling.
7. **Cleanup:** determine whether parsing writes to the database. Read `ui/tax_documents_screen.py` for any `add_`/`save_`/`insert` call in the success handlers. **If parsing is read-only (likely — it sets `zone.pdf_data` in memory), state that explicitly in the findings entry and no DB cleanup is needed.** If it *does* write, snapshot the affected table's row count before, and delete exactly the new rows after. Never skip this determination.

## Deliverables
One test script, four+ screenshots, one findings-log entry including: the verbatim error text for any PDF that failed to parse, the row counts of the three reconciliation tables, the shared-accessible-name defect, and an explicit statement of whether this screen writes to the DB.

## Hazards for this unit
- **NEVER CLICK A DROP ZONE.** Native modal = permanent hang.
- Three identical accessible names — use object attributes.
- **Long parses** — PDF parsing of 26AS/AIS can be slow. Use a 120s deadline, and distinguish "slow" from "hung" by whether the status label ever changes.
- §3.4 — the reconciliation tables are below the fold; `scroll_into_view` before screenshotting.
- **Record, do not fix.**

---

# UNIT 6 — Screen-by-Screen Sweep + Button Size Audit (9 screens, Aurora)

**Mode:** write-and-run. **Sequencing:** SEQUENTIAL. **Depends on:** Unit 1.

## Why this unit exists
This is §5's screen-by-screen checklist, steps 1, 2, 4, and 5, across all nine screens, in the light theme. §4 explicitly flags that **no button's rendered size has ever been measured on a real render** — only asserted in code.

## File to create
`tools/real_ui_tests/test_screen_sweep.py`

## The authoritative design scale (from `docs/FRONTEND_REDESIGN_PLAN.json` → `design_direction.scales_to_enforce`)
```
control_height_px:    sm = 28,  md = 36,  lg = 44
control_max_width_px: currency 200, date 160, select_short 200, select_long 320, text 420
Hard rule: NO button wider than 280px.
radius_px: control 8, card 12, modal 16, pill 999
```

## Exact steps
This unit is a **loop over the 9 nav indices**. For each index `i` in `0..8`:

1. `harness.click(dashboard._nav_buttons[i])`; `harness.settle(2.0)`.
2. **Title/content cross-check (§5 step 1):** record `stack.currentIndex()`, `page_title_lbl.text()`, `type(stack.currentWidget()).__name__`, `stack.currentWidget().objectName()`, and `dashboard._screen_errors.get(i)`. Screenshot `f"{i:02d}_screen.png"`. Assert index, title, and `objectName()` not starting with `"placeholder_"`. **A non-None `_screen_errors[i]` means the screen failed to construct — record the exception verbatim as a blocker BUG and skip to the next screen.**
3. **Enumerate every button and measure it (§5 step 2).** Walk the page widget tree:
   ```python
   from PySide6.QtWidgets import QPushButton, QToolButton, QAbstractButton
   page = dashboard.stack.currentWidget()
   for b in page.findChildren(QAbstractButton):
       if not b.isVisible():
           continue
       rec = dict(
           accessible = b.accessibleName(),
           text       = b.text() if hasattr(b, "text") else "",
           cls        = type(b).__name__,
           enabled    = b.isEnabled(),
           h          = b.height(),
           w          = b.width(),
       )
   ```
   **Note:** `b.height()` / `b.width()` are **logical** pixels, which is exactly what the design scale is expressed in — do **not** multiply by `dpr`. State this in your entry.
   Flag and record any button where:
   - `w > 280` → **violates the hard "no button wider than 280px" rule.**
   - `h` is not within ±2 of one of `{28, 36, 44}` → off-scale height. (±2 tolerance absorbs border/padding rounding; anything outside is a real finding.)
   - `accessibleName()` is empty → accessibility defect worth logging.
   Produce a compact table per screen in the findings entry: `accessible | text | class | w×h | verdict`.
4. **Enabled/disabled sanity (§5 step 2).** Record which buttons are disabled and whether that is plausible for the current state (e.g. "Delete selected" disabled with nothing selected is correct; a primary action disabled with a valid selection is a finding). Do not guess — state the observed state and your reasoning.
5. **Click every safe button (§5 step 2).** A button is **safe** if it does not delete data, does not import data, and does not open a native file dialog. **Skip (and record as skipped, with the reason):**
   - anything whose accessible name or label contains `delete`, `remove`, `restore`, `import`, `backup`, `browse`, `export`, `warm up`, `check ai`
   - anything that is a `DropZone`
   For each safe button, **wrap the click in the `QTimer.singleShot` modal pattern preemptively**, because you cannot know in advance whether it opens a `.exec()` dialog:
   ```python
   opened = {}
   def _probe():
       from PySide6.QtWidgets import QDialog
       dlg = harness.find_dialog(QDialog, timeout=1.5)
       opened["dlg"] = type(dlg).__name__ if dlg else None
       if dlg:
           harness.shot(f"{i:02d}_dlg_{safe_name}")
           dump_names(dlg, type(dlg).__name__)   # §5 step 4: are all fields reachable?
           dlg.reject()                           # Cancel path — closes without saving
   QTimer.singleShot(0, _probe)
   harness.click(button, wait=1.5)
   ```
   Record for each: did a dialog open, what class, what accessible names it exposed, did `reject()` close it cleanly, did anything crash. **Use `dlg.reject()` (Cancel), never `accept()`** — this unit must not write to the database.
   **Wrap every click in `try/except Exception` and record the traceback as a BUG finding** rather than letting one bad button abort the sweep.
6. **Scroll-below-the-fold check (§5 step 5).** Find the page's `QScrollArea` (if any). Record `verticalScrollBar().maximum()`. If > 0, the page is taller than the viewport: scroll to the bottom, `harness.settle(1.0)`, screenshot `f"{i:02d}_scrolled_bottom.png"`, and record **what is below the fold and whether a user would realize they need to scroll** (is there a visible scrollbar? does content get cut mid-card?). Note it even if it technically works.
7. **MoneyLabel tabular figures (§4 unknown).** On any screen containing `MoneyLabel` widgets (`from ui.widgets.money_label import MoneyLabel`; `page.findChildren(MoneyLabel)`), record for the first few: the text, `.font().family()`, and `.font().styleName()`. Then **verify digit alignment numerically**: using `QFontMetrics(lbl.font())`, measure `horizontalAdvance("0")` through `horizontalAdvance("9")` — **if all ten are equal, tabular figures are working; if they differ, they are NOT** and that is a real finding (columns of numbers will not align). Screenshot a screen with several money values side by side.

**After the loop:**
8. **Toast fade in/out (§4 unknown).** Trigger a toast. Read `ui/widgets/toast_utils.py` to find the public helper (likely `show_toast(parent, message, variant)`) and call it directly on the dashboard. Then: assert the toast widget appears in `QApplication.allWidgets()` and is visible; `harness.settle(0.5)` and record its graphics-effect opacity (mid-fade it should be between 0 and 1; **if it is stuck at 0.0 after `settle(1.5)`, the fade-in is broken** — a real BUG); screenshot; wait past `duration_ms` and assert it hides. Repeat once with `motion.ENABLED = False` and assert it appears instantly at full opacity. Restore `ENABLED = True`.
9. **CollapsibleSection animation (§4 unknown).** Find any `CollapsibleSection` (`from ui.widgets.section import CollapsibleSection`; search all 9 pages via `findChildren`). Record `is_expanded()`, call `toggle()`, `harness.settle(1.5)`, screenshot, and assert:
   - `is_expanded()` flipped
   - the content widget's `maximumHeight()` settled to either `0` (collapsed) or `16777215` (expanded — `animate_height` unclamps on finish). **A maximumHeight stuck at an intermediate value means the animation was starved and the section is half-drawn — a real BUG.**
   Toggle back and assert it returns. Repeat once with `motion.ENABLED = False`.

## Deliverables
One test script, ~20+ screenshots, and a findings-log entry containing **a per-screen button-measurement table** (this is the durable artifact §4 specifically asks for), the dialog inventory per screen, the below-the-fold notes, the MoneyLabel digit-width result, and the toast/CollapsibleSection motion verdicts.

## Hazards for this unit
- **This unit clicks many unknown buttons.** Wrap every click in `try/except`; preemptively use the `QTimer.singleShot` modal probe; always `reject()` dialogs.
- **Skip destructive and native-dialog buttons** per the skip-list. If in doubt, skip and record it as skipped.
- **Backup/restore buttons are especially dangerous** — `"Create database backup"`, `"Restore database from backup"`, `"Quick backup"` on the Settings screen. **Never click restore.**
- §3.4 scroll-into-view; §3.5 settle before every screenshot.
- **Record, do not fix.**

---

# UNIT 7 — ExcelTable Interactions + Nova Dark-Theme Repeat

**Mode:** write-and-run. **Sequencing:** SEQUENTIAL, **last**. **Depends on:** Unit 6 (reuse its button inventory and the confirmed accessible names).

## Why this unit exists
§5 step 3 (every ExcelTable interaction) and §5 step 6 (repeat on a dark theme). §3.6 makes the double-click path specifically ambiguous and this unit is where that gets resolved or explicitly marked unconfirmed.

## Files to create
- `tools/real_ui_tests/test_excel_table_interactions.py`
- `tools/real_ui_tests/test_dark_theme_sweep.py`

## test_excel_table_interactions.py

**Target table:** the Fixed Deposits screen (nav index 4). Verified accessible names in `ui/fixed_deposits_screen.py`: `"Fixed deposits table"`, `"Add fixed deposit"`, `"Delete selected fixed deposit"`, `"Save fixed deposit changes"`, `"Link transaction to fixed deposit"`, `"Recalculate selected fixed deposits"`, `"Auto-link fixed deposit transactions"`.

**CRITICAL — create your own row before any destructive test.** `models/fixed_deposit.py` provides `add_fd(account_id, person_id, principal_amount, ...)` and `delete_fd(fd_id)`, and `get_all_fds(person_id=None, status=None)`.

Steps:
1. Create a throwaway person, bank, and account programmatically with `RUIH_` prefixes (same as Unit 3/4). Then `add_fd(account_id, person_id, principal_amount=10000.0, ...)` — read the signature and supply the required args. Record `fd_id`. Snapshot `len(get_all_fds())`.
2. Launch (Aurora). Navigate to Fixed Deposits (`_nav_buttons[4]`). Settle 2.0. Assert index/title/no `_screen_errors[4]`. Screenshot.
3. `table = harness.find(dashboard.fd_page, "Fixed deposits table")`. Find your row: iterate `rowCount()` looking for the row whose stored user data matches `fd_id` (read `ExcelTable.addDataRow`'s `user_data` handling in `ui/widgets/excel_table.py` to see where it's stored — likely `item.data(Qt.ItemDataRole.UserRole)`). **Record the row index. Every subsequent step must act on THIS row only.**
4. **Cell click (select).** Use `QTest.mouseClick` on the table's viewport at the cell's visual rect:
   ```python
   from PySide6.QtTest import QTest
   from PySide6.QtCore import Qt
   idx = table.model().index(row, 1)
   rect = table.visualRect(idx)
   table.scrollTo(idx)
   harness.settle(0.5)
   QTest.mouseClick(table.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, rect.center())
   harness.settle(1.0)
   ```
   Assert `table.currentRow() == row`. Screenshot. **Note: `harness.click()` clicks a widget's center, which for a table is the middle of the viewport, not a specific cell — you must use the `visualRect` form above for cell-level clicks. State this in your findings as a harness limitation worth knowing.**
5. **Checkbox toggle + row-highlight sync.** The checkbox is in a specific column (read `ExcelTable._setup_table` / `addDataRow` — with `show_checkboxes=True` it is column 0). Click the checkbox cell the same way. Then assert **both**:
   - `row in table.getCheckedRows()`
   - the row is also selected/highlighted — `ExcelTable._sync_row_selection_to_checkbox(row, checked)` is the method responsible; assert `table.selectionModel().isRowSelected(row, QModelIndex())` or the equivalent. **A checked checkbox whose row is not highlighted is exactly the sync bug §5 step 3 asks about — a real finding.**
   Screenshot. Then uncheck and assert both un-set.
6. **Enter-to-edit.** Select the row, then `harness.key(table, None, Qt.Key.Key_Return)`. Wrap it in the **`QTimer.singleShot` modal pattern** first, because `FdDialog` is opened via `.exec()`. In the callback: find the dialog, `dump_names(dlg, "FdDialog")`, screenshot, `dlg.reject()`. Assert a dialog opened. Screenshot.
7. **Double-click-to-edit (§3.6 — handle with care).** Do all three of these and report all three results:
   - `harness.double_click(table.viewport())` (QTest) — **expected to be unreliable; a failure here is NOT an app bug.**
   - `harness.double_click_via_os(table)` (real OS double-click via pyautogui) — this is the credible path, but requires OS foreground focus; check the launch warning.
   - Compare against the Enter path from step 6.
   **Verdict rule:** if Enter opens the dialog and OS-double-click also opens it → **confirmed working**. If Enter works and OS-double-click does not → report as **UNCONFIRMED**, stating explicitly that QTest double-click is a known-broken measurement instrument (§3.6) and that OS double-click may have failed for focus reasons. **Never report "double-click is broken" based on `QTest.mouseDClick` alone.**
8. **Delete Selected — the destructive test.** Check **only your own row's** checkbox. Assert `table.getCheckedRows() == [row]` — **if any other row is checked, ABORT this step immediately and record why; do not click delete.** Then:
   - Click `"Delete selected fixed deposit"`, wrapped in the `QTimer.singleShot` pattern in case a confirmation `QMessageBox` appears (it likely does — in the callback, find the `QMessageBox` and click its Yes/OK button, found via `msgbox.button(QMessageBox.StandardButton.Yes)`).
   - Poll/settle, screenshot.
   - **Cross-check the DB directly:** `get_all_fds()` no longer contains `fd_id`, **and** its total count is exactly one less than the snapshot from step 1. **Assert both** — the count assertion is what catches an over-broad delete.
   - Also assert the visible table's row count decreased by exactly one.
9. **Cleanup in `report()`:** if `fd_id` still exists, `delete_fd(fd_id)`. Then `delete_account`, `delete_bank`, `delete_person` in that order. Assert all four counts return to baseline and print before/after.

## test_dark_theme_sweep.py

A condensed repeat of Unit 6's loop under the dark theme, looking for theme-specific rendering problems.

1. `ThemeManager.apply("Nova", save=False, notify=False)` **before** constructing the window. **`save=False` is mandatory — do not persist a theme change to the owner's settings.** At the end of `report()`, call `ThemeManager.apply("Aurora", save=False, notify=False)` to restore.
2. Launch and loop all 9 nav indices as in Unit 6 step 1-2 (navigate, settle 2.0, cross-check index/title/`_screen_errors`, screenshot `f"nova_{i:02d}_screen.png"`).
3. **Do not re-run the full button click sweep** — Unit 6 did that. Instead, for each screen record only the theme-sensitive measurements:
   - Re-run the **button size measurement** from Unit 6 step 3 and **diff it against Unit 6's Aurora numbers.** Any button whose width or height differs between themes is a finding (theme should not change control geometry).
   - Record any widget whose text colour visually matches its background in the screenshot (unreadable contrast). This is a visual judgement — describe it precisely: "on Tax screen, the `<label text>` at the top of the `<card>` renders dark-on-dark, illegible."
   - Record any place where a hardcoded light-theme colour bleeds through (white card on a dark page, black text on a dark surface). `ui/dashboard_screen.py`'s module docstring notes prior hardcoded-`rgba` bugs of exactly this kind, so it is a live risk.
4. Repeat the sidebar expand/collapse check from Unit 1 Part D once under Nova, screenshotting both states — §4 explicitly lists "any of the 4 themes other than Aurora, under real rendering" as unknown.
5. Screenshot the nav active accent bar under Nova and record whether it is visible against the dark sidebar.
6. **Cleanup:** restore Aurora with `save=False`. No DB rows are created by this test.

## Deliverables
Two test scripts, screenshots for both, and **one** findings-log entry covering both: the ExcelTable interaction results (with the explicit double-click verdict per §3.6), the destructive-delete DB proof (before/after counts), and the Nova theme findings including the button-geometry diff against Unit 6's Aurora numbers.

## Hazards for this unit
- **This is the only unit that deletes anything.** The create-your-own-row-first rule is absolute. Assert `getCheckedRows() == [your_row]` before clicking delete, and abort if not.
- **§3.6** — do not report a QTest double-click failure as an app bug.
- **Cell-level clicks need `visualRect` + `table.viewport()`**, not `harness.click(table)`.
- **A confirmation `QMessageBox`** on delete is itself a blocking modal — use the `QTimer.singleShot` pattern.
- **`ThemeManager.apply(..., save=False)`** always — never persist a theme change.
- **Record, do not fix.**

---

## Appendix A — Campaign completion checklist

The campaign is done when all of the following are true:
- [ ] Seven test scripts exist under `tools/real_ui_tests/` (Unit 2 produces none; Units 3 and 7 produce two each).
- [ ] `docs/VISUAL_TESTING_GUIDE.md`'s Findings log has **seven new dated entries**, one per unit, in the §0.8 format.
- [ ] Unit 1's entry contains an explicit verdict on the stale-Settings-screenshot question and on the collapsed sidebar.
- [ ] Unit 2's entry contains a SUSPECT/CONFIRMED-RISK list plus a SAFE-and-audited list.
- [ ] Unit 6's entry contains a per-screen button-measurement table against `sm 28 / md 36 / lg 44` and the 280px width rule.
- [ ] Unit 7's entry contains an explicit `CONFIRMED` / `UNCONFIRMED` verdict on double-click-to-edit.
- [ ] Every unit's entry proves DB cleanup with before/after row counts.
- [ ] **Zero application files were modified.** Verify with `git status` — the only changed/new paths should be `tools/real_ui_tests/*`, `tools/real_ui_tests/screenshots/*`, `docs/VISUAL_TESTING_GUIDE.md`, and `docs/UI_TEST_CAMPAIGN_PLAN.md`. **If anything under `ui/`, `models/`, `engines/`, or `core/` appears in `git status`, that is a campaign violation — revert it.**

## Appendix B — Files each unit will need to read

| Unit | Must read |
|---|---|
| all | `docs/VISUAL_TESTING_GUIDE.md` §3, §6; `tools/real_ui_test_harness.py` docstrings; `tools/real_ui_tests/test_add_person_flow.py` |
| 1 | `ui/dashboard_screen.py` (`_navigate` ~980-1006, `_build_sidebar` ~149-270, `_expand_sidebar`/`_collapse_sidebar` ~1130-1190, `_set_nav_active` ~319); `ui/widgets/motion.py`; `core/session.py` |
| 2 | all of `ui/`, `core/`, `main.py`, `config.py` (grep-driven) |
| 3 | `ui/settings_screen.py` (~550-560, 770-800); `ui/manage_data_screen.py`; `ui/dialogs/bank_dialog.py`; `ui/dialogs/account_dialog.py`; `models/bank.py`; `models/bank_account.py`; `models/person.py` |
| 4 | `ui/statement_import_screen_modern.py`; `ui/widgets/drop_zone.py`; `ui/widgets/loader.py`; `models/transaction.py`; `models/fixed_deposit.py` |
| 5 | `ui/tax_documents_screen.py` (~130-165, 290-355); `ui/widgets/drop_zone.py`; `ui/widgets/loader.py` |
| 6 | `docs/FRONTEND_REDESIGN_PLAN.json` → `design_direction.scales_to_enforce`; `ui/widgets/money_label.py`; `ui/widgets/toast.py`; `ui/widgets/toast_utils.py`; `ui/widgets/section.py`; `ui/widgets/motion.py` |
| 7 | `ui/widgets/excel_table.py`; `ui/fixed_deposits_screen.py`; `models/fixed_deposit.py`; `ui/theme/theme_manager.py` |

