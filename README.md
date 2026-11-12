# end-to-end-modernization-factory

AI-Accelerated Legacy-to-Fabric Modernization — Polar Slice Pizza fictional case study.
All six phases complete. See [docs/dossier.md](docs/dossier.md) for the full end-to-end record.

## Status

| Phase | Notebooks | Status |
|---|---|---|
| 1 Bronze | `nb_bronze_*`, `nb_bronze_run_all` | ✅ All 14 tables loaded |
| 2 Silver | `nb_silver_*`, `nb_silver_run_all` | ✅ Typed, flagged, matched |
| 3 Gold legacy | `nb_gold_legacy`, `nb_gold_run_legacy` | ✅ SliceDW reproduced — net sales $299,572.90 |
| 3 Gold corrected | `nb_gold_corrected`, `nb_gold_run_corrected` | ✅ Corrected results — net sales $268,893.08 |
| 3 Gold comparison | `nb_gold_comparison`, `nb_gold_run_comparison` | ✅ $30,679.82 delta attributed across 5 categories |
| 4 Reconciliation | `nb_gold_reconcile`, `nb_gold_run_reconcile` | ✅ Zero residual vs Silver sources |
| 5 Azure SQL | `sql/` scripts | ✅ DDL, load procedure, validation |
| 5 Dossier | `docs/dossier.md` | ✅ Complete |

## Repository layout

| Path | Contents |
|---|---|
| `data/1_source_systems/` | Source pack (Bronze input): MICROS, Aloha, AS/400, online app, master data |
| `data/2_legacy_warehouse_slicedw/` | SliceDW SQL artifacts and SSIS packages (legacy reference) |
| `data/generator/` | Fictional data generator scripts |
| `fabric/` | Fabric Git-synced items — lakehouse `lh_polarslice` and all notebooks |
| `sql/` | Azure SQL corrected Gold mart — DDL, load procedure, validation |
| `docs/` | Dossier, Gold evidence docs, OneLake upload instructions, AI context |
| `tests/` | Local PySpark regression tests |

The answer key (`3_answer_key/`) is excluded from the repository by `.gitignore`.

## Quick start

1. Upload source files to OneLake — see [docs/onelake-upload.md](docs/onelake-upload.md)
2. Sync `NG/Dev` to the Fabric workspace (Git folder: `/fabric`)
3. Run `nb_bronze_run_all` → `nb_silver_run_all` → `nb_gold_run_legacy` → `nb_gold_run_corrected`
4. Run `nb_gold_run_comparison` and `nb_gold_run_reconcile` for analysis
5. Deploy to Azure SQL — see [sql/README.md](sql/README.md)

See [docs/dossier.md](docs/dossier.md) for full results, batch IDs, and operational notes.