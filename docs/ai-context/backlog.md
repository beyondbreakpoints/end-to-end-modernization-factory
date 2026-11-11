# Backlog

Status reflects the prior session handoff; it has not been independently refreshed against Fabric or GitHub.

## Completed

- [x] Establish repository layout and keep Fabric items under `fabric/`.
- [x] Add source pack and SliceDW materials without including `3_answer_key/`.
- [x] Create the schema-enabled `lh_polarslice` lakehouse and five Bronze ingestion notebooks plus `nb_bronze_run_all`.
- [x] Align notebook paths and upload instructions to source folders directly under OneLake `Files/`.
- [x] User ran Bronze in Fabric; all notebook assertions passed.

Verified row counts from that run:

| Table | Rows | Table | Rows |
|---|---:|---|---:|
| `aloha_checks` | 2,505 | `aloha_items` | 7,341 |
| `as400_counts` | 380 | `as400_itemmast` | 19 |
| `as400_shipments` | 564 | `master_calendar` | 5 |
| `master_menu` | 19 | `master_recipes` | 62 |
| `master_stores` | 10 | `micros_check_detail` | 19,880 |
| `micros_check_header` | 6,815 | `online_customers` | 1,489 |
| `online_order_items` | 6,398 | `online_orders` | 2,302 |

## Next: Silver

- [ ] Define Silver table schemas, stable keys, parsing rules, and quality flags for each source.
- [ ] Implement typed Silver transformations for master data, MICROS, Aloha, online app, and AS/400; keep source lineage.
- [ ] Resolve cross-system matching for online/POS orders and the 631 Aloha web checks without counting app orders twice.
- [ ] Preserve flags/evidence for MICROS gifts, void-after-close rows, March 12 duplicates at store 1061, app cancellations/duplicate accounts, Aloha unknown items and tax-inclusive amounts, AS/400 credits, and KG cheese shipments.
- [ ] Add targeted validation for business-date boundaries, money/decimal parsing, unit conversion, credit signs, and row-level anomaly handling.
- [ ] Run Silver in Fabric and capture actual counts and quality results.

## Gold and reconciliation

- [ ] Read and document the applicable rules in `data/2_legacy_warehouse_slicedw/02_programmability.sql` and the associated legacy SQL/SSIS materials.
- [ ] Build Gold outputs that reproduce SliceDW numbers before changing business logic; record comparison totals and explain any remaining mismatches.
- [ ] Build corrected Gold outputs with explicit, documented treatments for the known legacy defects, including tax-inclusive Aloha sales, royalty holiday duration, and store 1078's opening date.
- [ ] Reconcile legacy and corrected outputs to source totals and the offline answer key. Do not copy answer-key material into Git or production artifacts.

## Azure SQL, dossier, and delivery

- [ ] Implement the Azure SQL deployment and supporting scripts in `sql/`.
- [ ] Prepare the final dossier covering source lineage, legacy reproduction, corrections, reconciliation, and operational instructions.
- [ ] Review all changes for secrets and answer-key content; update the root README and verify `main` contains the required Fabric items.
- [ ] Open the final PR from `NG/Dev` to `main` after all phases are complete.

## Operational follow-up

- [ ] Confirm whether the user has any pending Fabric Source control changes to commit (the handoff says they reported none).
- [ ] When guiding workspace actions, proceed step by step. A prior reference to “item 3” was ambiguous; the handoff inferred it meant the upload step, but it may have meant Gold. Confirm before acting on that old ambiguity.