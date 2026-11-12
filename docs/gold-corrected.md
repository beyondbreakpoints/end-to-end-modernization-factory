# Gold milestone 2: corrected business results

## Status and scope

The user approved corrected Gold on 2026-11-12 after reviewing the archived successful legacy run. `nb_gold_corrected` and `nb_gold_run_corrected` implement separate `gold.corrected_*` outputs. Local Spark reports match an independent raw-source Python/Decimal baseline exactly. **Fabric execution remains pending.**

Neither notebook writes to Bronze, Silver, `gold.legacy_*`, or `gold.reference_*`. The corrected runner consumes the existing reference snapshots rather than rerunning the reference notebook. The archived legacy batch remains the migration baseline. Comparison/bridge outputs, external answer-key reconciliation, Azure SQL, and the dossier are later milestones.

## Business decisions

| Area | Corrected treatment |
|---|---|
| Sales system of record | MICROS and Aloha POS checks only. App amounts never add revenue. |
| MICROS gifts | Exclude whole gift-load checks and their lines; gift-card tender on a genuine sale remains revenue. |
| MICROS voids | Validate that each reversing header cancels the original header's subtotal, discount, tax, tip, and total. Exclude both versions of the whole check and all its lines. Identity includes store, business date, and check number. |
| Duplicate polling | Retain one identical business version of each header/line. Conflicting versions fail rather than choosing an arbitrary amount. Silver keeps the raw duplicates. |
| Aloha date and net sales | Use DOB, including the last night's after-midnight checks. Net sales = `NETTOTAL - TAXINCL` exactly, not a second division or an app amount. |
| Aloha discounts and gross | User-approved policy: convert each COMP amount to pre-tax with decimal division by 1.13, round that comp to cents, then sum. Derive gross as net sales plus these discounts so check, daily, and promo amounts balance. Gross is therefore a reconciled reporting amount, not an independently rounded conversion of GROSS. |
| Item/recipe mapping | Use Silver's validated SKU mappings, including corrected `MDVEG` and previously missing codes. Only ITEM quantities from included POS checks contribute to theoretical use; comps reduce revenue, not physical quantities. |
| Online attribution | Retain all app orders as evidence. Unique valid Silver links attribute POS amounts. Cancelled orders and the ambiguous Aloha link have no attributed POS check/amount. Every row has zero incremental net sales. POS WEB tender supplies online sales even when an app link is ambiguous. |
| Royalty holiday | Read six months from `reference_royalty_terms`. Eligibility is `add_months(open_date, holiday_months) <= period_end`; corporate stores and stores still on holiday have no invoice. The authoritative opening date for 1078 remains 2025-12-01, so it is excluded. No date is fabricated to achieve a result. |
| Invoice arithmetic | Apply 5% royalty and 3% ad fund to corrected period net sales. Round each charge separately to cents, then apply approved adjustments. |
| Duplicate adjustment | In this versioned snapshot, duplicate business keys are store/date/type/amount/note. Retain the earliest keyed timestamp, then adjustment ID, and keep both decisions for audit. Adjustment 2 is included; duplicate adjustment 4 is excluded. Store 1055 receives one -120 credit, not -240. |
| Commissary units/credits | Consume Silver's signed base-unit quantities: CS converts using pack quantity; KG/EA already in base units does not. Subtract credit quantities. Preserve source evidence in Silver and batch linkage in the manifest. |
| Food cost | Opening + signed receipts - closing; theoretical use from included, deduplicated item quantities and recipes. Variance cost uses item-master pack cost / pack quantity and rounds to cents. Undefined percentage (zero theoretical usage) stays null. Explicit intermediate decimal types prevent early rounding of percentages. |
| Hierarchy | Validated organization ancestor closure, including store-self rows. Company daily totals must equal store totals; franchisee invoices aggregate only eligible store invoices. |

This is the supplied period's snapshot model. Holiday eligibility remains period-end based, not daily proration for a future period crossing the six-month anniversary. Finance approval would be needed to change that convention. The duplicate-credit policy is tied to the documented reference snapshot; identical amounts alone are not duplicate evidence.

## Contracts

All tables use `_gold_batch_id` and `_rules_version = polarslice-corrected-v1`.

| Gold output | Grain | Local rows |
|---|---|---:|
| `corrected_fact_checks` | source system + store/date/check key | 9,231 |
| `corrected_fact_check_lines` | source system + check key + source line number | 25,664 |
| `corrected_online_attribution` | app order ID | 2,302 |
| `corrected_daily_sales` | store + business date | 50 |
| `corrected_promo_cost` | store + business date + promo name | 69 |
| `corrected_adjustment_decisions` | reference adjustment ID, including excluded duplicate | 5 |
| `corrected_royalty_invoices` | store + period | 8 |
| `corrected_food_cost_variance` | store + period + ingredient | 190 |
| `corrected_region_daily_sales` | organizational unit + business date | 85 |
| `corrected_franchisee_invoices` | franchisee + period | 6 |
| `corrected_run_inputs` | input table + its batch ID, count, and selected period | 15 |

Checks, product lines, and app attribution retain source file, Bronze batch, and Silver batch lineage. Product lines contain physical SKU quantities, not allocated per-item net revenue. Nullable app attribution fields mean no definitive link; never sum attributed amounts as incremental sales. Customers remain in Silver; no unsupported account merging is introduced.

The manifest requires one shared Silver batch across all 12 Silver inputs and one shared reference batch across the three consumed reference tables (terms, hierarchy, adjustments). Reference batch and corrected output batch need not match. The legacy Aloha map is not an input.

Money outputs use `DECIMAL(19,4)`; business rounding is to cents as documented. Food quantities use `DECIMAL(18,3)`, percentages `DECIMAL(12,1)`. Report keys must be unique and non-null. The notebook verifies check totals, daily/promo reconciliation, invoice arithmetic, food quantity arithmetic, and company rollups. The runner verifies every output's batch matches its own ID.

Full opening and closing stock counts are required for every store/ingredient at the requested boundaries. The supplied counts cover March 9 opening and March 13 closing only. A shorter custom period **fails explicitly before publication**, rather than emitting an empty or misleading food-cost report. Future periods require corresponding source inputs, calendar entries, and boundary counts.

## Local baseline (not live Fabric output)

No answer key was read or generated. Reports were compared to raw exports with `corrected_source_baseline()` in `tests/test_gold_legacy.py`, using exact Decimal equality rather than tolerances.

| Metric | Corrected local total |
|---|---:|
| Net sales | 268,893.08 |
| Royalty invoice amount due | 17,251.74 |
| Promo discounts | 20,219.10 |
| Food variance cost, all ingredients | 4,097.42 |

| Business date | Corrected net sales |
|---|---:|
| 2026-03-09 | 43,308.58 |
| 2026-03-10 | 58,909.20 |
| 2026-03-11 | 44,235.16 |
| 2026-03-12 | 50,299.57 |
| 2026-03-13 | 72,140.57 |

| Store | Invoice amount due |
|---|---:|
| 1042 | 2,620.05 |
| 1043 | 2,223.89 |
| 1055 | 2,420.85 |
| 1061 | 1,934.16 |
| 1090 | 2,192.65 |
| 2207 | 2,450.57 |
| 2214 | 1,822.16 |
| 2231 | 1,587.41 |

Corrected cheese variance is 18.3% at store 1055 and 17.3% at 2214; the other stores are 2.0-4.0%. The loss signal remains after correcting the roughly tenfold Aloha unit error. This is not a new inference about an individual or a confirmed explanation for the losses.

Local tests use Parquet in place of Fabric Delta writes. They compare every keyed financial/quantity value in checks, item quantities, daily sales, promos, invoices, food cost, region totals, and franchisee invoices. They also cover cancellation/ambiguous-link handling, duplicate-credit decisions, reruns, preserving legacy/reference tables, mixed batches, conflicting duplicates, and missing stock-count boundaries.

Run with Java 17 and PySpark 3.5:

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
```

## Fabric run gate

1. Update Fabric from `NG/Dev`, Git folder `/fabric`.
2. Open `nb_gold_run_corrected`. Verify that its default lakehouse is the **actual item containing the successfully validated Silver and legacy Gold tables**, not another item with the same `lh_polarslice` name. The runner attachment matches the repository's Silver runner; verify the live attachment after sync.
3. Keep `period_start = "2026-03-09"` and `period_end = "2026-03-13"`. Use the existing successful Silver/reference snapshots; no new uploads or Silver reruns are required unless those snapshots have changed.
4. Run all cells. The runner invokes only `nb_gold_corrected` with `useRootDefaultLakehouse: True` and the shared batch/period parameters. Both notebooks use Fabric's native parameter-cell marker.
5. Capture the corrected batch ID, all 11 counts, daily totals, invoices, cheese variance, and app-attribution counts. Expected attribution counts are 1,637 MICROS matches, 630 Aloha matches, 34 cancelled orders, and one ambiguous Aloha order.
6. Review against the local baseline, archive the live results, then stop for user confirmation before comparison/bridge implementation.

Writes overwrite only the corrected snapshots, using Delta with schema replacement. Multi-table publication is **not transactional**. A failed run can leave mixed corrected batches; do not consume them until the full runner succeeds. Never rewrite batch IDs or weaken consistency guards to pass a run. Concurrent Silver/Gold reruns are unsupported; rerun the corrected runner after resolving the underlying input/context issue.
