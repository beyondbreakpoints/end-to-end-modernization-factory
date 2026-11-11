# Architecture decisions

These decisions are captured from the prior project handoff. Validate against the live Fabric workspace before changing workspace bindings or data paths.

## Repository and deployment boundary

- Keep Fabric items under `fabric/`; the Fabric workspace Git directory is `/fabric` on `NG/Dev`.
- Keep source data/code and legacy warehouse materials under `data/`, Fabric artifacts under `fabric/`, and reserve `sql/` for the final Azure SQL step.
- Commit the source pack and implementation code, but never commit `3_answer_key/`. The answer key is only an offline validation aid and must not enter the repository or pipeline.
- Fabric Git synchronizes workspace items, not lakehouse file data. Upload the source folders separately to the lakehouse `Files/` root.

## Lakehouse and notebook conventions

- Use schema-enabled lakehouse `lh_polarslice` (`defaultSchema` is `dbo`) and place Bronze tables in schema `bronze`. The notebook artifacts bind to this lakehouse; `nb_bronze_run_all` passes `useRootDefaultLakehouse: True` when invoking child notebooks to avoid cross-lakehouse reference errors.
- Notebook source uses Fabric's `notebook-content.py` format with `.platform` metadata and a `batch_id` parameter cell.
- The source upload layout is rooted directly at `Files/`, with `aloha/`, `as400_commissary/`, `master_data/`, `micros/`, and `online_app/` beneath it. Notebooks use `BASE = "Files"`; do not introduce a `polar_slice/` prefix without coordinating the upload layout and all consumers.
- Apply `with_meta(df, system)` directly to each file read, before later projections can discard file metadata. Retain `_source_system`, `_source_file`, `_file_modified`, `_ingest_ts`, and `_batch_id` on ingested records.

## Medallion contracts

### Bronze

- Preserve the source representation: string-valued/raw columns, no business cleaning, casting, or deduplication.
- Write Delta tables with overwrite and overwrite-schema semantics so reruns replace the current batch consistently.
- Use schema-qualified Bronze tables; avoid flat `bronze_`-prefixed table names.
- Use notebooks for ingestion rather than copy jobs. The orchestration notebook runs the five source notebooks and reports table counts.

### Silver (planned)

- Create typed, cleaned Delta tables in schema `silver`, while retaining source lineage and explicit anomaly/quality flags.
- Decode AS/400 CYYMMDD dates, implied decimals, trailing signs, and unit differences; parse Aloha business dates/times and split tax-inclusive amounts; map unknown item codes using menu evidence.
- Identify rather than silently erase gift checks, post-close voids, duplicate MICROS checks, online/POS overlap, cancelled orders, duplicate customer accounts, and unmatched web checks. Later layers must choose their treatment explicitly.

### Gold (planned)

- Keep separate, explainable outputs for **legacy reproduction** and **corrected business results**. Implement SliceDW rules first so differences can be attributed to specific corrections.
- Use POS/till checks as the sales system of record; link online orders for attribution, not as incremental revenue.
- Keep reconciliation outputs distinct from production marts and use the external answer key only for validation.

## Important source-specific semantics

- MICROS check identity joins header/detail by store, business date, and check number. Discount item codes include 9001 (2-for-1 Tuesday), 9002 (WELCOME10), and 9003 (staff 50%). Gift checks are not revenue/royalty; post-close void rows can net a prior check to zero; duplicated checks exist at store 1061 on March 12.
- Aloha check identity is store + DOB + CHECKID because CHECKID restarts daily. DOB is the business day ending at 4 a.m.; amounts are tax-inclusive and require tax separation. Some web checks have no direct app link, and item codes require mapping.
- AS/400 dates use CYYMMDD; numeric fields have implied decimals, and a trailing minus denotes a credit. Some cheese shipments are in KG rather than cases. Actual usage is opening count + shipments (in base units) - closing count; compare this with recipe-based theoretical usage.
- App completed orders duplicate POS/till sales. There are cancelled orders, duplicate customer accounts, late-arriving March 13 business-day orders, and small Aloha amount discrepancies; preserve the evidence for explicit matching and reconciliation decisions.

## Workspace branch safety

Fabric branch changes do not remove OneLake data, but can remove workspace items not present on the selected branch. Work from `NG/Dev`; do not switch the Fabric workspace to a branch that predates `fabric/` without first protecting or recreating the lakehouse item.