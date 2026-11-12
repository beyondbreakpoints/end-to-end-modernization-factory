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

## 3. Gold — legacy and corrected milestones successfully executed in Fabric

First reproduce SliceDW's existing business rules and numbers as closely as possible from the legacy SQL and SSIS artifacts. Only after establishing that baseline, implement corrected marts and identify each rule that changes a result.

**Milestone 1:** the user approved reference inputs and legacy reproduction only on 2026-11-11. `nb_gold_reference_data`, `nb_gold_legacy`, and `nb_gold_run_legacy` implement that scope. Local Spark execution compares every keyed report metric with an independent source-based Decimal baseline, including all 190 food-cost rows, and verifies reruns and batch consistency. Contracts, run instructions, and locally calculated totals are in [`../gold-legacy.md`](../gold-legacy.md).

**Current status:** on 2026-11-12, the user confirmed `nb_gold_run_legacy` ran successfully after resolving an incorrect lakehouse attachment and fixing native parameter-cell serialization. This confirms user-reported Fabric execution, not an independently inspected comparison of live outputs to the local baseline.

**Evidence review:** the user supplied Gold batch `07e7a5f4-2a8a-4884-9b80-58fb1c76c640`, all 18 output counts, five daily totals, nine invoices, and ten cheese-variance rows. These match the documented counts and independently calculated financial/quantity baseline exactly; the supplied results are archived in [`../gold-legacy.md`](../gold-legacy.md). Net sales are 299,572.90 and invoice amount due is 21,061.48. This is not a full live row-by-row reconciliation of every report.

**Milestone 2:** approved by the user on 2026-11-12 and implemented in `nb_gold_corrected` and `nb_gold_run_corrected`. Corrected POS-led marts remove gift/void/duplicate sales, use Aloha DOB and tax-exclusive values, retain app links only for attribution, apply the contractual holiday and single credit, and use signed base-unit receipts and corrected SKU recipes. The user approved per-comp cent rounding, with Aloha gross derived from net plus discounts. Local comparisons match the independent raw-source Decimal baseline exactly: net sales 268,893.08, invoices 17,251.74, food variance cost 4,097.42. See [`../gold-corrected.md`](../gold-corrected.md).

**Corrected Fabric evidence:** on 2026-11-12 the user reported `nb_gold_corrected Succeeded 100%` and supplied batch `175fdd4c-8417-4a00-b951-f563f4d533fd`. All 11 counts, five daily totals, eight invoice rows, ten cheese rows, and four attribution counts match the local baseline exactly and are archived in [`../gold-corrected.md`](../gold-corrected.md). Live net sales total 268,893.08 and invoices total 17,251.74. The all-ingredient variance and promo totals above remain local-only; their live values were not supplied.

**Next action:** obtain user feedback/confirmation before implementing the legacy-to-corrected comparison/bridge with attributable, balancing rule changes. Full input lineage and remaining live report evidence still need archiving for the dossier; deployed SliceDW/external validation comparisons remain pending.

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