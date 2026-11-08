# Repository structure and organization audit

## Current layout

- `core/` — authentication, database, encryption, backup, settings, and session services.
- `models/` — SQLite data access and record models.
- `engines/` — financial calculations, statement parsing, tax-document processing, and FD planning.
- `ui/` — PySide6 screens, dialogs, themes, and reusable widgets.
- `tests/` — headless automated tests, native GUI scripts under `native/`, and shared checks/helpers under `support/`; feature membership is documented in [tests/README.md](../tests/README.md).
- `tools/` — command-line diagnostics, maintenance utilities, and the generic headless suite runner.
- `artifacts/` — ignored generated material: native screenshots/rebuild evidence under `native/`, and per-run headless logs under `pytest/<UTC timestamp>/`.
- `docs/` — current guides and product specifications, indexed in [docs/README.md](README.md); completed plans are under `docs/archive/`.
- `data/`, `backups/` — local application and private financial data. Treat as user data; do not reorganize or alter during source cleanup.

## Organization decisions

- Added navigation indexes for documentation and tools, and replaced the root README's stale file-by-file tree with a concise architecture map.
- Archived superseded migration, redesign, pipeline, UI campaign, prediction, and completed rebuild plans under `docs/archive/`. The retained audit/rebuild specification remains linked from current readiness and test notes because it includes still-referenced behavior and calculation details.
- Moved native UI scripts and their runbook from `tools/real_ui_tests/` to `tests/native/`. They require a visible application session and are excluded from headless collection.
- Moved the reusable native harness to `tests/support/real_ui_test_harness.py`, the standalone prediction check to `tests/support/check_prediction.py`, and rebuild verification/P4 checks to `tests/native/rebuild_verify.py`.
- Native scripts now write screenshots, logs, scratch state, and P0–P5 evidence under ignored `artifacts/native/`. The ignored source/evidence relocation inventory is `artifacts/native/relocation_manifest.json`.

## Bounded runtime extraction

This work included a small runtime organization pass alongside the test and artifact relocation:

- Ten database migration and seed helpers moved from `core/database.py` into `core/database_migrations.py` (687 lines). The original public functions remain available through compatibility exports so existing imports keep working.
- `ThemeCard` moved to `ui/widgets/theme_card.py`, with its former import path retained as a compatibility export.
- TOTP enrollment and restore-recovery dialogs moved to `ui/dialogs/settings_security.py`, with compatibility exports retained from their former module.

These extractions establish narrower module boundaries without rewriting the broader application. The remaining statement, tax, planning, and screen decomposition inventory below still needs import mapping and feature coverage before further moves.

## Deferred runtime refactor inventory

Broader runtime decomposition remains future work. The targeted extractions above do not complete or rewrite these larger clusters:

- `engines/statement_parser.py`, `statement/`, `bank_parsers/`, and parser utilities: overlapping statement parsing layers that need import and coverage mapping first.
- `engines/tax_engine.py`, `advance_tax_engine.py`, tax-document parsers, and their persistence model: tax calculations and document ingestion have distinct boundaries but share UI-facing concepts.
- `engines/fd_*`, `family_fd_engine.py`, rate sources, and planner UI/dialog components: planner responsibilities span calculations, sources, and presentation.
- Large root-level `ui/*_screen.py` modules alongside `ui/dialogs/` and `ui/widgets/`: screen decomposition should follow current feature tests and UI ownership.
- Remaining `core/database.py` and models responsibilities: schema orchestration and model persistence still share database boundaries; map migration impact before further extraction.

Before any later runtime moves, map imports, test ownership, persistence boundaries, and native UI entry points. Keep private data, backups, ignored test evidence, and Git history intact.

## Validation and completion

- At the organization audit checkpoint, all 76 original modules and their functions were retained, with 77 modules including the manifest regression check; that isolated suite completed with **775 passed and 8 skipped**. This is historical evidence from before the current runtime extractions and added relocation/path regressions, not validation of the current tree. Evidence: [organization full suite](../artifacts/native/rebuild/organization_full_20261108.out).
- Final runner and bank-profile checks passed (**20** and **27** checks). The final manifest verification passed **7** checks. The combined checks log also contains a superseded manifest attempt; use the separate verified manifest log for the final manifest result. Evidence: [runner and bank-profile checks](../artifacts/native/rebuild/organization_final_checks_20261108.out), [final manifest verification](../artifacts/native/rebuild/organization_manifest_verified_20261108.out).
- Markdown links and source-feature patterns were checked; the independent Sol review repaired and approved the organization.
- Removed 15 generated `__pycache__` / `.pytest_cache` directories. Preserved `.venv`, ignored evidence, private data, backups, and Git history.

Test-group membership and rerun guidance are documented in [tests/README.md](../tests/README.md). The test manifest is [tests/feature_manifest.json](../tests/feature_manifest.json).
