/* =====================================================================================
   Polar Slice Pizza — Corrected Gold Mart  (Azure SQL Database)
   Load procedures: populate the gold schema from Fabric-exported CSV or Parquet.

   Loading pattern:
     1. Export each gold.corrected_* Delta table from Fabric to Azure Blob Storage as CSV
        (e.g., using a Fabric Pipeline with a Copy activity, or:
         COPY INTO 'wasbs://.../gold/corrected_fact_checks.csv' FROM gold.corrected_fact_checks)
     2. Run BULK INSERT from the exported CSVs into the stg.* staging tables below.
     3. Call usp_LoadCorrectedGold to validate staging counts, swap data, and verify.
   ===================================================================================== */
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = N'stg')
    EXEC('CREATE SCHEMA stg');
GO

/* ---------------------------------------------------------------- staging tables (mirror gold, no PKs) */
IF OBJECT_ID(N'stg.corrected_run_inputs',           N'U') IS NOT NULL DROP TABLE stg.corrected_run_inputs;
IF OBJECT_ID(N'stg.corrected_promo_cost',           N'U') IS NOT NULL DROP TABLE stg.corrected_promo_cost;
IF OBJECT_ID(N'stg.corrected_fact_checks',          N'U') IS NOT NULL DROP TABLE stg.corrected_fact_checks;
IF OBJECT_ID(N'stg.corrected_fact_check_lines',     N'U') IS NOT NULL DROP TABLE stg.corrected_fact_check_lines;
IF OBJECT_ID(N'stg.corrected_online_attribution',   N'U') IS NOT NULL DROP TABLE stg.corrected_online_attribution;
IF OBJECT_ID(N'stg.corrected_daily_sales',          N'U') IS NOT NULL DROP TABLE stg.corrected_daily_sales;
IF OBJECT_ID(N'stg.corrected_adjustment_decisions', N'U') IS NOT NULL DROP TABLE stg.corrected_adjustment_decisions;
IF OBJECT_ID(N'stg.corrected_royalty_invoices',     N'U') IS NOT NULL DROP TABLE stg.corrected_royalty_invoices;
IF OBJECT_ID(N'stg.corrected_food_cost_variance',   N'U') IS NOT NULL DROP TABLE stg.corrected_food_cost_variance;
IF OBJECT_ID(N'stg.corrected_region_daily_sales',   N'U') IS NOT NULL DROP TABLE stg.corrected_region_daily_sales;
IF OBJECT_ID(N'stg.corrected_franchisee_invoices',  N'U') IS NOT NULL DROP TABLE stg.corrected_franchisee_invoices;
GO

/* Staging tables have same columns as gold, no constraints, for fast BULK INSERT */
SELECT TOP 0 * INTO stg.corrected_run_inputs           FROM gold.corrected_run_inputs;
SELECT TOP 0 * INTO stg.corrected_promo_cost           FROM gold.corrected_promo_cost;
SELECT TOP 0 * INTO stg.corrected_fact_checks          FROM gold.corrected_fact_checks;
SELECT TOP 0 * INTO stg.corrected_fact_check_lines     FROM gold.corrected_fact_check_lines;
SELECT TOP 0 * INTO stg.corrected_online_attribution   FROM gold.corrected_online_attribution;
SELECT TOP 0 * INTO stg.corrected_daily_sales          FROM gold.corrected_daily_sales;
SELECT TOP 0 * INTO stg.corrected_adjustment_decisions FROM gold.corrected_adjustment_decisions;
SELECT TOP 0 * INTO stg.corrected_royalty_invoices     FROM gold.corrected_royalty_invoices;
SELECT TOP 0 * INTO stg.corrected_food_cost_variance   FROM gold.corrected_food_cost_variance;
SELECT TOP 0 * INTO stg.corrected_region_daily_sales   FROM gold.corrected_region_daily_sales;
SELECT TOP 0 * INTO stg.corrected_franchisee_invoices  FROM gold.corrected_franchisee_invoices;
GO

/* ---------------------------------------------------------------- load procedure */
CREATE OR ALTER PROCEDURE gold.usp_LoadCorrectedGold
    @period_start  DATE,
    @period_end    DATE,
    @gold_batch_id VARCHAR(50)   -- Fabric batch ID to verify: e.g. '175fdd4c-...'
AS
BEGIN
    SET NOCOUNT ON;

    /* 1. Verify staging tables are populated and batch IDs are consistent */
    DECLARE @stg_batch VARCHAR(50);
    SELECT @stg_batch = MIN(_gold_batch_id) FROM stg.corrected_run_inputs;
    IF @stg_batch IS NULL
        THROW 51000, 'stg.corrected_run_inputs is empty — load staging tables first.', 1;
    IF @stg_batch <> MAX(_gold_batch_id) FROM stg.corrected_run_inputs
        THROW 51001, 'Mixed batch IDs in stg.corrected_run_inputs.', 1;
    IF @gold_batch_id <> '' AND @stg_batch <> @gold_batch_id
        THROW 51002, 'Staging batch does not match expected @gold_batch_id.', 1;

    DECLARE @stg_period_start DATE, @stg_period_end DATE;
    SELECT @stg_period_start = MIN(CAST(period_start AS DATE)),
           @stg_period_end   = MAX(CAST(period_end   AS DATE))
    FROM stg.corrected_run_inputs;
    IF @stg_period_start <> @period_start OR @stg_period_end <> @period_end
        THROW 51003, 'Staging period does not match @period_start / @period_end.', 1;

    /* 2. Expected row counts for the standard 2026-03-09..2026-03-13 source pack */
    IF @period_start = '2026-03-09' AND @period_end = '2026-03-13'
    BEGIN
        IF (SELECT COUNT(*) FROM stg.corrected_fact_checks)       <> 9231  THROW 51010, 'corrected_fact_checks row count mismatch',       1;
        IF (SELECT COUNT(*) FROM stg.corrected_fact_check_lines)  <> 25664 THROW 51011, 'corrected_fact_check_lines row count mismatch',  1;
        IF (SELECT COUNT(*) FROM stg.corrected_online_attribution)<> 2302  THROW 51012, 'corrected_online_attribution row count mismatch', 1;
        IF (SELECT COUNT(*) FROM stg.corrected_daily_sales)       <> 50    THROW 51013, 'corrected_daily_sales row count mismatch',        1;
        IF (SELECT COUNT(*) FROM stg.corrected_promo_cost)        <> 69    THROW 51014, 'corrected_promo_cost row count mismatch',         1;
        IF (SELECT COUNT(*) FROM stg.corrected_adjustment_decisions)<> 5   THROW 51015, 'corrected_adjustment_decisions row count mismatch',1;
        IF (SELECT COUNT(*) FROM stg.corrected_royalty_invoices)  <> 8     THROW 51016, 'corrected_royalty_invoices row count mismatch',   1;
        IF (SELECT COUNT(*) FROM stg.corrected_food_cost_variance)<> 190   THROW 51017, 'corrected_food_cost_variance row count mismatch', 1;
        IF (SELECT COUNT(*) FROM stg.corrected_region_daily_sales)<> 85    THROW 51018, 'corrected_region_daily_sales row count mismatch', 1;
        IF (SELECT COUNT(*) FROM stg.corrected_franchisee_invoices)<> 6    THROW 51019, 'corrected_franchisee_invoices row count mismatch',1;
    END

    /* 3. Swap — truncate gold tables and insert from staging (single-period snapshot model) */
    BEGIN TRANSACTION;
    BEGIN TRY
        TRUNCATE TABLE gold.corrected_run_inputs;           INSERT INTO gold.corrected_run_inputs           SELECT * FROM stg.corrected_run_inputs;
        TRUNCATE TABLE gold.corrected_promo_cost;           INSERT INTO gold.corrected_promo_cost           SELECT * FROM stg.corrected_promo_cost;
        TRUNCATE TABLE gold.corrected_fact_check_lines;     INSERT INTO gold.corrected_fact_check_lines     SELECT * FROM stg.corrected_fact_check_lines;
        TRUNCATE TABLE gold.corrected_fact_checks;          INSERT INTO gold.corrected_fact_checks          SELECT * FROM stg.corrected_fact_checks;
        TRUNCATE TABLE gold.corrected_online_attribution;   INSERT INTO gold.corrected_online_attribution   SELECT * FROM stg.corrected_online_attribution;
        TRUNCATE TABLE gold.corrected_daily_sales;          INSERT INTO gold.corrected_daily_sales          SELECT * FROM stg.corrected_daily_sales;
        TRUNCATE TABLE gold.corrected_adjustment_decisions; INSERT INTO gold.corrected_adjustment_decisions SELECT * FROM stg.corrected_adjustment_decisions;
        TRUNCATE TABLE gold.corrected_royalty_invoices;     INSERT INTO gold.corrected_royalty_invoices     SELECT * FROM stg.corrected_royalty_invoices;
        TRUNCATE TABLE gold.corrected_food_cost_variance;   INSERT INTO gold.corrected_food_cost_variance   SELECT * FROM stg.corrected_food_cost_variance;
        TRUNCATE TABLE gold.corrected_region_daily_sales;   INSERT INTO gold.corrected_region_daily_sales   SELECT * FROM stg.corrected_region_daily_sales;
        TRUNCATE TABLE gold.corrected_franchisee_invoices;  INSERT INTO gold.corrected_franchisee_invoices  SELECT * FROM stg.corrected_franchisee_invoices;
        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        ROLLBACK TRANSACTION;
        THROW;
    END CATCH;

    /* 4. Post-load financial spot-check */
    DECLARE @net_sales DECIMAL(19,4);
    SELECT @net_sales = SUM(net_sales) FROM gold.corrected_daily_sales;
    IF ABS(@net_sales - 268893.08) > 0.02
        THROW 51020, 'corrected_daily_sales net_sales total does not match archived baseline 268893.08', 1;

    DECLARE @invoice_total DECIMAL(19,4);
    SELECT @invoice_total = SUM(amount_due) FROM gold.corrected_royalty_invoices;
    IF ABS(@invoice_total - 17251.74) > 0.02
        THROW 51021, 'corrected_royalty_invoices amount_due total does not match archived baseline 17251.74', 1;

    PRINT 'gold.usp_LoadCorrectedGold: load complete. batch=' + @stg_batch
        + '  net_sales=' + CAST(@net_sales AS VARCHAR(20))
        + '  invoices=' + CAST(@invoice_total AS VARCHAR(20));
END;
GO
