# Production readiness and release gates

**Status date:** 2026-11-08. The application is **not production-ready**. This page is the current release handoff; it separates completed evidence from open release gates.

## Completed evidence

- The original eight work phases (0 safety net, 1 statements, 2 tax documents, 3 interest, 4 tax engine, 5 data model, 6 UI, 7 security and honesty) are recorded in [`AUDIT_AND_REBUILD_PLAN.md`](AUDIT_AND_REBUILD_PLAN.md), including the historical state at `a328e80`.
- The later P0–P5 rebuild baseline completed: preflight, backup/reset, rebuild, GUI work, engine checks, and audit. Baseline: 69 files, 735 passed, 8 skipped. This is evidence for that baseline, not closure of the release gates below.
- Current-tree privacy scan passed with 9 tests and 2 subtests. It covers tracked files and optional local-secret checks; it does not certify repository history. Nine historical private-source paths remain.
- Password change atomicity: 4 focused checks passed. Evidence: [`production_password_atomicity_20261108.out`](../tools/real_ui_tests/screenshots/rebuild/production_password_atomicity_20261108.out).
- S14 password-change and relogin portion passed 7 assertions. Restore-after-change extension remains pending.
- Restore core: 11 checks passed; routing and foreign-key handling were reviewed and approved. Native session handoff remains pending.
- Scheduler: 2 checks passed and review approved.
- Independent prediction checks: 3 passed; existing chart checks: 4 passed; income-category check: 1 passed. Bank-scoped FD matching was reviewed and approved.

## Open release gates

1. **Privacy history:** nine historical private-source paths remain. The owner confirms the repository stayed local and was not distributed. Do not rewrite history in this work or claim history is clean; distribution remains gated.
2. **S14 extension and native handoff:** complete the restore-after-change extension and verify native session handoff on a fresh scratch copy.
3. **Installability and settings:** the installer is downloading Qt; clean-install validation remains open. Settings UI work remains in progress; display the TOTP URI transiently.
4. **Planner acceptance:** the integrated independent planner gate is pending. Preserve established source-data facts while gathering evidence.
5. **Later work:** full Sol UI audit and cleanup/refactor remain scheduled after the current gates, in the owner’s requested order.

The live database and existing source-data facts remain frozen during these gates. The rebuild runbook at [`../tools/real_ui_tests/REBUILD_PLAN.md`](../tools/real_ui_tests/REBUILD_PLAN.md) and the visual handoff at [`VISUAL_TESTING_GUIDE.md`](VISUAL_TESTING_GUIDE.md) link here for the authoritative readiness status.
