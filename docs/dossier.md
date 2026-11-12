# Polar Slice Pizza — Modernization Factory Dossier

AI-Accelerated Legacy-to-Fabric Modernization of a fictional 10-store Ontario pizza chain.
Reporting period: **2026-03-09 (Mon) through 2026-03-13 (Fri)**.

---

## 1. Architecture overview

```
Source files (CSV/JSON/TXT)
        │
        ▼ Bronze (5 loaders + nb_bronze_run_all)
  lh_polarslice  schema: bronze
  Raw Delta tables — string-valued, no business logic, ingestion metadata preserved
        │
        ▼ Silver (5 transformers + nb_silver_run_all)
  lh_polarslice  schema: silver
  Typed, flagged, matched — POS ↔ app links, anomaly flags, DOB/close_ts, unit conversions
        │
        ▼ Gold milestone 1 — nb_gold_legacy / nb_gold_run_legacy
  lh_polarslice  schema: gold  (legacy_* tables)
  SliceDW reproduction — intentional defects retained as migration baseline
        │
        ▼ Gold milestone 2 — nb_gold_corrected / nb_gold_run_corrected
  lh_polarslice  schema: gold  (corrected_* tables)
  Corrected business results — gifts/voids/dups removed, Aloha tax corrected,
  app attribution-only, 6-month holiday, signed commissary units
        │
        ▼ Gold Phase 3 — nb_gold_comparison / nb_gold_run_comparison
  gold.comparison_*  — legacy↔corrected bridge, waterfall, invoice delta
        │
        ▼ Gold Phase 4 — nb_gold_reconcile / nb_gold_run_reconcile
  gold.reconcile_*   — corrected↔Silver source reconciliation, SliceDW equivalence
        │
        ▼ Azure SQL (sql/)
  gold schema — corrected mart tables, load procedure, validation scripts
```

**Lakehouse:** `lh_polarslice` (schema-enabled; `defaultSchema = dbo`).  
**Branch:** `NG/Dev` → PR → `main`.

---

## 2. Source systems

| System | POS type | Stores | Period files |
|---|---|---|---|
| MICROS | POS till | 1042, 1043, 1055, 1061, 1078, 1090, 3015 | `check_header_YYYYMMDD.txt` + `check_detail_YYYYMMDD.txt` |
| Aloha | POS till | 2207, 2214, 2231 | `CHECKS.csv` + `ITEMS.csv` per store per day |
| AS/400 commissary | Inventory | all 10 stores | Fixed-width `.TXT` with `.CPY` copybooks |
| Online app | Orders | all 10 stores | `orders_YYYYMMDD.json` + `customers.csv` |
| Master data | Reference | — | `stores.csv`, `menu.csv`, `recipes.csv`, `calendar.csv` |

Upload layout: folders directly under OneLake `Files/` (no prefix folder).  
Tuesday 2026-03-10 carries a 2-for-1 promotion. HST = 13%. Eastern time (UTC−04:00).

---

## 3. Source lineage (batch IDs)

| Layer | Batch ID | Date run |
|---|---|---|
| Silver | `5d6ca0a2-b89d-4b3d-b54a-8429243d0871` | 2026-11-11 |
| Gold reference data | (contained within legacy batch) | 2026-11-12 |
| Gold legacy (milestone 1) | `07e7a5f4-2a8a-4884-9b80-58fb1c76c640` | 2026-11-12 |
| Gold corrected (milestone 2) | `175fdd4c-8417-4a00-b951-f563f4d533fd` | 2026-11-12 |
| Gold comparison (Phase 3) | `ff7553d1-0cde-409b-9caf-06cebecfb179` | 2026-11-12 |
| Gold reconciliation (Phase 4) | `8bb1ddcf-b5e5-4852-ba84-a8c3351a04c9` | 2026-11-12 |

All Silver tables carry batch `5d6ca0a2`. Legacy and corrected Gold consumed the same Silver batch. The corrected runner also consumed the reference snapshot from the legacy run.

---

## 4. Bronze

All five loaders succeeded; 14 tables loaded. See `docs/ai-context/backlog.md` for verified row counts. Key figures:

| Table | Rows |
|---|---:|
| `bronze.micros_check_header` | 6,815 |
| `bronze.micros_check_detail` | 19,880 |
| `bronze.aloha_checks` | 2,505 |
| `bronze.aloha_items` | 7,341 |
| `bronze.online_orders` | 2,302 |

---

## 5. Silver

Five source-specific transformation notebooks. POS ↔ app matching assertions:

| Match type | Count |
|---|---:|
| Unique MICROS ↔ app matches | 1,637 |
| Unique Aloha ↔ app matches | 630 |
| Retained ambiguous Aloha match | 1 |

Anomaly flags preserved (not removed) in Silver: `is_gift_check`, `is_void_reversal`, `is_duplicate_check`, `is_after_midnight`, `is_possible_duplicate_customer`, `is_item_unmapped`, `is_possible_aloha_match`.

---

## 6. Gold legacy reproduction (milestone 1)

`nb_gold_legacy` mirrors `data/2_legacy_warehouse_slicedw/sql/02_programmability.sql` formula-for-formula, including known defects. See `docs/gold-reconcile.md` (reconcile_slicedw table) for full equivalence documentation.

**Known defects intentionally reproduced:**

| Defect | Legacy behaviour | Corrected behaviour |
|---|---|---|
| Aloha tax-inclusive net sales | Uses NETTOTAL (gross−comp, tax-inclusive) | Uses NETTOTAL−TAXINCL (tax-exclusive) |
| App revenue double-counted | Adds `online_only_sales` from non-POS-matched orders | App amounts are attribution-only (zero incremental net sales) |
| New-store royalty holiday | 3-month hardcoded (SQL ignores the term table) | 6-month from `reference_royalty_terms` |
| Commissary signed receipts | Unsigned `qty_cases × pack_qty` (misses credits + KG items) | Signed base-unit quantities from Silver |
| Gift checks in revenue | Gift-load checks included | Excluded |
| Void-matched pairs in revenue | Originals included (reversals excluded) | Both sides excluded |
| Duplicate MICROS checks | All copies included | One canonical copy retained |

**Legacy period results:**

| Metric | Value |
|---|---:|
| Net sales | 299,572.90 |
| Royalty invoice amount due | 21,061.48 |

Full evidence: `docs/gold-legacy.md`.

---

## 7. Corrected Gold results (milestone 2)

`nb_gold_corrected` applies all corrections documented above.

**Corrected period results:**

| Metric | Value |
|---|---:|
| Net sales | 268,893.08 |
| Royalty invoice amount due | 17,251.74 |
| Promo discounts | 20,219.10 |
| All-ingredient food variance cost | 4,097.42 |

**Daily net sales:**

| Date | Net sales |
|---|---:|
| 2026-03-09 | 43,308.58 |
| 2026-03-10 | 58,909.20 |
| 2026-03-11 | 44,235.16 |
| 2026-03-12 | 50,299.57 |
| 2026-03-13 | 72,140.57 |

Full evidence including all 8 invoice rows and 10 cheese variance rows: `docs/gold-corrected.md`.

---

## 8. Legacy-to-corrected bridge (Phase 3)

The $30,679.82 net-sales delta and $3,809.74 invoice delta are fully attributed. See `docs/gold-comparison.md` for per-store-day detail and invoice comparison.

**Period waterfall:**

| Correction | Delta |
|---|---:|
| Aloha tax correction (BOTH) | −9,212.81 |
| MICROS exclusions (gifts/voids/dups) | −3,345.83 |
| Aloha date shift | −362.45 |
| Aloha close-outside-period (corrected adds) | +1,154.87 |
| App revenue removed | −18,913.60 |
| **Total** | **−30,679.82** |

Store 1078 is LEGACY_ONLY in the invoice comparison — the 6-month holiday correctly removes it from corrected billing (legacy invoice $1,562.58, corrected $0.00).

---

## 9. Source reconciliation (Phase 4)

Corrected Gold is verified to derive exactly from Silver sources with zero residual across all three checks. See `docs/gold-reconcile.md`.

**Anomaly summary (checked counts):**

| Anomaly | Checks | Amount |
|---|---:|---:|
| Aloha after-midnight (close outside period) | 37 | +1,154.87 |
| Aloha DOB-outside-period | 0 | 0.00 |
| Aloha tax-inclusive → exclusive | 2,505 | +9,385.15 |
| MICROS duplicate surplus | 12 | — |
| MICROS gift excluded | 49 | +2,875.00 |
| MICROS void-matched originals | 14 | +470.83 |
| MICROS void-reversal rows | 14 | +502.06 |

SliceDW equivalence: 11 of 12 metrics MATCH including bug-for-bug reproduction of the 3-month holiday. The one DIFFERS (commissary receipts) is a known SliceDW defect corrected in the Fabric pipeline.

---

## 10. Azure SQL deployment (Phase 5)

Scripts in `sql/`:

| Script | Contents |
|---|---|
| `01_schema.sql` | `gold` schema + 11 corrected mart tables |
| `02_load_procedures.sql` | `stg` staging tables + `gold.usp_LoadCorrectedGold` |
| `03_validation.sql` | Post-load row-count, financial, and integrity assertions |
| `README.md` | Deployment instructions (export from Fabric → BULK INSERT → load procedure) |

The load procedure verifies staging counts against archived Fabric baselines, wraps the swap in a transaction, and spot-checks period net sales ($268,893.08) and invoice total ($17,251.74).

---

## 11. Operational instructions

**To re-run the pipeline from scratch:**
1. Upload source files to OneLake `Files/` (see `docs/onelake-upload.md`).
2. Run `nb_bronze_run_all` → verify row counts.
3. Run `nb_silver_run_all` → verify counts and anomaly assertions.
4. Run `nb_gold_run_legacy` (reference data + legacy Gold) → verify 18 counts.
5. Run `nb_gold_run_corrected` → verify 11 counts + financial totals.
6. Run `nb_gold_run_comparison` → verify bridge nets to −30,679.82.
7. Run `nb_gold_run_reconcile` → verify zero residuals.
8. Export corrected Gold tables from Fabric to Azure Blob Storage.
9. Load Azure SQL: run `01_schema.sql`, `02_load_procedures.sql`, load staging, call `usp_LoadCorrectedGold`, run `03_validation.sql`.

**Branch safety:** Always work from `NG/Dev`. Do not switch the Fabric workspace to a branch that predates the `fabric/` folder without first protecting the lakehouse item. Git sync moves Fabric items only; source data files must be uploaded separately via OneLake.

**Answer key:** The `3_answer_key/` folder is offline validation material only. It must never be committed, exported to notebooks, or included in any artifact or PR.
