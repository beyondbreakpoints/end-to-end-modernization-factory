# Roadmap

The sequence is intentionally gated: each phase should produce inspectable evidence before the next depends on it. Detailed remaining tasks are in [`backlog.md`](backlog.md).

## 1. Bronze — completed

Ingest each source faithfully into raw Delta tables in `bronze`, attach file/batch lineage, and make the load rerunnable. The user ran the notebooks in Fabric and reported that all assertions passed. Preserve the observed row counts as a baseline, but re-run if the workspace or input files change.

**Gate:** all five loaders and the orchestration notebook complete; expected source-file/row checks pass; all tables retain ingestion metadata.

## 2. Silver — implemented and successfully executed in Fabric

Create typed, standardized Delta tables in `silver`. Handle each source's date, money, identifier, and unit conventions. Retain flags and source evidence for anomalies rather than silently dropping rows. Establish explicit POS/app matching so completed online orders are linked to, not added on top of, till sales.

**Gate:** transformations run in Fabric; keys and business-date rules are validated; anomaly and matching counts are explainable; source lineage survives.

**Current status:** on 2026-11-11, the user confirmed Fabric execution completed with all Silver notebooks marked `Succeeded` after the menu-mapping fixes. This confirms the execution gate and embedded assertions passed for that run; the workspace was not independently inspected in this session.

**Carry-forward notes:** the matching assertions require 1,637 unique MICROS links, 630 unique Aloha links, and one retained ambiguous Aloha match. The ambiguity remains an explicit Gold/reconciliation task, not a notebook failure. Archive the successful run's count/quality output and run identifier for the dossier; these were not included in the user's status report.

## 3. Gold — next: legacy reproduction, then corrected results

First reproduce SliceDW's existing business rules and numbers as closely as possible from the legacy SQL and SSIS artifacts. Only after establishing that baseline, implement corrected marts and identify each rule that changes a result.

**Next action:** inspect `data/2_legacy_warehouse_slicedw/sql/02_programmability.sql` and associated SQL/SSIS artifacts, document the rule dependencies, and agree the Gold plan before implementing. Gold work has not started.

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