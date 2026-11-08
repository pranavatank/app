# Repository structure and organization audit

## Current layout

- `core/` — authentication, database, encryption, backup, settings, and session services.
- `models/` — SQLite data access and record models.
- `engines/` — financial calculations, statement parsing, tax-document processing, and FD planning.
- `ui/` — PySide6 screens, dialogs, themes, and reusable widgets.
- `tests/` — headless automated tests; group membership is documented in [tests/README.md](../tests/README.md).
- `tools/` — command-line diagnostics, maintenance utilities, and a separate `real_ui_tests/` native GUI harness.
- `docs/` — current guides and product specifications, indexed in [docs/README.md](README.md); completed plans are under `docs/archive/`.
- `data/`, `backups/` — local application and private financial data. Treat as user data; do not reorganize or alter during source cleanup.

## Organization decisions

- Added navigation indexes for documentation and tools, and replaced the root README's stale file-by-file tree with a concise architecture map.
- Archived superseded migration, redesign, pipeline, UI campaign, prediction, and completed rebuild plans under `docs/archive/`. The retained audit/rebuild specification remains linked from current readiness and test notes because it includes still-referenced behavior and calculation details.
- Kept native real-UI scripts in their existing location: they require a visible application session and do not belong in headless test groups.
- Kept `tools/test_prediction_engine.py`: it is a distinct standalone check, while its normal pytest counterpart can be selected through the test manifest.
- No tools were removed: current coverage and safety semantics have not been shown to be redundant.

## Deferred runtime refactor inventory

This documentation pass does not restructure runtime packages. Future code organization can assess these clusters without moving them during documentation cleanup:

- `engines/statement_parser.py`, `statement/`, `bank_parsers/`, and parser utilities: overlapping statement parsing layers that need import and coverage mapping first.
- `engines/tax_engine.py`, `advance_tax_engine.py`, tax-document parsers, and their persistence model: tax calculations and document ingestion have distinct boundaries but share UI-facing concepts.
- `engines/fd_*`, `family_fd_engine.py`, rate sources, and planner UI/dialog components: planner responsibilities span calculations, sources, and presentation.
- Large root-level `ui/*_screen.py` modules alongside `ui/dialogs/` and `ui/widgets/`: screen decomposition should follow current feature tests and UI ownership.
- `core/database.py` and the models package: schema initialization and model persistence are coupled; migration impact should be inventoried before extraction.

Before any later runtime moves, map imports, test ownership, persistence boundaries, and native UI entry points. Keep private data, backups, ignored test evidence, and Git history intact.

## Validation and completion

- All 76 original test modules and their functions were retained; the reorganized suite now has 77 modules including the manifest regression check. The isolated full suite completed with **775 passed and 8 skipped** across all 77 modules. Evidence: [organization full suite](../tools/real_ui_tests/screenshots/rebuild/organization_full_20261108.out).
- Final runner and bank-profile checks passed (**20** and **27** checks). The final manifest verification passed **7** checks. The combined checks log also contains a superseded manifest attempt; use the separate verified manifest log for the final manifest result. Evidence: [runner and bank-profile checks](../tools/real_ui_tests/screenshots/rebuild/organization_final_checks_20261108.out), [final manifest verification](../tools/real_ui_tests/screenshots/rebuild/organization_manifest_verified_20261108.out).
- Markdown links and source-feature patterns were checked; the independent Sol review repaired and approved the organization.
- Removed 15 generated `__pycache__` / `.pytest_cache` directories. Preserved `.venv`, ignored evidence, private data, backups, and Git history.

Test-group membership and rerun guidance are documented in [tests/README.md](../tests/README.md). The test manifest is [tests/feature_manifest.json](../tests/feature_manifest.json).
