# end-to-end-modernization-factory

Polar Slice Pizza legacy-to-Fabric modernization (fictional data).

| Path | Contents |
|---|---|
| `data/` | Source pack: `1_source_systems/` (Bronze input), `2_legacy_warehouse_slicedw/` (SliceDW, step 5), `generator/`. The answer key is intentionally not in the repo. |
| `fabric/` | Fabric Git-synced items: lakehouse `lh_polarslice`, Bronze notebooks, CopyJob. Set the workspace Git folder to `/fabric`. |
| `sql/` | Reserved for Azure SQL scripts (step 5). |
| `docs/` | Instructions, starting with [uploading source files to OneLake](docs/onelake-upload.md). |

Steps: 1 Bronze (done here), 2 Silver, 3 Gold, 4 reconciliation, 5 Azure SQL / dossier.