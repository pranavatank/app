# Tools guide

Tools are grouped by purpose. Most are command-line utilities; native interactive UI procedures are kept in `real_ui_tests/` and are separate from headless pytest.

## Test commands

Use the suite runner with the project Python environment. The test-group names are `accounts`, `security`, `backup`, `statements`, `tax`, `planning`, `income`, `rebuild`, `infrastructure`, and `ui`.

```powershell
.venv\Scripts\python.exe tools/run_full_tests.py
.venv\Scripts\python.exe tools/run_full_tests.py --feature accounts
.venv\Scripts\python.exe tools/run_full_tests.py --feature statements --feature planning
.venv\Scripts\python.exe tools/run_full_tests.py --list
```

Append extra pytest options after `--`, or pass a test directory/module path directly. See [tests/README.md](../tests/README.md) for the feature manifest and rerun guidance. `tools/real_ui_tests/` contains native GUI scripts; they may open windows, interact with the app, or create evidence, so follow the [visual testing guide](../docs/VISUAL_TESTING_GUIDE.md) and [rebuild runbook](real_ui_tests/REBUILD_PLAN.md). Those scripts are not run by the headless feature groups.

## Maintenance and diagnostics

- `audit_repository_privacy.py` — scan repository content for privacy issues.
- `extraction_audit.py`, `taxdoc_audit.py`, `tax_reconcile.py` — inspect statement extraction and tax-document reconciliation.
- `rebuild_verify.py` — verify rebuild-related outputs.
- `test_prediction_engine.py` — focused legacy standalone prediction check; prefer the feature-group runner for normal test selection.

## Data import and maintenance

- `pipeline_import.py` — statement parsing/import pipeline.
- `taxdoc_import.py` — tax-document import CLI.
- `backfill_transactions.py` — transaction backfill utility. Never run it against the rebuilt database. Its `--dry-run` mode can inspect intended changes; do not run a write against the rebuild.
- `delete_account.py` — destructive account deletion utility. Use `--dry-run` first and verify the account identity and dependencies before confirming a deletion.
- `private_sources.py` — source-document locator used by rebuild workflows; it reads private sources and should not copy or modify them.

Private source financial documents under `data/data/` and files under `backups/` must be treated as user data. Diagnostic logs, screenshots, and generated evidence belong in the ignored paths documented by the runbook. Do not commit those materials.
