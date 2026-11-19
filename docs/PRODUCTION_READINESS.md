# Production readiness and release gates

The production baseline and acceptance gates were recorded on 2026-11-08. The [organization audit](REPOSITORY_STRUCTURE.md) documents the later test relocation and runtime extractions. **Public distribution remains gated** by nine private-source paths in local Git history.

## New Windows device checkpoint

On 2026-11-19, `main` at `8c83270` was checked in `D:\Study\Projects\app`. Python 3.12.10 runs from the local `.venv`, which uses the unpacked runtime under `artifacts/python312/runtime/tools`. `pip check` passed. Launch the app from the checkout with `.\.venv\Scripts\python.exe main.py`.

The Windows startup smoke used an isolated app copy and a disposable database. First-run password setup, login, onboarding, and all 11 dashboard pages passed. SQLite integrity returned `ok` and the foreign-key check found no violations. A second run used the bundled QtAwesome fonts because the sandbox restricts the Windows per-user font directory. See the [smoke log](../artifacts/native/device-smoke-20261119/smoke-bundled-fonts.log) and [installed package versions](../artifacts/native/device-smoke-20261119/installed-versions.txt).

The 78-module headless run reported 77 clean exits. The FD Planner screen module passed its assertions and then crashed at Qt shutdown. Its fixture now disposes of the widget while Qt is active after a successful close. The affected module passed all 12 tests and exited cleanly on four isolated reruns. Together, the full run and focused rerun cover **765 passed and 47 skipped**, with 2 additional passing subtests. The skips comprise 36 missing document fixtures, 4 missing live-database checks, 2 statement-import cases without a person fixture, and 5 full-session parity placeholders. See the [full run](../artifacts/pytest/device-20261119/suite.log), [FD Planner rerun](../artifacts/pytest/device-20261119-planner-rerun/suite.log), and [repeat checks](../artifacts/pytest/device-20261119-planner-rerun/repeats.log).

The [temporary-database verification](../artifacts/native/rebuild/P4_verify_tempdb.json) recorded zero failures, and the tracked-path privacy check passed. The device smoke took place before the live database was initialized on this checkout.

The current checkout preflight and workbook-dependent scenarios require the actual inputs. The prior device's rebuild counts and screenshots are historical evidence. Once the new source files are available, begin with the read-only preflight in the [native rebuild runbook](../tests/native/REBUILD_PLAN.md).

## Compact UI checkpoint

Batch 1 addresses the dashboard selectors, transaction ledger, statement preview, Fixed Deposits toolbar and Tax Documents results. The [visual testing guide](VISUAL_TESTING_GUIDE.md#batch-1-compact-layout-and-statement-feedback) records the checks and links to the synthetic captures and test logs. The statement native scripts were updated for the disabled action states. The real-PDF native replay remains a release verification step.

## Completed evidence

- The original eight work phases (0 safety net, 1 statements, 2 tax documents, 3 interest, 4 tax engine, 5 data model, 6 UI, 7 security and honesty) are recorded in [`AUDIT_AND_REBUILD_PLAN.md`](AUDIT_AND_REBUILD_PLAN.md), including the historical state at `a328e80`.
- The later P0–P5 rebuild baseline completed: preflight, backup/reset, rebuild, GUI work, engine checks, and audit. Baseline: 69 files, 735 passed, 8 skipped. This is evidence for that baseline, not closure of the release gates below.
- Current-tree privacy scan passed with 9 tests and 2 subtests. It covers tracked files and optional local-secret checks; it does not certify repository history. Nine historical private-source paths remain.
- Password change atomicity: 4 focused checks passed. Evidence: [`production_password_atomicity_20261108.out`](../artifacts/native/rebuild/production_password_atomicity_20261108.out).
- S14 native password change, relogin, pre-change restore, and restored-secret checks passed 15/15. Evidence: [`production_password_restore_gui_20261108.out`](../artifacts/native/rebuild/production_password_restore_gui_20261108.out).
- Settings native GUI checks passed 36/36, including TOTP enrollment/login/disable, full restore, and people/bank management. Evidence: [`production_settings_gui_20261108.out`](../artifacts/native/rebuild/production_settings_gui_20261108.out) and [`P3_09_Settings_S.json`](../artifacts/native/rebuild/P3_09_Settings_S.json).
- Restore core: 11 checks passed; routing and foreign-key handling were reviewed and approved. Native R08 and R11 passed with exit code 0 and fingerprint guards passing. Evidence: [`production_prediction_gui_20261108.out`](../artifacts/native/rebuild/production_prediction_gui_20261108.out) and [`production_refresh_gui_20261108.out`](../artifacts/native/rebuild/production_refresh_gui_20261108.out).
- Scheduler: 2 checks passed and review approved.
- Independent prediction checks: 3 passed; existing chart checks: 4 passed; income-category check: 1 passed. Bank-scoped FD matching was reviewed and approved.
- Independent planner acceptance: 1 check passed. Evidence: [`production_planner_verified_20261108.out`](../artifacts/native/rebuild/production_planner_verified_20261108.out).
- Clean install succeeded with the tested package versions; `pip check` found no broken requirements. Evidence: [`production_clean_install_tested_20261108.out`](../artifacts/native/rebuild/production_clean_install_tested_20261108.out) and [`production_clean_install_check_20261108.out`](../artifacts/native/rebuild/production_clean_install_check_20261108.out).
- Final isolated clean-environment suite passed: 76 files, 771 tests passed, 8 skipped. Evidence: [`production_clean_suite_20261108.out`](../artifacts/native/rebuild/production_clean_suite_20261108.out).
- Final engine/tempdb verification and P5 collection exited 0. P5 used the `resume_20261108_before` database/preferences baseline. Evidence: [`production_final_engines_20261108.out`](../artifacts/native/rebuild/production_final_engines_20261108.out) and [`production_final_collection_20261108.out`](../artifacts/native/rebuild/production_final_collection_20261108.out).
- Final hash, theme, SQLite integrity, and foreign-key audit passed. Evidence: [`production_final_audit_20261108.out`](../artifacts/native/rebuild/production_final_audit_20261108.out).
- The Settings TOTP enrollment URI is presented in a persistent dialog and remains copyable; its availability was verified in the native Settings run.

## Remaining release limitation and next work

1. **History and distribution:** nine historical private-source paths remain. The repository stayed local and was not distributed. Do not rewrite history here or claim it is clean; public distribution remains gated.
2. **Remaining engineering work.** The private visual audit is complete. The next UI batch covers shared controls, tables and theme consistency. The [organization audit](REPOSITORY_STRUCTURE.md) lists deferred runtime refactors. See the [cleanup inventory](../artifacts/native/rebuild/cleanup_inventory_20261108.md) for the previous device's remaining runtime candidates and migration cautions.

The live database and existing source-data facts remain frozen during subsequent organization and refactor work. The [native rebuild runbook](../tests/native/REBUILD_PLAN.md) and [visual testing guide](VISUAL_TESTING_GUIDE.md) link here for the current readiness status.
