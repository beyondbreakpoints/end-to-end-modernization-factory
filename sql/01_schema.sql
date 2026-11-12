/* =====================================================================================
   Polar Slice Pizza — Corrected Gold Mart  (Azure SQL Database)
   Modernized corrected results from nb_gold_corrected (Fabric medallion pipeline).
   Rules version: polarslice-corrected-v1
   Run order: 01_schema.sql, 02_load_procedures.sql, 03_validation.sql
   ===================================================================================== */
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = N'gold')
    EXEC('CREATE SCHEMA gold');
GO

/* ---------------------------------------------------------------- drop existing tables */
IF OBJECT_ID(N'gold.corrected_run_inputs',          N'U') IS NOT NULL DROP TABLE gold.corrected_run_inputs;
IF OBJECT_ID(N'gold.corrected_promo_cost',          N'U') IS NOT NULL DROP TABLE gold.corrected_promo_cost;
IF OBJECT_ID(N'gold.corrected_fact_check_lines',    N'U') IS NOT NULL DROP TABLE gold.corrected_fact_check_lines;
IF OBJECT_ID(N'gold.corrected_fact_checks',         N'U') IS NOT NULL DROP TABLE gold.corrected_fact_checks;
IF OBJECT_ID(N'gold.corrected_online_attribution',  N'U') IS NOT NULL DROP TABLE gold.corrected_online_attribution;
IF OBJECT_ID(N'gold.corrected_daily_sales',         N'U') IS NOT NULL DROP TABLE gold.corrected_daily_sales;
IF OBJECT_ID(N'gold.corrected_adjustment_decisions',N'U') IS NOT NULL DROP TABLE gold.corrected_adjustment_decisions;
IF OBJECT_ID(N'gold.corrected_royalty_invoices',    N'U') IS NOT NULL DROP TABLE gold.corrected_royalty_invoices;
IF OBJECT_ID(N'gold.corrected_food_cost_variance',  N'U') IS NOT NULL DROP TABLE gold.corrected_food_cost_variance;
IF OBJECT_ID(N'gold.corrected_region_daily_sales',  N'U') IS NOT NULL DROP TABLE gold.corrected_region_daily_sales;
IF OBJECT_ID(N'gold.corrected_franchisee_invoices', N'U') IS NOT NULL DROP TABLE gold.corrected_franchisee_invoices;
GO

/* ---------------------------------------------------------------- manifest */
CREATE TABLE gold.corrected_run_inputs (
    input_table      VARCHAR(80)   NOT NULL,
    input_batch_id   VARCHAR(50)   NOT NULL,
    row_count        BIGINT        NOT NULL,
    period_start     DATE          NOT NULL,
    period_end       DATE          NOT NULL,
    _gold_batch_id   VARCHAR(50)   NOT NULL,
    _rules_version   VARCHAR(50)   NOT NULL,
    CONSTRAINT PK_corrected_run_inputs PRIMARY KEY (input_table)
);
GO

/* ---------------------------------------------------------------- promotions */
CREATE TABLE gold.corrected_promo_cost (
    store_id         INT             NOT NULL,
    business_date    DATE            NOT NULL,
    promo_name       VARCHAR(20)     NOT NULL,
    discount_amount  DECIMAL(19,4)   NOT NULL,
    _gold_batch_id   VARCHAR(50)     NOT NULL,
    _rules_version   VARCHAR(50)     NOT NULL,
    CONSTRAINT PK_corrected_promo_cost PRIMARY KEY (store_id, business_date, promo_name)
);
GO

/* ---------------------------------------------------------------- POS check headers */
CREATE TABLE gold.corrected_fact_checks (
    store_id          INT             NOT NULL,
    business_date     DATE            NOT NULL,
    source_system     VARCHAR(10)     NOT NULL,   -- MICROS | ALOHA
    check_id          VARCHAR(30)     NOT NULL,
    check_key         VARCHAR(50)     NOT NULL,
    order_type        VARCHAR(20)         NULL,
    tender            VARCHAR(20)         NULL,
    gross             DECIMAL(19,4)   NOT NULL,
    discount          DECIMAL(19,4)   NOT NULL,
    net_sales         DECIMAL(19,4)   NOT NULL,
    tax               DECIMAL(19,4)   NOT NULL,
    tip               DECIMAL(19,4)   NOT NULL,
    total             DECIMAL(19,4)   NOT NULL,
    online_ref        VARCHAR(30)         NULL,
    is_online         BIT             NOT NULL,
    _source_file      VARCHAR(500)    NOT NULL,
    _batch_id         VARCHAR(50)     NOT NULL,
    _silver_batch_id  VARCHAR(50)     NOT NULL,
    _gold_batch_id    VARCHAR(50)     NOT NULL,
    _rules_version    VARCHAR(50)     NOT NULL,
    CONSTRAINT PK_corrected_fact_checks PRIMARY KEY (source_system, check_key)
);
CREATE INDEX IX_corrected_fact_checks_store_date ON gold.corrected_fact_checks (store_id, business_date);
GO

/* ---------------------------------------------------------------- POS check lines */
CREATE TABLE gold.corrected_fact_check_lines (
    store_id          INT             NOT NULL,
    business_date     DATE            NOT NULL,
    source_system     VARCHAR(10)     NOT NULL,
    check_key         VARCHAR(50)     NOT NULL,
    line_no           INT             NOT NULL,
    sku               VARCHAR(15)         NULL,
    source_item_code  VARCHAR(15)         NULL,
    qty               INT             NOT NULL,
    _source_file      VARCHAR(500)    NOT NULL,
    _batch_id         VARCHAR(50)     NOT NULL,
    _silver_batch_id  VARCHAR(50)     NOT NULL,
    _gold_batch_id    VARCHAR(50)     NOT NULL,
    _rules_version    VARCHAR(50)     NOT NULL,
    CONSTRAINT PK_corrected_fact_check_lines PRIMARY KEY (source_system, check_key, line_no)
);
GO

/* ---------------------------------------------------------------- online order attribution */
CREATE TABLE gold.corrected_online_attribution (
    order_id                    VARCHAR(30)     NOT NULL,
    store_id                    INT             NOT NULL,
    business_date               DATE            NOT NULL,
    status                      VARCHAR(20)         NULL,
    pos_match_status            VARCHAR(30)         NULL,
    pos_match_system            VARCHAR(10)         NULL,
    pos_match_check_key         VARCHAR(50)         NULL,
    pos_match_candidate_count   INT                 NULL,
    pos_match_best_tie_count    INT                 NULL,
    pos_match_time_delta_seconds FLOAT               NULL,
    attribution_status          VARCHAR(30)     NOT NULL,
    attributed_check_key        VARCHAR(50)         NULL,
    attributed_net_sales        DECIMAL(19,4)       NULL,
    incremental_net_sales       DECIMAL(19,4)   NOT NULL,
    _source_file                VARCHAR(500)    NOT NULL,
    _batch_id                   VARCHAR(50)     NOT NULL,
    _silver_batch_id            VARCHAR(50)     NOT NULL,
    _gold_batch_id              VARCHAR(50)     NOT NULL,
    _rules_version              VARCHAR(50)     NOT NULL,
    CONSTRAINT PK_corrected_online_attribution PRIMARY KEY (order_id)
);
GO

/* ---------------------------------------------------------------- daily store sales */
CREATE TABLE gold.corrected_daily_sales (
    store_id              INT             NOT NULL,
    business_date         DATE            NOT NULL,
    gross_sales           DECIMAL(19,4)   NOT NULL,
    discounts             DECIMAL(19,4)   NOT NULL,
    net_sales             DECIMAL(19,4)   NOT NULL,
    tax                   DECIMAL(19,4)   NOT NULL,
    tips                  DECIMAL(19,4)   NOT NULL,
    online_pos_net_sales  DECIMAL(19,4)   NOT NULL,
    check_count           INT             NOT NULL,
    tender_list           VARCHAR(100)        NULL,
    _gold_batch_id        VARCHAR(50)     NOT NULL,
    _rules_version        VARCHAR(50)     NOT NULL,
    CONSTRAINT PK_corrected_daily_sales PRIMARY KEY (store_id, business_date)
);
GO

/* ---------------------------------------------------------------- manual adjustment decisions */
CREATE TABLE gold.corrected_adjustment_decisions (
    adjustment_id    INT             NOT NULL,
    store_id         INT             NOT NULL,
    business_date    DATE            NOT NULL,
    adj_type         VARCHAR(30)         NULL,
    amount           DECIMAL(19,4)   NOT NULL,
    note             VARCHAR(200)        NULL,
    keyed_at         DATETIME2           NULL,
    duplicate_rank   INT             NOT NULL,
    is_included      BIT             NOT NULL,
    decision         VARCHAR(30)     NOT NULL,
    _gold_batch_id   VARCHAR(50)     NOT NULL,
    _rules_version   VARCHAR(50)     NOT NULL,
    CONSTRAINT PK_corrected_adjustment_decisions PRIMARY KEY (adjustment_id)
);
GO

/* ---------------------------------------------------------------- royalty invoices (store level) */
CREATE TABLE gold.corrected_royalty_invoices (
    franchisee_id    VARCHAR(10)     NOT NULL,
    franchisee_name  NVARCHAR(100)   NOT NULL,
    store_id         INT             NOT NULL,
    period_start     DATE            NOT NULL,
    period_end       DATE            NOT NULL,
    net_sales        DECIMAL(19,4)   NOT NULL,
    royalty          DECIMAL(19,4)   NOT NULL,
    ad_fund          DECIMAL(19,4)   NOT NULL,
    adjustments      DECIMAL(19,4)   NOT NULL,
    amount_due       DECIMAL(19,4)   NOT NULL,
    _gold_batch_id   VARCHAR(50)     NOT NULL,
    _rules_version   VARCHAR(50)     NOT NULL,
    CONSTRAINT PK_corrected_royalty_invoices PRIMARY KEY (store_id, period_start, period_end)
);
GO

/* ---------------------------------------------------------------- food cost variance */
CREATE TABLE gold.corrected_food_cost_variance (
    store_id           INT             NOT NULL,
    period_start       DATE            NOT NULL,
    period_end         DATE            NOT NULL,
    item_code          VARCHAR(15)     NOT NULL,
    base_uom           VARCHAR(5)      NOT NULL,
    opening_qty        DECIMAL(18,3)   NOT NULL,
    received_qty       DECIMAL(18,3)   NOT NULL,
    closing_qty        DECIMAL(18,3)   NOT NULL,
    actual_usage       DECIMAL(18,3)   NOT NULL,
    theoretical_usage  DECIMAL(18,3)   NOT NULL,
    variance           DECIMAL(18,3)   NOT NULL,
    variance_pct       DECIMAL(12,1)       NULL,   -- NULL when theoretical_usage = 0
    variance_cost      DECIMAL(19,4)   NOT NULL,
    _gold_batch_id     VARCHAR(50)     NOT NULL,
    _rules_version     VARCHAR(50)     NOT NULL,
    CONSTRAINT PK_corrected_food_cost_variance PRIMARY KEY (store_id, period_start, period_end, item_code)
);
GO

/* ---------------------------------------------------------------- region / org-unit daily sales */
CREATE TABLE gold.corrected_region_daily_sales (
    unit_id        INT             NOT NULL,
    unit_name      NVARCHAR(100)   NOT NULL,
    unit_type      VARCHAR(20)     NOT NULL,
    business_date  DATE            NOT NULL,
    net_sales      DECIMAL(19,4)   NOT NULL,
    _gold_batch_id VARCHAR(50)     NOT NULL,
    _rules_version VARCHAR(50)     NOT NULL,
    CONSTRAINT PK_corrected_region_daily_sales PRIMARY KEY (unit_id, business_date)
);
GO

/* ---------------------------------------------------------------- franchisee rollup invoices */
CREATE TABLE gold.corrected_franchisee_invoices (
    franchisee_id    VARCHAR(10)     NOT NULL,
    franchisee_name  NVARCHAR(100)   NOT NULL,
    period_start     DATE            NOT NULL,
    period_end       DATE            NOT NULL,
    stores           INT             NOT NULL,
    net_sales        DECIMAL(19,4)   NOT NULL,
    royalty          DECIMAL(19,4)   NOT NULL,
    ad_fund          DECIMAL(19,4)   NOT NULL,
    adjustments      DECIMAL(19,4)   NOT NULL,
    amount_due       DECIMAL(19,4)   NOT NULL,
    _gold_batch_id   VARCHAR(50)     NOT NULL,
    _rules_version   VARCHAR(50)     NOT NULL,
    CONSTRAINT PK_corrected_franchisee_invoices PRIMARY KEY (franchisee_id, period_start, period_end)
);
GO
