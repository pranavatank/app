# Visual UI Testing Guide — read this before touching UI code again

**Audience:** an AI agent (or human) picking up this project with zero prior context.
**Purpose:** explain what real visual testing tooling exists, why it exists, exactly
what it caught, and what to do next. You should be able to act on this document
alone, without re-reading the rest of the conversation history that produced it.

---

## 1. The problem this solves

Every round of "I verified this works" earlier in this project's redesign used
`QTest.mouseClick()` / `QTest.keyClick()` under `QT_QPA_PLATFORM=offscreen`. That
approach **injects events directly into Qt's internal event queue** — it never
touches the real OS input pipeline (no real mouse, no real window manager, no real
screen). It is fine for pure logic checks (does this function get called, does this
value change), but for anything about **whether a human can actually click it**, it
produces false confidence: code appeared fully correct in dozens of offscreen QTest
runs across this project's redesign, while the user, testing the same features by
hand on a real Windows desktop, kept reporting **the exact same "buttons don't work
/ nothing is clickable" issues** after every round of fixes.

The gap between those two experiences turned out to be real and reproducible — see
§3. This guide is the result of instrumenting real, visible, mouse-and-keyboard-driven
testing to find out why, and it uncovered genuine, confirmed bugs in the testing
approach itself (not necessarily all in the app — see §4 for what's still unknown).

---

## 2. What was installed, and why

All installed into the project's `.venv` (already done — nothing further to install
unless the venv is recreated):

| Package | Why |
|---|---|
| `pyautogui` | Sends **real OS-level** mouse moves/clicks and keyboard input, indistinguishable (to the OS) from a human using the mouse/keyboard. Also provides `pyautogui.screenshot()` for a real screen capture. |
| `pywin32` | Provides `win32gui` / `win32con`. This is the **only** thing that reliably forces a script-launched window into genuine Windows foreground focus (see §3.3) — Qt's own `activateWindow()` is not enough. |
| `pygetwindow` | Lightweight window enumeration; installed as a simpler alternative for basic cases. `pywin32` is what's actually used in the harness below because it's the only one that solved the focus problem. |
| `mss` | Fast screenshot library; installed as an alternative to `pyautogui.screenshot()`. Not currently used by the harness (pyautogui's screenshot works fine) but available if performance ever matters. |

Install command, if the venv is ever rebuilt:
```
.venv/Scripts/python -m pip install pyautogui pygetwindow pywin32 mss
```

**The reusable harness is `tools/real_ui_test_harness.py`.** It wraps every gotcha
below into one `RealUIHarness` class so you don't rediscover them one at a time.
Read that file's docstrings — each helper explains the specific failure it exists to
prevent. Minimal usage:

```python
import os
os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
# Do NOT set QT_QPA_PLATFORM=offscreen here — the whole point is a REAL window.
import sys; sys.path.insert(0, r"D:\Pranav\app")

from tools.real_ui_test_harness import RealUIHarness
from ui.dashboard_screen import DashboardScreen
from ui.theme.theme_manager import ThemeManager

ThemeManager.apply("Aurora", save=False, notify=False)
harness = RealUIHarness(screenshot_dir=r"C:\path\to\somewhere")
dashboard = harness.launch(lambda: DashboardScreen(), maximized=True)  # see §3.2 on why maximized
harness.shot("00_overview")

settings_btn = dashboard._nav_buttons[8]
harness.click(settings_btn)
harness.shot("01_settings")
print(dashboard.page_title_lbl.text())   # cross-check widget state, not just the pixel
```

**Always launch maximized** (the harness default) unless you have a specific reason
not to — see §3.2 for why a fixed size is risky.

---

## 3. Confirmed findings — what real testing caught that offscreen QTest missed

These were each independently reproduced with root-cause certainty (not
guessed) during this session. Every one of them is a real trap that will bite again
if `tools/real_ui_test_harness.py` isn't used, or if its lessons aren't followed in a
hand-rolled script.

### 3.1 DPI-scaling coordinate mismatch (confirmed, severe)

This dev machine runs Windows display scaling at **125%**
(`QApplication.primaryScreen().devicePixelRatio() == 1.25`). Qt widget geometry
(`mapToGlobal()`, `.rect()`, `.resize()`, `.move()`) is **always in logical pixels**.
`pyautogui` is **always in physical screen pixels**. Passing a raw Qt coordinate to
`pyautogui.moveTo()`/`.click()` without correction lands the click at **80% of the
intended distance from the origin** — consistently up-and-to-the-left of the real
target, by an amount proportional to distance from (0,0).

**Symptom observed:** clicking the Settings sidebar button did *nothing visible* —
no navigation, no highlight change — because the real click landed on empty sidebar
space, not the button.

**Fix:** multiply every Qt-derived coordinate by `devicePixelRatio` before handing it
to pyautogui. `RealUIHarness.to_physical()` does this; use it for anything not going
through `harness.click()`.

**Why this matters beyond testing:** if the *real app* has any layout that assumes
1:1 logical-to-physical mapping (custom painting, manually-computed geometry,
anything that reads raw screen coordinates), it would misbehave identically for a
real user on a 125%-scaled display — which is a common laptop configuration, not an
edge case. **Nobody has audited the app itself for DPI-scaling correctness.** That's
a real, open, unstarted item — see §5.

### 3.2 Window geometry can silently extend past the physical screen (confirmed)

A window requested at logical `resize(1600, 900)` positioned at logical `move(50, 50)`
becomes **physically** `2000×1125` at `(62, 62)` under 125% scaling. On a
1920×1080 physical screen, the bottom ~45 physical pixels of that window — and
everything painted there — are off-screen. Qt still returns a perfectly valid
`mapToGlobal()` coordinate for a button in that clipped region; nothing errors.
A click sent there just lands off-screen or on whatever's behind the window, with
zero feedback that anything went wrong.

**Symptom observed:** the Settings screen's "Manage People" button, positioned
correctly according to Qt, was documented as un-clickable because the window itself
didn't fit the screen at the fixed size+position first used for testing.

**Fix:** launch maximized (`showMaximized()`) instead of a fixed `resize`/`move`.
This is now the harness default. If a fixed size is ever genuinely needed, verify
`(position + size) * dpr` stays inside `QApplication.primaryScreen().geometry()`
before trusting anything inside it.

### 3.3 Windows blocks script-launched windows from real foreground focus (confirmed)

Qt's own `widget.activateWindow()` / `.raise_()` frequently do **not** give a
script-launched window genuine OS input focus — Windows' focus-stealing prevention
silently keeps some other window (e.g. the terminal that launched the script)
foregrounded for input purposes, even though the target window is visibly drawn on
top. A click sent via pyautogui in that state is delivered to the OS's actual
foreground window, not the one on top visually. No exception, no error — the click
just does nothing, indistinguishable from "the button doesn't work."

**Fix:** give the window a unique, searchable title, then force it with `pywin32`:
```python
hwnd = win32gui.FindWindow(None, "UNIQUE_TITLE")
win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
win32gui.SetForegroundWindow(hwnd)
win32gui.BringWindowToTop(hwnd)
```
`RealUIHarness.launch()` does this and prints a warning if it still fails to
actually take foreground focus (`win32gui.GetForegroundWindow() != hwnd`) — **always
check that warning**, don't assume it worked silently.

### 3.4 Widgets inside a QScrollArea need explicit scrolling before clicking (confirmed)

`mapToGlobal()` returns *a* coordinate for a widget even when it's scrolled
completely out of view — Qt doesn't refuse just because it's not currently visible.
Clicking that coordinate hits whatever **is** actually visible there (often a
completely different control), silently.

**Symptom observed:** exactly the "Manage People" button case above, compounded
with §3.2 — after fixing the window size, the button was still below the visible
scroll position of the Settings page's content area.

**Fix:** `RealUIHarness.click()` walks up the widget's parent chain looking for a
`QScrollArea` and calls `ensureWidgetVisible()` first, automatically. If you bypass
the harness, do this yourself before computing any click target.

### 3.5 Manual `processEvents()` polling lags real repaint (confirmed, likely test-only)

After an action that changes visible state (e.g. sidebar navigation), the widget's
**internal Qt state** (`label.text()`, `.isChecked()`) updates immediately and
correctly. The **actual pixels presented to the Windows compositor** can lag behind
that by up to ~1-2 seconds when the event loop is driven by a script calling
`app.processEvents()` a few times, rather than a real, continuous `app.exec()` loop.
A screenshot taken immediately after a click showed the **previous** screen's pixels
even though `dashboard.page_title_lbl.text()` queried at the same instant already
correctly returned the new value.

**This is very likely an artifact of driving Qt from a script**, not something the
real app exhibits to a real user (since `main.py` runs a genuine, continuous
`app.exec()` loop, which processes paint/present events far more promptly than
sporadic manual polling does). But it means: **a screenshot alone, taken too early,
is not trustworthy evidence of a bug.**

**Fix:** always pump for a real 1-2 seconds after any interaction before treating a
screenshot as ground truth (`RealUIHarness.settle()`, used automatically after
`click()`/`double_click()`), and **always cross-check a screenshot against direct
widget-state introspection** (label text, `.isChecked()`, a DB query) — trust
neither one alone.

### 3.6 `QTest.mouseDClick` does not reliably fire `doubleClicked` at all (confirmed)

Connecting a bare `lambda idx: fired.update(flag=True)` directly to a table's
`doubleClicked` signal — with **zero application logic involved** — and then firing
`QTest.mouseDClick()` at the correct widget/position never triggered it, under
**both** `offscreen` and the real Windows platform. This is a limitation of how
`QTest` synthesizes double-click timing, not an app bug.

**Practical consequence:** any prior "verified" double-click-to-edit behavior in
this codebase's test suite that used `QTest.mouseDClick` was not actually testing
what it claimed to. `pyautogui.doubleClick()` (a genuine OS double-click) is the only
method that's been tested and found credible for this so far — but even that hasn't
been fully re-verified across every double-click interaction in the app; see §5.

**Fix / fallback:** `RealUIHarness.double_click()` uses `pyautogui.doubleClick()`. If
a specific double-click-to-edit interaction still needs verifying and this remains
ambiguous, cross-check with the keyboard-equivalent path (e.g. select the row, press
Enter) if the code is known to treat them the same way — and say explicitly in your
findings that double-click itself is unconfirmed, rather than reporting it as
verified.

---

## 4. What is still unknown — do not assume these are fixed or broken

Real testing this session got as far as: launch app → navigate to Settings → open
"Manage People". It has **not yet** covered:

- Person/Bank/Account creation dialogs (add/edit/save flows) — never reached via real
  clicks yet.
- Statement Import's new card-based flow (person card → account card → format →
  drop/browse → parse → preview → import) — only verified via headless QTest and
  direct method calls in prior rounds, **never with real OS clicks**.
- Fixed Deposits table interactions (cell click/select, checkbox, Enter/double-click
  to edit, Delete Selected) — same: verified via QTest and direct calls, **not real
  clicks** (§3.6 means the double-click path specifically is unconfirmed).
- Tax Documents' three drop zones with real 26AS/AIS/TIS files, clicked for real.
- Every button's actual on-screen size versus the design system's stated scale
  (`control_height_px`: sm 28 / md 36 / lg 44; `control_max_width_px` per role; no
  button should exceed 280px) — **never measured on a real render**, only asserted
  in code.
- Sidebar in both expanded and collapsed states, and the nav icon/label spacing fix,
  under real rendering.
- Any of the 4 themes other than Aurora, under real rendering.
- Whether the DPI-scaling questions in §3.1 point to an actual **app** bug (not just
  a testing-harness bug) — e.g. does any part of the app do manual pixel-coordinate
  math that would misbehave under Windows scaling ≠ 100%? Not yet audited.

**Do not report any of the above as "working" or "broken" without actually running
it through `RealUIHarness` and checking both a screenshot and the underlying widget
state, per §3.5.**

---

## 5. The audit plan — what to actually do next

Work through this list **using `tools/real_ui_test_harness.py`**, one item at a
time. For each item: take a screenshot, cross-check widget/DB state, and write down
exactly what's wrong (not "seems fine" — describe pixel positions, exact button
labels, exact sizes if measurable) directly into a findings section you append to
the bottom of this file (or a new dated file in `docs/` if this one gets long) so the
next person/agent inherits real, dated findings instead of re-discovering them.

**Setup, once, at the start of any real-testing session:**
1. Confirm `devicePixelRatio` on the current machine (it may not be 1.25 on a
   different machine — never hard-code 1.25, always read it live).
2. Launch via `RealUIHarness(...).launch(..., maximized=True)`.
3. Confirm the harness's foreground-focus warning did **not** print. If it did, stop
   and fix that before trusting any click result.

**Screen-by-screen checklist (repeat for each of the 9 screens):**
1. Navigate to the screen via a real sidebar click. Screenshot. Confirm the title
   label and visible content actually match (§3.5 — check both).
2. For every visible button: is it enabled/disabled as expected for the current
   state? Hover/click it for real — does the expected thing happen (dialog opens,
   state changes, nothing crashes)? Measure its rendered height/width in the
   screenshot against the design system's scale (see `docs/FRONTEND_REDESIGN_PLAN.json`
   → `design_direction.scales_to_enforce` for the authoritative numbers) — flag any
   button that visually looks bigger/smaller than sm=28/md=36/lg=44 or wider than
   280px.
3. For every visible table (ExcelTable-based): click a data cell for real (does it
   select?), click a checkbox cell for real (does it toggle, does the row highlight
   sync per the fix already made this session?), select a row and press Enter for
   real (does the edit dialog open?), try a real double-click too and note if it
   differs from Enter's behavior (§3.6), check a checkbox and click "Delete
   Selected"/equivalent for real (does the right record actually leave the
   database? — query the DB directly, don't trust the UI alone).
4. For every dialog reachable from the screen: open it for real, check every field
   is reachable/fillable, check Cancel and the primary action both do what they say.
5. Scroll the whole screen if it's taller than one viewport (§3.4) — is anything
   below the fold that a user might not realize needs scrolling? Note it even if it
   technically "works" once scrolled to.
6. Repeat steps 1-5 for at least one more theme (pick a dark one, e.g. "Nova") to
   catch theme-specific contrast/sizing issues real rendering can reveal that
   offscreen captures might not.

**Specific flows to run end-to-end for real** (per the owner's explicit request):
1. Settings → Manage People → Add Person (real name) → Save → confirm it appears in
   the list → confirm it now appears as a person card on Statement Import.
2. Settings → Manage Bank → Add Bank (use a real bank name from
   `docs/AUDIT_AND_REBUILD_PLAN.md` §3 — Jana, Equitas, IDFC, or Ujjivan) → Save.
3. Accounts → Add Account, linking the new person + new bank → Save → confirm it
   shows up as an account card on Statement Import for that person.
4. Statement Import: select the new person card → select the new account card →
   select PDF format → browse to a real file (`data/PersonalData/Pranav/Statement/
   Jana - Pranav.pdf` or similar — see that same audit doc §"how to use") → Parse →
   confirm the preview table populates → Import → confirm the transactions actually
   land in the database for that account.
5. Tax Documents: click each of the three real drop zones
   (`data/PersonalData/Pranav/26AS.pdf`, `AIS.pdf`, `TIS.pdf`) for real, confirm each
   parses without the app hanging/crashing, confirm the reconciliation view
   populates.

Append findings below this line as you go, dated, one entry per issue, specific
enough that someone could fix it without re-running your test:

---

## Findings log

*(append new dated entries below — do not delete prior ones)*

### 2026-09-12 — initial real-testing session (this document's origin)

- Confirmed working via real click: sidebar navigation to Settings (§3, after fixing
  the DPI/geometry/focus issues above).
- Confirmed NOT working before the fix, now understood as a test-harness bug, not an
  app bug: clicking the Settings sidebar button appeared to do nothing (§3.1, §3.2).
- Session ended here due to token constraints before reaching the person/bank/
  account/statement-import flow the owner asked to be tested. **Next session should
  resume directly at the "Specific flows to run end-to-end for real" list above,
  step 1 (Add Person).**

### 2026-09-12 — harness rebuilt: pyautogui coordinate-clicking replaced (§3.7, §3.8)

Continuing the resume point above (Add Person flow) surfaced two more real,
reproducible bugs in the **harness itself** — not the app — severe enough that the
harness's default interaction method changed. `tools/real_ui_test_harness.py` and
`tools/real_ui_tests/test_add_person_flow.py` (a new, permanent, self-cleaning
end-to-end test — see §6) are both in the repo now; read the harness's module
docstring for the full design rationale, summarized here:

#### 3.7 Blind-coordinate OS clicks misclick (confirmed, severe)

Driving the UI purely via `pyautogui` coordinates (`widget.mapToGlobal(widget.rect()
.center())` → physical pixels → `pyautogui.click()`) produced a real, reproducible
misclick: a click intended for the "Add Person" button instead landed on the
Manage Data dialog's own close (X) button, closing the whole dialog instead of
opening a new one. There is no error, no exception — the coordinate is just wrong
by the time the click lands, because it was computed once and trusted blindly, with
no way to confirm what was actually under the cursor at click time. Separately,
`win32gui.SetForegroundWindow` was observed to sometimes raise
`pywintypes.error: (0, 'SetForegroundWindow', 'No error message is available')`
outright (Windows' focus-stealing prevention refusing the call, not just silently
ignoring it) — worse than the "no error, click just does nothing" case §3.3
originally documented.

**Fix — the harness's default interaction method changed.** Since this app runs
in-process with the test script (never offscreen, always a real visible window),
there is a strictly more reliable option than OS-level coordinates: find the
target widget by its accessible name (this codebase already calls
`setAccessibleName()` on essentially every interactive control) and drive it via
`QTest.mouseClick()`/`keyClicks()` **on the widget object directly**. This still
goes through Qt's real event loop and produces a real repaint — it only skips the
OS input queue, which is exactly the layer where DPI math and focus-stealing
prevention live. `harness.click(root, "Accessible Name")` and
`harness.type_into(root, "Accessible Name", text)` are now the default, primary
API. The old OS-coordinate path still exists as an explicit opt-in escape hatch —
`harness.click_via_os(widget)` / `harness.type_text_via_os(text)` — for the rare
case for you specifically need to prove genuine OS input delivery (e.g. a
focus-stealing-sensitive modal). `harness.find_via_uia()` (via `pywinauto`, now a
project dependency) is available as an independent cross-check that a control is
genuinely reachable through Windows UI Automation, not just present in Qt's own
object tree.

**Why this matters beyond testing:** none of this is an app bug — `setAccessibleName()`
calls throughout `ui/` are exactly what made the fix possible. No app code changed.

#### 3.8 A modal `dlg.exec()` call blocks `QTest.mouseClick()` itself (confirmed)

After switching to `QTest.mouseClick()`, clicking "Add Person" appeared to silently
do nothing — the dialog never showed up in `QApplication.allWidgets()` even after
polling. Root cause: `ManageDataScreen._on_add_person()` does
`dlg = PersonDialog(self); dlg.exec()` — a **blocking** modal call. `QTest
.mouseClick()` delivers the click synchronously, and the slot it triggers
(`_on_add_person`) runs to completion inside that same delivery — including the
nested event loop `exec()` spins up. That nested loop only returns when the dialog
is closed, and nothing was closing it, so the click call itself was still on the
stack, waiting, the entire time the test script thought it had "returned."

**Fix:** schedule the fill-in-fields-and-click-Save steps with
`QTimer.singleShot(0, callback)` **before** clicking the button that opens the
modal dialog, not after. The scheduled callback fires once `exec()`'s nested loop
is already spinning, and `harness.settle()` (which pumps `app.processEvents()` in a
loop) is what actually drives that nested loop forward, letting the callback run,
fill the form, click Save, and let `exec()` return. See
`tools/real_ui_tests/test_add_person_flow.py` for the concrete pattern — any test
that needs to interact with a **modal** (`.exec()`-opened) dialog must use this
`QTimer.singleShot` pattern, not a plain sequential click-then-interact script.

**This is a real, general gotcha for testing this codebase specifically**, since
`manage_data_screen.py` and other dialogs (`PersonDialog`, `BankDialog`,
`AccountDialog`) are all opened via blocking `.exec()` calls, not non-modal
`.show()`. It is not an app bug — blocking modal dialogs are completely normal,
correct Qt usage — it only matters for how a test script must be structured.

### 2026-09-12 — Add Person end-to-end flow: PASSED

Running `tools/real_ui_tests/test_add_person_flow.py` after the §3.7/§3.8 fixes,
fully automated start to finish (real on-screen window, real `QTest`-driven
clicks/typing, no OS coordinates), all checks passed:

- Settings page title updates correctly on real sidebar navigation.
- "Manage People" button opens the Manage Data dialog.
- "Add Person" button opens the Add Person modal (confirmed via the
  `QTimer.singleShot` pattern above).
- Typed nickname is held correctly by the QLineEdit.
- Save closes the dialog.
- The new person is present in the database immediately after Save.
- The new person is present in the visible People table with **no manual
  refresh needed** — `ManageDataScreen._load_people()` is called correctly after
  `add_person()`.

The test cleans up its own test person record after every run (success or
failure), so it can be re-run freely without accumulating junk data. It does
**not** yet cover Add Bank / Add Account / Statement Import / Tax Documents —
those remain open per §4/§5; the pattern established here (accessible-name lookup,
`QTimer.singleShot` for modals) should carry over directly.

---

## 6. Adding a new real-click test

Follow `tools/real_ui_tests/test_add_person_flow.py` as the template:

1. Put new test scripts under `tools/real_ui_tests/`, one file per flow.
2. Use `harness.click(root, "Accessible Name")` / `harness.type_into(...)` as the
   default — never hand-roll coordinate math.
3. If the flow opens a **modal** dialog (anything opened via `.exec()`, not
   `.show()`), use the `QTimer.singleShot(0, callback)` pattern from §3.8 — do not
   click-then-immediately-look-for-the-dialog in a straight line.
4. If the flow creates any database row, delete it in a `finally`-equivalent
   cleanup path (see `report()` in the template) so repeated runs never pollute
   real data — this project's database is not a disposable test fixture.
5. Cross-check both a screenshot AND direct widget/DB state per §3.5 — never
   trust a screenshot alone.
