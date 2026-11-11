# Roadmap

The sequence is intentionally gated: each phase should produce inspectable evidence before the next depends on it. Detailed remaining tasks are in [`backlog.md`](backlog.md).

## 1. Bronze — completed

Ingest each source faithfully into raw Delta tables in `bronze`, attach file/batch lineage, and make the load rerunnable. The user ran the notebooks in Fabric and reported that all assertions passed. Preserve the observed row counts as a baseline, but re-run if the workspace or input files change.

**Gate:** all five loaders and the orchestration notebook complete; expected source-file/row checks pass; all tables retain ingestion metadata.

## 2. Silver — next

Create typed, standardized Delta tables in `silver`. Handle each source's date, money, identifier, and unit conventions. Retain flags and source evidence for anomalies rather than silently dropping rows. Establish explicit POS/app matching so completed online orders are linked to, not added on top of, till sales.

**Gate:** transformations run in Fabric; keys and business-date rules are validated; anomaly and matching counts are explainable; source lineage survives.

## 3. Gold — legacy reproduction, then corrected results

First reproduce SliceDW's existing business rules and numbers as closely as possible from the legacy SQL and SSIS artifacts. Only after establishing that baseline, implement corrected marts and identify each rule that changes a result.

**Gate:** legacy reproduction is compared to SliceDW; corrected outputs document their differences and reconcile to Silver/source totals.

## 4. Reconciliation

Compare Bronze/Silver source evidence, legacy Gold, corrected Gold, and the answer key. Use the answer key only as a validation reference outside the repository. Explain variances rather than treating a matching grand total as sufficient proof.

**Gate:** documented totals and row-level explanations cover known data defects, cross-system matches, units, promotions, taxes, and royalty treatment.

## 5. Azure SQL and dossier

Use `sql/` for the requested Azure SQL deployment work and final supporting scripts. Assemble the project dossier with architecture, operating steps, legacy-vs-corrected results, and reconciliation evidence.

**Gate:** deployment is repeatable and the dossier is self-contained and traceable to repository artifacts.

## 6. Final review and presentation

Review the complete diff for secrets, local-only data, and answer-key content; update the root README; confirm the target branch has the Fabric items; then present the completed work through one PR from `NG/Dev` to `main`.

**Gate:** final branch/PR contains only publishable materials and the Fabric workspace configuration is understood before changing branches.