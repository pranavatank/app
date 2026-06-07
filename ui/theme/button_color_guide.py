"""
ui/theme/button_color_guide.md — Button color convention for all screens.

RULE: In any one screen/section, each button should have a DISTINCT color.
Use this mapping:

  primary    = Blue    — main positive action (Add, Save, Apply, Unlock)
  success    = Green   — confirmatory save / import complete
  danger     = Red     — destructive (Delete, Remove)
  warning    = Amber   — caution (Restore, Overwrite)
  info       = Cyan    — informational / link actions
  edit       = Violet  — edit / modify / recalculate
  secondary  = Grey    — cancel / back / neutral
  ghost      = Text-only — minor action

SCREEN BUTTON COLOR MAP:

Transactions Screen (action bar):
  ＋ Add Transaction  → primary   (blue)
  ✏ Edit             → edit      (violet)
  🗑 Delete           → danger    (red)
  Reprocess Data     → secondary (grey)
  Apply (filter)     → primary   (blue)
  Clear (filter)     → secondary (grey)

Fixed Deposits Screen:
  ＋ Add FD           → primary   (blue)
  🗑 Delete Selected  → danger    (red)
  🔗 Link Txn        → info      (cyan)
  ⚡ Auto-Link        → success   (green)
  📊 Recalculate     → edit      (violet)
  💾 Save Changes    → warning   (amber) — caution: overwrites

Accounts Screen:
  📋/🎴 Toggle View   → secondary (grey)
  ＋ Add Account      → primary   (blue)
  (Card) Edit         → edit      (violet)
  (Card) Delete       → danger    (red)
  (Card) Close        → secondary (grey)

Settings Screen:
  Change Password    → primary   (blue)
  💾 Create Backup   → success   (green)
  🔄 Restore Backup  → danger    (red)  — destructive
  Manage Persons     → primary   (blue)
  Manage Accounts    → info      (cyan)
  Manage Banks       → secondary (grey)

Tax Screen:
  ⚡ Estimate Tax     → primary   (blue)

Reports Screen:
  🔄 Refresh          → primary   (blue)

AIS/TIS Screen:
  📄 Import PDF       → primary   (blue)
  🔄 Refresh          → secondary (grey)

Reconciliation Screen:
  🔄 Reconcile        → primary   (blue)
  📄 Import 26AS     → info      (cyan)

Statement Import:
  Browse             → secondary (grey)
  Next →             → primary   (blue)
  ← Back             → secondary (grey)
  Finish             → success   (green)

FD Dialog:
  Show Calculations  → info      (cyan)
  Cancel             → secondary (grey)
  Save FD            → primary   (blue)

LinkFD Dialog:
  Unlink             → danger    (red)
  Cancel             → secondary (grey)
  Link Selected      → primary   (blue)

Login:
  🔓 Unlock           → hero      (gradient)

Setup:
  ✅ Create Account   → hero      (gradient)
"""
# This file is documentation only — no code.
