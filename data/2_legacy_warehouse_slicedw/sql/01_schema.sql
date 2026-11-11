/* =====================================================================================
   SliceDW  -  Polar Slice Pizza legacy data warehouse (fictional)
   Originally built on SQL Server 2016, loaded nightly by SSIS. Deploy to Azure SQL Database.
   Run order: 01_schema.sql, 02_programmability.sql, 03_reference_data.sql, 04_*.sql, 05_run_legacy.sql
   ===================================================================================== */
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO
CREATE SCHEMA stg;
GO
CREATE SCHEMA cfg;
GO
CREATE SCHEMA dw;
GO
CREATE SCHEMA rpt;
GO
CREATE SCHEMA adj;
GO

/* ---------------------------------------------------------------- staging (landed by SSIS) */
CREATE TABLE stg.micros_check_header (
    store          INT          NOT NULL,
    business_date  DATE         NOT NULL,
    check_no       INT          NOT NULL,
    open_time      TIME(0)      NOT NULL,
    close_time     TIME(0)      NOT NULL,
    order_type     VARCHAR(10)  NOT NULL,
    guest_count    INT          NOT NULL,
    subtotal       MONEY        NOT NULL,
    discount       MONEY        NOT NULL,
    tax            MONEY        NOT NULL,
    tip            MONEY        NOT NULL,
    total          MONEY        NOT NULL,
    tender         VARCHAR(10)  NOT NULL,
    void_flag      CHAR(1)      NOT NULL,
    online_ref     VARCHAR(20)  NULL,
    employee_id    VARCHAR(10)  NULL,
    load_ts        DATETIME     NOT NULL CONSTRAINT DF_stg_mch_load_ts DEFAULT (GETDATE())
);

CREATE TABLE stg.micros_check_detail (
    store          INT          NOT NULL,
    business_date  DATE         NOT NULL,
    check_no       INT          NOT NULL,
    line_no        INT          NOT NULL,
    item_no        INT          NOT NULL,
    item_name      VARCHAR(30)  NOT NULL,
    qty            INT          NOT NULL,
    unit_price     MONEY        NOT NULL,
    line_amount    MONEY        NOT NULL,
    line_type      VARCHAR(5)   NOT NULL,
    load_ts        DATETIME     NOT NULL CONSTRAINT DF_stg_mcd_load_ts DEFAULT (GETDATE())
);

CREATE TABLE stg.aloha_checks (
    store          INT          NOT NULL,
    dob            CHAR(8)      NOT NULL,
    checkid        INT          NOT NULL,
    tablenum       VARCHAR(5)   NULL,
    ordermode      VARCHAR(10)  NOT NULL,
    opentime       DATETIME     NOT NULL,
    closetime      DATETIME     NOT NULL,
    gross          MONEY        NOT NULL,
    comp           MONEY        NOT NULL,
    nettotal       MONEY        NOT NULL,
    taxincl        MONEY        NOT NULL,
    tip            MONEY        NOT NULL,
    total          MONEY        NOT NULL,
    paytype        VARCHAR(12)  NOT NULL,
    employee       VARCHAR(10)  NULL,
    load_ts        DATETIME     NOT NULL CONSTRAINT DF_stg_alc_load_ts DEFAULT (GETDATE())
);

CREATE TABLE stg.aloha_items (
    store          INT          NOT NULL,
    dob            CHAR(8)      NOT NULL,
    checkid        INT          NOT NULL,
    entryid        INT          NOT NULL,
    itemcode       VARCHAR(10)  NOT NULL,
    itemname       VARCHAR(20)  NOT NULL,
    qty            INT          NOT NULL,
    price          MONEY        NOT NULL,
    amount         MONEY        NOT NULL,
    type           VARCHAR(5)   NOT NULL,
    ordertime      DATETIME     NOT NULL,
    load_ts        DATETIME     NOT NULL CONSTRAINT DF_stg_ali_load_ts DEFAULT (GETDATE())
);

CREATE TABLE stg.online_order (
    order_id        VARCHAR(20)        NOT NULL,
    placed_at       DATETIMEOFFSET(0)  NOT NULL,
    store_id        INT                NOT NULL,
    channel         VARCHAR(5)         NOT NULL,
    fulfilment      VARCHAR(10)        NOT NULL,
    status          VARCHAR(12)        NOT NULL,
    promo_code      VARCHAR(12)        NULL,
    customer_id     INT                NOT NULL,
    customer_name   NVARCHAR(100)      NULL,
    customer_email  NVARCHAR(200)      NULL,
    customer_phone  VARCHAR(25)        NULL,
    subtotal        MONEY              NOT NULL,
    discount        MONEY              NOT NULL,
    tax             MONEY              NOT NULL,
    tip             MONEY              NOT NULL,
    total           MONEY              NOT NULL,
    pos_check_no    INT                NULL,
    load_ts         DATETIME           NOT NULL CONSTRAINT DF_stg_oo_load_ts DEFAULT (GETDATE())
);

CREATE TABLE stg.online_order_item (
    order_id       VARCHAR(20)   NOT NULL,
    line_no        INT           NOT NULL,
    sku            VARCHAR(12)   NOT NULL,
    item_name      NVARCHAR(60)  NOT NULL,
    qty            INT           NOT NULL,
    unit_price     MONEY         NOT NULL
);

CREATE TABLE stg.online_customer (
    customer_id      INT            NOT NULL,
    full_name        NVARCHAR(100)  NOT NULL,
    email            NVARCHAR(200)  NULL,
    phone            VARCHAR(25)    NULL,
    created_at       DATETIME       NOT NULL,
    home_store_id    INT            NULL,
    loyalty_points   INT            NOT NULL,
    marketing_opt_in BIT            NOT NULL
);

-- AS/400 extracts land as raw fixed-width lines; the procedures cut them up
CREATE TABLE stg.as400_itemmast_raw (raw_line CHAR(47) NOT NULL);
CREATE TABLE stg.as400_shipment_raw (file_name VARCHAR(20) NOT NULL, line_no INT NOT NULL, raw_line CHAR(59) NOT NULL);
CREATE TABLE stg.as400_count_raw    (file_name VARCHAR(20) NOT NULL, line_no INT NOT NULL, raw_line CHAR(31) NOT NULL);

/* ---------------------------------------------------------------- configuration */
CREATE TABLE cfg.Store (
    store_id         INT           NOT NULL CONSTRAINT PK_cfg_Store PRIMARY KEY,
    store_name       VARCHAR(40)   NOT NULL,
    city             VARCHAR(40)   NOT NULL,
    province         CHAR(2)       NOT NULL,
    ownership        VARCHAR(10)   NOT NULL,
    franchisee_id    VARCHAR(10)   NULL,
    franchisee_name  VARCHAR(60)   NULL,
    pos_system       VARCHAR(10)   NOT NULL,
    open_date        DATE          NOT NULL
);

CREATE TABLE cfg.MenuItem (
    sku              VARCHAR(12)   NOT NULL CONSTRAINT PK_cfg_MenuItem PRIMARY KEY,
    item_name        VARCHAR(60)   NOT NULL,
    category         VARCHAR(10)   NOT NULL,
    size             CHAR(1)       NULL,
    price_excl_tax   MONEY         NOT NULL,
    micros_item_no   INT           NOT NULL
);

-- Keyed in by hand after the 2022 acquisition; never finished
CREATE TABLE cfg.AlohaItemMap (
    aloha_item_code  VARCHAR(10)   NOT NULL CONSTRAINT PK_cfg_AlohaItemMap PRIMARY KEY,
    sku              VARCHAR(12)   NOT NULL CONSTRAINT FK_AlohaItemMap_MenuItem REFERENCES cfg.MenuItem (sku),
    mapped_by        VARCHAR(30)   NULL,
    mapped_on        DATETIME      NULL
);

CREATE TABLE cfg.Recipe (
    sku                   VARCHAR(12)   NOT NULL CONSTRAINT FK_Recipe_MenuItem REFERENCES cfg.MenuItem (sku),
    ingredient_item_code  VARCHAR(8)    NOT NULL,
    qty_per_unit          DECIMAL(9,3)  NOT NULL,
    base_uom              CHAR(2)       NOT NULL,
    CONSTRAINT PK_cfg_Recipe PRIMARY KEY (sku, ingredient_item_code)
);

CREATE TABLE cfg.RoyaltyTerm (
    term_code   VARCHAR(30)    NOT NULL CONSTRAINT PK_cfg_RoyaltyTerm PRIMARY KEY,
    term_value  DECIMAL(9,4)   NOT NULL,
    note        VARCHAR(200)   NULL
);

CREATE TABLE cfg.OrgUnit (
    unit_id         INT          NOT NULL CONSTRAINT PK_cfg_OrgUnit PRIMARY KEY,
    parent_unit_id  INT          NULL CONSTRAINT FK_OrgUnit_Parent REFERENCES cfg.OrgUnit (unit_id),
    unit_name       VARCHAR(60)  NOT NULL,
    unit_type       VARCHAR(10)  NOT NULL,
    store_id        INT          NULL
);

CREATE TABLE cfg.EtlRunLog (
    run_id         INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_cfg_EtlRunLog PRIMARY KEY,
    proc_name      VARCHAR(100)  NOT NULL,
    business_date  DATE          NULL,
    started_at     DATETIME      NOT NULL,
    finished_at    DATETIME      NOT NULL,
    rows_affected  INT           NULL
);

/* ---------------------------------------------------------------- manual adjustments (from Excel) */
CREATE TABLE adj.ManualAdjustment (
    adj_id         INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_adj_ManualAdjustment PRIMARY KEY,
    store_id       INT            NOT NULL CONSTRAINT FK_ManualAdjustment_Store REFERENCES cfg.Store (store_id),
    business_date  DATE           NOT NULL,
    adj_type       VARCHAR(20)    NOT NULL,
    amount         MONEY          NOT NULL,
    note           NVARCHAR(200)  NULL,
    keyed_by       VARCHAR(30)    NOT NULL,
    keyed_at       DATETIME       NOT NULL
);

CREATE TABLE adj.ManualAdjustmentAudit (
    audit_id    INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_adj_ManualAdjustmentAudit PRIMARY KEY,
    adj_id      INT       NOT NULL,
    action      CHAR(1)   NOT NULL,
    amount      MONEY     NULL,
    changed_by  SYSNAME   NOT NULL CONSTRAINT DF_adj_audit_by DEFAULT (SUSER_SNAME()),
    changed_at  DATETIME  NOT NULL CONSTRAINT DF_adj_audit_at DEFAULT (GETDATE())
);

/* ---------------------------------------------------------------- warehouse */
CREATE TABLE dw.DimDate (
    date_key       INT          NOT NULL CONSTRAINT PK_dw_DimDate PRIMARY KEY,
    calendar_date  DATE         NOT NULL,
    day_name       VARCHAR(10)  NOT NULL,
    is_2for1       BIT          NOT NULL
);

CREATE TABLE dw.DimItem (
    item_code   VARCHAR(8)    NOT NULL CONSTRAINT PK_dw_DimItem PRIMARY KEY,
    item_desc   VARCHAR(20)   NOT NULL,
    pack_uom    CHAR(2)       NOT NULL,
    base_uom    CHAR(2)       NOT NULL,
    pack_qty    DECIMAL(9,3)  NOT NULL,
    pack_cost   MONEY         NOT NULL
);

CREATE TABLE dw.FactCheck (
    fact_check_id  INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_dw_FactCheck PRIMARY KEY,
    store_id       INT          NOT NULL CONSTRAINT FK_FactCheck_Store REFERENCES cfg.Store (store_id),
    business_date  DATE         NOT NULL,
    source_system  VARCHAR(6)   NOT NULL,
    check_id       VARCHAR(20)  NOT NULL,
    order_type     VARCHAR(10)  NOT NULL,
    tender         VARCHAR(12)  NULL,
    gross          MONEY        NOT NULL,
    discount       MONEY        NOT NULL,
    tax            MONEY        NOT NULL,
    tip            MONEY        NOT NULL,
    net_sales      MONEY        NOT NULL,
    online_ref     VARCHAR(20)  NULL,
    loaded_at      DATETIME     NOT NULL CONSTRAINT DF_dw_FactCheck_loaded DEFAULT (GETDATE())
);

CREATE TABLE dw.FactCheckLine (
    fact_line_id      INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_dw_FactCheckLine PRIMARY KEY,
    store_id          INT          NOT NULL,
    business_date     DATE         NOT NULL,
    source_system     VARCHAR(6)   NOT NULL,
    check_id          VARCHAR(20)  NOT NULL,
    sku               VARCHAR(12)  NULL,
    source_item_code  VARCHAR(10)  NOT NULL,
    qty               INT          NOT NULL,
    amount            MONEY        NOT NULL
);

CREATE TABLE dw.FactOnlineOrder (
    order_id             VARCHAR(20)  NOT NULL CONSTRAINT PK_dw_FactOnlineOrder PRIMARY KEY,
    store_id             INT          NOT NULL,
    business_date        DATE         NOT NULL,
    status               VARCHAR(12)  NOT NULL,
    net_sales            MONEY        NOT NULL,
    pos_check_no         INT          NULL,
    is_duplicate_of_pos  BIT          NOT NULL CONSTRAINT DF_dw_FOO_dup DEFAULT (0)
);

CREATE TABLE dw.FactDailySales (
    store_id           INT           NOT NULL,
    business_date      DATE          NOT NULL,
    gross_sales        MONEY         NOT NULL,
    discounts          MONEY         NOT NULL,
    voids              MONEY         NOT NULL,
    net_sales_tills    MONEY         NOT NULL,
    online_only_sales  MONEY         NOT NULL,
    net_sales          MONEY         NOT NULL,
    tax                MONEY         NOT NULL,
    check_count        INT           NOT NULL,
    tender_list        VARCHAR(200)  NULL,
    built_at           DATETIME      NOT NULL CONSTRAINT DF_dw_FDS_built DEFAULT (GETDATE()),
    CONSTRAINT PK_dw_FactDailySales PRIMARY KEY (store_id, business_date)
);

CREATE TABLE dw.FactShipment (
    store_id     INT           NOT NULL,
    ship_date    DATE          NOT NULL,
    item_code    VARCHAR(8)    NOT NULL,
    qty_cases    DECIMAL(9,2)  NOT NULL,
    ext_cost     MONEY         NOT NULL,
    source_file  VARCHAR(20)   NOT NULL
);

CREATE TABLE dw.FactStockCount (
    store_id    INT            NOT NULL,
    count_date  DATE           NOT NULL,
    count_type  CHAR(1)        NOT NULL,
    item_code   VARCHAR(8)     NOT NULL,
    qty         DECIMAL(12,3)  NOT NULL
);

/* ---------------------------------------------------------------- reporting */
CREATE TABLE rpt.RoyaltyInvoice (
    invoice_id       INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_rpt_RoyaltyInvoice PRIMARY KEY,
    franchisee_id    VARCHAR(10)  NOT NULL,
    franchisee_name  VARCHAR(60)  NOT NULL,
    store_id         INT          NOT NULL,
    period_start     DATE         NOT NULL,
    period_end       DATE         NOT NULL,
    net_sales        MONEY        NOT NULL,
    royalty          MONEY        NOT NULL,
    ad_fund          MONEY        NOT NULL,
    adjustments      MONEY        NOT NULL,
    amount_due       MONEY        NOT NULL,
    created_at       DATETIME     NOT NULL CONSTRAINT DF_rpt_RI_created DEFAULT (GETDATE())
);

CREATE TABLE rpt.FoodCostVariance (
    store_id           INT            NOT NULL,
    period_start       DATE           NOT NULL,
    period_end         DATE           NOT NULL,
    item_code          VARCHAR(8)     NOT NULL,
    opening_qty        DECIMAL(12,3)  NOT NULL,
    received_qty       DECIMAL(12,3)  NOT NULL,
    closing_qty        DECIMAL(12,3)  NOT NULL,
    actual_usage       DECIMAL(12,3)  NOT NULL,
    theoretical_usage  DECIMAL(12,3)  NOT NULL,
    variance           DECIMAL(12,3)  NOT NULL,
    variance_pct       DECIMAL(9,1)   NULL,
    variance_cost      MONEY          NOT NULL
);

CREATE TABLE rpt.PromoCost (
    store_id         INT          NOT NULL,
    business_date    DATE         NOT NULL,
    promo_name       VARCHAR(12)  NOT NULL,
    discount_amount  MONEY        NOT NULL
);

CREATE TABLE rpt.RegionDailySales (
    unit_id        INT          NOT NULL,
    unit_name      VARCHAR(60)  NOT NULL,
    unit_type      VARCHAR(10)  NOT NULL,
    business_date  DATE         NOT NULL,
    net_sales      MONEY        NOT NULL
);
GO
