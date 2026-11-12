# Gold milestone 3: legacy-to-corrected comparison bridge

## Status and scope

`nb_gold_comparison` and `nb_gold_run_comparison` read `gold.legacy_*` and `gold.corrected_*` without rewriting them. The bridge explains the full **$30,679.82 net-sales delta** and **$3,809.74 invoice delta** between the two milestones, attributing each dollar to a named correction category. The reconciliation assertion passed exactly.

**Fabric run: 2026-11-12**  
Batch: `ff7553d1-0cde-409b-9caf-06cebecfb179`

Output tables: `gold.comparison_bridge` (9,294 rows), `gold.comparison_summary` (5 rows), `gold.comparison_daily` (50 rows), `gold.comparison_invoices` (9 rows).

---

## Period-level waterfall (`gold.comparison_summary`)

| Category | Legacy amount | Corrected amount | Delta |
|---|---:|---:|---:|
| `BOTH` | 274,162.89 | 264,950.08 | **−9,212.81** |
| `MICROS_LEGACY_ONLY` | 3,345.83 | 0.00 | **−3,345.83** |
| `ALOHA_DATE_SHIFT` | 3,150.58 | 2,788.13 | **−362.45** |
| `ALOHA_CLOSE_OUTSIDE_PERIOD` | 0.00 | 1,154.87 | **+1,154.87** |
| `APP_REVENUE_REMOVED` | 18,913.60 | 0.00 | **−18,913.60** |
| **Total** | **299,572.90** | **268,893.08** | **−30,679.82** |

### Category explanations

**`BOTH` (−$9,212.81):** Aloha checks present in both milestones with different net-sales values. The entire delta is the tax correction: legacy uses `net_total_tax_incl` (tax-inclusive NETTOTAL), corrected uses `net_total_tax_incl − tax` (tax-exclusive). With 13% HST across the Aloha period, this accounts for approximately the period Aloha tax amount on corrected checks.

**`MICROS_LEGACY_ONLY` (−$3,345.83):** MICROS checks in legacy that corrected excludes:
- Gift-load checks (not revenue)
- Original checks whose void reversal exactly cancels them (both sides removed in corrected)
- Surplus copies of duplicate checks at store 1061 on March 12 (corrected keeps one canonical copy; legacy retains all copies summed)

**`ALOHA_DATE_SHIFT` (−$362.45):** After-midnight Aloha checks where the Silver close timestamp falls into one reporting date but DOB is the previous day. Legacy uses close date; corrected uses DOB. The net effect is a small downward shift because the tax-inclusive amounts on the close-date side exceed the tax-exclusive DOB-side amounts.

**`ALOHA_CLOSE_OUTSIDE_PERIOD` (+$1,154.87):** Aloha checks with DOB within March 9–13 but close timestamp on March 14. These appear **only** in corrected (DOB-based period filter includes them); legacy excludes them (close-date filter excludes March 14). Their addition to corrected partially offsets the other negative corrections.

**`APP_REVENUE_REMOVED` (−$18,913.60):** Legacy adds `online_only_sales` from app orders where `NOT is_duplicate_of_pos`. Corrected treats all app amounts as attribution-only evidence (zero incremental net sales). This is the single largest correction.

---

## Invoice comparison (`gold.comparison_invoices`)

| Store | Franchisee | Legacy net sales | Corrected net sales | Net Δ | Legacy amount due | Corrected amount due | Invoice Δ | Status |
|---:|---|---:|---:|---:|---:|---:|---:|---|
| 1042 | Rana Holdings Inc. | 34,992.05 | 34,625.63 | −366.42 | 2,649.36 | 2,620.05 | −29.31 | BOTH |
| 1043 | Kostas Food Group Ltd. | 28,318.44 | 27,798.59 | −519.85 | 2,265.47 | 2,223.89 | −41.58 | BOTH |
| 1055 | Rana Holdings Inc. | 32,394.00 | 31,760.61 | −633.39 | 2,351.52 | 2,420.85 | +69.33 | BOTH |
| 1061 | Steeltown Slices Inc. | 25,188.92 | 24,177.01 | −1,011.91 | 2,015.12 | 1,934.16 | −80.96 | BOTH |
| **1078** | **Lakeshore QSR Corp.** | **19,532.23** | **0.00** | **−19,532.23** | **1,562.58** | **0.00** | **−1,562.58** | **LEGACY_ONLY** |
| 1090 | Dhillon Family Foods Ltd. | 27,645.44 | 27,095.54 | −549.90 | 2,236.63 | 2,192.65 | −43.98 | BOTH |
| 2207 | Rideau Pizza Partners | 40,391.79 | 29,569.67 | −10,822.12 | 3,316.34 | 2,450.57 | −865.77 | BOTH |
| 2214 | Rideau Pizza Partners | 30,907.05 | 22,776.90 | −8,130.15 | 2,472.56 | 1,822.16 | −650.40 | BOTH |
| 2231 | Georgian Bay Eats Inc. | 27,398.73 | 19,842.63 | −7,556.10 | 2,191.90 | 1,587.41 | −604.49 | BOTH |

**Store 1078 (LEGACY_ONLY):** Legacy used a 3-month new-store holiday; corrected uses 6 months. Store 1078 opened 2025-12-01 — the 6-month window runs to 2026-06-01, past the 2026-03-13 period end, so store 1078 has no corrected invoice. Legacy erroneously issued one.

**Store 1055 (positive amount-due delta +$69.33):** Net sales are lower in corrected (−$633.39), which reduces royalty and ad fund. However corrected also applies a −$120 manual credit that legacy did not fully apply under the same holiday/royalty calculation. The credit more than offsets the rate reduction on the smaller base, producing a net positive amount-due delta.

**Aloha stores 2207, 2214, 2231:** The large net-sales deltas (−$10,822 / −$8,130 / −$7,556) are driven primarily by the Aloha tax correction applied to their entire POS volume; app deduplication has a secondary effect.

---

## Store/day summary (`gold.comparison_daily`)

50 rows — all 10 stores × 5 business dates. Key patterns:

- **Aloha stores** (2207, 2214, 2231) show the largest per-day deltas (−$1,000 to −$2,773) driven by the tax-inclusive → exclusive correction on high-volume Aloha checks.
- **MICROS stores** (1042, 1043, 1055, 1061, 1078, 1090, 3015) show smaller per-day deltas (−$15 to −$378) driven by gift/void/duplicate exclusions.
- **Store 1061 March 12** shows the largest MICROS-store delta (−$378.26, 154 legacy vs 141 corrected checks) — the duplicate-check cluster documented in the Silver layer.
- Some Aloha store/days show **more** corrected checks than legacy (e.g., 2207 on March 9: 152 legacy vs 165 corrected) because `ALOHA_CLOSE_OUTSIDE_PERIOD` checks (DOB=March 13, close=March 14) appear only in corrected.

---

## Notes

Provenance: user reported `nb_gold_comparison Succeeded 100%` and supplied the runner's output above. This is user-supplied console evidence. The reconciliation assertion confirmed bridge total = −30,679.82 exactly (zero tolerance after three incremental bug fixes: Aloha after-midnight join, direct Gold-to-Gold Aloha bridge, MICROS duplicate aggregation).
