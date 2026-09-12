# Frontend migration evaluation — PyQt6 vs. alternatives

**Date:** 2026-09-12
**Trigger:** Real-click UI testing (`tools/real_ui_test_harness.py`) hit repeated
flakiness — misclicks from blind pixel coordinates, DPI-scaling (125% Windows
display scaling) translation bugs, and Windows focus-stealing prevention
blocking programmatic window focus. That testing problem is **already fixed** in
the harness itself (see `docs/VISUAL_TESTING_GUIDE.md` §3.7–3.8) by switching to
`QTest` + accessible-name widget lookup, which needs no OS-level coordinates at
all. This document is a separate question the owner asked to have researched
regardless: **would a different UI stack be a genuinely better foundation for
this app**, independent of whether the original bug required it.

**Scope note:** this app's business logic (`models/`, `core/`, `engines/`) has no
UI imports and is reusable as-is under every option below. Only `ui/` — screens,
dialogs, the `ui/theme/` design system, custom tables, drag-and-drop zones —
would be rewritten.

---

## 1. Is PyQt6 itself the problem?

No. The bugs that triggered this evaluation were in the *test harness's*
approach (blind `pyautogui` coordinates), not in PyQt6. `pytest-qt`/`QTest`
drives the real Qt object tree in-process — no coordinates, no DPI math, no
window-focus dependency — and fully resolves the original complaint without
touching the app. PyQt6 is mature, actively maintained, and technically capable.

Its real limitation is **ergonomics for a modern, fluid, "interactive" feel**.
Qt Widgets (what this app uses) has no CSS-like cascading transitions — animating
anything means hand-rolling `QPropertyAnimation`/`QGraphicsEffect` per widget.
Qt's other API, QML, does support fluid animation natively, but it's a separate
language and layout model bolted onto Python — adopting it is nearly as large a
rewrite as leaving Qt entirely, for a smaller ecosystem than either Qt Widgets or
the web.

**A free, near-zero-risk option worth doing regardless of anything else in this
document:** swap `PyQt6` → `PySide6`. Same API (~99.9% identical, a handful of
enum-scoping differences), same widget model, same `pytest-qt` testability
story, same theme system carried over almost unchanged. The only real
difference is licensing (PySide6 is LGPL, the Qt Company's own official
binding) — moot for a solo, non-distributed app, but PySide6 is the more
future-proof long-term binding per current guidance. This doesn't address the
"more interactive/modern" desire at all, but costs almost nothing.

---

## 2. Alternatives evaluated

| Option | Interactivity / modern feel | Custom theming ergonomics | Financial data tables | Testability | Maturity (2025) |
|---|---|---|---|---|---|
| **PyQt6 (current)** | Manual, per-widget animation code | QSS stylesheets (verbose, no cascading transitions) | `QTableWidget`/custom — works, but hand-built | `pytest-qt`/`QTest`, in-process, no coordinates — solved | High |
| **PySide6** | Same as PyQt6 | Same as PyQt6 | Same as PyQt6 | Same as PyQt6 | High |
| **Flet** (Flutter-backed) | Strong — real Flutter animation engine | Flutter widget styling | DIY on Flutter primitives | Immature; no Playwright-equivalent | **Low** — 1.0 only reached beta Dec 2025 |
| **Electron + React/Vue + Python** | Full CSS/JS animation, mature component libraries | CSS — best-in-class | AG Grid / TanStack Table (industry standard for financial grids) | Playwright — extremely mature | High, but trending toward "legacy default" vs. Tauri |
| **Tauri + React/Vue + Python (sidecar)** | Same as Electron | Same as Electron | Same as Electron | Playwright | High, fast-growing; adds a Rust toolchain dependency |
| **pywebview + React/Vue + Python (in-process)** | Same as Electron/Tauri | Same as Electron/Tauri | Same as Electron/Tauri | Playwright | High; uses Windows' built-in WebView2, no new toolchain beyond a frontend build |
| **NiceGUI** (Python, renders real HTML via FastAPI/Vue/Quasar) | Good — real CSS/Quasar animation | Quasar/Tailwind theming (less granular control than raw CSS) | Quasar table components | Playwright | Medium — smaller ecosystem, one maintainer's opinions |
| Kivy / wxPython / Dear PyGui | Not competitive for a desktop line-of-business app (touch-first, or no testability/theming edge) | — | — | No advantage over PyQt6 | Ruled out |

### Why testability is the sharpest axis

Playwright (used by every web-based option above) locates elements by role,
label, text, or CSS selector against the DOM/accessibility tree, and is
explicitly documented as immune to the DPI-scaling and coordinate-drift
problems that caused this project's original harness pain. It's also a vastly
larger, better-tooled ecosystem than anything available for Qt testing (trace
viewer, codegen, network mocking, CI integration).

Important nuance: **`pytest-qt` already gets PyQt6 to "no DPI/coordinate/focus
problems" parity** with Playwright for the *specific* bugs that triggered this
evaluation. Playwright's remaining edge is tooling maturity and ecosystem size,
not a problem Qt testing can't solve at all.

---

## 3. Migration cost, top contenders

All three web-based contenders require a full rewrite of `ui/` — every screen,
the `ui/theme/` system reimplemented in CSS, tables reimplemented in AG Grid or
TanStack Table, drag-and-drop reimplemented with native HTML5 drag events.
Backend logic (`models/`, `core/`, `engines/`) carries over as-is; the new work
is an API/bridge surface (a FastAPI layer, or a JS↔Python bridge).

1. **pywebview + React/Vue, Python in-process** — no separate sidecar process,
   no IPC hop; the built-in `window.pywebview.api` bridge calls straight into
   existing Python services. Uses Windows' native WebView2 runtime (ships with
   Windows 11), so packaging stays close to the current `.venv`/PyInstaller-style
   model — just add a frontend build step. **Lowest-friction path to a
   genuinely modern, Playwright-testable UI given this project's existing
   Python-centric stack.**

2. **Tauri + React/Vue, Python sidecar** — smaller installer, stronger process
   sandboxing than Electron/pywebview, but introduces a Rust toolchain and a
   PyInstaller-built sidecar binary as new build-pipeline surface.

3. **NiceGUI** — smallest conceptual jump (still pure Python, no second
   frontend codebase to learn/maintain), Playwright-testable since it renders
   real HTML. Trade-off: less fine-grained design-system control than a
   hand-built React/CSS frontend, more dependent on one framework's component
   opinions.

**PySide6** — near-zero cost/risk, worth doing immediately regardless of the
bigger decision below.

---

## 4. Recommendation

This is the researcher's read, not a decision — the owner should weigh it.

Given the explicit instruction that cost is not the constraint, **pywebview +
React (or Vue) + Python backend in-process** is the strongest fit: real
CSS-driven theming (Aurora/Nova/Midnight Pro/Slate become CSS variable sets,
trivially, vs. today's QSS), genuine animation/interactivity, Playwright testing
with zero coordinate/DPI/focus-stealing surface area, the largest and most
future-proof component/table ecosystem, and the smallest new-toolchain burden
given the app is already Python/`.venv`-based.

**Tauri** is the runner-up if a smaller installer and stronger sandboxing
matter enough to justify a Rust toolchain. **NiceGUI** is the fallback if a
second frontend language/codebase isn't wanted at all. **PySide6** is worth
doing either way — it's free, safe, and doesn't foreclose a bigger move later.

This document does not recommend a specific next step beyond that — it's the
owner's call whether to pursue a rewrite, and at what scope.
