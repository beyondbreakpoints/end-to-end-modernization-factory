# end-to-end-modernization-factory

Polar Slice Pizza legacy-to-Fabric modernization (fictional data).

| Path | Contents |
|---|---|
| `data/` | Source pack: `1_source_systems/` (Bronze input), `2_legacy_warehouse_slicedw/` (SliceDW, step 5), `generator/`. The answer key is intentionally not in the repo. |
| `fabric/` | Fabric Git-synced items: lakehouse `lh_polarslice`, Bronze and Silver notebooks, legacy Gold notebooks, CopyJob. Set the workspace Git folder to `/fabric`. |
| `sql/` | Reserved for Azure SQL scripts (step 5). |
| `docs/` | Instructions, starting with [uploading source files to OneLake](docs/onelake-upload.md). |

Steps: 1 Bronze and 2 Silver successfully run in Fabric; 3 Gold legacy milestone implemented, Fabric run pending; corrected Gold, 4 reconciliation, and 5 Azure SQL / dossier remain ahead.

For Gold milestone 1, sync `NG/Dev` and run `nb_gold_run_legacy` after Silver. See [legacy Gold contracts, execution steps, and baseline evidence](docs/gold-legacy.md).