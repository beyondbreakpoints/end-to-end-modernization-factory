# Backlog

Status reflects repository work on `NG/Dev` and the user's 2026-11-11 report that Fabric execution completed with all Silver notebooks marked `Succeeded`. Live execution was confirmed by the user, not independently inspected in this session.

## Completed

- [x] Establish repository layout and keep Fabric items under `fabric/`.
- [x] Add source pack and SliceDW materials without including `3_answer_key/`.
- [x] Create the schema-enabled `lh_polarslice` lakehouse and five Bronze ingestion notebooks plus `nb_bronze_run_all`.
- [x] Align notebook paths and upload instructions to source folders directly under OneLake `Files/`.
- [x] User ran Bronze in Fabric; all notebook assertions passed.
- [x] Implement typed Silver transformations, quality flags, source lineage, and the dependency-ordered Silver runner.

Verified Bronze row counts from that run:

| Table | Rows | Table | Rows |
|---|---:|---|---:|
| `aloha_checks` | 2,505 | `aloha_items` | 7,341 |
| `as400_counts` | 380 | `as400_itemmast` | 19 |
| `as400_shipments` | 564 | `master_calendar` | 5 |
| `master_menu` | 19 | `master_recipes` | 62 |
| `master_stores` | 10 | `micros_check_detail` | 19,880 |
| `micros_check_header` | 6,815 | `online_customers` | 1,489 |
| `online_order_items` | 6,398 | `online_orders` | 2,302 |

## Silver — implemented and successfully executed in Fabric

- [x] Sync the updated `NG/Dev` branch to Fabric and run `nb_silver_run_all` after Bronze; the user reported all notebooks `Succeeded` on 2026-11-11.
- [x] Fix the invalid unique-price assertion and price-only Aloha mapping after the initial master-data run failed; verify row-preserving mappings with local Spark regressions.
- [x] Complete the embedded row-count and anomaly assertions in the successful notebook run, including MICROS gifts/voids/duplicates, Aloha post-midnight checks, app cancellations, and AS/400 credit/KG handling.
- [x] Complete POS matching assertions: 1,637 unique MICROS matches, 630 unique Aloha matches, and one explicitly ambiguous Aloha match retained for reconciliation.
- [x] Update the backlog and roadmap with the successful Fabric execution report.
- [ ] Archive the Silver runner's count/quality output and run identifier for the dossier; no output export or successful-run batch ID was supplied with the status report.

## Gold and reconciliation

- [x] Assess and agree the Gold plan; user approved milestone 1 (reference inputs plus legacy reproduction) on 2026-11-11 and requested a stop for feedback before the next milestone.
- [x] Read and document the legacy SQL/SSIS dependencies and business rules in `docs/gold-legacy.md`.
- [x] Implement versioned royalty, hierarchy, legacy Aloha map, and manual-adjustment inputs, preserving both duplicate-credit rows.
- [x] Implement `nb_gold_legacy` and `nb_gold_run_legacy`; locally compare every report metric to an independent raw-source/Decimal baseline and verify idempotent reruns.
- [ ] Sync `NG/Dev`, run `nb_gold_run_legacy` in Fabric, and capture statuses, batch ID, counts, and output totals. Local Spark tests do not exercise Fabric Delta writes/orchestration.
- [ ] Compare legacy Gold with actual SliceDW/externally provided validation exports; do not claim a deployed SQL Server match from local tests alone.
- [ ] Obtain user feedback/confirmation before starting corrected Gold; implementation stops at milestone 1.
- [ ] Build corrected Gold outputs with explicit, documented treatments for the known legacy defects, including tax-inclusive Aloha sales, royalty holiday duration, and store 1078's opening date.
- [ ] Reconcile legacy and corrected outputs to source totals and the offline answer key. Do not copy answer-key material into Git or production artifacts.
- [ ] Resolve or explicitly document the flagged ambiguous Aloha order match without inventing a link or counting online sales twice.

## Azure SQL, dossier, and delivery

- [ ] Implement the Azure SQL deployment and supporting scripts in `sql/`.
- [ ] Prepare the final dossier covering source lineage, legacy reproduction, corrections, reconciliation, and operational instructions.
- [ ] Review all changes for secrets and answer-key content; update the root README and verify `main` contains the required Fabric items.
- [ ] Open the final PR from `NG/Dev` to `main` after all phases are complete.

## Operational follow-up

- [ ] Confirm whether the user has any pending Fabric Source control changes to commit (the handoff says they reported none).
- [x] Obtain user confirmation of successful Silver Fabric execution; all notebooks were reported `Succeeded`.
- [ ] When guiding workspace actions, proceed step by step. A prior reference to “item 3” was ambiguous; the handoff inferred it meant the upload step, but it may have meant Gold. Confirm before acting on that old ambiguity.