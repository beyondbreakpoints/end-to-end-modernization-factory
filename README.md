# end-to-end-modernization-factory

Polar Slice Pizza legacy-to-Fabric modernization (fictional data).

| Path | Contents |
|---|---|
| `data/` | Source pack: `1_source_systems/` (Bronze input), `2_legacy_warehouse_slicedw/` (SliceDW, step 5), `generator/`. The answer key is intentionally not in the repo. |
| `fabric/` | Fabric Git-synced items: lakehouse `lh_polarslice`, Bronze and Silver notebooks, separate legacy/corrected Gold notebooks, CopyJob. Set the workspace Git folder to `/fabric`. |
| `sql/` | Reserved for Azure SQL scripts (step 5). |
| `docs/` | Instructions, starting with [uploading source files to OneLake](docs/onelake-upload.md). |

Steps: 1 Bronze, 2 Silver, and 3 Gold legacy/corrected milestones successfully run in Fabric, with supplied Gold outputs matching the local baselines. Comparison/bridge, 4 external reconciliation, and 5 Azure SQL / dossier remain ahead.

For Gold milestone 1, sync `NG/Dev` and run `nb_gold_run_legacy` after Silver. See [legacy Gold contracts, execution steps, and baseline evidence](docs/gold-legacy.md).

For approved Gold milestone 2, run `nb_gold_run_corrected` against the existing Silver/reference snapshots. It preserves legacy outputs. See [corrected Gold rules, contracts, baseline, and Fabric run gate](docs/gold-corrected.md).