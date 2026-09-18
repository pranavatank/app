
# PySide6 Migration + Widget UI Redesign — Execution Roadmap

**Target executor:** Haiku 4.5 sub-agents, one unit at a time, with no context other than this document.
**Repo:** `D:\Pranav\app` (Windows, Python, git, branch `main`).

## Ground rules that apply to EVERY unit

Restate these to the agent executing any unit.

* **NO TEST GATES.** The app has many known bugs; testing is a separate future effort. Do **not** run `pytest` as a gate. Do **not** modify code to make tests pass. Do **not** block on test results. Tests are ported mechanically for import-time correctness only.
* **Coding standards (from the project's global CLAUDE.md):**
  * Follow existing codebase patterns, naming, structure and folder organisation. No new patterns or libraries unless required.
  * Reuse existing shared components/widgets/helpers first; **extend rather than duplicate**. A new focused component is acceptable only when extending would need more than 1–2 extra props or conditional branches.
  * Simplicity over cleverness. Readable, small, focused functions. Clear naming.
  * Minimal comments — only for genuinely non-obvious decisions.
  * Stay within scope. No unrelated refactors or renames. Preserve existing behaviour unless the task requires changing it.
  * Prefer deriving values over storing derived state.
* **Two project-specific do-not-regress rules (from `docs/FRONTEND_REDESIGN_PLAN.json`):**
  * **No raw hex colour anywhere in `ui/` outside `ui/theme/`.** Always use `Theme.TOKEN`.
  * **No new inline `setStyleSheet()` calls outside `ui/theme/`.** New styling goes into the global QSS in `ui/theme/theme.py` or a helper in `ui/theme/components.py`.
* **Qt virtual-method hazard:** in Qt/Python, an unhandled exception inside a reimplemented virtual (`showEvent`, `paintEvent`, `resizeEvent`) can abort the process with no traceback. Never reference a widget attribute inside one without a `getattr(self, "_x", None)` guard.

## Unit dependency graph

```
Unit 1  (binding + env)            SEQUENTIAL — must be first
   |
   +-- Unit 2  (ui/ core port)     \
   +-- Unit 3  (ui/ leaf port)      >  all three PARALLEL with each other
   +-- Unit 4  (tests/tools port)  /
        |
        +-- Unit 5 (theme + motion foundation)   SEQUENTIAL after 2,3,4
              |
              +-- Unit 6 (shared widget library)  SEQUENTIAL after 5
                    |
                    +-- Unit 7 (shell + nav rework)   \  PARALLEL with 8
                    +-- Unit 8 (screen + dialog polish) /
                          |
                          +-- Optional launch smoke check
```

**8 units total.** Units 2/3/4 fan out in parallel. Units 7/8 fan out in parallel. Everything else is sequential.

---

## UNIT 1 — Binding selection, dependencies and entry point

**Mode:** SEQUENTIAL. Must complete before any other unit. Nothing runs in parallel with it.
**Files touched:** 3 (`requirements.txt`, `main.py`, `README.md`)

### Why this unit exists
Both `matplotlib` (via `matplotlib.backends.backend_qtagg`) and `qtawesome` choose their Qt binding **at import time**, based on what is already in `sys.modules` or on the `QT_API` environment variable. If both PyQt6 and PySide6 are installed, either library can bind the wrong one and the app will crash or render blank icons. This unit removes the ambiguity permanently.

### Decision (already made — do not re-decide)
1. **`QT_API` is set to `"pyside6"` as the very first executable statement in `main.py`,** before any import that could pull in Qt.
2. **PyQt6 is REMOVED from `requirements.txt`** and should be uninstalled from the venv. Keeping both installed is the exact hazard this unit prevents. `QT_API` is belt-and-braces for the case where a stale PyQt6 lingers in a developer's environment.
3. `qtawesome` stays — it supports PySide6 and honours `QT_API`.

### Step 1.1 — `requirements.txt`
Open `D:\Pranav\app\requirements.txt`. The current first two lines are:
```
PyQt6>=6.6.0
qtawesome>=1.3.0
```
Replace **exactly those two lines** with **exactly**:
```
PySide6>=6.6.0
qtawesome>=1.3.0
```
Change nothing else in the file. All other pins (cryptography, pyotp, pdfplumber, pypdf, camelot-py[cv], pandas, openpyxl, msoffcrypto-tool, xlrd, matplotlib, numpy, Pillow, python-dateutil, PyYAML, and the dev-only real-UI-test block: pyautogui, pywin32, pygetwindow, mss, pywinauto) stay byte-for-byte as they are.

### Step 1.2 — `main.py`: set `QT_API` before anything else
Open `D:\Pranav\app\main.py`. The file currently begins:
```python
"""
main.py — Application entry point for Personal Financial Manager.
"""

import sys
import os
import importlib.util

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
```
Replace that block with **exactly**:
```python
"""
main.py — Application entry point for Personal Financial Manager.
"""

import sys
import os
import importlib.util

# matplotlib and qtawesome both pick their Qt binding at import time. Pin it
# before any Qt-touching import so neither can bind a stale PyQt6 install.
os.environ["QT_API"] = "pyside6"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
```
The `os.environ["QT_API"]` line **must sit above** `sys.path.insert` and above every `from PySide6...` import in the file. `import os` must precede it — it already does.

### Step 1.3 — `main.py`: rewrite `check_dependencies()`
In `check_dependencies()`, the dict currently reads:
```python
    required_modules = {
        'PyQt6.QtWidgets': 'PyQt6',
        'qtawesome': 'qtawesome',
        'pdfplumber': 'pdfplumber',
        'pypdf': 'pypdf',
        'pandas': 'pandas',
        'openpyxl': 'openpyxl',
        'dateutil': 'python-dateutil',
    }
```
Replace the first entry so the dict becomes **exactly**:
```python
    required_modules = {
        'PySide6.QtWidgets': 'PySide6',
        'qtawesome': 'qtawesome',
        'pdfplumber': 'pdfplumber',
        'pypdf': 'pypdf',
        'pandas': 'pandas',
        'openpyxl': 'openpyxl',
        'dateutil': 'python-dateutil',
    }
```

### Step 1.4 — `main.py`: delete the PyQt6 namespace-package branch
Immediately after the `for module_name, pip_name in required_modules.items():` loop there is a block beginning with the comment `# Special case: if PyQt6.QtWidgets is missing, check if it's the namespace package issue` and ending with `        except ImportError:\n            pass`. It spans roughly lines 33–49 and contains `import PyQt6`, `if PyQt6.__file__ is None:`, an `error_msg` about "namespace package with no bindings", a `_show_error_dialog(error_msg)` and `sys.exit(1)`.

**Delete that entire block.** It is PyQt6-specific (the namespace-package failure mode is a PyQt6 packaging artefact) and has no PySide6 equivalent. Do not replace it with anything. The generic "Report any missing dependencies" block that follows already covers a missing PySide6 with a correct message, because Step 1.3 made it print `PySide6`.

After deletion, the code must flow directly from the end of the `for` loop to the line:
```python
    # Report any missing dependencies
    if missing:
```

### Step 1.5 — `main.py`: `_show_error_dialog` fallback
Inside `_show_error_dialog(message)`, change:
```python
    # Try PyQt6 dialog
    try:
        from PyQt6.QtWidgets import QApplication, QMessageBox
```
to **exactly**:
```python
    # Try a Qt dialog
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
```
Leave the tkinter fallback below it untouched.

### Step 1.6 — `main.py`: the three top-level Qt imports
Further down, `main.py` has these three lines:
```python
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont
from PyQt6.QtCore import qInstallMessageHandler
```
Replace with **exactly**:
```python
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont
from PySide6.QtCore import qInstallMessageHandler
```

### Step 1.7 — `README.md`
Line 63 reads:
```
- **UI Framework**: PyQt6
```
Change to **exactly**:
```
- **UI Framework**: PySide6
```
That is the only change in README.md.

### Explicitly OUT of scope for this unit
* Do **not** edit `docs/AUDIT_AND_REBUILD_PLAN.md`, `docs/FRONTEND_MIGRATION_EVALUATION.md`, or any other doc. Their PyQt6 mentions are historical records of how past audits were performed and must stay accurate to history.
* Do **not** touch any file under `ui/`, `tests/` or `tools/` — later units own those.

### Hazards for Unit 1
* `os.environ["QT_API"]` **must** be above `sys.path.insert` and above all `from PySide6...` imports. If a Qt import runs first, the env var has no effect.
* Do not use `os.environ.setdefault` here — a stale `QT_API=pyqt6` in a developer shell would win and reintroduce the exact bug this prevents. Use plain assignment.
* `main.py` calls `check_dependencies()` twice (once under `if __name__ == "__main__":` at module import, once inside `bootstrap()`). Both call sites are fine unchanged; do not "clean up" the duplication — out of scope.

---

## UNIT 2 — Mechanical port: `ui/` core screens

**Mode:** PARALLEL with Units 3 and 4. Depends on Unit 1.
**Files touched:** 19 (all of `ui/*.py` that import Qt, plus `ui/dialogs/*.py`)

### File list (exact)
```
ui/accounts_screen.py
ui/dashboard_screen.py
ui/fixed_deposits_screen.py
ui/icons.py
ui/income_management_screen.py
ui/login_screen.py
ui/logo.py
ui/manage_data_screen.py
ui/messagebox_utils.py
ui/ollama_worker.py
ui/onboarding.py
ui/settings_screen.py
ui/setup_screen.py
ui/statement_import_screen_modern.py
ui/tax_documents_screen.py
ui/tax_screen.py
ui/transactions_screen.py
ui/dialogs/account_details_dialog.py
ui/dialogs/account_dialog.py
ui/dialogs/account_metadata_dialog.py
ui/dialogs/bank_dialog.py
ui/dialogs/column_mapping_dialog.py
ui/dialogs/fd_dialog.py
ui/dialogs/income_expectation_dialog.py
ui/dialogs/income_source_dialog.py
ui/dialogs/link_fd_transaction_dialog.py
ui/dialogs/password_dialog.py
ui/dialogs/person_dialog.py
ui/dialogs/transaction_dialog.py
ui/dialogs/transaction_edit_dialog.py
```
(Do **not** touch `ui/__init__.py`, `ui/date_utils.py`, `ui/dialogs/__init__.py` — they import no Qt.)

### The ONLY two transformations in this unit

**Transformation A — module name.** In every listed file, replace the literal substring `PyQt6.` with `PySide6.` on import lines. Concretely, every line matching `from PyQt6.QtCore import ...`, `from PyQt6.QtGui import ...`, `from PyQt6.QtWidgets import ...` becomes `from PySide6.QtCore import ...` / `from PySide6.QtGui import ...` / `from PySide6.QtWidgets import ...`. This includes parenthesised multi-line imports — only the first line (the one containing `PyQt6`) changes; the names inside the parentheses are untouched.

Note the alignment-padded variants that exist in this codebase and must keep their spacing:
* `ui/icons.py` has `from PyQt6.QtGui     import QIcon, QPixmap, QColor` and `from PyQt6.QtCore    import QSize`. Preserve the multiple spaces: they become `from PySide6.QtGui     import QIcon, QPixmap, QColor` and `from PySide6.QtCore    import QSize`. (Do not re-align, do not collapse whitespace — that would be an out-of-scope reformat.)

There are also nested/function-local imports (e.g. inside `try:` blocks or functions). Apply the same rule to those. Search each file for the case-sensitive string `PyQt6` and ensure **zero** occurrences remain (except inside a human-readable comment or docstring — see Transformation C).

**Transformation B — `pyqtSignal` → `Signal`.** Three of this unit's files use signals:
* `ui/income_management_screen.py:11` — `from PyQt6.QtCore import Qt, QDate, pyqtSignal` → `from PySide6.QtCore import Qt, QDate, Signal`
* `ui/ollama_worker.py:8` — `from PyQt6.QtCore import QObject, pyqtSignal` → `from PySide6.QtCore import QObject, Signal`; then lines 20–21 `finished = pyqtSignal(str)` → `finished = Signal(str)` and `failed = pyqtSignal(str)` → `failed = Signal(str)`
* `ui/settings_screen.py:28` — `from PyQt6.QtCore import Qt, QSize, pyqtSignal, QTimer` → `from PySide6.QtCore import Qt, QSize, Signal, QTimer`; then line 71 `selected = pyqtSignal(str)` → `selected = Signal(str)`
* `ui/statement_import_screen_modern.py:16` — `from PyQt6.QtCore import Qt, pyqtSignal, QThread, QObject, QMimeData, QEvent` → `from PySide6.QtCore import Qt, Signal, QThread, QObject, QMimeData, QEvent`; then line 68 `progress = pyqtSignal(str)` → `progress = Signal(str)` and line 97 `progress = pyqtSignal(str)` → `progress = Signal(str)`
* `ui/tax_documents_screen.py:17` — `from PyQt6.QtCore import Qt, pyqtSignal, QObject` → `from PySide6.QtCore import Qt, Signal, QObject`

Rule, generalised: replace the whole-word identifier `pyqtSignal` with `Signal`, everywhere it appears — in import lists and in class-body declarations. Do not rename the signal attributes themselves (`finished`, `failed`, `progress`, `selected` keep their names). Signal argument types (`str`) are unchanged.

There is **no** `pyqtSlot` and **no** `pyqtProperty` in this codebase — if you encounter one, `pyqtSlot`→`Slot` and `pyqtProperty`→`Property`, imported from `PySide6.QtCore`, but you should not find any.

**Transformation C — comment/docstring mentions.** Where `PyQt6` appears in a comment or docstring that describes current behaviour, update it to `PySide6`. Known instances:
* `ui/widgets/chart_widget.py` has `# Try QtAgg (PyQt6 native)` — that file belongs to Unit 3, not this one.
* If you find `PyQt6` in a comment in one of *this* unit's files, change it to `PySide6` only when the sentence is describing the binding currently in use. Do not rewrite comments that narrate past history.

### What must NOT change (verified — resist the urge)
* **Do not touch any enum access.** Every `Qt.AlignmentFlag.AlignCenter`, `Qt.FocusPolicy.NoFocus`, `Qt.ItemFlag.ItemIsEnabled`, `Qt.CursorShape.PointingHandCursor`, `Qt.ItemDataRole.UserRole`, `Qt.WidgetAttribute.*`, `Qt.PenStyle.*`, `Qt.Key.*`, `Qt.WindowType.*`, `QDialog.DialogCode.Accepted`, `QMessageBox.StandardButton.*`, `QMessageBox.Icon.*`, `QMessageBox.ButtonRole.*`, `QFont.Weight.Bold`, `QSizePolicy.Policy.*`, `QHeaderView.ResizeMode.*`, `QFrame.Shape.*`, `QFrame.Shadow.*`, `QAbstractItemView.EditTrigger.*`, `QComboBox.InsertPolicy.*`, `QLineEdit.EchoMode.*`, `QPainter.RenderHint.*`, `QTableWidget.SelectionBehavior.*` etc. is **already** in the fully-qualified Qt6 form that PySide6 6.4+ supports. Leave every one of them exactly as-is. Shortening them (e.g. `Qt.AlignCenter`) is a regression.
* **Do not change `.exec()` to `.exec_()`.** PySide6 supports `.exec()`. All 37 sites stay.
* **Do not change `QDialog.DialogCode.Accepted` comparisons.**
* **Do not touch `QFont("Segoe UI", 18, QFont.Weight.Bold)` constructions** — identical in PySide6.
* **Do not touch `QTimer.singleShot(ms, callable)` calls** — identical in PySide6. (Sites: `ui/fixed_deposits_screen.py:355`, `ui/login_screen.py:226`, `ui/settings_screen.py:508`.)
* **Do not touch `setData`/`data` with `Qt.ItemDataRole.UserRole`.** PySide6 stores and returns the native Python object; there is no `QVariant` wrapping and no `.toPython()` needed.
* **Do not add `qRegisterMetaType` anywhere.** Verified: all cross-thread signal payloads in this codebase are `str` or `object`, both of which PySide6 marshals natively.
* **Do not "fix" the `mousePressEvent = lambda e: ...` assignments** in `ui/accounts_screen.py:223` and `:320`. Assigning a lambda to a Python-side virtual works identically in PySide6. Note that these lambdas capture `account` via a default argument (`lambda e: self._on_card_clicked(account)` inside a loop) — if the existing code already binds correctly, leave it; behaviour is unchanged by the binding swap. Do not refactor.
* **Do not reformat, reorder imports, or run a formatter.** The only diff in this unit should be `PyQt6`→`PySide6` and `pyqtSignal`→`Signal`.

### Hazards for Unit 2
* **`ui/settings_screen.py` has TWO separate Qt import lines** — line 28 (`from PyQt6.QtCore import Qt, QSize, pyqtSignal, QTimer`) and line 45 (`from PyQt6.QtCore import QThread`). Both must be converted. Do not merge them.
* **`ui/statement_import_screen_modern.py` is 1855 lines** — the largest file in the unit. Search it exhaustively for `PyQt6` and `pyqtSignal`; there are imports near the top and possibly function-local ones. Confirm zero remaining occurrences before finishing.
* `ui/icons.py` calls `pm.save(path, "PNG")` at line 337 — `QPixmap.save` is identical in PySide6. No change.
* `ui/messagebox_utils.py` installs copyable error dialogs and calls `box.exec()` at line 33 — no change needed.
* After finishing, run `grep -rn "PyQt6\|pyqtSignal\|pyqtSlot\|pyqtProperty" ui/*.py ui/dialogs/*.py` and confirm it returns nothing. Do **not** run pytest.

---

## UNIT 3 — Mechanical port: `ui/theme/` and `ui/widgets/`

**Mode:** PARALLEL with Units 2 and 4. Depends on Unit 1.
**Files touched:** ~14 Qt-importing files across two packages

### File list (exact)
```
ui/theme/theme.py
ui/theme/components.py
ui/theme/checkbox_asset.py
ui/theme/theme_manager.py
ui/theme/button_color_guide.py
ui/widgets/advance_tax_banner.py
ui/widgets/chart_widget.py
ui/widgets/drop_zone.py
ui/widgets/excel_table.py
ui/widgets/inline_error.py
ui/widgets/kpi_tile.py
ui/widgets/loader.py
ui/widgets/money_label.py
ui/widgets/privacy_overlay.py
ui/widgets/section.py
ui/widgets/states.py
ui/widgets/summary_panel.py
ui/widgets/toast.py
ui/widgets/toast_utils.py
```
(`ui/theme/constants.py`, `ui/theme/theme_aurora_light.py`, `theme_nova_dark.py`, `theme_slate_light.py`, `theme_midnight_pro.py`, `ui/theme/__init__.py`, `ui/widgets/__init__.py` are pure-Python colour tables with no Qt import — **do not touch them**. If you find a Qt import in one, convert it by the same rules.)

### Transformations
Apply **exactly the same Transformation A (`PyQt6.` → `PySide6.` on import lines)** and **Transformation B (`pyqtSignal` → `Signal`)** as described in Unit 2, with the same complete list of things that must NOT change (enums, `.exec()`, `QTimer.singleShot`, `UserRole` data, no `qRegisterMetaType`, no reformatting).

Signal sites in this unit, explicitly:
* `ui/widgets/drop_zone.py:12` → `from PySide6.QtCore import Qt, Signal, QMimeData`; line 25 `fileSelected = Signal(str)`
* `ui/widgets/excel_table.py:11` → `from PySide6.QtCore import Qt, Signal, QModelIndex`; lines 56–58 `selectionStatsChanged = Signal(str)`, `cellDataChanged = Signal()`, `deleteRequested = Signal()`
* `ui/widgets/loader.py:43` — this is a parenthesised multi-line import whose body reads `Qt, QTimer, QThread, pyqtSignal, QObject, QRect`. The opening line `from PyQt6.QtCore import (` becomes `from PySide6.QtCore import (` and the body becomes `Qt, QTimer, QThread, Signal, QObject, QRect`. Then lines 345–346: `finished = Signal(object)`, `error    = Signal(object)` — **preserve the alignment spacing on `error`**.
* `ui/widgets/states.py:16` → `from PySide6.QtCore import Qt, Signal`; line 31 `action_clicked = Signal()`; line 180 `retry_clicked = Signal()`
* `ui/widgets/toast.py:9` → `from PySide6.QtCore import Qt, QTimer, Signal`; line 18 `closed = Signal()`
* `ui/widgets/excel_table.py:12` → `from PySide6.QtGui import QKeySequence, QKeyEvent` (note: `QKeySequence` and `QKeyEvent` are in `QtGui` in **both** bindings — location is unchanged; the `QKeySequence.StandardKey.Copy`/`Paste`/`SelectAll`/`Cut`/`MoveToStartOfDocument`/`MoveToEndOfDocument` accesses at lines 491–655 are already correctly scoped and must not change)

### Step 3.X — the ONE real API decision in this unit: `ui/widgets/chart_widget.py`

This file is the single genuine matplotlib-binding hazard. Its current header is:
```python
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt

from ui.theme import Theme

# ── Backend setup ────────────────────────────────────────────────────────────
_MPL_AVAILABLE = False
FigureCanvas = None

try:
    import matplotlib
    # Try QtAgg (PyQt6 native)
    try:
        matplotlib.use("QtAgg")
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as _FC
```
Make **exactly** these changes:
1. `from PyQt6.QtWidgets import ...` → `from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel`
2. `from PyQt6.QtCore import Qt` → `from PySide6.QtCore import Qt`
3. Change the comment `# Try QtAgg (PyQt6 native)` to `# Try QtAgg (PySide6 native)`
4. **Insert a `QT_API` guard immediately above `import matplotlib`.** The `try:` block must become **exactly**:
```python
try:
    import os
    os.environ.setdefault("QT_API", "pyside6")
    import matplotlib
    # Try QtAgg (PySide6 native)
    try:
        matplotlib.use("QtAgg")
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as _FC
```
(If `import os` already exists at module top level, do not re-import it inside the try — just keep the `os.environ.setdefault(...)` line there. Check the file's existing imports: it currently has `import functools` and `import traceback` under `from __future__ import annotations`. Add `import os` to that top-level group instead and put only `os.environ.setdefault("QT_API", "pyside6")` inside the try, above `import matplotlib`.)

Rationale to keep in mind but **not** to write as a comment beyond one line: `main.py` already hard-sets `QT_API`, but `chart_widget.py` is also imported by test/tool entry points that never go through `main.py`. `setdefault` here is correct (unlike in `main.py`) precisely because `main.py`'s hard assignment must win when present.

5. **Leave the `qt5agg` and `agg` fallback chain exactly as it is.** Under PySide6, `backend_qtagg` resolves correctly and the fallbacks never fire; they remain as harmless defence. Do not delete them — that is an out-of-scope refactor.

### Step 3.Y — `ui/icons.py` note
`ui/icons.py` belongs to **Unit 2**, not this one. But note for whoever runs Unit 2: `qtawesome` also binds at import time. No code change is needed there because `main.py` sets `QT_API` first and PyQt6 will have been uninstalled. Do not add a second `QT_API` line to `ui/icons.py`.

### Hazards for Unit 3
* `ui/theme/theme.py` is 1321 lines and starts with a **UTF-8 BOM** (the file begins with `\ufeff"""`). Preserve it — write the file back in the same encoding. Corrupting the BOM or re-encoding the file will produce a spurious diff and may break the QSS f-strings.
* `ui/theme/theme.py:8` is `from PyQt6.QtWidgets import QPushButton, QGraphicsDropShadowEffect` and line 7 is `from PyQt6.QtGui import QFont`. Both convert. `QGraphicsDropShadowEffect` lives in `QtWidgets` in both bindings — the import location is unchanged.
* `ui/theme/components.py:40` has a **function-local** import: `from PyQt6.QtWidgets import QGraphicsDropShadowEffect` inside `make_shadow(...)`. It is easy to miss with a header-only scan. Convert it.
* `ui/widgets/loader.py` hand-rolls a fade with `self._opacity` and a 16 ms `QTimer` (lines 181–275). **Do not replace it with a QPropertyAnimation in this unit** — that is Unit 5's job. In this unit it is a pure mechanical port.
* `ui/theme/checkbox_asset.py` calls `pm.save(_ASSET_PATH, "PNG")` — identical API, no change.
* After finishing, `grep -rn "PyQt6\|pyqtSignal" ui/theme/ ui/widgets/` must return nothing. Do **not** run pytest.

---

## UNIT 4 — Mechanical port: `tests/` and `tools/`

**Mode:** PARALLEL with Units 2 and 3. Depends on Unit 1.
**Files touched:** ~14

### Scope note the executing agent must read first
These files are ported **for import-time correctness only**. Their passing is **not** a gate and is **not** your responsibility. Do not modify test logic, assertions, fixtures, expected values or skip markers to make anything pass. Do not run pytest. If a test looks wrong, leave it wrong — a separate testing effort will handle it.

### File list
Every file under `tests/` and `tools/` that contains the string `PyQt6`. Find them with:
```
grep -rln "PyQt6" tests/ tools/
```
Known members include `tests/conftest.py`, `tests/test_button_hierarchy.py`, `tests/test_chart_relocation.py`, `tests/test_dashboard_lazy.py`, `tests/test_excel_mapping.py`, `tests/test_excel_table_enter_key.py`, `tests/test_excel_table_parity.py`, `tests/test_kpi_tile.py`, `tests/test_money_label.py`, `tests/test_readme_shortcuts.py`, `tests/test_screen_render.py`, `tests/test_statement_import_flow.py`, `tests/test_summary_panel.py`, `tests/test_theme_qss.py`, `tests/test_ui_threading.py`, `tools/real_ui_test_harness.py`, `tools/real_ui_tests/test_add_person_flow.py`. Use the grep result as the authoritative list, not this one.

**Do not touch `.venv/`.** Restrict every operation to `tests/` and `tools/`.

### Transformations
1. **Transformation A:** `from PyQt6.QtCore import ...` → `from PySide6.QtCore import ...`; same for `QtGui`, `QtWidgets`, and **`QtTest`**.
   * `tests/test_statement_import_flow.py:21` — `from PyQt6.QtTest import QTest` → `from PySide6.QtTest import QTest`
   * `tools/real_ui_test_harness.py:100` — `from PyQt6.QtTest import QTest` → `from PySide6.QtTest import QTest`
   * `PySide6.QtTest` exists and exports `QTest` with the same `QTest.keyClick`, `QTest.mouseClick`, `QTest.qWait` surface used here.
2. **Transformation B:** `pyqtSignal` → `Signal` if present (whole-word).
3. **Transformation C:** update `PyQt6` in comments/docstrings to `PySide6` **only** where the sentence describes the binding the code runs against. Two known cases to handle:
   * `tools/real_ui_test_harness.py` contains a docstring line "Since this app is a normal on-screen (non-offscreen) PyQt6 window running in the…" → change `PyQt6` to `PySide6`.
   * `tools/real_ui_test_harness.py:124` and `:259` reference `QDialog.exec()` / `app.exec()` in prose — those are still accurate; leave the sentences alone except for the `PyQt6` word if present.
   * Leave narrative comments that record *past* audit methodology unchanged.

### Step 4.4 — `tests/conftest.py` binding pin
`tests/conftest.py` currently begins:
```python
import os
import sys
import tempfile
import shutil

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```
Add a `QT_API` pin so tests that import `chart_widget` or `qtawesome` without going through `main.py` bind correctly. Change that block to **exactly**:
```python
import os
import sys
import tempfile
import shutil

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyside6")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```
Nothing else in `conftest.py` changes. Do not touch the `setup_test_database` fixture or its temp-dir/DB-path patching.

### Step 4.5 — `tools/real_ui_test_harness.py` binding pin
This file is an independent entry point. Add, as the first executable statement after its imports of `os`/`sys` and **before** the `from PySide6.QtTest import QTest` on line 100 and before any other Qt import in the file:
```python
os.environ.setdefault("QT_API", "pyside6")
```
If `import os` is not already at the top of the file, add it to the existing top-level import group. Place the `setdefault` line immediately after that import group and above every `PySide6` import in the file.

### What must NOT change
* Same "do not change" list as Unit 2: no enum rewriting, no `.exec_()`, no `qRegisterMetaType`, no reformatting.
* `tests/test_ui_threading.py:15` — `from PyQt6.QtCore import QThread, QTimer, Qt` → `from PySide6.QtCore import QThread, QTimer, Qt`. Its comment at line 63 ("Run worker in a separate thread (simulating QThread)") is fine as-is.
* `tests/test_readme_shortcuts.py:18` and `tests/test_excel_table_parity.py:17` import `QKeySequence`/`QKeyEvent` from `QtGui` — same location in PySide6, only the module prefix changes.
* Do **not** add, remove or edit any assertion, any `@pytest.mark.skip`/`xfail`, or any expected-value constant.

### Hazards for Unit 4
* A naive project-wide `sed` will hit `.venv/` (which contains matplotlib's `qt_compat.py` and qtpy, both of which legitimately reference `PyQt6`). **Scope every operation to `tests/` and `tools/` explicitly.**
* `tools/real_ui_tests/test_add_person_flow.py` uses `QTimer.singleShot(0, _fill_and_save_person_dialog)` at line 117 to pre-schedule work before a blocking `dlg.exec()`. This pattern works identically in PySide6. Do not change it.
* One PySide6 behaviour worth knowing but **not** worth pre-emptively coding around: PySide6 keeps a reference to a signal's Python receiver differently from PyQt6 in some lambda-connection cases. In *this* codebase every `.connect()` target is either a bound method of a long-lived widget or a lambda capturing loop variables by default-argument — neither is at risk. **Do not add `functools.partial` rewrites or explicit reference-holding to "fix" a problem that does not exist here.** If a specific crash surfaces later, that is the separate testing effort's problem.
* After finishing, `grep -rn "PyQt6" tests/ tools/` must return nothing. Do **not** run pytest.

---

## UNIT 5 — Theme tokens, QSS polish, and the shared motion helper

**Mode:** SEQUENTIAL. Depends on Units 2, 3 and 4 all being complete (the port must land before redesign touches the same files, so a later crash is attributable to redesign rather than to a binding difference).
**Files touched:** 8

### File list
```
ui/theme/theme.py            (extend: motion tokens, QSS polish)
ui/theme/components.py       (extend: elevation + motion style helpers)
ui/theme/constants.py        (extend: motion + elevation constants)
ui/theme/theme_aurora_light.py
ui/theme/theme_nova_dark.py
ui/theme/theme_slate_light.py
ui/theme/theme_midnight_pro.py
ui/widgets/motion.py         (NEW — the one new module this whole roadmap creates)
```

### Design direction (binding — from `docs/FRONTEND_REDESIGN_PLAN.json`, do not reinvent)
* **Colour carries meaning.** One accent for the primary action per screen. Green = money in / positive; red = money out / destructive; amber = attention; blue/indigo = neutral action. Nothing else gets a fill.
* **Data is the decoration.** Colour comes from charts and money figures, not chrome.
* **Density with air.** Whitespace goes *between groups*, not inside every control.
* **MOTION ONLY TO EXPLAIN.** A 120 ms ease on hover/expand is enough. **No animation on data.**
* Radius scale: control 8, card 12, modal 16, pill 999. These already exist in `ui/theme/constants.py` as `RADIUS_CONTROL`/`RADIUS_CARD`/`RADIUS_MODAL`/`RADIUS_PILL` — **reuse them, do not add a parallel scale.**
* Spacing scale: 4, 8, 12, 16, 24, 32, 48.
* Control heights: sm 28, md 36, lg 44.

### Step 5.1 — Motion tokens in `ui/theme/constants.py`
`ui/theme/constants.py` already ends with a "Radius scale constants" block followed by legacy shadow aliases. **Append** a new block at the end of the file, after the existing legacy aliases:
```python
# Motion scale — see ui/widgets/motion.py. Durations in ms.
MOTION_FAST   = 120      # hover, press, chip toggle
MOTION_BASE   = 180      # fade in/out, expand/collapse
MOTION_SLOW   = 260      # page/route transitions
MOTION_EASING = "OutCubic"   # QEasingCurve.Type member name

# Elevation scale — QGraphicsDropShadowEffect params (blur, offset_y, alpha)
ELEVATION_CARD   = (2,  1,  16)
ELEVATION_RAISED = (12, 4,  26)
ELEVATION_MODAL  = (32, 12, 46)
```
Do not remove or reorder anything already in the file. Do not touch the big `from .theme_aurora_light import (...)` re-export block.

### Step 5.2 — Surface the motion tokens on `Theme`
In `ui/theme/theme.py`, the `Theme` class assigns colour tokens from `c` (the `constants` module, imported as `from . import constants as c`). Find the block where radius constants are surfaced (search for `RADIUS_CONTROL`). **Immediately after** the radius block, add:
```python
    MOTION_FAST   = c.MOTION_FAST
    MOTION_BASE   = c.MOTION_BASE
    MOTION_SLOW   = c.MOTION_SLOW
    MOTION_EASING = c.MOTION_EASING

    ELEVATION_CARD   = c.ELEVATION_CARD
    ELEVATION_RAISED = c.ELEVATION_RAISED
    ELEVATION_MODAL  = c.ELEVATION_MODAL
```
These are theme-independent (motion timing does not change per theme), so **do not** add them to the four `theme_*.py` colour modules and **do not** add them to `ThemeManager`'s patch list.

### Step 5.3 — Per-theme accent polish (the four `theme_*.py` files)
For each of `theme_aurora_light.py`, `theme_nova_dark.py`, `theme_slate_light.py`, `theme_midnight_pro.py`:
* **Do not add or remove any token name.** All four must keep exactly the same set of exported names, because `constants.py` re-exports a fixed list from `theme_aurora_light` and `ThemeManager` patches by name. Adding a name to one theme and not the others will break theme switching.
* The permitted change in this step is **value tuning only**: adjust `BORDER` and `DIVIDER` toward a lighter hairline (the design direction says "Cards lose their heavy 1.5px borders in favour of a subtle shadow plus a 1px hairline"), and verify `SHADOW_RGBA_CARD` / `SHADOW_RGBA_ELEVATED` read as soft rather than heavy.
* **Contrast rule:** any text-on-background pair you change must keep at least 4.5:1 contrast. If unsure whether a tweak is safe, **do not make it.** Value tuning here is optional polish; token-set integrity is mandatory.

### Step 5.4 — QSS polish in `ui/theme/theme.py`
`ui/theme/theme.py` contains the global stylesheet as a large f-string (`Theme.get_stylesheet()`), interpolating `{t.TOKEN}` values. Make these targeted edits **inside that f-string only**:
1. **Unify radii.** Find every literal pixel radius in the QSS (e.g. `border-radius: 14px`, `border-radius: 10px`) and replace it with the matching scale token: controls/inputs/buttons → `{t.RADIUS_CONTROL}px`, cards/frames/group boxes → `{t.RADIUS_CARD}px`, dialogs → `{t.RADIUS_MODAL}px`, avatars/pills/chips → `{t.RADIUS_PILL}px`. Some already use the tokens (e.g. line 677's `QTabWidget::pane`) — leave those.
2. **Unify borders to a 1px hairline.** Replace any `border: 2px solid {t.BORDER}` or `1.5px` with `border: 1px solid {t.BORDER}`. **Exception:** keep 2px where it is a *focus ring* (`{t.BORDER_FOCUS}` / `{t.FOCUS_RING}`) or an intentional emphasis state — focus visibility is an accessibility requirement and must not be weakened.
3. **Unify control heights.** Give `QLineEdit`, `QComboBox`, `QDateEdit`, `QSpinBox`, `QDoubleSpinBox` and `QPushButton` a `min-height` from the {28, 36, 44} scale — default `36px` unless a rule already sets a deliberate different height.
4. **Add a hover state to every interactive rule that lacks one.** For `QPushButton`, `QToolButton`, `QComboBox`, table rows and nav items, ensure a `:hover` selector exists using an existing token (`{t.SIDEBAR_HOVER}`, `{t.SURFACE_ALT}`, or a `{t.PRIMARY_GRADIENT_HOVER_START}`/`END` gradient via `{Theme.gradient(...)}`). Do **not** invent new colours — every value must come from an existing `Theme` token.
5. **Do not add `transition:` properties.** Qt's QSS does not support CSS transitions. All motion goes through `ui/widgets/motion.py` (Step 5.5). Writing `transition:` in QSS is silently ignored and is a common mistake — do not do it.
6. **Do not add raw hex.** Every colour in the QSS must be a `{t.TOKEN}` interpolation.
7. **Performance note:** theme switching is ~245 ms with one screen built. Adding bulk QSS makes that worse and is a known, accepted trade. Do **not** attempt to "fix" it by moving rules to per-widget `setStyleSheet()` — that would violate the inline-stylesheet budget.

### Step 5.5 — NEW FILE: `ui/widgets/motion.py`

This is the single shared motion helper. **All motion in the app goes through it.** No screen may create its own `QPropertyAnimation`.

Create `D:\Pranav\app\ui\widgets\motion.py` with this exact structure (fill in the bodies; the signatures, names and imports are fixed):

```python
"""ui/widgets/motion.py — Shared motion helpers.

Motion explains state change; it never decorates data. Durations and easing
come from Theme.MOTION_*; callers pass a widget, not a duration.
"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QAbstractAnimation, Qt
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget

from ui.theme import Theme


def _curve() -> QEasingCurve:
    return QEasingCurve(getattr(QEasingCurve.Type, Theme.MOTION_EASING))


def fade_in(widget: QWidget, duration: int | None = None) -> QPropertyAnimation:
    """Fade a widget from transparent to opaque. Returns the running animation."""


def fade_out(widget: QWidget, duration: int | None = None, hide_on_finish: bool = True) -> QPropertyAnimation:
    """Fade a widget to transparent, optionally hiding it when done."""


def slide_in(widget: QWidget, dx: int = 0, dy: int = 12, duration: int | None = None) -> QPropertyAnimation:
    """Animate a widget's geometry from an offset back to its laid-out position."""


def animate_width(widget: QWidget, target: int, duration: int | None = None) -> QPropertyAnimation:
    """Animate a widget's fixed width (used by the sidebar expand/collapse)."""


def animate_height(widget: QWidget, target: int, duration: int | None = None) -> QPropertyAnimation:
    """Animate a widget's maximum height (used by collapsible sections)."""
```

Implementation rules, all mandatory:
* **Default duration** is `Theme.MOTION_BASE` when `duration is None`, except `animate_width`/`animate_height` which default to `Theme.MOTION_FAST`.
* **Lifetime:** every animation must be kept alive or it will be garbage-collected mid-flight and the widget will snap. Two mechanisms, use both: construct with the widget as parent (`QPropertyAnimation(effect, b"opacity", widget)`), **and** store the animation on the widget as `widget._motion_anim = anim` before starting. Before starting a new animation on a widget, stop and clear any existing `widget._motion_anim`.
* **Start with** `anim.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)`.
* **Opacity effects:** `fade_in`/`fade_out` must **reuse** an existing `QGraphicsOpacityEffect` if `widget.graphicsEffect()` already returns one, rather than installing a second. Installing a graphics effect replaces any existing one — so a widget that already has a `QGraphicsDropShadowEffect` from `Theme.shadow_card()` **cannot** also have an opacity effect. Guard: if `widget.graphicsEffect()` is a `QGraphicsDropShadowEffect`, **skip the fade entirely and return `None`**, rather than destroying the shadow. Document this in one comment line.
* **Reduced motion:** add a module-level `ENABLED = True` flag. Every function returns immediately (setting the final value directly, no animation) when `ENABLED` is `False`. This gives a single kill-switch for offscreen rendering and future accessibility work.
* **Return type** is `QPropertyAnimation | None` — `None` when motion was skipped.
* **Do not** add animation for data values (money figures, table cells, chart series). The design direction forbids it.

### Step 5.6 — Replace the hand-rolled fade in `ui/widgets/loader.py`
`ui/widgets/loader.py` lines ~181–275 implement a fade with `self._opacity`, `self._fade_timer = QTimer(self)`, `_fade_in_step()` incrementing by 0.1 every 16 ms, and a `paintEvent` that reads `int(self._opacity * 140)`.

This is a hand-rolled animation that now duplicates `motion.fade_in`. **However:** the loader's overlay paints its own scrim via `paintEvent` using `self._opacity` directly, so swapping in `QGraphicsOpacityEffect` would change what is being animated. **Decision: leave `loader.py`'s fade as it is.** Replacing it is a behaviour change with no user-visible benefit, and the standards say to preserve existing behaviour unless the task requires changing it. Add nothing to `loader.py` in this unit.

(This decision is recorded here so a later agent does not "helpfully" refactor it.)

### Hazards for Unit 5
* **`ui/theme/theme.py` has a UTF-8 BOM.** Preserve it.
* **Token-set symmetry across the four `theme_*.py` files is load-bearing.** `constants.py` re-exports a fixed name list from `theme_aurora_light`, and `ThemeManager.apply()` patches `Theme` by name. Any name present in one theme module and absent from another will raise at theme-switch time. Add no names in this unit.
* **`QGraphicsOpacityEffect` and `QGraphicsDropShadowEffect` are mutually exclusive on one widget.** `setGraphicsEffect` replaces. The guard in Step 5.5 is mandatory, not optional.
* **Qt QSS has no `transition` property.** Do not write one.
* **Do not touch any file under `ui/widgets/` other than the new `motion.py`** in this unit — Unit 6 owns the rest.
* Do **not** run pytest.

---

## UNIT 6 — Shared widget library upgrade

**Mode:** SEQUENTIAL. Depends on Unit 5 (needs `Theme.MOTION_*`, `Theme.ELEVATION_*` and `ui/widgets/motion.py` to exist).
**Files touched:** 9

### File list
```
ui/widgets/kpi_tile.py        (upgrade)
ui/widgets/money_label.py     (upgrade)
ui/widgets/section.py         (upgrade — animated collapse)
ui/widgets/states.py          (upgrade — empty/error states)
ui/widgets/toast.py           (upgrade — fade in/out)
ui/widgets/summary_panel.py   (polish)
ui/widgets/inline_error.py    (polish)
ui/widgets/advance_tax_banner.py (polish)
ui/widgets/__init__.py        (export surface)
```

### Reuse-first rule for this unit
**Extend the existing widgets. Create no new widget modules.** Every item below is phrased as an extension of a file that already exists. If you find yourself wanting a new class, re-read the standard: a new focused component is acceptable only when extending would need more than 1–2 extra props or conditional branches — and none of the below crosses that line.

### Step 6.1 — `ui/widgets/kpi_tile.py` (currently 214 lines)
The design direction says: *"KPI tiles get a large value, a small label, a sparkline and a delta chip — the same component on every screen."*
* Add two **optional** keyword parameters to the existing constructor: `delta: str | None = None` and `sparkline: list[float] | None = None`. Both default to `None` so every existing call site keeps working unchanged.
* When `delta` is provided, render a small pill below/beside the value. Colour it by sign using existing tokens: `Theme.SUCCESS_TEXT` when the string starts with `+`, `Theme.DANGER_TEXT` when it starts with `-`, `Theme.TEXT_MUTED` otherwise. Style it with the existing `Theme.badge_style(...)` helper — do **not** write a new inline stylesheet.
* When `sparkline` is provided, render it in a `paintEvent` on a small fixed-height (24 px) child `QWidget` using `QPainter` + `QPen` with `Theme.CHART_COLORS[0]`. **Guard the `paintEvent` body with `getattr(self, "_spark_data", None)`** — an unhandled exception in a paintEvent can abort the process.
* Apply `Theme.ELEVATION_CARD` via the existing `Theme.shadow_card()`. Do not stack a second effect.
* **Do not animate the value.** "No animation on data."
* Do **not** change the existing positional signature or any existing call site.

### Step 6.2 — `ui/widgets/money_label.py` (currently 152 lines)
The direction says money figures get *"a tabular-figures font feature and colour by sign."*
* In whatever method currently builds the label's font, enable tabular figures. In PySide6:
  ```python
  font = self.font()
  font.setStyleName("")  # leave as-is if already set
  font.setFeature("tnum", 1)   # Qt 6.7+
  ```
  **Hazard:** `QFont.setFeature` requires Qt ≥ 6.7. Guard it: `if hasattr(font, "setFeature"): font.setFeature("tnum", 1)`. Do not crash on older Qt.
* Confirm the sign-colouring path uses `Theme.SUCCESS_TEXT` for positive and `Theme.DANGER_TEXT` for negative. If it already does, change nothing there.
* No new constructor parameters unless the existing API cannot express the above.

### Step 6.3 — `ui/widgets/section.py` — animated collapse (currently 188 lines)
This is the clearest motion win. The widget already has `self._expanded`, a clickable `self._header` (with `mousePressEvent` assigned at line 49), a `self._chevron_label`, and a content area.
* In whichever method toggles `self._expanded`, replace the instant show/hide of the content area with `from ui.widgets.motion import animate_height` and animate the content widget's `maximumHeight` between `0` and its `sizeHint().height()`.
* Expand: set `maximumHeight` to 0, call `show()`, then `animate_height(content, content.sizeHint().height())`. On finish, set `maximumHeight` to `16777215` so later relayouts are not clamped — connect to `anim.finished`.
* Collapse: `animate_height(content, 0)`, and connect `anim.finished` to `content.hide()`.
* Duration: let `animate_height` use its `Theme.MOTION_FAST` default. Do not pass an explicit duration.
* **Do not** animate the chevron rotation — it adds a `QPropertyAnimation` on a custom property for negligible gain and `pyqtProperty`/`Property` plumbing this codebase does not currently have. Keep the existing instant chevron swap.
* The header currently does `self._header.mousePressEvent = self._on_header_click` — leave that assignment pattern alone.

### Step 6.4 — `ui/widgets/toast.py` — fade (currently 130 lines)
The toast has `closed = Signal()` and `self.dismiss_timer = QTimer()`.
* On show: `from ui.widgets.motion import fade_in; fade_in(self)`.
* On dismiss: `fade_out(self, hide_on_finish=True)`, and connect the animation's `finished` to the existing close/emit path so `closed` still fires exactly once.
* **Hazard:** if the toast already has a drop shadow via `Theme.shadow_card()`, `fade_in` will return `None` (per the Unit 5 guard) and the toast must still appear. Ensure the show path works whether or not the fade ran — do not make visibility depend on the animation.
* Do not change the dismiss timing or the `closed` signal contract.

### Step 6.5 — `ui/widgets/states.py` (currently 255 lines)
Contains the empty state (`action_clicked = Signal()`) and error state (`retry_clicked = Signal()`).
* Style both through the existing `Theme.empty_state_style(...)` helper. If either currently writes an inline stylesheet with literal values, move those values into `ui/theme/components.py` / `theme.py` and call the helper instead — this reduces the inline-stylesheet count, which is the direction the project wants.
* Add `fade_in` on show for both states.
* Keep both signal names and their emit points exactly as they are; screens connect to them.

### Step 6.6 — Polish pass: `summary_panel.py`, `inline_error.py`, `advance_tax_banner.py`
For each: apply the elevation/radius/hairline scale via existing `Theme.*` helpers, replace any inline stylesheet containing literal colours or radii with the matching `Theme.card_style(...)` / `Theme.banner_style(...)` / `Theme.badge_style(...)` call, and add `fade_in` on show where the widget appears in response to a user action (`inline_error`, `advance_tax_banner`) but **not** where it is part of a static layout (`summary_panel`). No API changes.

### Step 6.7 — `ui/widgets/__init__.py`
Currently:
```python
# ui.widgets package

from .advance_tax_banner import AdvanceTaxBanner

__all__ = ["AdvanceTaxBanner"]
```
Do **not** expand this into a re-export hub. Every other widget is imported by its full module path today (`from ui.widgets.toast import Toast`), and changing that is an out-of-scope refactor across dozens of call sites. The only permitted change is **none** — leave the file as-is. It is listed in this unit solely so you know not to touch it.

### Hazards for Unit 6
* **Every existing call site must keep working.** New widget parameters are keyword-only with defaults. Grep for each widget's constructor before changing its signature: `grep -rn "KPITile(\|MoneyLabel(\|CollapsibleSection(" ui/`.
* **`paintEvent` exception = process abort.** Any new `paintEvent` (the sparkline) must guard every attribute access with `getattr`.
* **`QFont.setFeature` is Qt ≥ 6.7.** `hasattr` guard is mandatory.
* **Opacity vs shadow effect collision** — the Unit 5 `fade_in` guard handles it, but every call site must tolerate a `None` return.
* **Inline-stylesheet budget:** this unit should *reduce* the count of `setStyleSheet()` calls outside `ui/theme/`, never increase it. If an edit would add one, put the style in `ui/theme/components.py` instead.
* Do **not** run pytest.

---

## UNIT 7 — App shell: layout and navigation rework

**Mode:** PARALLEL with Unit 8. Depends on Units 5 and 6.
**Files touched:** 2 (`ui/dashboard_screen.py`, plus QSS additions in `ui/theme/theme.py`)

**Coordination note:** Units 7 and 8 both may touch `ui/theme/theme.py`. To avoid a conflict, **Unit 7 owns all shell/sidebar/topbar QSS rules** and **Unit 8 owns all screen-content QSS rules**. If you are running Unit 7, restrict your `theme.py` edits to selectors named `#sidebar`, `#navLabel`, `#sidebarToggle`, `[nav_item="true"]`, `#topbar`, `#contentArea`, `#pageHeader`. Touch nothing else in that file.

### Current structure (verified — orient yourself here first)
`ui/dashboard_screen.py` (1183 lines) is the `QMainWindow` shell:
* `_NAV_ITEMS` list at line 36 — `(label, icon)` tuples driving the sidebar.
* `_build_ui()` at ~line 119 — `QHBoxLayout` root: `_build_sidebar()` on the left, then a right column of `_build_topbar()` + `_build_content_area()`.
* `_build_sidebar()` at line 144 — a `QWidget` named `"sidebar"`, `setFixedWidth(248 if self.sidebar_expanded else 76)`, holds `self.nav_lbl`, `self._nav_buttons: list[QToolButton]`, and `self._sidebar_toggle_btn`.
* `_make_nav_btn()` at line 230 — builds a `QToolButton` container with `setProperty("nav_item", True)`, an icon `QLabel` and a `nav_label` `QLabel`, with different margins for expanded vs collapsed.
* `_toggle_sidebar()` — flips `self.sidebar_expanded`, persists via `session.is_sidebar_open()`.
* `self.stack = QStackedWidget()` at line 510 — screens are **lazily built** into `self._screen_pages: dict[int, QWidget | None]`, with construction errors captured into `self._screen_errors`.
* `_navigate(index)` at ~line 303 — resolves `screen_key` from `_NAV_ITEMS[index]`, builds the page if needed, sets the stack.
* `_set_nav_active(index)` — applies active styling via `components.sidebar_nav_active()` / `sidebar_nav_normal()`.
* `self.page_title_lbl` updated from `_NAV_ITEMS[index][0]` at line 1001.
* `ThemeManager.register_on_change(self._on_theme_changed)` in `__init__`.

### Step 7.1 — Animate the sidebar expand/collapse
In `_toggle_sidebar()`, the width currently changes instantly via `setFixedWidth`. Replace with:
```python
from ui.widgets.motion import animate_width
```
(at module top, with the other `ui.` imports) and animate between `76` and `248`. Because the widget uses `setFixedWidth`, animate the `minimumWidth` and `maximumWidth` together, or switch to `setMaximumWidth`/`setMinimumWidth` and animate `maximumWidth` — `animate_width` in `ui/widgets/motion.py` handles this; call it and let it own the mechanism.
* The label visibility toggle (`self.nav_lbl.setVisible(...)` and the per-button `nav_label` show/hide) must fire **at the end** of a collapse and **at the start** of an expand, so text never renders in a 76 px-wide sidebar. Connect to `anim.finished` for the collapse case.
* Keep the `session.is_sidebar_open()` persistence exactly as it is.
* Keep `76` and `248` as the two widths — do not retune them.

### Step 7.2 — Cross-fade on screen navigation
In `_navigate(index)`, after `self.stack.setCurrentWidget(page)` (or `setCurrentIndex`), add `fade_in(page)` from `ui.widgets.motion`.
* Use the `Theme.MOTION_BASE` default. Do **not** build a slide transition between stack pages — `QStackedWidget` does not support two pages being visible at once without a custom paint path, and the direction says motion only explains.
* **Critical:** the lazy-build path can raise; `self._screen_errors[index]` exists precisely because a screen constructor can fail. Only call `fade_in` on a successfully built page. If the page is an error placeholder, show it without animation.
* Do not change the lazy-build logic, the error capture, or `_detached_placeholders`.

### Step 7.3 — Nav item hover and active treatment
* Move the nav-item hover state into the QSS (selector `[nav_item="true"]:hover`) using `{t.SIDEBAR_HOVER}`, so it is declarative rather than code-driven. The active state already flows through `components.sidebar_nav_active()` — leave that mechanism alone; just ensure the hover rule exists and does not fight the active rule (active must win; put the active rule after hover in the stylesheet, or scope hover to `:!checked`).
* Add a **2–3 px left accent bar** on the active nav item using a `border-left` in the active style, coloured `{t.SIDEBAR_ACTIVE}`. This is the cheapest high-impact "which screen am I on" affordance and matches the direction's "3px left accent only where the card has a status".

### Step 7.4 — Topbar / page header
* `self.page_title_lbl` at line 433 is set with `QFont("Segoe UI", 15, QFont.Weight.Bold)` inline. Leave the font call (changing it is churn), but ensure the topbar container is styled via the QSS `#topbar` selector using `{t.TOPBAR_BG}` and `{t.TOPBAR_BORDER}`, not inline.
* Add breadcrumb-style secondary text **only if** a secondary context string already exists in the shell's state. **Do not invent new data to display.** If no such state exists, skip this sub-step entirely.

### Step 7.5 — Content-area rhythm
In `_build_content_area()`, set the outer content margins to the spacing scale: `setContentsMargins(24, 24, 24, 24)` and `setSpacing(16)`. Do not change any individual screen's internal layout — that is Unit 8's territory.

### Explicitly OUT of scope for Unit 7
* Do **not** change `_NAV_ITEMS` — not its order, not its labels, not its icons. Reordering navigation changes muscle memory and is not a requested goal.
* Do **not** convert the sidebar to a different widget type (no `QListWidget`, no `QToolBar`).
* Do **not** touch `self.stack`'s lazy-build contract.
* Do **not** edit any file under `ui/dialogs/` or any screen other than `dashboard_screen.py`.

### Hazards for Unit 7
* **`dashboard_screen.py` is 1183 lines and is the app's single point of failure** — if it raises at construction, nothing renders. Make small, surgical edits.
* **Screens are lazily built**, so a constructor error in a screen stays hidden until that screen is visited. Your changes must not make `_navigate` throw before the existing error-capture runs.
* **`ThemeManager.register_on_change(self._on_theme_changed)`** means your new QSS must survive a live theme switch. Do not cache a colour value in Python; read it from `Theme.*` at style-build time, as the existing code does.
* **Width animation + `setFixedWidth` conflict:** `setFixedWidth` pins min and max. If you animate only `maximumWidth`, the pinned `minimumWidth` will prevent the collapse. Handle both bounds.
* Do **not** run pytest.

---

## UNIT 8 — Screen and dialog visual polish

**Mode:** PARALLEL with Unit 7. Depends on Units 5 and 6.
**Files touched:** ~9 screens + 13 dialogs (visual-only edits)

**Coordination note:** see Unit 7's note. Unit 8 owns screen-content QSS in `ui/theme/theme.py`; it must **not** edit the `#sidebar` / `#topbar` / `[nav_item]` / `#contentArea` selectors.

### File list
```
ui/accounts_screen.py
ui/fixed_deposits_screen.py
ui/income_management_screen.py
ui/manage_data_screen.py
ui/settings_screen.py
ui/statement_import_screen_modern.py
ui/tax_documents_screen.py
ui/tax_screen.py
ui/transactions_screen.py
ui/dialogs/*.py   (all 13)
```
(`ui/dashboard_screen.py` is Unit 7's. `ui/login_screen.py`, `ui/setup_screen.py`, `ui/onboarding.py` are pre-auth flows — **leave them alone**; changing the login path risks locking the user out of their own app for zero visual-goal payoff.)

### The four rules to apply, per file, mechanically

**Rule 1 — One primary action per screen.** In each screen, find every `Theme.btn(...)` / `Theme.style_button(...)` call. At most **one** button per screen may use `variant="primary"`. Every other action becomes `"secondary"` (or `"danger"` where it is genuinely destructive). The direction: *"the moment two buttons with different jobs share a colour, colour has stopped being information and become noise."* Pick the primary by asking "what is this screen for?" — Transactions → *Add transaction*; Fixed Deposits → *Add FD*; Statement Import → *Import*; Accounts → *Add account*; Income Management → *Add income source*; Tax → the single compute/save action; Manage Data → *Add* on the active tab; Tax Documents → *Upload*; Settings → *Save*. If a screen genuinely has no single primary, make them all secondary.

**Rule 2 — Per-screen accent.** `ui/theme/theme.py` already has `Theme.screen_accent(screen_key)` (line 188). Use it for each screen's section headings and its one primary button, via the existing `Theme.section_label_style(size, accent_color=...)` helper. **Do not invent new per-screen palettes** — `screen_accent` draws from the theme's chart palette, which is exactly what the direction asks for. If a screen does not currently call `screen_accent`, add the call; do not hardcode a colour.

**Rule 3 — Inline stylesheets and raw hex.** In every file, search for `setStyleSheet(` and for a raw hex pattern (`#` followed by 3 or 6 hex digits inside a string). For each hit:
* If it contains a literal colour → replace the colour with the matching `Theme.TOKEN`.
* If the whole rule duplicates an existing helper (`Theme.card_style`, `Theme.badge_style`, `Theme.banner_style`, `Theme.stat_tile_style`, `Theme.action_bar_style`, `Theme.filter_bar_style`, `Theme.icon_chip_style`, `Theme.empty_state_style`, `Theme.page_header_style`, `Theme.hero_header_style`, `Theme.tinted_surface_style`, `Theme.group_box_style`, `Theme.panel_strip_style`, `Theme.metric_card_style`, `Theme.regime_card_style`, `Theme.info_banner_style`) → call the helper instead.
* If neither applies and the rule is genuinely one-off, leave it — but **never add a new one**.
The net count of inline `setStyleSheet()` calls outside `ui/theme/` must go **down or stay flat**, never up.

**Rule 4 — Scale conformance.** Replace stray literal radii with `Theme.RADIUS_CONTROL/CARD/MODAL/PILL`. Replace stray `setContentsMargins`/`setSpacing` values with the nearest member of {4, 8, 12, 16, 24, 32, 48}. Set input/button `setFixedHeight`/`setMinimumHeight` to the nearest of {28, 36, 44}. Apply `setMaximumWidth` caps to over-wide controls per the direction's control-max-width scale: currency 200, date 160, short select 200, long select 320, text 420.

### Motion in this unit
The **only** motion permitted here is calling `fade_in` from `ui.widgets.motion` when a screen-level panel appears in response to a user action (a results panel after an import, an error banner, an expanded detail card). 
* **Do not** animate table rows, chart draws, money values, or KPI numbers.
* **Do not** add a `QPropertyAnimation` directly in a screen file — always go through `ui/widgets/motion.py`.
* **Do not** animate anything in a dialog's `__init__`/`showEvent` — a dialog that fades in during a modal `exec()` is a flicker risk.

### Dialogs (`ui/dialogs/*.py`) — restricted scope
For the 13 dialogs, apply **only Rule 1, Rule 3 and Rule 4**. Specifically:
* Ensure each dialog has exactly one primary button (the confirm/save action); Cancel is secondary.
* Set the dialog's own corner radius to `Theme.RADIUS_MODAL`.
* Normalise field heights to 36 and apply the control-max-width caps — the direction explicitly calls out that inputs are too wide.
* **Do not restructure any dialog.** In particular: `AccountDialog`'s 31 fields across 5 tabs (Basic Info / Bank Details / Contact / Debit Card / Account Holders) is a **verified good** design per `docs/FRONTEND_REDESIGN_PLAN.json` — do not flatten it.
* **Do not** change any `.exec()` call or any `QDialog.DialogCode.Accepted` comparison.
* **Do not** "fix" dialog modality. `isModal()` returning `False` before `exec()` is expected and is documented as a verified non-issue.

### Explicitly OUT of scope for Unit 8
* No behaviour changes. No data-flow changes. No new computed values. No renames.
* No changes to `ui/widgets/excel_table.py` or `ui/widgets/chart_widget.py` — table and chart internals are out of scope for a visual-polish pass and are high-risk.
* No changes to `ui/login_screen.py`, `ui/setup_screen.py`, `ui/onboarding.py`, `ui/dashboard_screen.py`.
* No terminology changes — `docs/TERMINOLOGY.md` already locks one word per concept and a prior pass (commit `113222b`) applied it.

### Hazards for Unit 8
* **`ui/statement_import_screen_modern.py` is 1855 lines** and was heavily reworked in the two most recent commits (`96cfc2a`, `170dede`: statement import redesign, checkbox/selection sync, dropzone clicks, chart collapse). Its current state is deliberate and recent. Apply **only** Rules 3 and 4 there — do not re-lay-out it, do not touch the drop-zone click handling, the checkbox/selection sync, or the chart collapse. That work is fresh and correct.
* **Screens are lazily constructed**, so any error you introduce will not surface until that screen is opened. Be conservative.
* **`showEvent`/`paintEvent`/`resizeEvent` exception = silent process abort.** If you touch one, guard every attribute with `getattr`.
* **Theme-switch survival:** never cache a `Theme.*` value at class-definition time; read it inside the style-building method, as the existing code does. Screens register `_on_theme_changed` handlers — if you add styling, make sure the refresh path re-applies it.
* **`ui/settings_screen.py` has a live `QThread` warmup** (`self._warmup_thread`, `self._warmup_worker`, lines 836–838) and a `QTimer.singleShot(2200, self._refresh_badges)` at line 508. Do not touch either — visual polish only.
* **Contrast:** any colour pair you touch must stay at 4.5:1 or better. When in doubt, do not change the colour.
* Do **not** run pytest.

---

## OPTIONAL — final launch smoke check

**Mode:** SEQUENTIAL, after Unit 8 (and Unit 7). Optional.

This is the **only** verification step in the entire roadmap, and it is optional. It is not a gate — if it fails, record what failed and stop; do not start fixing bugs, because bug-fixing is a separate future effort.

```
cd D:\Pranav\app
.venv\Scripts\python.exe -m pip uninstall -y PyQt6 PyQt6-Qt6 PyQt6-sip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe main.py
```
Success = the window appears and the login (or setup) screen renders. Close it.

If it does not launch, capture the traceback and report it verbatim. Do not attempt a fix.

**Do not run `pytest` at any point.**

---

## Appendix — consolidated "verified, do not change" list

These were each checked against the real code. An agent that "fixes" one of them is introducing a regression.

| Thing | Status | Action |
|---|---|---|
| Enum access style (`Qt.AlignmentFlag.AlignCenter` etc.) | Already fully-scoped Qt6 form throughout, 0 short-form | **No change** |
| `.exec()` (37 sites) | Already Qt6 spelling | **No change** — never `.exec_()` |
| `QDialog.DialogCode.Accepted` comparisons | Correct in both bindings | **No change** |
| `sip` / `sip.isdeleted` | Does not exist in project code | **Nothing to port** |
| `shiboken6.isValid` | Not needed | **Do not add** |
| `QAction` / `QShortcut` / `QActionGroup` | Not used anywhere | **Nothing to port** |
| `QKeySequence`, `QKeyEvent` | In `QtGui` in both bindings | **Module prefix only** |
| `QVariant` / `.toPython()` | Not used; `UserRole` data is plain `str`/`int` | **No change** |
| Mouse position accessors (`.pos()`, `.globalPos()`) | Zero handlers read the event position | **Nothing to port** |
| `QFontMetrics` (2 sites) | No use of the removed `.width()` | **No change** |
| `QTimer.singleShot(ms, fn)` (4 sites) | Identical signature | **No change** |
| `qRegisterMetaType` | All cross-thread payloads are `str`/`object` | **Do not add** |
| `QFont(family, size, QFont.Weight.Bold)` | Identical | **No change** |
| `pyqtSlot` / `pyqtProperty` | Zero occurrences | **Nothing to port** |
| Dialog modality (`isModal()` False before `exec()`) | Documented verified non-issue | **Do not "fix"** |
| `AccountDialog` 5-tab layout | Documented verified good | **Do not flatten** |
| `ui/widgets/loader.py` hand-rolled fade | Paints its own scrim; effect-based fade would change behaviour | **Leave as-is** |
| `matplotlib` qt5agg/agg fallback chain in `chart_widget.py` | Harmless defence | **Keep** |
| `ui/widgets/__init__.py` minimal export | Expanding it is an out-of-scope refactor | **Leave as-is** |
| `_NAV_ITEMS` order/labels/icons | Reordering navigation is not a requested goal | **Do not change** |

---

## Final report — unit summary

| # | Unit name | Mode | Depends on | Files |
|---|---|---|---|---|
| 1 | Binding selection, dependencies and entry point | **SEQUENTIAL** (first) | — | 3 |
| 2 | Mechanical port: `ui/` core screens | **PARALLEL** (with 3, 4) | 1 | 30 |
| 3 | Mechanical port: `ui/theme/` and `ui/widgets/` | **PARALLEL** (with 2, 4) | 1 | 19 |
| 4 | Mechanical port: `tests/` and `tools/` | **PARALLEL** (with 2, 3) | 1 | ~17 |
| 5 | Theme tokens, QSS polish, shared motion helper | **SEQUENTIAL** | 2, 3, 4 | 8 (1 new: `ui/widgets/motion.py`) |
| 6 | Shared widget library upgrade | **SEQUENTIAL** | 5 | 9 |
| 7 | App shell: layout and navigation rework | **PARALLEL** (with 8) | 5, 6 | 2 |
| 8 | Screen and dialog visual polish | **PARALLEL** (with 7) | 5, 6 | ~22 |
| — | Optional launch smoke check | SEQUENTIAL, optional | 7, 8 | 0 |

**8 units.** Two fan-out points: {2, 3, 4} and {7, 8}. Exactly one new file across the whole roadmap (`ui/widgets/motion.py`). Zero test gates; one optional launch check at the end.

**Fan-out instruction for you:** dispatch Unit 1 alone; on completion dispatch 2, 3, 4 concurrently; on all three completing dispatch 5, then 6; on 6 completing dispatch 7 and 8 concurrently. The Unit 7/8 `theme.py` ownership split (shell selectors vs. screen-content selectors) is stated inside both units so the parallel pair does not collide.

**Path to write this to:** `D:\Pranav\app\docs\PYSIDE6_MIGRATION_PLAN.md`

---

## UNIT 4 — Mechanical port: `tests/` and `tools/`

**Mode:** PARALLEL with Units 2 and 3. Depends on Unit 1.
**Files touched:** ~14

### Scope note the executing agent must read first
These files are ported **for import-time correctness only**. Their passing is **not** a gate and is **not** your responsibility. Do not modify test logic, assertions, fixtures, expected values or skip markers to make anything pass. Do not run pytest. If a test looks wrong, leave it wrong — a separate testing effort will handle it.

### File list
Every file under `tests/` and `tools/` that contains the string `PyQt6`. Find them with:
```
grep -rln "PyQt6" tests/ tools/
```
Known members include `tests/conftest.py`, `tests/test_button_hierarchy.py`, `tests/test_chart_relocation.py`, `tests/test_dashboard_lazy.py`, `tests/test_excel_mapping.py`, `tests/test_excel_table_enter_key.py`, `tests/test_excel_table_parity.py`, `tests/test_kpi_tile.py`, `tests/test_money_label.py`, `tests/test_readme_shortcuts.py`, `tests/test_screen_render.py`, `tests/test_statement_import_flow.py`, `tests/test_summary_panel.py`, `tests/test_theme_qss.py`, `tests/test_ui_threading.py`, `tools/real_ui_test_harness.py`, `tools/real_ui_tests/test_add_person_flow.py`. Use the grep result as the authoritative list, not this one.

**Do not touch `.venv/`.** Restrict every operation to `tests/` and `tools/`.

### Transformations
1. **Transformation A:** `from PyQt6.QtCore import ...` → `from PySide6.QtCore import ...`; same for `QtGui`, `QtWidgets`, and **`QtTest`**.
   * `tests/test_statement_import_flow.py:21` — `from PyQt6.QtTest import QTest` → `from PySide6.QtTest import QTest`
   * `tools/real_ui_test_harness.py:100` — `from PyQt6.QtTest import QTest` → `from PySide6.QtTest import QTest`
   * `PySide6.QtTest` exists and exports `QTest` with the same `QTest.keyClick`, `QTest.mouseClick`, `QTest.qWait` surface used here.
2. **Transformation B:** `pyqtSignal` → `Signal` if present (whole-word).
3. **Transformation C:** update `PyQt6` in comments/docstrings to `PySide6` **only** where the sentence describes the binding the code runs against. Two known cases to handle:
   * `tools/real_ui_test_harness.py` contains a docstring line "Since this app is a normal on-screen (non-offscreen) PyQt6 window running in the…" → change `PyQt6` to `PySide6`.
   * `tools/real_ui_test_harness.py:124` and `:259` reference `QDialog.exec()` / `app.exec()` in prose — those are still accurate; leave the sentences alone except for the `PyQt6` word if present.
   * Leave narrative comments that record *past* audit methodology unchanged.

### Step 4.4 — `tests/conftest.py` binding pin
`tests/conftest.py` currently begins:
```python
import os
import sys
import tempfile
import shutil

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```
Add a `QT_API` pin so tests that import `chart_widget` or `qtawesome` without going through `main.py` bind correctly. Change that block to **exactly**:
```python
import os
import sys
import tempfile
import shutil

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyside6")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```
Nothing else in `conftest.py` changes. Do not touch the `setup_test_database` fixture or its temp-dir/DB-path patching.

### Step 4.5 — `tools/real_ui_test_harness.py` binding pin
This file is an independent entry point. Add, as the first executable statement after its imports of `os`/`sys` and **before** the `from PySide6.QtTest import QTest` on line 100 and before any other Qt import in the file:
```python
os.environ.setdefault("QT_API", "pyside6")
```
If `import os` is not already at the top of the file, add it to the existing top-level import group. Place the `setdefault` line immediately after that import group and above every `PySide6` import in the file.

### What must NOT change
* Same "do not change" list as Unit 2: no enum rewriting, no `.exec_()`, no `qRegisterMetaType`, no reformatting.
* `tests/test_ui_threading.py:15` — `from PyQt6.QtCore import QThread, QTimer, Qt` → `from PySide6.QtCore import QThread, QTimer, Qt`. Its comment at line 63 ("Run worker in a separate thread (simulating QThread)") is fine as-is.
* `tests/test_readme_shortcuts.py:18` and `tests/test_excel_table_parity.py:17` import `QKeySequence`/`QKeyEvent` from `QtGui` — same location in PySide6, only the module prefix changes.
* Do **not** add, remove or edit any assertion, any `@pytest.mark.skip`/`xfail`, or any expected-value constant.

### Hazards for Unit 4
* A naive project-wide `sed` will hit `.venv/` (which contains matplotlib's `qt_compat.py` and qtpy, both of which legitimately reference `PyQt6`). **Scope every operation to `tests/` and `tools/` explicitly.**
* `tools/real_ui_tests/test_add_person_flow.py` uses `QTimer.singleShot(0, _fill_and_save_person_dialog)` at line 117 to pre-schedule work before a blocking `dlg.exec()`. This pattern works identically in PySide6. Do not change it.
* One PySide6 behaviour worth knowing but **not** worth pre-emptively coding around: PySide6 keeps a reference to a signal's Python receiver differently from PyQt6 in some lambda-connection cases. In *this* codebase every `.connect()` target is either a bound method of a long-lived widget or a lambda capturing loop variables by default-argument — neither is at risk. **Do not add `functools.partial` rewrites or explicit reference-holding to "fix" a problem that does not exist here.** If a specific crash surfaces later, that is the separate testing effort's problem.
* After finishing, `grep -rn "PyQt6" tests/ tools/` must return nothing. Do **not** run pytest.

---

## UNIT 5 — Theme tokens, QSS polish, and the shared motion helper

**Mode:** SEQUENTIAL. Depends on Units 2, 3 and 4 all being complete (the port must land before redesign touches the same files, so a later crash is attributable to redesign rather than to a binding difference).
**Files touched:** 8

### File list
```
ui/theme/theme.py            (extend: motion tokens, QSS polish)
ui/theme/components.py       (extend: elevation + motion style helpers)
ui/theme/constants.py        (extend: motion + elevation constants)
ui/theme/theme_aurora_light.py
ui/theme/theme_nova_dark.py
ui/theme/theme_slate_light.py
ui/theme/theme_midnight_pro.py
ui/widgets/motion.py         (NEW — the one new module this whole roadmap creates)
```

### Design direction (binding — from `docs/FRONTEND_REDESIGN_PLAN.json`, do not reinvent)
* **Colour carries meaning.** One accent for the primary action per screen. Green = money in / positive; red = money out / destructive; amber = attention; blue/indigo = neutral action. Nothing else gets a fill.
* **Data is the decoration.** Colour comes from charts and money figures, not chrome.
* **Density with air.** Whitespace goes *between groups*, not inside every control.
* **MOTION ONLY TO EXPLAIN.** A 120 ms ease on hover/expand is enough. **No animation on data.**
* Radius scale: control 8, card 12, modal 16, pill 999. These already exist in `ui/theme/constants.py` as `RADIUS_CONTROL`/`RADIUS_CARD`/`RADIUS_MODAL`/`RADIUS_PILL` — **reuse them, do not add a parallel scale.**
* Spacing scale: 4, 8, 12, 16, 24, 32, 48.
* Control heights: sm 28, md 36, lg 44.

### Step 5.1 — Motion tokens in `ui/theme/constants.py`
`ui/theme/constants.py` already ends with a "Radius scale constants" block followed by legacy shadow aliases. **Append** a new block at the end of the file, after the existing legacy aliases:
```python
# Motion scale — see ui/widgets/motion.py. Durations in ms.
MOTION_FAST   = 120      # hover, press, chip toggle
MOTION_BASE   = 180      # fade in/out, expand/collapse
MOTION_SLOW   = 260      # page/route transitions
MOTION_EASING = "OutCubic"   # QEasingCurve.Type member name

# Elevation scale — QGraphicsDropShadowEffect params (blur, offset_y, alpha)
ELEVATION_CARD   = (2,  1,  16)
ELEVATION_RAISED = (12, 4,  26)
ELEVATION_MODAL  = (32, 12, 46)
```
Do not remove or reorder anything already in the file. Do not touch the big `from .theme_aurora_light import (...)` re-export block.

### Step 5.2 — Surface the motion tokens on `Theme`
In `ui/theme/theme.py`, the `Theme` class assigns colour tokens from `c` (the `constants` module, imported as `from . import constants as c`). Find the block where radius constants are surfaced (search for `RADIUS_CONTROL`). **Immediately after** the radius block, add:
```python
    MOTION_FAST   = c.MOTION_FAST
    MOTION_BASE   = c.MOTION_BASE
    MOTION_SLOW   = c.MOTION_SLOW
    MOTION_EASING = c.MOTION_EASING

    ELEVATION_CARD   = c.ELEVATION_CARD
    ELEVATION_RAISED = c.ELEVATION_RAISED
    ELEVATION_MODAL  = c.ELEVATION_MODAL
```
These are theme-independent (motion timing does not change per theme), so **do not** add them to the four `theme_*.py` colour modules and **do not** add them to `ThemeManager`'s patch list.

### Step 5.3 — Per-theme accent polish (the four `theme_*.py` files)
For each of `theme_aurora_light.py`, `theme_nova_dark.py`, `theme_slate_light.py`, `theme_midnight_pro.py`:
* **Do not add or remove any token name.** All four must keep exactly the same set of exported names, because `constants.py` re-exports a fixed list from `theme_aurora_light` and `ThemeManager` patches by name. Adding a name to one theme and not the others will break theme switching.
* The permitted change in this step is **value tuning only**: adjust `BORDER` and `DIVIDER` toward a lighter hairline (the design direction says "Cards lose their heavy 1.5px borders in favour of a subtle shadow plus a 1px hairline"), and verify `SHADOW_RGBA_CARD` / `SHADOW_RGBA_ELEVATED` read as soft rather than heavy.
* **Contrast rule:** any text-on-background pair you change must keep at least 4.5:1 contrast. If unsure whether a tweak is safe, **do not make it.** Value tuning here is optional polish; token-set integrity is mandatory.

### Step 5.4 — QSS polish in `ui/theme/theme.py`
`ui/theme/theme.py` contains the global stylesheet as a large f-string (`Theme.get_stylesheet()`), interpolating `{t.TOKEN}` values. Make these targeted edits **inside that f-string only**:
1. **Unify radii.** Find every literal pixel radius in the QSS (e.g. `border-radius: 14px`, `border-radius: 10px`) and replace it with the matching scale token: controls/inputs/buttons → `{t.RADIUS_CONTROL}px`, cards/frames/group boxes → `{t.RADIUS_CARD}px`, dialogs → `{t.RADIUS_MODAL}px`, avatars/pills/chips → `{t.RADIUS_PILL}px`. Some already use the tokens (e.g. line 677's `QTabWidget::pane`) — leave those.
2. **Unify borders to a 1px hairline.** Replace any `border: 2px solid {t.BORDER}` or `1.5px` with `border: 1px solid {t.BORDER}`. **Exception:** keep 2px where it is a *focus ring* (`{t.BORDER_FOCUS}` / `{t.FOCUS_RING}`) or an intentional emphasis state — focus visibility is an accessibility requirement and must not be weakened.
3. **Unify control heights.** Give `QLineEdit`, `QComboBox`, `QDateEdit`, `QSpinBox`, `QDoubleSpinBox` and `QPushButton` a `min-height` from the {28, 36, 44} scale — default `36px` unless a rule already sets a deliberate different height.
4. **Add a hover state to every interactive rule that lacks one.** For `QPushButton`, `QToolButton`, `QComboBox`, table rows and nav items, ensure a `:hover` selector exists using an existing token (`{t.SIDEBAR_HOVER}`, `{t.SURFACE_ALT}`, or a `{t.PRIMARY_GRADIENT_HOVER_START}`/`END` gradient via `{Theme.gradient(...)}`). Do **not** invent new colours — every value must come from an existing `Theme` token.
5. **Do not add `transition:` properties.** Qt's QSS does not support CSS transitions. All motion goes through `ui/widgets/motion.py` (Step 5.5). Writing `transition:` in QSS is silently ignored and is a common mistake — do not do it.
6. **Do not add raw hex.** Every colour in the QSS must be a `{t.TOKEN}` interpolation.
7. **Performance note:** theme switching is ~245 ms with one screen built. Adding bulk QSS makes that worse and is a known, accepted trade. Do **not** attempt to "fix" it by moving rules to per-widget `setStyleSheet()` — that would violate the inline-stylesheet budget.

### Step 5.5 — NEW FILE: `ui/widgets/motion.py`

This is the single shared motion helper. **All motion in the app goes through it.** No screen may create its own `QPropertyAnimation`.

Create `D:\Pranav\app\ui\widgets\motion.py` with this exact structure (fill in the bodies; the signatures, names and imports are fixed):

```python
"""ui/widgets/motion.py — Shared motion helpers.

Motion explains state change; it never decorates data. Durations and easing
come from Theme.MOTION_*; callers pass a widget, not a duration.
"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QAbstractAnimation, Qt
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget

from ui.theme import Theme


def _curve() -> QEasingCurve:
    return QEasingCurve(getattr(QEasingCurve.Type, Theme.MOTION_EASING))


def fade_in(widget: QWidget, duration: int | None = None) -> QPropertyAnimation:
    """Fade a widget from transparent to opaque. Returns the running animation."""


def fade_out(widget: QWidget, duration: int | None = None, hide_on_finish: bool = True) -> QPropertyAnimation:
    """Fade a widget to transparent, optionally hiding it when done."""


def slide_in(widget: QWidget, dx: int = 0, dy: int = 12, duration: int | None = None) -> QPropertyAnimation:
    """Animate a widget's geometry from an offset back to its laid-out position."""


def animate_width(widget: QWidget, target: int, duration: int | None = None) -> QPropertyAnimation:
    """Animate a widget's fixed width (used by the sidebar expand/collapse)."""


def animate_height(widget: QWidget, target: int, duration: int | None = None) -> QPropertyAnimation:
    """Animate a widget's maximum height (used by collapsible sections)."""
```

Implementation rules, all mandatory:
* **Default duration** is `Theme.MOTION_BASE` when `duration is None`, except `animate_width`/`animate_height` which default to `Theme.MOTION_FAST`.
* **Lifetime:** every animation must be kept alive or it will be garbage-collected mid-flight and the widget will snap. Two mechanisms, use both: construct with the widget as parent (`QPropertyAnimation(effect, b"opacity", widget)`), **and** store the animation on the widget as `widget._motion_anim = anim` before starting. Before starting a new animation on a widget, stop and clear any existing `widget._motion_anim`.
* **Start with** `anim.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)`.
* **Opacity effects:** `fade_in`/`fade_out` must **reuse** an existing `QGraphicsOpacityEffect` if `widget.graphicsEffect()` already returns one, rather than installing a second. Installing a graphics effect replaces any existing one — so a widget that already has a `QGraphicsDropShadowEffect` from `Theme.shadow_card()` **cannot** also have an opacity effect. Guard: if `widget.graphicsEffect()` is a `QGraphicsDropShadowEffect`, **skip the fade entirely and return `None`**, rather than destroying the shadow. Document this in one comment line.
* **Reduced motion:** add a module-level `ENABLED = True` flag. Every function returns immediately (setting the final value directly, no animation) when `ENABLED` is `False`. This gives a single kill-switch for offscreen rendering and future accessibility work.
* **Return type** is `QPropertyAnimation | None` — `None` when motion was skipped.
* **Do not** add animation for data values (money figures, table cells, chart series). The design direction forbids it.

### Step 5.6 — Replace the hand-rolled fade in `ui/widgets/loader.py`
`ui/widgets/loader.py` lines ~181–275 implement a fade with `self._opacity`, `self._fade_timer = QTimer(self)`, `_fade_in_step()` incrementing by 0.1 every 16 ms, and a `paintEvent` that reads `int(self._opacity * 140)`.

This is a hand-rolled animation that now duplicates `motion.fade_in`. **However:** the loader's overlay paints its own scrim via `paintEvent` using `self._opacity` directly, so swapping in `QGraphicsOpacityEffect` would change what is being animated. **Decision: leave `loader.py`'s fade as it is.** Replacing it is a behaviour change with no user-visible benefit, and the standards say to preserve existing behaviour unless the task requires changing it. Add nothing to `loader.py` in this unit.

(This decision is recorded here so a later agent does not "helpfully" refactor it.)

### Hazards for Unit 5
* **`ui/theme/theme.py` has a UTF-8 BOM.** Preserve it.
* **Token-set symmetry across the four `theme_*.py` files is load-bearing.** `constants.py` re-exports a fixed name list from `theme_aurora_light`, and `ThemeManager.apply()` patches `Theme` by name. Any name present in one theme module and absent from another will raise at theme-switch time. Add no names in this unit.
* **`QGraphicsOpacityEffect` and `QGraphicsDropShadowEffect` are mutually exclusive on one widget.** `setGraphicsEffect` replaces. The guard in Step 5.5 is mandatory, not optional.
* **Qt QSS has no `transition` property.** Do not write one.
* **Do not touch any file under `ui/widgets/` other than the new `motion.py`** in this unit — Unit 6 owns the rest.
* Do **not** run pytest.

---

## UNIT 6 — Shared widget library upgrade

**Mode:** SEQUENTIAL. Depends on Unit 5 (needs `Theme.MOTION_*`, `Theme.ELEVATION_*` and `ui/widgets/motion.py` to exist).
**Files touched:** 9

### File list
```
ui/widgets/kpi_tile.py        (upgrade)
ui/widgets/money_label.py     (upgrade)
ui/widgets/section.py         (upgrade — animated collapse)
ui/widgets/states.py          (upgrade — empty/error states)
ui/widgets/toast.py           (upgrade — fade in/out)
ui/widgets/summary_panel.py   (polish)
ui/widgets/inline_error.py    (polish)
ui/widgets/advance_tax_banner.py (polish)
ui/widgets/__init__.py        (export surface)
```

### Reuse-first rule for this unit
**Extend the existing widgets. Create no new widget modules.** Every item below is phrased as an extension of a file that already exists. If you find yourself wanting a new class, re-read the standard: a new focused component is acceptable only when extending would need more than 1–2 extra props or conditional branches — and none of the below crosses that line.

### Step 6.1 — `ui/widgets/kpi_tile.py` (currently 214 lines)
The design direction says: *"KPI tiles get a large value, a small label, a sparkline and a delta chip — the same component on every screen."*
* Add two **optional** keyword parameters to the existing constructor: `delta: str | None = None` and `sparkline: list[float] | None = None`. Both default to `None` so every existing call site keeps working unchanged.
* When `delta` is provided, render a small pill below/beside the value. Colour it by sign using existing tokens: `Theme.SUCCESS_TEXT` when the string starts with `+`, `Theme.DANGER_TEXT` when it starts with `-`, `Theme.TEXT_MUTED` otherwise. Style it with the existing `Theme.badge_style(...)` helper — do **not** write a new inline stylesheet.
* When `sparkline` is provided, render it in a `paintEvent` on a small fixed-height (24 px) child `QWidget` using `QPainter` + `QPen` with `Theme.CHART_COLORS[0]`. **Guard the `paintEvent` body with `getattr(self, "_spark_data", None)`** — an unhandled exception in a paintEvent can abort the process.
* Apply `Theme.ELEVATION_CARD` via the existing `Theme.shadow_card()`. Do not stack a second effect.
* **Do not animate the value.** "No animation on data."
* Do **not** change the existing positional signature or any existing call site.

### Step 6.2 — `ui/widgets/money_label.py` (currently 152 lines)
The direction says money figures get *"a tabular-figures font feature and colour by sign."*
* In whatever method currently builds the label's font, enable tabular figures. In PySide6:
  ```python
  font = self.font()
  font.setStyleName("")  # leave as-is if already set
  font.setFeature("tnum", 1)   # Qt 6.7+
  ```
  **Hazard:** `QFont.setFeature` requires Qt ≥ 6.7. Guard it: `if hasattr(font, "setFeature"): font.setFeature("tnum", 1)`. Do not crash on older Qt.
* Confirm the sign-colouring path uses `Theme.SUCCESS_TEXT` for positive and `Theme.DANGER_TEXT` for negative. If it already does, change nothing there.
* No new constructor parameters unless the existing API cannot express the above.

### Step 6.3 — `ui/widgets/section.py` — animated collapse (currently 188 lines)
This is the clearest motion win. The widget already has `self._expanded`, a clickable `self._header` (with `mousePressEvent` assigned at line 49), a `self._chevron_label`, and a content area.
* In whichever method toggles `self._expanded`, replace the instant show/hide of the content area with `from ui.widgets.motion import animate_height` and animate the content widget's `maximumHeight` between `0` and its `sizeHint().height()`.
* Expand: set `maximumHeight` to 0, call `show()`, then `animate_height(content, content.sizeHint().height())`. On finish, set `maximumHeight` to `16777215` so later relayouts are not clamped — connect to `anim.finished`.
* Collapse: `animate_height(content, 0)`, and connect `anim.finished` to `content.hide()`.
* Duration: let `animate_height` use its `Theme.MOTION_FAST` default. Do not pass an explicit duration.
* **Do not** animate the chevron rotation — it adds a `QPropertyAnimation` on a custom property for negligible gain and `pyqtProperty`/`Property` plumbing this codebase does not currently have. Keep the existing instant chevron swap.
* The header currently does `self._header.mousePressEvent = self._on_header_click` — leave that assignment pattern alone.

### Step 6.4 — `ui/widgets/toast.py` — fade (currently 130 lines)
The toast has `closed = Signal()` and `self.dismiss_timer = QTimer()`.
* On show: `from ui.widgets.motion import fade_in; fade_in(self)`.
* On dismiss: `fade_out(self, hide_on_finish=True)`, and connect the animation's `finished` to the existing close/emit path so `closed` still fires exactly once.
* **Hazard:** if the toast already has a drop shadow via `Theme.shadow_card()`, `fade_in` will return `None` (per the Unit 5 guard) and the toast must still appear. Ensure the show path works whether or not the fade ran — do not make visibility depend on the animation.
* Do not change the dismiss timing or the `closed` signal contract.

### Step 6.5 — `ui/widgets/states.py` (currently 255 lines)
Contains the empty state (`action_clicked = Signal()`) and error state (`retry_clicked = Signal()`).
* Style both through the existing `Theme.empty_state_style(...)` helper. If either currently writes an inline stylesheet with literal values, move those values into `ui/theme/components.py` / `theme.py` and call the helper instead — this reduces the inline-stylesheet count, which is the direction the project wants.
* Add `fade_in` on show for both states.
* Keep both signal names and their emit points exactly as they are; screens connect to them.

### Step 6.6 — Polish pass: `summary_panel.py`, `inline_error.py`, `advance_tax_banner.py`
For each: apply the elevation/radius/hairline scale via existing `Theme.*` helpers, replace any inline stylesheet containing literal colours or radii with the matching `Theme.card_style(...)` / `Theme.banner_style(...)` / `Theme.badge_style(...)` call, and add `fade_in` on show where the widget appears in response to a user action (`inline_error`, `advance_tax_banner`) but **not** where it is part of a static layout (`summary_panel`). No API changes.

### Step 6.7 — `ui/widgets/__init__.py`
Currently:
```python
# ui.widgets package

from .advance_tax_banner import AdvanceTaxBanner

__all__ = ["AdvanceTaxBanner"]
```
Do **not** expand this into a re-export hub. Every other widget is imported by its full module path today (`from ui.widgets.toast import Toast`), and changing that is an out-of-scope refactor across dozens of call sites. The only permitted change is **none** — leave the file as-is. It is listed in this unit solely so you know not to touch it.

### Hazards for Unit 6
* **Every existing call site must keep working.** New widget parameters are keyword-only with defaults. Grep for each widget's constructor before changing its signature: `grep -rn "KPITile(\|MoneyLabel(\|CollapsibleSection(" ui/`.
* **`paintEvent` exception = process abort.** Any new `paintEvent` (the sparkline) must guard every attribute access with `getattr`.
* **`QFont.setFeature` is Qt ≥ 6.7.** `hasattr` guard is mandatory.
* **Opacity vs shadow effect collision** — the Unit 5 `fade_in` guard handles it, but every call site must tolerate a `None` return.
* **Inline-stylesheet budget:** this unit should *reduce* the count of `setStyleSheet()` calls outside `ui/theme/`, never increase it. If an edit would add one, put the style in `ui/theme/components.py` instead.
* Do **not** run pytest.

---

## UNIT 7 — App shell: layout and navigation rework

**Mode:** PARALLEL with Unit 8. Depends on Units 5 and 6.
**Files touched:** 2 (`ui/dashboard_screen.py`, plus QSS additions in `ui/theme/theme.py`)

**Coordination note:** Units 7 and 8 both may touch `ui/theme/theme.py`. To avoid a conflict, **Unit 7 owns all shell/sidebar/topbar QSS rules** and **Unit 8 owns all screen-content QSS rules**. If you are running Unit 7, restrict your `theme.py` edits to selectors named `#sidebar`, `#navLabel`, `#sidebarToggle`, `[nav_item="true"]`, `#topbar`, `#contentArea`, `#pageHeader`. Touch nothing else in that file.

### Current structure (verified — orient yourself here first)
`ui/dashboard_screen.py` (1183 lines) is the `QMainWindow` shell:
* `_NAV_ITEMS` list at line 36 — `(label, icon)` tuples driving the sidebar.
* `_build_ui()` at ~line 119 — `QHBoxLayout` root: `_build_sidebar()` on the left, then a right column of `_build_topbar()` + `_build_content_area()`.
* `_build_sidebar()` at line 144 — a `QWidget` named `"sidebar"`, `setFixedWidth(248 if self.sidebar_expanded else 76)`, holds `self.nav_lbl`, `self._nav_buttons: list[QToolButton]`, and `self._sidebar_toggle_btn`.
* `_make_nav_btn()` at line 230 — builds a `QToolButton` container with `setProperty("nav_item", True)`, an icon `QLabel` and a `nav_label` `QLabel`, with different margins for expanded vs collapsed.
* `_toggle_sidebar()` — flips `self.sidebar_expanded`, persists via `session.is_sidebar_open()`.
* `self.stack = QStackedWidget()` at line 510 — screens are **lazily built** into `self._screen_pages: dict[int, QWidget | None]`, with construction errors captured into `self._screen_errors`.
* `_navigate(index)` at ~line 303 — resolves `screen_key` from `_NAV_ITEMS[index]`, builds the page if needed, sets the stack.
* `_set_nav_active(index)` — applies active styling via `components.sidebar_nav_active()` / `sidebar_nav_normal()`.
* `self.page_title_lbl` updated from `_NAV_ITEMS[index][0]` at line 1001.
* `ThemeManager.register_on_change(self._on_theme_changed)` in `__init__`.

### Step 7.1 — Animate the sidebar expand/collapse
In `_toggle_sidebar()`, the width currently changes instantly via `setFixedWidth`. Replace with:
```python
from ui.widgets.motion import animate_width
```
(at module top, with the other `ui.` imports) and animate between `76` and `248`. Because the widget uses `setFixedWidth`, animate the `minimumWidth` and `maximumWidth` together, or switch to `setMaximumWidth`/`setMinimumWidth` and animate `maximumWidth` — `animate_width` in `ui/widgets/motion.py` handles this; call it and let it own the mechanism.
* The label visibility toggle (`self.nav_lbl.setVisible(...)` and the per-button `nav_label` show/hide) must fire **at the end** of a collapse and **at the start** of an expand, so text never renders in a 76 px-wide sidebar. Connect to `anim.finished` for the collapse case.
* Keep the `session.is_sidebar_open()` persistence exactly as it is.
* Keep `76` and `248` as the two widths — do not retune them.

### Step 7.2 — Cross-fade on screen navigation
In `_navigate(index)`, after `self.stack.setCurrentWidget(page)` (or `setCurrentIndex`), add `fade_in(page)` from `ui.widgets.motion`.
* Use the `Theme.MOTION_BASE` default. Do **not** build a slide transition between stack pages — `QStackedWidget` does not support two pages being visible at once without a custom paint path, and the direction says motion only explains.
* **Critical:** the lazy-build path can raise; `self._screen_errors[index]` exists precisely because a screen constructor can fail. Only call `fade_in` on a successfully built page. If the page is an error placeholder, show it without animation.
* Do not change the lazy-build logic, the error capture, or `_detached_placeholders`.

### Step 7.3 — Nav item hover and active treatment
* Move the nav-item hover state into the QSS (selector `[nav_item="true"]:hover`) using `{t.SIDEBAR_HOVER}`, so it is declarative rather than code-driven. The active state already flows through `components.sidebar_nav_active()` — leave that mechanism alone; just ensure the hover rule exists and does not fight the active rule (active must win; put the active rule after hover in the stylesheet, or scope hover to `:!checked`).
* Add a **2–3 px left accent bar** on the active nav item using a `border-left` in the active style, coloured `{t.SIDEBAR_ACTIVE}`. This is the cheapest high-impact "which screen am I on" affordance and matches the direction's "3px left accent only where the card has a status".

### Step 7.4 — Topbar / page header
* `self.page_title_lbl` at line 433 is set with `QFont("Segoe UI", 15, QFont.Weight.Bold)` inline. Leave the font call (changing it is churn), but ensure the topbar container is styled via the QSS `#topbar` selector using `{t.TOPBAR_BG}` and `{t.TOPBAR_BORDER}`, not inline.
* Add breadcrumb-style secondary text **only if** a secondary context string already exists in the shell's state. **Do not invent new data to display.** If no such state exists, skip this sub-step entirely.

### Step 7.5 — Content-area rhythm
In `_build_content_area()`, set the outer content margins to the spacing scale: `setContentsMargins(24, 24, 24, 24)` and `setSpacing(16)`. Do not change any individual screen's internal layout — that is Unit 8's territory.

### Explicitly OUT of scope for Unit 7
* Do **not** change `_NAV_ITEMS` — not its order, not its labels, not its icons. Reordering navigation changes muscle memory and is not a requested goal.
* Do **not** convert the sidebar to a different widget type (no `QListWidget`, no `QToolBar`).
* Do **not** touch `self.stack`'s lazy-build contract.
* Do **not** edit any file under `ui/dialogs/` or any screen other than `dashboard_screen.py`.

### Hazards for Unit 7
* **`dashboard_screen.py` is 1183 lines and is the app's single point of failure** — if it raises at construction, nothing renders. Make small, surgical edits.
* **Screens are lazily built**, so a constructor error in a screen stays hidden until that screen is visited. Your changes must not make `_navigate` throw before the existing error-capture runs.
* **`ThemeManager.register_on_change(self._on_theme_changed)`** means your new QSS must survive a live theme switch. Do not cache a colour value in Python; read it from `Theme.*` at style-build time, as the existing code does.
* **Width animation + `setFixedWidth` conflict:** `setFixedWidth` pins min and max. If you animate only `maximumWidth`, the pinned `minimumWidth` will prevent the collapse. Handle both bounds.
* Do **not** run pytest.

---

## UNIT 8 — Screen and dialog visual polish

**Mode:** PARALLEL with Unit 7. Depends on Units 5 and 6.
**Files touched:** ~9 screens + 13 dialogs (visual-only edits)

**Coordination note:** see Unit 7's note. Unit 8 owns screen-content QSS in `ui/theme/theme.py`; it must **not** edit the `#sidebar` / `#topbar` / `[nav_item]` / `#contentArea` selectors.

### File list
```
ui/accounts_screen.py
ui/fixed_deposits_screen.py
ui/income_management_screen.py
ui/manage_data_screen.py
ui/settings_screen.py
ui/statement_import_screen_modern.py
ui/tax_documents_screen.py
ui/tax_screen.py
ui/transactions_screen.py
ui/dialogs/*.py   (all 13)
```
(`ui/dashboard_screen.py` is Unit 7's. `ui/login_screen.py`, `ui/setup_screen.py`, `ui/onboarding.py` are pre-auth flows — **leave them alone**; changing the login path risks locking the user out of their own app for zero visual-goal payoff.)

### The four rules to apply, per file, mechanically

**Rule 1 — One primary action per screen.** In each screen, find every `Theme.btn(...)` / `Theme.style_button(...)` call. At most **one** button per screen may use `variant="primary"`. Every other action becomes `"secondary"` (or `"danger"` where it is genuinely destructive). The direction: *"the moment two buttons with different jobs share a colour, colour has stopped being information and become noise."* Pick the primary by asking "what is this screen for?" — Transactions → *Add transaction*; Fixed Deposits → *Add FD*; Statement Import → *Import*; Accounts → *Add account*; Income Management → *Add income source*; Tax → the single compute/save action; Manage Data → *Add* on the active tab; Tax Documents → *Upload*; Settings → *Save*. If a screen genuinely has no single primary, make them all secondary.

**Rule 2 — Per-screen accent.** `ui/theme/theme.py` already has `Theme.screen_accent(screen_key)` (line 188). Use it for each screen's section headings and its one primary button, via the existing `Theme.section_label_style(size, accent_color=...)` helper. **Do not invent new per-screen palettes** — `screen_accent` draws from the theme's chart palette, which is exactly what the direction asks for. If a screen does not currently call `screen_accent`, add the call; do not hardcode a colour.

**Rule 3 — Inline stylesheets and raw hex.** In every file, search for `setStyleSheet(` and for a raw hex pattern (`#` followed by 3 or 6 hex digits inside a string). For each hit:
* If it contains a literal colour → replace the colour with the matching `Theme.TOKEN`.
* If the whole rule duplicates an existing helper (`Theme.card_style`, `Theme.badge_style`, `Theme.banner_style`, `Theme.stat_tile_style`, `Theme.action_bar_style`, `Theme.filter_bar_style`, `Theme.icon_chip_style`, `Theme.empty_state_style`, `Theme.page_header_style`, `Theme.hero_header_style`, `Theme.tinted_surface_style`, `Theme.group_box_style`, `Theme.panel_strip_style`, `Theme.metric_card_style`, `Theme.regime_card_style`, `Theme.info_banner_style`) → call the helper instead.
* If neither applies and the rule is genuinely one-off, leave it — but **never add a new one**.
The net count of inline `setStyleSheet()` calls outside `ui/theme/` must go **down or stay flat**, never up.

**Rule 4 — Scale conformance.** Replace stray literal radii with `Theme.RADIUS_CONTROL/CARD/MODAL/PILL`. Replace stray `setContentsMargins`/`setSpacing` values with the nearest member of {4, 8, 12, 16, 24, 32, 48}. Set input/button `setFixedHeight`/`setMinimumHeight` to the nearest of {28, 36, 44}. Apply `setMaximumWidth` caps to over-wide controls per the direction's control-max-width scale: currency 200, date 160, short select 200, long select 320, text 420.

### Motion in this unit
The **only** motion permitted here is calling `fade_in` from `ui.widgets.motion` when a screen-level panel appears in response to a user action (a results panel after an import, an error banner, an expanded detail card). 
* **Do not** animate table rows, chart draws, money values, or KPI numbers.
* **Do not** add a `QPropertyAnimation` directly in a screen file — always go through `ui/widgets/motion.py`.
* **Do not** animate anything in a dialog's `__init__`/`showEvent` — a dialog that fades in during a modal `exec()` is a flicker risk.

### Dialogs (`ui/dialogs/*.py`) — restricted scope
For the 13 dialogs, apply **only Rule 1, Rule 3 and Rule 4**. Specifically:
* Ensure each dialog has exactly one primary button (the confirm/save action); Cancel is secondary.
* Set the dialog's own corner radius to `Theme.RADIUS_MODAL`.
* Normalise field heights to 36 and apply the control-max-width caps — the direction explicitly calls out that inputs are too wide.
* **Do not restructure any dialog.** In particular: `AccountDialog`'s 31 fields across 5 tabs (Basic Info / Bank Details / Contact / Debit Card / Account Holders) is a **verified good** design per `docs/FRONTEND_REDESIGN_PLAN.json` — do not flatten it.
* **Do not** change any `.exec()` call or any `QDialog.DialogCode.Accepted` comparison.
* **Do not** "fix" dialog modality. `isModal()` returning `False` before `exec()` is expected and is documented as a verified non-issue.

### Explicitly OUT of scope for Unit 8
* No behaviour changes. No data-flow changes. No new computed values. No renames.
* No changes to `ui/widgets/excel_table.py` or `ui/widgets/chart_widget.py` — table and chart internals are out of scope for a visual-polish pass and are high-risk.
* No changes to `ui/login_screen.py`, `ui/setup_screen.py`, `ui/onboarding.py`, `ui/dashboard_screen.py`.
* No terminology changes — `docs/TERMINOLOGY.md` already locks one word per concept and a prior pass (commit `113222b`) applied it.

### Hazards for Unit 8
* **`ui/statement_import_screen_modern.py` is 1855 lines** and was heavily reworked in the two most recent commits (`96cfc2a`, `170dede`: statement import redesign, checkbox/selection sync, dropzone clicks, chart collapse). Its current state is deliberate and recent. Apply **only** Rules 3 and 4 there — do not re-lay-out it, do not touch the drop-zone click handling, the checkbox/selection sync, or the chart collapse. That work is fresh and correct.
* **Screens are lazily constructed**, so any error you introduce will not surface until that screen is opened. Be conservative.
* **`showEvent`/`paintEvent`/`resizeEvent` exception = silent process abort.** If you touch one, guard every attribute with `getattr`.
* **Theme-switch survival:** never cache a `Theme.*` value at class-definition time; read it inside the style-building method, as the existing code does. Screens register `_on_theme_changed` handlers — if you add styling, make sure the refresh path re-applies it.
* **`ui/settings_screen.py` has a live `QThread` warmup** (`self._warmup_thread`, `self._warmup_worker`, lines 836–838) and a `QTimer.singleShot(2200, self._refresh_badges)` at line 508. Do not touch either — visual polish only.
* **Contrast:** any colour pair you touch must stay at 4.5:1 or better. When in doubt, do not change the colour.
* Do **not** run pytest.

---

## OPTIONAL — final launch smoke check

**Mode:** SEQUENTIAL, after Unit 8 (and Unit 7). Optional.

This is the **only** verification step in the entire roadmap, and it is optional. It is not a gate — if it fails, record what failed and stop; do not start fixing bugs, because bug-fixing is a separate future effort.

```
cd D:\Pranav\app
.venv\Scripts\python.exe -m pip uninstall -y PyQt6 PyQt6-Qt6 PyQt6-sip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe main.py
```
Success = the window appears and the login (or setup) screen renders. Close it.

If it does not launch, capture the traceback and report it verbatim. Do not attempt a fix.

**Do not run `pytest` at any point.**

---

## Appendix — consolidated "verified, do not change" list

These were each checked against the real code. An agent that "fixes" one of them is introducing a regression.

| Thing | Status | Action |
|---|---|---|
| Enum access style (`Qt.AlignmentFlag.AlignCenter` etc.) | Already fully-scoped Qt6 form throughout, 0 short-form | **No change** |
| `.exec()` (37 sites) | Already Qt6 spelling | **No change** — never `.exec_()` |
| `QDialog.DialogCode.Accepted` comparisons | Correct in both bindings | **No change** |
| `sip` / `sip.isdeleted` | Does not exist in project code | **Nothing to port** |
| `shiboken6.isValid` | Not needed | **Do not add** |
| `QAction` / `QShortcut` / `QActionGroup` | Not used anywhere | **Nothing to port** |
| `QKeySequence`, `QKeyEvent` | In `QtGui` in both bindings | **Module prefix only** |
| `QVariant` / `.toPython()` | Not used; `UserRole` data is plain `str`/`int` | **No change** |
| Mouse position accessors (`.pos()`, `.globalPos()`) | Zero handlers read the event position | **Nothing to port** |
| `QFontMetrics` (2 sites) | No use of the removed `.width()` | **No change** |
| `QTimer.singleShot(ms, fn)` (4 sites) | Identical signature | **No change** |
| `qRegisterMetaType` | All cross-thread payloads are `str`/`object` | **Do not add** |
| `QFont(family, size, QFont.Weight.Bold)` | Identical | **No change** |
| `pyqtSlot` / `pyqtProperty` | Zero occurrences | **Nothing to port** |
| Dialog modality (`isModal()` False before `exec()`) | Documented verified non-issue | **Do not "fix"** |
| `AccountDialog` 5-tab layout | Documented verified good | **Do not flatten** |
| `ui/widgets/loader.py` hand-rolled fade | Paints its own scrim; effect-based fade would change behaviour | **Leave as-is** |
| `matplotlib` qt5agg/agg fallback chain in `chart_widget.py` | Harmless defence | **Keep** |
| `ui/widgets/__init__.py` minimal export | Expanding it is an out-of-scope refactor | **Leave as-is** |
| `_NAV_ITEMS` order/labels/icons | Reordering navigation is not a requested goal | **Do not change** |

---

## Final report — unit summary

| # | Unit name | Mode | Depends on | Files |
|---|---|---|---|---|
| 1 | Binding selection, dependencies and entry point | **SEQUENTIAL** (first) | — | 3 |
| 2 | Mechanical port: `ui/` core screens | **PARALLEL** (with 3, 4) | 1 | 30 |
| 3 | Mechanical port: `ui/theme/` and `ui/widgets/` | **PARALLEL** (with 2, 4) | 1 | 19 |
| 4 | Mechanical port: `tests/` and `tools/` | **PARALLEL** (with 2, 3) | 1 | ~17 |
| 5 | Theme tokens, QSS polish, shared motion helper | **SEQUENTIAL** | 2, 3, 4 | 8 (1 new: `ui/widgets/motion.py`) |
| 6 | Shared widget library upgrade | **SEQUENTIAL** | 5 | 9 |
| 7 | App shell: layout and navigation rework | **PARALLEL** (with 8) | 5, 6 | 2 |
| 8 | Screen and dialog visual polish | **PARALLEL** (with 7) | 5, 6 | ~22 |
| — | Optional launch smoke check | SEQUENTIAL, optional | 7, 8 | 0 |

**8 units.** Two fan-out points: {2, 3, 4} and {7, 8}. Exactly one new file across the whole roadmap (`ui/widgets/motion.py`). Zero test gates; one optional launch check at the end.
