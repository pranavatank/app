# Production readiness and release gates

**Status date:** 2026-11-08. Current coding and acceptance gates are complete. **Public production release remains blocked** because nine historical private-source paths remain in repository history; the owner confirms the repository stayed local and was not distributed. This page is the current release handoff.

## Completed evidence

- The original eight work phases (0 safety net, 1 statements, 2 tax documents, 3 interest, 4 tax engine, 5 data model, 6 UI, 7 security and honesty) are recorded in [`AUDIT_AND_REBUILD_PLAN.md`](AUDIT_AND_REBUILD_PLAN.md), including the historical state at `a328e80`.
- The later P0–P5 rebuild baseline completed: preflight, backup/reset, rebuild, GUI work, engine checks, and audit. Baseline: 69 files, 735 passed, 8 skipped. This is evidence for that baseline, not closure of the release gates below.
- Current-tree privacy scan passed with 9 tests and 2 subtests. It covers tracked files and optional local-secret checks; it does not certify repository history. Nine historical private-source paths remain.
- Password change atomicity: 4 focused checks passed. Evidence: [`production_password_atomicity_20261108.out`](../tools/real_ui_tests/screenshots/rebuild/production_password_atomicity_20261108.out).
- S14 native password change, relogin, pre-change restore, and restored-secret checks passed 15/15. Evidence: [`production_password_restore_gui_20261108.out`](../tools/real_ui_tests/screenshots/rebuild/production_password_restore_gui_20261108.out).
- Settings native GUI checks passed 36/36, including TOTP enrollment/login/disable, full restore, and people/bank management. Evidence: [`production_settings_gui_20261108.out`](../tools/real_ui_tests/screenshots/rebuild/production_settings_gui_20261108.out) and [`P3_09_Settings_S.json`](../tools/real_ui_tests/screenshots/rebuild/P3_09_Settings_S.json).
- Restore core: 11 checks passed; routing and foreign-key handling were reviewed and approved. Native R08 and R11 passed with exit code 0 and fingerprint guards passing. Evidence: [`production_prediction_gui_20261108.out`](../tools/real_ui_tests/screenshots/rebuild/production_prediction_gui_20261108.out) and [`production_refresh_gui_20261108.out`](../tools/real_ui_tests/screenshots/rebuild/production_refresh_gui_20261108.out).
- Scheduler: 2 checks passed and review approved.
- Independent prediction checks: 3 passed; existing chart checks: 4 passed; income-category check: 1 passed. Bank-scoped FD matching was reviewed and approved.
- Independent planner acceptance: 1 check passed. Evidence: [`production_planner_verified_20261108.out`](../tools/real_ui_tests/screenshots/rebuild/production_planner_verified_20261108.out).
- Clean install succeeded with the tested package versions; `pip check` found no broken requirements. Evidence: [`production_clean_install_tested_20261108.out`](../tools/real_ui_tests/screenshots/rebuild/production_clean_install_tested_20261108.out) and [`production_clean_install_check_20261108.out`](../tools/real_ui_tests/screenshots/rebuild/production_clean_install_check_20261108.out).
- Final isolated clean-environment suite passed: 76 files, 771 tests passed, 8 skipped. Evidence: [`production_clean_suite_20261108.out`](../tools/real_ui_tests/screenshots/rebuild/production_clean_suite_20261108.out).
- Final engine/tempdb verification and P5 collection exited 0. P5 used the `resume_20261108_before` database/preferences baseline. Evidence: [`production_final_engines_20261108.out`](../tools/real_ui_tests/screenshots/rebuild/production_final_engines_20261108.out) and [`production_final_collection_20261108.out`](../tools/real_ui_tests/screenshots/rebuild/production_final_collection_20261108.out).
- Final hash, theme, SQLite integrity, and foreign-key audit passed. Evidence: [`production_final_audit_20261108.out`](../tools/real_ui_tests/screenshots/rebuild/production_final_audit_20261108.out).
- The Settings TOTP enrollment URI is presented in a persistent dialog and remains copyable; its availability was verified in the native Settings run.

## Remaining release limitation and next work

1. **History and distribution:** nine historical private-source paths remain. The repository stayed local and was not distributed. Do not rewrite history here or claim it is clean; public distribution remains gated.
2. **Next sequence:** the first cleanup batch removed the validated ignored clean-install environment and copied wheel cache; logs and tested-constraints snapshot were preserved. Organize files and tests next, then refactor, then perform the full Sol UI audit. File/test moves remain pending. See the read-only [cleanup inventory](../tools/real_ui_tests/screenshots/rebuild/cleanup_inventory_20261108.md) for candidates and migration cautions.

The live database and existing source-data facts remain frozen during subsequent organization/refactor work. The rebuild runbook at [`../tools/real_ui_tests/REBUILD_PLAN.md`](../tools/real_ui_tests/REBUILD_PLAN.md) and the visual handoff at [`VISUAL_TESTING_GUIDE.md`](VISUAL_TESTING_GUIDE.md) link here for the authoritative readiness status.
