# Test organization

Tests live under feature folders. `feature_manifest.json` is the source of truth: `features` lists the test files for each feature, while `source_features` maps repository source paths or globs to recommended feature reruns. The isolated runner reads the manifest and discovers tests recursively.

## Run tests

From the repository root:

- Full suite: `python tools/run_full_tests.py`
- Preview all selected test files: `python tools/run_full_tests.py --list`
- One feature: `python tools/run_full_tests.py --feature statements`
- Several features: `python tools/run_full_tests.py --feature statements --feature planning`
- A feature directory or explicit file: `python tools/run_full_tests.py tests/statements` or `python tools/run_full_tests.py tests/statements/test_statement_rows.py`
- Pass pytest options after `--`: `python tools/run_full_tests.py --feature ui -- -v --tb=short`

Feature names are `accounts`, `security`, `backup`, `statements`, `tax`, `planning`, `income`, `rebuild`, `infrastructure`, and `ui`. `pytest` collection is limited to `tests/`; operational scripts and native UI harnesses under `tools/` are not pytest targets.

## Rerun matrix

Run the directly affected feature first. Also rerun dependent features when a shared contract crosses feature boundaries:

| Changed area | Direct feature | Dependent reruns |
|---|---|---|
| Account holders, banks, accounts | `accounts` | `security`, `backup`, `statements`, `planning` |
| Login, encryption, settings, session | `security` | `accounts`, `backup`, `infrastructure`, `tax` (tax document password checks) |
| Backup and restore | `backup` | `security`, `accounts`, `infrastructure` |
| Statement parsing/import/mapping and bank profiles | `statements` | `planning`, `income`, `tax` |
| Tax engine or tax documents | `tax` | `income`, `planning`, `statements` |
| FD, family, investments, prediction | `planning` | `income`, `statements`, `tax` |
| Income and interest calculations | `income` | `planning`, `tax` |
| Rebuild scripts and collection | `rebuild` | `infrastructure`, plus features touched by the rebuild |
| Shared runner, database fixtures, session reload | `infrastructure` | all affected feature folders |
| Shared UI widgets/theme | `ui` | the feature screens using the changed widget |

For precise recommendations, match changed source paths against `source_features` in the manifest and combine the listed features with the dependent reruns above. Use the full suite before integrating broad shared changes.

## Native UI regressions

Headless pytest does not cover all native Windows flows. The native S-mode feature reports run through the fresh scratch wrapper described in the [real-UI runbook](../tools/real_ui_tests/REBUILD_PLAN.md). For each flow, run `python tools/real_ui_tests/run_on_scratch.py --fresh tools/real_ui_tests/<script>` so mutations stay on fresh scratch data.

| Flow | Native script |
|---|---|
| S03 Income | `rebuild_p3_03_income.py` |
| S04 Fixed Deposits | `rebuild_p3_04_fixed_deposits.py` |
| S05 Statements | `rebuild_p3_05_statement_import.py` |
| S06 Tax documents | `rebuild_p3_06_tax_documents.py` |
| S09 Settings | `rebuild_p3_09_settings.py` |
| S14 Password change | `rebuild_p3_14_password_change.py` |
