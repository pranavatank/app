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

### 2026-09-18 — post-PySide6-migration triage: harness OK, one real bug found

Context: the app was migrated PyQt6 -> PySide6 and given a UI pass (motion
tokens, `ui/widgets/motion.py`, animated sidebar, toast fades) immediately
before this session.

**Harness status: WORKING, no repair needed.** `tools/real_ui_tests/test_add_person_flow.py`
was run unchanged under PySide6 and passed every check end to end (real visible
window, real QTest-driven clicks, screenshots, DB verification, self-cleanup).
`PySide6.QtTest.QTest` is a drop-in for the PyQt6 one for everything this
harness uses. Accessible-name lookup, the `QTimer.singleShot` modal pattern and
the DB cross-checks all carry over unchanged.

**BUG FOUND AND FIXED (app bug, introduced by the UI pass, now reverted):
navigation left the incoming page at opacity 0.**
`DashboardScreen._navigate()` had been given a `fade_in(screen)` call.
`motion.fade_in()` installs a `QGraphicsOpacityEffect` and sets it to 0.0
before animating to 1.0. Under a real continuous `app.exec()` loop the fade
completed correctly (measured: 0.0 immediately after the call, 1.0 after 1.5s).
Under a script-driven loop it did **not** — `processEvents()` returns instantly,
so almost no wall-clock time passes, the 180ms animation barely advances, and
the page stayed at **opacity 0.0**: laid out, `isVisible()` True, `page_title_lbl`
already reading "Settings", and painting nothing. The screenshot showed the
*previous* screen's pixels.

This is the §3.5 repaint-lag trap with a genuine app bug underneath it — worth
noting because §3.5 would have led you to dismiss the screenshot as a test
artifact. It was not. `_on_refresh_all()` runs on the line right after the fade
and can block on DB work, so a real user could hit the same blank screen.

Disambiguation method (reusable): after navigating, read
`stack.currentIndex()`, `type(stack.currentWidget()).__name__`,
`currentWidget().isVisible()`, **and** `currentWidget().graphicsEffect().opacity()`
alongside the screenshot. The opacity read is what separates "compositor lag"
from "actually transparent". Setting `ui.widgets.motion.ENABLED = False` removes
the effect entirely and is a clean bisect switch.

Fix applied (commit 369e5e2): the page fade is removed from `_navigate()` —
a transition that can leave a screen blank is not worth it. `motion.fade_in()`
now also snaps to 1.0 on `finished`, and `motion._start()` snaps an interrupted
animation to its end value before stopping it, so rapid re-triggering cannot
strand a widget at a partial value. The sidebar width animation is unaffected.

**Confirmed NOT a bug:** the collapsed icons-only sidebar seen in screenshots is
persisted session state (`ui/dashboard_screen.py:149` reads
`session.is_sidebar_open()`), not a rendering regression.

**Still open** — everything in §4 and §5 other than Add Person remains untested
with real clicks. The campaign roadmap for that work is
`docs/UI_TEST_CAMPAIGN_PLAN.md`.

### 2026-09-18 — Unit 2: DPI-Scaling Code Audit

**Ran:** code audit only — no window opened.

**Result:** 3 findings were originally reported. **Two were later verified as FALSE
POSITIVES and one was downgraded** — see the "VERIFICATION" note under each. The
audit was code-reading only, with no measurements; the corrections below were made
by running the actual APIs at dpr=1.25 on this machine. Treat the SAFE list at the
bottom as still-useful, but treat any unmeasured DPI claim with suspicion.

#### FINDING 2.1 — Login/Setup screens centered off-screen at 125% DPI [CONFIRMED-RISK]
- **What I did:** Code reading audit of screen-geometry mixing patterns.
- **Expected:** Window centering logic should account for DPI when mixing physical screen geometry with logical window coordinates.
- **Observed (mechanism):** `ui/login_screen.py:278-283` and `ui/setup_screen.py:194-199` both call `QGuiApplication.primaryScreen().geometry()` which returns **physical** pixels on Windows, then compute a center point, and pass it to `self.move()` which expects **logical** pixels. At 125% DPI, logical and physical are 1:1.25 — the window's intended center (computed in physical) is 1.25× further from origin than the code intended in logical coordinates.
- **Concrete scenario:** On a 1920×1080 physical screen (1536×864 logical at 125%), the window computed to center at logical pixel (768, 432) would render centered. The code instead computes physical center (960, 540), passes that directly to `move()`, resulting in the window positioned at logical (960, 540) — **off-center by ~192 logical pixels right and ~108 down**, and partially clipped at the right and bottom edges of the viewport.
- **Severity:** major (affects first-run experience and login, every launch).
- **NOT FIXED** (per campaign rule).
- **VERIFICATION 2026-09-18 — THIS IS A FALSE POSITIVE. Do not act on it.**
  The premise is wrong: `QGuiApplication.primaryScreen().geometry()` returns
  **logical** pixels, not physical. Measured live on this machine at dpr=1.25:
  `geometry()` returns `QRect(0, 0, 1536, 864)` — i.e. the 1920x1080 physical
  screen already divided by 1.25. `frameGeometry()` and `move()` are logical too,
  so the centering math is consistently in one coordinate space. Reproducing the
  exact `_center_on_screen()` sequence with a 560x650 window put it at (488, 92),
  fully inside the screen bounds. **The code is the standard, correct Qt centering
  idiom.** No bug.

#### FINDING 2.2 — Checkbox indicator pixmap created without DPI compensation [CONFIRMED-RISK]
- **What I did:** Code reading of custom painting and pixmap generation.
- **Expected:** QPixmap assets used in UI should be scaled for the device's pixel ratio to render crisp on HiDPI displays.
- **Observed (mechanism):** `ui/theme/checkbox_asset.py:36-37` creates a QPixmap with `QPixmap(size, size)` where `size = 14` (hardcoded) **without calling `setDevicePixelRatio()`**. At 125% DPI, this 14×14-pixel bitmap is rendered by Qt at its true logical size (14 logical × 1.25 = 17.5 physical pixels rendered), but the bitmap was never scaled to fit that density — it renders blurry / half-size, exactly the classic HiDPI pixmap bug. The checkmark glyph drawn inside is rendered at 14 logical pixels but should be rendered at 18-20 logical to account for the 1.25 scaling.
- **Concrete scenario:** A checked checkbox indicator on a 125%-scaled Windows display would show a checkmark that is noticeably smaller and blurrier than the unchecked indicator (which is an SVG/styled border, not a pixmap).
- **Severity:** ~~major~~ **downgraded to MINOR** — see verification.
- **NOT FIXED** (per campaign rule).
- **VERIFICATION 2026-09-18 — REAL, but milder than described.**
  Measured: the generated PNG is 14x14 with `devicePixelRatio == 1.0`. The QSS
  indicator is 18x18 logical = 22.5 physical at dpr 1.25, so a 14-physical-pixel
  source bitmap is upscaled into it. That does cause mild softness. It does NOT
  render "half-size" — Qt scales the image to the styled box, it does not draw it
  at 1:1 and leave it small. Fix, when someone gets to it: generate the pixmap at
  `14 * devicePixelRatio()` and call `pm.setDevicePixelRatio(dpr)` before saving,
  or ship an SVG. Low priority, cosmetic only.

#### FINDING 2.3 — Icon scale factor computed without considering devicePixelRatio [SUSPECT]
- **What I did:** Code reading of icon rendering pipeline.
- **Expected:** Icon rendering should account for the screen's `devicePixelRatio()` to scale icons correctly at non-1.0 DPI.
- **Observed (mechanism):** `ui/icons.py:206` computes `opts: dict = {"scale_factor": max(size / 16, 1.0)}` to control qtawesome's icon rendering. This divides the desired pixel size by a hardcoded baseline (16) to compute a relative scale. **This does not account for `devicePixelRatio()`**, so on a 125% display, the computed scale is 25% too small. At size=24, this produces `scale_factor=1.5`, but on a 125% display it should be `scale_factor=1.875` to maintain the intended visual size. The resulting icons render smaller than intended on HiDPI.
- **Concrete scenario:** At 125% DPI, requesting a 24-pixel icon (e.g. in `ui/settings_screen.py:332` or `ui/dashboard_screen.py:268`) would render at ~19 logical pixels instead of 24.
- **Severity:** ~~minor to major~~ **none — false positive.**
- **NOT FIXED** (per campaign rule).
- **VERIFICATION 2026-09-18 — THIS IS A FALSE POSITIVE. Do not act on it.**
  Two errors in the reasoning. First, `QIcon` is resolution-independent: Qt asks
  it for a pixmap at the device's real pixel size at paint time, so icon sharpness
  at 125% is handled by Qt, not by this call site. Second, qtawesome's
  `scale_factor` scales the **glyph within its box**, it is not a pixel-size
  parameter, so multiplying it by dpr would make icons render *larger than the
  space allotted*, not more correct. Icons were confirmed rendering non-null and
  correctly sized in the real-window runs. No bug.

#### SAFE — audited and clear

The following files and patterns were read and confirmed safe (use only logical pixel coordinates, or do not depend on screen geometry):

- `ui/dashboard_screen.py` — All `.setFixedWidth()`, `.setFixedHeight()`, `.setFixedSize()` calls use design-system constants (e.g. 248, 76, 40, 44), **not** screen-derived values. Widget layout is pure logical geometry.
- `ui/widgets/loader.py:175, 267` — `.setGeometry(parent.rect())` operates on widget-local coordinates (parent's rect in parent's space), not screen coordinates. Safe.
- `ui/widgets/toast_utils.py:29` — `.setGeometry(content_area.rect())` uses content area's own rect (logical widget coords), not screen geometry. Safe.
- `ui/widgets/motion.py:116, 125` — `.setFixedWidth(target)` uses design constants. Safe.
- `ui/widgets/section.py:60` — `.setFixedSize(20, 20)` is a design constant (chevron icon size). Safe.
- `ui/kpi_tile.py:49, 97` — `.setFixedHeight(105)`, `.setFixedHeight(30)` are design constants. The sparkline painting (`paintEvent`, line 212) uses logical widget coordinates for layout (`self.width()`, `self.height()`, relative positioning) and hardcoded logical sizes (`int(x) - 2, int(y) - 2, 4, 4` for the dot). All logical, handled by Qt. Safe.
- `ui/widgets/toast.py:56` — `.setFixedSize(28, 28)` is a design constant. Safe.
- `ui/logo.py:27` — `pixmap.scaled(size, size, ...)` scales a loaded image to a requested logical size; Qt handles DPI for the result since the source pixmap's DPI is unspecified (defaults to 1.0). Borderline, but safe in practice since the result is displayed via `QLabel.setPixmap()` which Qt composites at the correct logical size.
- `ui/settings_screen.py:330` — `.setFixedSize(32, 32)` is a design constant. Safe.
- `ui/advance_tax_banner.py:33, 60` — `.setFixedSize(28, 28)` and `.setFixedSize(28, 28)` are design constants. Safe.
- `ui/statement_import_screen_modern.py:602, 614` — `.setFixedSize(26, 26)` and `.setFixedSize(24, 2)` are design constants. Safe.
- `ui/dialogs/account_metadata_dialog.py:178` — `.setFixedHeight(1)` is a divider line (design constant). Safe.
- `ui/summary_panel.py:66, 83, 193` — `.setFixedSize(38, 38)`, `.setFixedHeight(1)`, `.setFixedHeight(1)` are design constants for icon backgrounds and dividers. Safe.
- `main.py` and `config.py` — No explicit High DPI policy attributes set (`AA_EnableHighDpiScaling`, `AA_UseHighDpiPixmaps`, `HighDpiScaleFactorRoundingPolicy`). Qt6 defaults to high-DPI scaling enabled with `HighDpiScaleFactorRoundingPolicy.Round` (rounds factors like 1.25 to 1.0 for integer-aligned layouts). **Note:** At exactly 125%, the rounding policy is critical — `Round` will produce a ~1-pixel layout shift at borders compared to `PassThrough`. Current app relies on Qt defaults; this is a design trade-off, not a bug.
- **No usage of `pyautogui`, `win32gui`, `win32api` inside `ui/`** (good).
- **No usage of `grab()`, `render()`, `QScreen.grabWindow` inside app code** (only in test harness).
- **No usage of `mapToGlobal()`, `globalPos()`, `QCursor.pos()` inside app code** (only in test harness).

**Nothing-to-report checks:** Confirmed absence of screen-coordinate mixings in all 9 nav screens, dialogs, widgets, and the core launch pipeline. High-DPI settings left to Qt defaults (not explicitly overridden).

**NOT FIXED** (per the campaign's record-do-not-fix rule).

### 2026-09-18 — Unit 3: Add Bank + Add Account End-to-End Flows

**Ran:** `tools/real_ui_tests/test_add_bank_flow.py` and `tools/real_ui_tests/test_add_account_flow.py` (theme: Aurora, dpr: 1.25, maximized)
**Result:** all checks passed.

#### Test Execution Summary

**test_add_bank_flow.py:**
- Navigated to Settings via sidebar button (real click).
- Opened Manage Data dialog via "Manage banks (master)" button.
- Switched to Banks tab (index 1).
- Clicked "Add bank", filled nickname="RUIH_TestBank_01" and name="Jana Small Finance Bank".
- Verified field contents and clicked "Save bank".
- Confirmed new bank appeared in DB and visible table **without manual refresh**.
- Tested Cancel path: opened Add Bank dialog, typed throwaway nickname, clicked "Cancel bank dialog".
- Verified Cancel closed the dialog without adding a row to the database.

**test_add_account_flow.py:**
- Created test person and bank **programmatically** (not via UI) with RUIH_ prefixes for deterministic cleanup.
- Navigated to Settings → Manage bank accounts.
- Switched to Accounts tab (index 2).
- Clicked "Add account", filled person selector (combo), bank selector (combo), account holder name, masked account number, opening balance.
- Verified fields and clicked "Save account".
- Confirmed new account appeared in DB and visible table **without manual refresh**.
- Cross-checked Statement Import screen: verified test person card appeared, clicking it revealed the account card.
- Cleanup deleted account → bank → person in FK order; all counts returned to baseline.

#### FINDING 3.1 — All checks PASSED [NO-BUG]
- **What I did:** Real on-screen test: Add Person (via UI, already working from prior session) → Add Bank (nickname + actual name + optional TAN) → Save + Cancel paths → Database and table visibility cross-checks → Add Account (person + bank + holder name + account number) → save + cross-check Statement Import propagation.
- **Expected:** (a) Bank and account dialogs open via `.exec()` (blocking modals); (b) form fields accept typed input; (c) clicking Save accepts the dialog and writes a new row to the database; (d) the new row appears in the visible management table immediately, with no manual refresh call; (e) Cancel closes the dialog without writing a row; (f) newly created accounts appear as cards on the Statement Import screen when their person is selected.
- **Observed (widget/DB state):** All expectations met. Bank test: `before_banks=0`, added 1 via Save, added 0 via Cancel, final count after cleanup=0. Account test: `before_accounts=1`, added 1 via dialog, final count after cleanup=1. Both dialogs opened, fields accepted input, Save accepted and closed, Cancel closed without writing. ManageDataScreen's `_load_banks()` and `_load_accounts()` called automatically, tables updated without manual refresh. Statement Import successfully found the test person card and the test account card when person was selected.
- **Observed (screenshot):** All 11 screenshots (bank flow) + all 11 screenshots (account flow) show correct progression: dashboard → settings → manage dialog → banks/accounts tab → add dialog open → fields filled → save → table updated → statement import showing new cards.
- **Repaint-lag ruled out?** Yes; widget state and table row counts checked in addition to screenshots. Tables show correct data, database reflects all rows, all dialogs closed correctly.
- **Severity:** N/A — no bug found.

**Nothing-to-report checks:** 
- Settings navigation via sidebar button works correctly.
- Both Add Bank and Add Account dialogs open, populate, accept/reject, and close correctly via the QTimer.singleShot modal pattern.
- Bank combo display format "NICKNAME (bank_name)" is correctly parsed by combo's `findText()` after adding a bank with both fields.
- Account combo selectors (Person, Bank) populate correctly and can be indexed.
- Form fields (Account holder name, Masked account number) accept typed input and persist until save.
- ManageDataScreen's automatic `_load_banks()` / `_load_accounts()` calls on dialog save refresh the visible tables (no manual refresh needed).
- Statement Import screen correctly propagates newly created accounts as selectable cards when their person is selected.
- Database cleanup (delete account → delete bank → delete person in FK order) succeeds without integrity errors.

### 2026-09-18 — Unit 4: Statement Import End-to-End with Real PDF

**Ran:** `tools/real_ui_tests/test_statement_import_flow.py` (theme: Aurora, dpr: 1.25, maximized).
**Result:** 0 checks passed, 1 blocker failure — PDF parsing hangs indefinitely.

#### FINDING 4.1 — PDF statement parsing hangs indefinitely [BUG | BLOCKER]
- **What I did:** Real on-screen test: created test person/bank/account programmatically → navigated to Statement Import → selected person card → selected account card → selected PDF format → set file path via drop zone fileSelected signal → clicked "Next button" to trigger parse → polled for preview table to populate (60-second timeout with 0.5-second polling intervals).
- **Expected:** Within 60 seconds, the statement parser (running on background `QThread` via `Loader.run()`) would complete, populate the `preview_table` with parsed transactions, and display them on screen.
- **Observed (widget state):** After 60 seconds of continuous polling, `preview_table.rowCount()` remained 0. The app window was still open and responsive to screenshots, but the parser never completed and never populated the preview table. The debug output pane (`import_screen.debug_output`) remained empty — no error messages, no progress, no indication of hang.
- **Observed (screenshot):** `tools/real_ui_tests/screenshots/07_06_parse_started.png` shows the Statement Import screen at the parsing phase, with the PDF format button checked, file selected indicator visible, and the "Next button" visible (but likely relabeled to "Parse →" or similar — was not re-dumped after reaching this screen).
- **Repaint-lag ruled out?** Yes; the widget state (`rowCount()`) is queried directly, not inferred from a screenshot.
- **Suspected location:** `ui/statement_import_screen_modern.py` → `_StatementParseWorker.run()` line ~81 calls `parse_statement_with_debug()` from `engines/statement_parser.py`. The worker is started via `Loader.run()` on a `QThread`. Either the worker never starts, never completes, or the result callback never fires to populate the preview table.
- **Severity:** blocker — the entire Statement Import flow is blocked; transactions cannot be imported via the UI.
- **NOT FIXED** (per the campaign's record-do-not-fix rule).

#### Additional Observations

**Test Cleanup:** Database state after interrupted test run. Test setup created 5 copies of the same person (`RUIH_ImportPerson_01`), 1 bank (`RUIH_ImportBank_01`), and 5 accounts (`RUIH_ImportTest`). Cleanup deleted all rows successfully in FK order without constraint errors. **This indicates the test's setup and cleanup logic is sound; the hang occurs after the UI flow is fully rendered and the Next button is clicked, during the background thread handoff.**

**Next Steps for a Fixer:**
1. Run the test with a debugger attached to the `_StatementParseWorker.run()` method to observe whether it enters, exits, or hangs.
2. Check whether `Loader.run()` is correctly installing the result callback.
3. If the parse itself times out (e.g. in `parse_statement_with_debug()`), lower-level statement parsing may have a hang of its own — test with a simple, tiny PDF first.

**Nothing-to-report checks:**
- Person card selection works correctly; card is checked and account cards rebuild for the selected person.
- Account card selection works correctly; account card is checked.
- PDF format selection works correctly; button becomes checked.
- Drop zone file selection via signal works correctly; file path is accepted and displayed.
- Database creation and cleanup of test person/bank/account works correctly in FK order.
- Screenshots are captured correctly at each step up to the parse phase.

### 2026-09-18 — Unit 4 CORRECTION: the parser is fine; a modal dialog blocks the flow

**The Unit 4 entry above claims "PDF parsing hangs indefinitely [BLOCKER]" and
points at `_StatementParseWorker.run()`. That diagnosis is WRONG.** The symptom
(preview table never populates) is real and reproducible, but the cause is not
the parser and not the worker thread. Corrected by direct measurement:

1. **The parser is fast and correct.** Calling
   `parse_statement_with_debug("data/PersonalData/Pranav/Statement/Jana - Pranav.pdf",
   "pdf", "Jana")` directly, with no UI, returns **65 transactions in 1.0 second**.
2. **The worker thread is fine.** `Loader.run()` was traced: `on_done` fires with
   the parsed `(txns, debug_info)` tuple. `Loader.run()` was also exercised in
   isolation under PySide6 and delivers its result correctly.
3. **The real blocker is in `_process_parsed_statement()`**,
   `ui/statement_import_screen_modern.py:1096-1105`. After the parse succeeds it
   extracts metadata, and when `any(metadata.values())` is true it constructs an
   **`AccountMetadataDialog` and calls `dialog.exec()` — a BLOCKING modal — in the
   middle of processing the parse result.** Everything downstream (preview table
   population, the import step) waits on that dialog being dismissed.

   For `Jana - Pranav.pdf` the metadata extractor returns a populated dict
   (account_number_full, ifsc_code, micr_code, branch_name, email_id, phone_no,
   account_type, currency), so `any(...)` is **True** and the dialog **always**
   opens for this file. Verified live: the visible dialog is
   `AccountMetadataDialog`, `isModal() == True`, window title
   **"Update Account Details - <bank>"**.

**This is a real user-facing bug, independently reported by the app owner as
"update account dialog is not responding and window is hanged" / "it's opening in
the background".** From the user's seat the app appears frozen after clicking
Parse, because the dialog that is waiting for them can end up behind the main
window — there is no visible cue that anything is waiting for input.

**Why it also breaks tests:** this is guide §3.8 exactly. `dialog.exec()` spins a
nested event loop inside the callback, so any test that clicks Parse and then
polls `preview_table.rowCount()` will poll forever. A test for this flow MUST
pre-arm a `QTimer.singleShot(0, ...)` handler that finds and dismisses
`AccountMetadataDialog` — or the flow must be driven with metadata handling
stubbed.

**Not fixed** (campaign rule: record, do not fix). When someone does fix it, the
question to answer first is a product one, not a technical one: should importing
a statement interrupt the user with a metadata-confirmation modal at all, or
should those details be applied silently / offered non-modally after the preview
appears? A non-modal (`show()`) dialog, or deferring it until after the preview
populates, would remove both the apparent hang and the test blocker.

**Also note:** the Unit 4 test `tools/real_ui_tests/test_statement_import_flow.py`
verified the steps BEFORE the parse correctly (person card, account card, format
selection, drop-zone file selection) and its DB cleanup is sound. Only its
conclusion about the parse is wrong. Its 60s timeout was hitting the modal, not a
slow parser.

### 2026-09-18 — Statement Import FIXED end-to-end (supersedes the Unit 4 finding)

`tools/real_ui_tests/test_statement_import_flow.py` now passes completely:
**65 transactions parsed, previewed, and imported**, with the DB verified clean
afterwards (0 transactions, 0 RUIH_ rows, the one real person/account intact).

Three distinct bugs were blocking it. All were found by dumping thread stacks at
the hang with `faulthandler.dump_traceback_later()` — worth remembering as the
technique, because none of them produced an exception or any on-screen error.

**BUG A (root cause, affects the whole app) — `Loader.run()` ran its callbacks on
the worker thread.** `ui/widgets/loader.py` connected `on_done`/`on_error` as
plain Python callables. A plain callable has **no thread affinity**, so Qt
invoked them *directly on the emitting (worker) thread*. Everything in
`_process_parsed_statement` — populating the preview table, switching the
QStackedWidget page, showing dialogs — was therefore executing off the GUI
thread. Constructing a `QMessageBox` there deadlocked the process outright: the
window went "Not Responding" (Windows showed a `Ghost` class window) with **no
dialog visible anywhere**. Fixed by routing results through a `_GuiRelay`
QObject parented to the loader, with an explicit `Qt.ConnectionType.QueuedConnection`.
Note this was never PySide6-specific — it is a latent Qt threading bug that
affected **every** `Loader.run()` caller, i.e. statement import, settings warmup
and any other background operation.

**BUG B — a blocking modal in the middle of the parse result handler.**
`_process_parsed_statement` opened `AccountMetadataDialog.exec()` as soon as
metadata extracted cleanly (which for `Jana - Pranav.pdf` is always). The import
flow then waited on user input that the user could not see, because the dialog
could sit behind the main window. Reported independently by the app owner as
"update account dialog is not responding and window is hanged / it's opening in
the background". Disabled behind `SHOW_METADATA_DIALOG = False` in
`ui/statement_import_screen_modern.py`; restore it once it is reworked to be
non-modal or deferred until after the preview renders.

**BUG C — `QMessageBox.critical` in the catch-all handler** at the end of the
same method. Harmless in principle, but combined with BUG A it was the thing
that actually deadlocked. Resolved by fixing BUG A.

**The Unit 4 entry's "PDF parsing hangs indefinitely [BLOCKER]" diagnosis was
wrong on the mechanism** — the parser returns 65 transactions in 1.0s when
called directly. Keep the symptom, discard the cause.

**Test-harness fixes made at the same time:**
- All four tests now close their window in an always-runs teardown
  (`_close_all_windows()`), dismissing stray dialogs first. Previously
  `harness.close()` only ran on the success path, so any failing test left a
  window — and sometimes a blocking modal — stranded on screen. This is what the
  app owner reported as "why are you not closing the tab after completion".
- `sys.stdout`/`sys.stderr` are reconfigured to UTF-8. A `UnicodeEncodeError` on
  the rupee sign was killing an otherwise-passing run at the reporting step on a
  cp1252 Windows console.
- Cleanup note: deleting FDs before transactions raises `FOREIGN KEY constraint
  failed` on the transaction delete, but the rows go anyway via cascade. Verified
  clean afterwards. Harmless, but delete transactions first to avoid the noise.

**Theme contrast (all four themes measured, WCAG AA 4.5:1):** only one failure —
Aurora `TEXT_MUTED` (#75718F) on `BG` (#F7F7FD) is **4.36:1**. Every other
text/background pair checked passes in Aurora, Nova, Slate and Midnight Pro,
including all the dark themes. Not fixed (record-only).

### 2026-09-18 — Unit 5: Tax Documents drop zones (real files)

New test: `tools/real_ui_tests/test_tax_documents_flow.py`. Navigates to Tax
Documents (nav index 6) and hands each of the three real PDFs to its drop zone
via `fileSelected(str)` — the same signal the browse button emits once a path is
chosen. The literal browse click is NOT covered (a native QFileDialog cannot be
driven by QTest). Read-only: nothing is written to the database.

**Results:**
- Navigation, screen construction and all three drop zones: PASS.
- **Form 26AS parsed successfully in 4.7s with no blocking modal.** This is an
  independent confirmation of the `Loader.run()` GUI-thread fix on a code path
  completely separate from statement import — all three handlers here go through
  `Loader.run()`, and before the fix that meant GUI work on the worker thread.
- **AIS: FAILED to parse. TIS: same cause.**

#### FINDING 5.1 — Tax Documents cannot import encrypted AIS/TIS at all [MAJOR]

Measured: `26AS.pdf` `is_encrypted=False`; **`AIS.pdf` and `TIS.pdf` are both
`is_encrypted=True`.** Parsing either directly with `password=None` raises
`pdfplumber.utils.exceptions.PdfminerException`.

`ui/tax_documents_screen.py` hardcodes `password=None` in all three handlers
(lines 297, 319, 341) and never checks whether the file is encrypted:
```python
def parse_ais(): return parse_ais_pdf(path, password=None)
```
There is no encryption check and no password prompt, so **an encrypted AIS or TIS
can never be imported through the UI** — which, for this user's real documents,
is both of them.

This is an inconsistency rather than an oversight in isolation, because the
infrastructure already exists:
- `ui/statement_import_screen_modern.py` DOES do this properly:
  `_is_statement_file_encrypted()` -> `_prompt_statement_password()` -> passes the
  password through to the parser.
- `models/person.py` already has `get_ais_tis_password()` / `set_ais_tis_password()`,
  backed by an `ais_tis_password_enc` column on `Person`. **Grep confirms
  `get_ais_tis_password` is never called from anywhere in `ui/`.** The storage
  layer for this exact feature was built and left unwired.

Fix direction (not applied — record-only): mirror the statement-import path.
Check encryption, look up the person's stored AIS/TIS password, prompt if absent,
and pass it to `parse_ais_pdf` / `parse_tis_pdf` / `parse_form26as_pdf`.

**Good news on error handling:** the app did NOT hang or crash on the failed
parse. The `on_error` path fired, the zone showed an error status, and the window
stayed responsive — so the failure is clean and recoverable, just not actionable
by the user.

**Not covered yet:** the reconciliation view, because it needs all three
documents parsed. Re-run this test once the password path is wired.

**Test-script caveats (not app bugs), fix before trusting a re-run:**
- The "App still responsive after all three parses" check FAILED, but a
  screenshot taken at that moment shows the test window was already closed, so
  the assertion was measuring a closed window rather than a frozen one. The app
  did not freeze. Treat that single FAIL as a test defect.
- AIS and TIS each burned the full 91s timeout because the wait polled only for
  `zone.pdf_data`, which never arrives on failure. The parse itself fails fast.
  The wait now also accepts an "Error:" status on the zone, so a failed parse
  reports in seconds instead of 90s.

### 2026-09-18 — Unit 6: button size audit on a real render (36 buttons, 9 screens)

New test: `tools/real_ui_tests/test_button_size_audit.py`. Builds each of the
nine nav screens in a real maximized window and measures every visible
QPushButton/QToolButton's **rendered** height and width against
`design_direction.scales_to_enforce` (heights 28/36/44 +/-2px, 280px width cap).
This closes the §4 gap "never measured on a real render, only asserted in code".
Reports only — changes nothing.

**Result: 36 visible buttons measured, 14 off-scale.** Clean screens: Overview,
Accounts, Fixed Deposits, Statement Import.

#### FINDING 6.1 — eight primary action buttons are 40px, between md and lg [MINOR]
40px is not on the {28, 36, 44} scale — it sits between `md` and `lg`. Affected:
Transactions (Add Transaction, Edit, Delete, Link Transfers, Import Statement),
Income & Expectations (Add Expected Income), Tax Documents (Add), Tax
(Estimate Tax).

Source is an explicit `height=40` argument to `Theme.btn(...)`. Grep shows the
same literal in `ui/transactions_screen.py` (x4), `ui/tax_screen.py`,
`ui/dialogs/account_details_dialog.py` (x3) and
`ui/dialogs/account_metadata_dialog.py` (x2) — so dialogs carry it too, they were
just not measured here. Fix is mechanical: `height=40` -> `height=Theme.HEIGHT_MD`
(36) or `Theme.HEIGHT_LG` (44), whichever the design intends for a screen's
primary action. Not applied — it is a visual change across several screens and
should be one deliberate pass, not a silent edit during a test run.

#### FINDING 6.2 — six Settings buttons exceed the 280px width cap [MINOR]
Change Password (320px), Manage People (322px), Manage Bank (322px), Manage Banks
(322px), Create Backup (320px), Restore Backup (320px). These are built in
`ui/settings_screen.py` with `min_width=155` inside a stretching layout, so the
layout — not the min-width — is what pushes them past the cap. A `setMaximumWidth`
of 280 on that row, or a trailing stretch, would hold the scale.

Neither finding is a functional bug; both are design-scale drift that only a real
render could reveal.

#### Harness note — a PySide6 API difference worth knowing
`QObject.findChildren()` accepts a **single** type in PySide6; passing a tuple
like `findChildren((QPushButton, QToolButton))` raises `TypeError`. PyQt6 allowed
the tuple form. Call it once per type and concatenate. This is the kind of
difference that only surfaces when the code actually runs, not at import.

### 2026-09-19 — Full pipeline on REAL data: extraction fixed, reconciliation gap quantified

Real DB, real documents. 506 transactions imported across four real accounts
(Jana 65, IDFC 376, Ujjivan 27, Equitas 38 via password), 20 FDs, principal
2,700,000. Income 6,495,691.21 / Expense 6,388,400.18.

**Extraction — fixed.** The UI was calling the LEGACY statement parser while a
modern one existed. After switching and porting the missing bits:
  Jana    confidence 64% -> 100%, balance failures 39 -> 0, income rows 12 -> 32
  IDFC    73% -> 100%, 5 -> 0, income rows 14 -> 115
  Ujjivan 41% -> 100%, 4 -> 0, income rows 0 -> 16
Ujjivan detecting ZERO income rows before is the headline: every interest credit
was typed as an expense, which made tax reconciliation impossible.
reference_no recovered from continuation lines (bare tokens below the row, which
land in the description column, not the ref column): Jana 34 -> 46/65, IDFC 343
-> 358/376 (matching legacy exactly).

**26AS — fixed.** Was 49 records with tax_deducted None on every one, extracting
0.00. Now 86 Part-I + 72 Part-II records with deductor/TAN/section populated and
per-record TDS summing to exactly 13,367.00, matching the document's own total,
with 27 reversal rows correctly netted.

**FD auto-creation is UI-only.** `add_fd_from_statement` is called from
`ui/statement_import_screen_modern.py`, not from the model layer, so a headless
import creates no FDs. That is a TEST-METHOD gap, not an app bug — running the
same `_is_fd_opening_transaction` detector over the imported rows found 19
FD-opening transactions totalling 2,200,000 and created them without error.

#### FINDING — interest reconciliation gap (NOT yet explained, needs the owner)
Comparing 26AS section 194A (Part-I + Part-II 15G/15H) against DB interest income:

| bank    | 26AS 194A incl Part-II | DB interest income |
|---------|------------------------|--------------------|
| Equitas | 54,816.00              | 92,257.00          |
| Jana    | 34,469.00              | 4,001.00           |
| Ujjivan | 79,077.00              | 0.00               |
| IDFC    | (none in 26AS)         | 244.00             |
| TOTAL   | 168,362.00             | 96,502.00          |

AIS and TIS agree with each other and report total interest 302,825.00
(savings 46,183 + FD 256,642) — far above both. The likely explanation is that
most FD interest is credited inside the FD, not as a savings-account transaction,
so it will never appear in statement rows. UJJIVAN showing 79,077 in 26AS and
0.00 in the DB is the clearest case to investigate first.

**TDS is entirely absent from transactions.** 26AS shows 13,367.00 TDS
(Enlightvision 10,508 under 194JB/194JA, Jana 2,859 under 194A). No transaction
description contains "TDS" or "TAX DEDUCT". TDS is deducted before credit, so it
is not a bank-statement line — it has to come from the tax documents, which is
exactly what the reconciliation view is for.

**Dark mode:** the owner's "white background" report was real but not on Statement
Import. A ChartWidget takes its facecolor at construction, and
IncomeManagementScreen never defined `refresh_theme()` while dashboard_screen
called it inside `except Exception: pass` — so the AttributeError was swallowed
and its three charts stayed white after a theme switch. Measured 69.6% bright ->
0.0% after the fix. Every other screen already rendered correctly in both dark
themes (0.1-0.8% bright).
