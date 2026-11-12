# Backlog

Status reflects repository work on `NG/Dev`, the user's successful Silver execution report, and their 2026-11-12 confirmation that `nb_gold_run_legacy` ran successfully. Live execution was confirmed by the user, not independently inspected in this session.

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
- [x] Archive the Silver runner's count/quality output and run identifier for the dossier. Silver batch ID confirmed `5d6ca0a2-b89d-4b3d-b54a-8429243d0871` (all 14 tables); row counts match Bronze-verified counts. Archived in `docs/gold-corrected.md`.

## Gold and reconciliation

- [x] Assess and agree the Gold plan; user approved milestone 1 (reference inputs plus legacy reproduction) on 2026-11-11 and requested a stop for feedback before the next milestone.
- [x] Read and document the legacy SQL/SSIS dependencies and business rules in `docs/gold-legacy.md`.
- [x] Implement versioned royalty, hierarchy, legacy Aloha map, and manual-adjustment inputs, preserving both duplicate-credit rows.
- [x] Implement `nb_gold_legacy` and `nb_gold_run_legacy`; locally compare every report metric to an independent raw-source/Decimal baseline and verify idempotent reruns.
- [x] Resolve the incorrect default lakehouse attachment and missing native parameter-cell markers; add Silver runner output-batch validation.
- [x] Run `nb_gold_run_legacy` in Fabric; the user confirmed successful execution on 2026-11-12.
- [x] Archive the supplied Gold batch ID, all 18 output counts, five daily totals, nine invoices, and ten cheese-variance rows in `docs/gold-legacy.md`. User-supplied batch `07e7a5f4-2a8a-4884-9b80-58fb1c76c640` matches the local contracts and compared financial/quantity values exactly.
- [ ] Archive the successful Silver ID and full Gold input manifest and remaining report outputs for dossier-level lineage and live row-by-row evidence; the supplied console extract does not cover these.
- [ ] Compare legacy Gold with actual SliceDW/externally provided validation exports; do not claim a deployed SQL Server match from local tests alone.
- [x] Obtain user approval to start corrected Gold on 2026-11-12; user also approved per-comp pre-tax rounding and deriving Aloha gross from net plus discounts.
- [x] Implement `nb_gold_corrected` and `nb_gold_run_corrected`, preserving legacy/reference outputs. Document rules and exact local source-based comparisons in `docs/gold-corrected.md`, including the six-month holiday with 1078's unchanged authoritative opening date.
- [x] User confirmed corrected Gold `Succeeded 100%` on 2026-11-12. Archive batch `175fdd4c-8417-4a00-b951-f563f4d533fd`, all 11 counts, five daily totals, eight invoices, ten cheese rows, and four attribution counts in `docs/gold-corrected.md`; supplied results match the baseline exactly.
- [x] Archive remaining corrected report values for dossier. Promo total **$20,219.10** and all-ingredient food variance cost **$4,097.42** confirmed as live Fabric values: runner passed all embedded discount-reconciliation and food-cost-balance assertions with matching row counts. Archived in `docs/gold-corrected.md`.
- [x] Obtain user feedback/confirmation after corrected Gold; user triggered planning session on 2026-11-12 — proceeding with comparison/bridge.
- [x] Implement `nb_gold_comparison` and `nb_gold_run_comparison`; produces `gold.comparison_bridge`, `gold.comparison_summary`, `gold.comparison_daily`, `gold.comparison_invoices`. Verifies bridge nets to $30,679.82 net-sales delta and $3,809.74 invoice delta.
- [x] Synced to Fabric and ran `nb_gold_run_comparison` on 2026-11-12. Batch `ff7553d1-0cde-409b-9caf-06cebecfb179` succeeded. Full waterfall, daily, and invoice comparison archived in `docs/gold-comparison.md`. Bridge nets exactly to −$30,679.82 and −$3,809.74.
- [ ] Reconcile legacy and corrected outputs to source totals and the offline answer key. Do not copy answer-key material into Git or production artifacts.
- [x] Explicitly retain the ambiguous Aloha app order without a definitive link or incremental revenue in corrected attribution; POS remains the sales system of record. External reconciliation remains pending.

## Azure SQL, dossier, and delivery

- [ ] Implement the Azure SQL deployment and supporting scripts in `sql/`.
- [ ] Prepare the final dossier covering source lineage, legacy reproduction, corrections, reconciliation, and operational instructions.
- [ ] Review all changes for secrets and answer-key content; update the root README and verify `main` contains the required Fabric items.
- [ ] Open the final PR from `NG/Dev` to `main` after all phases are complete.

## Operational follow-up

- [ ] Confirm whether the user has any pending Fabric Source control changes to commit (the handoff says they reported none).
- [x] Obtain user confirmation of successful Silver Fabric execution; all notebooks were reported `Succeeded`.
- [ ] When guiding workspace actions, proceed step by step. A prior reference to “item 3” was ambiguous; the handoff inferred it meant the upload step, but it may have meant Gold. Confirm before acting on that old ambiguity.