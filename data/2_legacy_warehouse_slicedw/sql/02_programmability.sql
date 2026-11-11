/* =====================================================================================
   SliceDW  -  functions, synonyms, trigger, views and stored procedures
   The business rules (and their bugs) live here. Comments are as the original developers left them.
   ===================================================================================== */
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

/* ---------------------------------------------------------------- helpers */
CREATE FUNCTION dw.fn_CyymmddToDate (@c CHAR(7))
RETURNS DATE
AS
BEGIN
    RETURN DATEFROMPARTS(1900 + CAST(LEFT(@c, 1) AS INT) * 100 + CAST(SUBSTRING(@c, 2, 2) AS INT),
                         CAST(SUBSTRING(@c, 4, 2) AS INT),
                         CAST(SUBSTRING(@c, 6, 2) AS INT));
END;
GO

CREATE SYNONYM dw.CommissaryShipments FOR stg.as400_shipment_raw;
GO
CREATE SYNONYM dw.CommissaryCounts FOR stg.as400_count_raw;
GO

CREATE TRIGGER adj.trg_ManualAdjustment_Audit
ON adj.ManualAdjustment
AFTER INSERT, UPDATE, DELETE
AS
BEGIN
    SET NOCOUNT ON;
    INSERT INTO adj.ManualAdjustmentAudit (adj_id, action, amount)
    SELECT i.adj_id, CASE WHEN d.adj_id IS NULL THEN 'I' ELSE 'U' END, i.amount
    FROM inserted i
    LEFT JOIN deleted d ON d.adj_id = i.adj_id
    UNION ALL
    SELECT d.adj_id, 'D', d.amount
    FROM deleted d
    WHERE NOT EXISTS (SELECT 1 FROM inserted i WHERE i.adj_id = d.adj_id);
END;
GO

/* ---------------------------------------------------------------- views */
CREATE VIEW rpt.vw_StoreDaySales
WITH SCHEMABINDING
AS
SELECT store_id, business_date, source_system,
       SUM(net_sales) AS net_sales,
       SUM(tax)       AS tax,
       COUNT_BIG(*)   AS check_count
FROM dw.FactCheck
GROUP BY store_id, business_date, source_system;
GO
CREATE UNIQUE CLUSTERED INDEX IX_rpt_vw_StoreDaySales ON rpt.vw_StoreDaySales (store_id, business_date, source_system);
GO

CREATE VIEW rpt.vw_DailySales
AS
SELECT f.business_date, s.store_id, s.store_name, s.city, s.ownership, s.franchisee_id,
       f.gross_sales, f.discounts, f.voids, f.net_sales_tills, f.online_only_sales, f.net_sales, f.tax, f.check_count
FROM dw.FactDailySales f
JOIN cfg.Store s ON s.store_id = f.store_id;
GO

CREATE VIEW rpt.vw_FranchiseeInvoice
AS
SELECT franchisee_id, franchisee_name, period_start, period_end,
       COUNT(*) AS stores, SUM(net_sales) AS net_sales, SUM(royalty) AS royalty,
       SUM(ad_fund) AS ad_fund, SUM(adjustments) AS adjustments, SUM(amount_due) AS amount_due
FROM rpt.RoyaltyInvoice
GROUP BY franchisee_id, franchisee_name, period_start, period_end;
GO

/* ---------------------------------------------------------------- logging */
CREATE PROCEDURE dw.usp_LogRun
    @ProcName VARCHAR(100), @BusinessDate DATE, @StartedAt DATETIME, @Rows INT
AS
BEGIN
    SET NOCOUNT ON;
    INSERT INTO cfg.EtlRunLog (proc_name, business_date, started_at, finished_at, rows_affected)
    VALUES (@ProcName, @BusinessDate, @StartedAt, GETDATE(), @Rows);
END;
GO

/* ---------------------------------------------------------------- tills */
CREATE PROCEDURE dw.usp_LoadFactCheckMicros
    @BusinessDate DATE
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @started DATETIME = GETDATE(), @rows INT;

    DELETE FROM dw.FactCheckLine WHERE source_system = 'MICROS' AND business_date = @BusinessDate;
    DELETE FROM dw.FactCheck     WHERE source_system = 'MICROS' AND business_date = @BusinessDate;

    -- Void rows (void_flag = 'V') are reported separately in usp_BuildNetSales
    INSERT INTO dw.FactCheck (store_id, business_date, source_system, check_id, order_type, tender,
                              gross, discount, tax, tip, net_sales, online_ref)
    SELECT h.store, h.business_date, 'MICROS', CAST(h.check_no AS VARCHAR(20)), h.order_type, h.tender,
           h.subtotal, h.discount, h.tax, h.tip, h.subtotal - h.discount, NULLIF(h.online_ref, '')
    FROM stg.micros_check_header h
    WHERE h.business_date = @BusinessDate
      AND h.void_flag = 'N';
    SET @rows = @@ROWCOUNT;

    INSERT INTO dw.FactCheckLine (store_id, business_date, source_system, check_id, sku, source_item_code, qty, amount)
    SELECT d.store, d.business_date, 'MICROS', CAST(d.check_no AS VARCHAR(20)), m.sku,
           CAST(d.item_no AS VARCHAR(10)), d.qty, d.line_amount
    FROM stg.micros_check_detail d
    LEFT JOIN cfg.MenuItem m ON m.micros_item_no = d.item_no
    WHERE d.business_date = @BusinessDate
      AND d.line_type IN ('ITEM', 'GIFT');

    EXEC dw.usp_LogRun 'usp_LoadFactCheckMicros', @BusinessDate, @started, @rows;
END;
GO

CREATE PROCEDURE dw.usp_LoadFactCheckAloha
    @BusinessDate DATE
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @started DATETIME = GETDATE(), @rows INT;

    DELETE FROM dw.FactCheckLine WHERE source_system = 'ALOHA' AND business_date = @BusinessDate;
    DELETE FROM dw.FactCheck     WHERE source_system = 'ALOHA' AND business_date = @BusinessDate;

    -- Aloha NETTOTAL is the check net, same as MICROS subtotal - discount
    INSERT INTO dw.FactCheck (store_id, business_date, source_system, check_id, order_type, tender,
                              gross, discount, tax, tip, net_sales, online_ref)
    SELECT c.store, @BusinessDate, 'ALOHA', c.dob + '-' + CAST(c.checkid AS VARCHAR(10)), c.ordermode, c.paytype,
           c.gross, c.comp, c.taxincl, c.tip, c.nettotal, NULL
    FROM stg.aloha_checks c
    WHERE CAST(c.closetime AS DATE) = @BusinessDate;
    SET @rows = @@ROWCOUNT;

    INSERT INTO dw.FactCheckLine (store_id, business_date, source_system, check_id, sku, source_item_code, qty, amount)
    SELECT i.store, @BusinessDate, 'ALOHA', i.dob + '-' + CAST(i.checkid AS VARCHAR(10)), am.sku,
           i.itemcode, i.qty, i.amount
    FROM stg.aloha_items i
    JOIN stg.aloha_checks c ON c.store = i.store AND c.dob = i.dob AND c.checkid = i.checkid
    LEFT JOIN cfg.AlohaItemMap am ON am.aloha_item_code = i.itemcode
    WHERE CAST(c.closetime AS DATE) = @BusinessDate
      AND i.type = 'ITEM';

    EXEC dw.usp_LogRun 'usp_LoadFactCheckAloha', @BusinessDate, @started, @rows;
END;
GO

/* ---------------------------------------------------------------- online app */
CREATE PROCEDURE dw.usp_LoadFactOnline
    @BusinessDate DATE
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @started DATETIME = GETDATE(), @rows INT;

    DELETE FROM dw.FactOnlineOrder WHERE business_date = @BusinessDate;

    INSERT INTO dw.FactOnlineOrder (order_id, store_id, business_date, status, net_sales, pos_check_no, is_duplicate_of_pos)
    SELECT o.order_id, o.store_id, CAST(o.placed_at AS DATE), o.status, o.subtotal - o.discount, o.pos_check_no, 0
    FROM stg.online_order o
    WHERE CAST(o.placed_at AS DATE) = @BusinessDate
      AND o.status <> 'refunded';          -- skip orders that never went through
    SET @rows = @@ROWCOUNT;

    EXEC dw.usp_LogRun 'usp_LoadFactOnline', @BusinessDate, @started, @rows;
END;
GO

CREATE PROCEDURE dw.usp_DedupOnline
    @BusinessDate DATE
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @started DATETIME = GETDATE(), @rows INT;

    -- An app order that the till also rang up is already in the till's sales
    UPDATE o
    SET is_duplicate_of_pos = 1
    FROM dw.FactOnlineOrder o
    WHERE o.business_date = @BusinessDate
      AND o.pos_check_no IS NOT NULL
      AND EXISTS (SELECT 1
                  FROM dw.FactCheck f
                  WHERE f.source_system = 'MICROS'
                    AND f.store_id = o.store_id
                    AND f.business_date = o.business_date
                    AND f.check_id = CAST(o.pos_check_no AS VARCHAR(20)));
    SET @rows = @@ROWCOUNT;

    EXEC dw.usp_LogRun 'usp_DedupOnline', @BusinessDate, @started, @rows;
END;
GO

/* ---------------------------------------------------------------- daily sales */
CREATE PROCEDURE dw.usp_BuildNetSales
    @BusinessDate DATE
AS
BEGIN
    SET NOCOUNT ON;
    SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;
    DECLARE @started DATETIME = GETDATE(), @rows INT;

    DELETE FROM dw.FactDailySales WHERE business_date = @BusinessDate;

    WITH tills AS (
        SELECT store_id, SUM(gross) AS gross_sales, SUM(discount) AS discounts,
               SUM(net_sales) AS net_sales_tills, SUM(tax) AS tax, COUNT(*) AS check_count
        FROM dw.FactCheck
        WHERE business_date = @BusinessDate
        GROUP BY store_id
    ), online AS (
        SELECT store_id, SUM(net_sales) AS online_only_sales
        FROM dw.FactOnlineOrder
        WHERE business_date = @BusinessDate AND is_duplicate_of_pos = 0
        GROUP BY store_id
    ), voids AS (
        SELECT store AS store_id, -SUM(subtotal) AS voids
        FROM stg.micros_check_header
        WHERE business_date = @BusinessDate AND void_flag = 'V'
        GROUP BY store
    ), stores AS (
        SELECT store_id FROM tills
        UNION
        SELECT store_id FROM online
    )
    INSERT INTO dw.FactDailySales (store_id, business_date, gross_sales, discounts, voids, net_sales_tills,
                                   online_only_sales, net_sales, tax, check_count, tender_list)
    SELECT s.store_id, @BusinessDate,
           ISNULL(t.gross_sales, 0), ISNULL(t.discounts, 0), ISNULL(v.voids, 0), ISNULL(t.net_sales_tills, 0),
           ISNULL(o.online_only_sales, 0),
           ISNULL(t.net_sales_tills, 0) + ISNULL(o.online_only_sales, 0),
           ISNULL(t.tax, 0), ISNULL(t.check_count, 0),
           STUFF((SELECT DISTINCT ',' + f.tender
                  FROM dw.FactCheck f
                  WHERE f.store_id = s.store_id AND f.business_date = @BusinessDate
                  FOR XML PATH('')), 1, 1, '')
    FROM stores s
    LEFT JOIN tills  t ON t.store_id = s.store_id
    LEFT JOIN online o ON o.store_id = s.store_id
    LEFT JOIN voids  v ON v.store_id = s.store_id;
    SET @rows = @@ROWCOUNT;

    EXEC dw.usp_LogRun 'usp_BuildNetSales', @BusinessDate, @started, @rows;
END;
GO

CREATE PROCEDURE dw.usp_BuildPromoCost
    @BusinessDate DATE
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @started DATETIME = GETDATE(), @rows INT;

    DELETE FROM rpt.PromoCost WHERE business_date = @BusinessDate;

    INSERT INTO rpt.PromoCost (store_id, business_date, promo_name, discount_amount)
    SELECT x.store_id, @BusinessDate, x.promo_name, SUM(x.amount)
    FROM (
        SELECT d.store AS store_id,
               CASE d.item_no WHEN 9001 THEN '2FOR1TUE' WHEN 9002 THEN 'WELCOME10' ELSE 'STAFF50' END AS promo_name,
               -d.line_amount AS amount
        FROM stg.micros_check_detail d
        WHERE d.business_date = @BusinessDate AND d.line_type = 'DISC'
        UNION ALL
        SELECT i.store,
               CASE i.itemcode WHEN '2F1TUE' THEN '2FOR1TUE' ELSE 'STAFF50' END,
               -i.amount
        FROM stg.aloha_items i
        WHERE CAST(i.ordertime AS DATE) = @BusinessDate AND i.type = 'COMP'
    ) x
    GROUP BY x.store_id, x.promo_name;
    SET @rows = @@ROWCOUNT;

    EXEC dw.usp_LogRun 'usp_BuildPromoCost', @BusinessDate, @started, @rows;
END;
GO

/* ---------------------------------------------------------------- commissary */
CREATE PROCEDURE dw.usp_LoadCommissary
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @started DATETIME = GETDATE(), @rows INT;

    TRUNCATE TABLE dw.DimItem;
    INSERT INTO dw.DimItem (item_code, item_desc, pack_uom, base_uom, pack_qty, pack_cost)
    SELECT SUBSTRING(raw_line, 1, 8),
           RTRIM(SUBSTRING(raw_line, 9, 20)),
           SUBSTRING(raw_line, 29, 2),
           SUBSTRING(raw_line, 31, 2),
           CAST(SUBSTRING(raw_line, 33, 7) AS DECIMAL(9,0)) / 1000,
           CAST(SUBSTRING(raw_line, 40, 7) AS DECIMAL(9,0)) / 100
    FROM stg.as400_itemmast_raw;

    TRUNCATE TABLE dw.FactShipment;
    INSERT INTO dw.FactShipment (store_id, ship_date, item_code, qty_cases, ext_cost, source_file)
    SELECT CAST(SUBSTRING(s.raw_line, 1, 5) AS INT),
           dw.fn_CyymmddToDate(SUBSTRING(s.raw_line, 6, 7)),
           SUBSTRING(s.raw_line, 13, 8),
           CAST(SUBSTRING(s.raw_line, 41, 7) AS DECIMAL(9,0)) / 100,    -- commissary ships in cases
           CAST(SUBSTRING(s.raw_line, 50, 9) AS DECIMAL(11,0)) / 100,
           s.file_name
    FROM dw.CommissaryShipments s;
    SET @rows = @@ROWCOUNT;

    TRUNCATE TABLE dw.FactStockCount;
    INSERT INTO dw.FactStockCount (store_id, count_date, count_type, item_code, qty)
    SELECT CAST(SUBSTRING(c.raw_line, 1, 5) AS INT),
           dw.fn_CyymmddToDate(SUBSTRING(c.raw_line, 6, 7)),
           SUBSTRING(c.raw_line, 13, 1),
           SUBSTRING(c.raw_line, 14, 8),
           CAST(SUBSTRING(c.raw_line, 22, 8) AS DECIMAL(12,0)) / 1000
    FROM dw.CommissaryCounts c;

    EXEC dw.usp_LogRun 'usp_LoadCommissary', NULL, @started, @rows;
END;
GO

/* ---------------------------------------------------------------- period reports */
CREATE PROCEDURE dw.usp_CalcRoyalty
    @PeriodStart DATE, @PeriodEnd DATE
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @started DATETIME = GETDATE(), @rows INT;
    DECLARE @royalty DECIMAL(9,4) = (SELECT term_value FROM cfg.RoyaltyTerm WHERE term_code = 'ROYALTY_RATE');
    DECLARE @adfund  DECIMAL(9,4) = (SELECT term_value FROM cfg.RoyaltyTerm WHERE term_code = 'AD_FUND_RATE');

    DELETE FROM rpt.RoyaltyInvoice WHERE period_start = @PeriodStart AND period_end = @PeriodEnd;

    INSERT INTO rpt.RoyaltyInvoice (franchisee_id, franchisee_name, store_id, period_start, period_end,
                                    net_sales, royalty, ad_fund, adjustments, amount_due)
    SELECT s.franchisee_id, s.franchisee_name, s.store_id, @PeriodStart, @PeriodEnd,
           ns.net_sales,
           ROUND(CAST(ns.net_sales AS DECIMAL(19,4)) * @royalty, 2),
           ROUND(CAST(ns.net_sales AS DECIMAL(19,4)) * @adfund, 2),
           ISNULL(a.adjustments, 0),
           ROUND(CAST(ns.net_sales AS DECIMAL(19,4)) * @royalty, 2)
             + ROUND(CAST(ns.net_sales AS DECIMAL(19,4)) * @adfund, 2)
             + ISNULL(a.adjustments, 0)
    FROM cfg.Store s
    JOIN (SELECT store_id, SUM(net_sales) AS net_sales
          FROM dw.FactDailySales
          WHERE business_date BETWEEN @PeriodStart AND @PeriodEnd
          GROUP BY store_id) ns ON ns.store_id = s.store_id
    LEFT JOIN (SELECT store_id, SUM(amount) AS adjustments
               FROM adj.ManualAdjustment
               WHERE business_date BETWEEN @PeriodStart AND @PeriodEnd
               GROUP BY store_id) a ON a.store_id = s.store_id
    WHERE s.ownership = 'FRANCHISE'
      AND s.open_date <= DATEADD(MONTH, -3, @PeriodEnd);      -- new stores get a royalty holiday
    SET @rows = @@ROWCOUNT;

    EXEC dw.usp_LogRun 'usp_CalcRoyalty', @PeriodEnd, @started, @rows;
END;
GO

CREATE PROCEDURE dw.usp_CalcFoodCost
    @PeriodStart DATE, @PeriodEnd DATE
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @started DATETIME = GETDATE(), @rows INT;

    DELETE FROM rpt.FoodCostVariance WHERE period_start = @PeriodStart AND period_end = @PeriodEnd;

    WITH theo AS (
        SELECT l.store_id, r.ingredient_item_code AS item_code, SUM(l.qty * r.qty_per_unit) AS theoretical
        FROM dw.FactCheckLine l
        JOIN cfg.Recipe r ON r.sku = l.sku
        WHERE l.business_date BETWEEN @PeriodStart AND @PeriodEnd
        GROUP BY l.store_id, r.ingredient_item_code
    ), recv AS (
        SELECT sh.store_id, sh.item_code, SUM(sh.qty_cases * i.pack_qty) AS received
        FROM dw.FactShipment sh
        JOIN dw.DimItem i ON i.item_code = sh.item_code
        WHERE sh.ship_date BETWEEN @PeriodStart AND @PeriodEnd
        GROUP BY sh.store_id, sh.item_code
    ), opening AS (
        SELECT store_id, item_code, qty FROM dw.FactStockCount WHERE count_type = 'O' AND count_date = @PeriodStart
    ), closing AS (
        SELECT store_id, item_code, qty FROM dw.FactStockCount WHERE count_type = 'C' AND count_date = @PeriodEnd
    )
    INSERT INTO rpt.FoodCostVariance (store_id, period_start, period_end, item_code, opening_qty, received_qty,
                                      closing_qty, actual_usage, theoretical_usage, variance, variance_pct, variance_cost)
    SELECT o.store_id, @PeriodStart, @PeriodEnd, o.item_code,
           o.qty, ISNULL(rc.received, 0), c.qty,
           o.qty + ISNULL(rc.received, 0) - c.qty,
           ISNULL(t.theoretical, 0),
           o.qty + ISNULL(rc.received, 0) - c.qty - ISNULL(t.theoretical, 0),
           CASE WHEN ISNULL(t.theoretical, 0) = 0 THEN NULL
                ELSE ROUND((o.qty + ISNULL(rc.received, 0) - c.qty - t.theoretical) / t.theoretical * 100, 1) END,
           ROUND((o.qty + ISNULL(rc.received, 0) - c.qty - ISNULL(t.theoretical, 0)) * CAST(i.pack_cost AS DECIMAL(19,4)) / i.pack_qty, 2)
    FROM opening o
    JOIN closing c   ON c.store_id = o.store_id AND c.item_code = o.item_code
    JOIN dw.DimItem i ON i.item_code = o.item_code
    LEFT JOIN recv rc ON rc.store_id = o.store_id AND rc.item_code = o.item_code
    LEFT JOIN theo t  ON t.store_id = o.store_id AND t.item_code = o.item_code;
    SET @rows = @@ROWCOUNT;

    EXEC dw.usp_LogRun 'usp_CalcFoodCost', @PeriodEnd, @started, @rows;
END;
GO

CREATE PROCEDURE dw.usp_BuildRegionRollup
    @PeriodStart DATE, @PeriodEnd DATE
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @started DATETIME = GETDATE(), @rows INT;

    DELETE FROM rpt.RegionDailySales WHERE business_date BETWEEN @PeriodStart AND @PeriodEnd;

    WITH tree AS (
        SELECT unit_id AS root_id, unit_id, store_id, 0 AS depth
        FROM cfg.OrgUnit
        UNION ALL
        SELECT t.root_id, c.unit_id, c.store_id, t.depth + 1
        FROM tree t
        JOIN cfg.OrgUnit c ON c.parent_unit_id = t.unit_id
    )
    INSERT INTO rpt.RegionDailySales (unit_id, unit_name, unit_type, business_date, net_sales)
    SELECT u.unit_id, u.unit_name, u.unit_type, f.business_date, SUM(f.net_sales)
    FROM tree t
    JOIN cfg.OrgUnit u ON u.unit_id = t.root_id
    JOIN dw.FactDailySales f ON f.store_id = t.store_id
    WHERE t.store_id IS NOT NULL
      AND f.business_date BETWEEN @PeriodStart AND @PeriodEnd
    GROUP BY u.unit_id, u.unit_name, u.unit_type, f.business_date
    OPTION (MAXRECURSION 10);
    SET @rows = @@ROWCOUNT;

    EXEC dw.usp_LogRun 'usp_BuildRegionRollup', @PeriodEnd, @started, @rows;
END;
GO

/* ---------------------------------------------------------------- housekeeping */
CREATE PROCEDURE dw.usp_PurgeStaging
    @KeepDays INT = 35
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @started DATETIME = GETDATE();

    SET ROWCOUNT 5000;
    WHILE 1 = 1
    BEGIN
        DELETE FROM stg.micros_check_detail WHERE load_ts < DATEADD(DAY, -@KeepDays, GETDATE());
        IF @@ROWCOUNT = 0 BREAK;
    END;
    WHILE 1 = 1
    BEGIN
        DELETE FROM stg.micros_check_header WHERE load_ts < DATEADD(DAY, -@KeepDays, GETDATE());
        IF @@ROWCOUNT = 0 BREAK;
    END;
    SET ROWCOUNT 0;

    EXEC dw.usp_LogRun 'usp_PurgeStaging', NULL, @started, NULL;
END;
GO

/* ---------------------------------------------------------------- orchestration */
CREATE PROCEDURE dw.usp_RunNightly
    @BusinessDate DATE
AS
BEGIN
    SET NOCOUNT ON;
    EXEC dw.usp_LoadFactCheckMicros @BusinessDate;
    EXEC dw.usp_LoadFactCheckAloha  @BusinessDate;
    EXEC dw.usp_LoadFactOnline      @BusinessDate;
    EXEC dw.usp_DedupOnline         @BusinessDate;
    EXEC dw.usp_BuildNetSales       @BusinessDate;
    EXEC dw.usp_BuildPromoCost      @BusinessDate;
END;
GO

CREATE PROCEDURE dw.usp_RunPeriod
    @PeriodStart DATE, @PeriodEnd DATE
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @d DATE;

    DECLARE date_cursor CURSOR LOCAL FAST_FORWARD FOR
        SELECT calendar_date FROM dw.DimDate
        WHERE calendar_date BETWEEN @PeriodStart AND @PeriodEnd
        ORDER BY calendar_date;
    OPEN date_cursor;
    FETCH NEXT FROM date_cursor INTO @d;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        EXEC dw.usp_RunNightly @d;
        FETCH NEXT FROM date_cursor INTO @d;
    END;
    CLOSE date_cursor;
    DEALLOCATE date_cursor;

    EXEC dw.usp_LoadCommissary;
    EXEC dw.usp_CalcRoyalty       @PeriodStart, @PeriodEnd;
    EXEC dw.usp_CalcFoodCost      @PeriodStart, @PeriodEnd;
    EXEC dw.usp_BuildRegionRollup @PeriodStart, @PeriodEnd;
    EXEC dw.usp_PurgeStaging;
END;
GO
