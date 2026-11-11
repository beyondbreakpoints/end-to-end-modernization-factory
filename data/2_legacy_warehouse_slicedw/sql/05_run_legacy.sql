/* Run the legacy nightly and period processing for the dev slice, then look at the results */
EXEC dw.usp_RunPeriod @PeriodStart = '2026-03-09', @PeriodEnd = '2026-03-13';
GO
SELECT * FROM rpt.vw_DailySales ORDER BY business_date, store_id;
SELECT * FROM rpt.RoyaltyInvoice ORDER BY franchisee_id, store_id;
SELECT * FROM rpt.FoodCostVariance WHERE item_code = 'MOZ00410' ORDER BY store_id;
SELECT * FROM rpt.PromoCost ORDER BY business_date, store_id, promo_name;
SELECT * FROM cfg.EtlRunLog ORDER BY run_id;
