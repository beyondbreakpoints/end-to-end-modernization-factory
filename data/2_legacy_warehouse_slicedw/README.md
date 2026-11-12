# 2. Legacy warehouse: SliceDW

SliceDW is the legacy warehouse that produces Polar Slice's daily sales reports, royalty invoices and food cost reports. It was built on SQL Server 2016 and loaded nightly by SSIS. In the hackathon it's the source for:

- **The Migration Assistant**, via a DACPAC extracted from it.
- **The AI dossier**, via its stored procedures and SSIS packages.
- **The reconciliation**, via its reports, which a migration must first reproduce exactly.

## What's here

| Item | What it is |
|---|---|
| `sql/01_schema.sql` | Schemas and tables |
| `sql/02_programmability.sql` | Functions, synonyms, the trigger, views and the 14 stored procedures. **The business rules (and bugs) are here** |
| `sql/03_reference_data.sql` | Stores, menu, Aloha item map, recipes, royalty terms, org hierarchy, calendar, manual adjustments |
| `sql/04a` to `04h` | Staging data: the source files as SSIS would have landed them (about 4.7 MB) |
| `sql/05_run_legacy.sql` | Runs the legacy processing for 9–13 March and shows the results |
| `ssis_packages/` | Simplified versions of the five SSIS packages. They show what loads what, for the AI dossier's dependency graph; they're not meant to be run |
| `ManualAdjustments_March2026.csv` | The finance team's manual adjustments spreadsheet (the "Excel" that `LoadAdjustments` reads) |

## Deploy it

1. Create an Azure SQL Database called `SliceDW`. The smallest paid tier is enough.
2. Run the scripts in `sql/` in name order: `01`, `02`, `03`, `04a` to `04h`, then `05`. Use Azure Data Studio, SSMS, VS Code's SQL Server extension, or `sqlcmd`. With `sqlcmd`, from the `sql` folder:

   ```
   for f in 0*.sql; do sqlcmd -S <server>.database.windows.net -d SliceDW -U <user> -P <password> -f 65001 -i "$f" || break; done
   ```

   The Azure portal's query editor is likely to struggle with the larger `04` files.
3. `05_run_legacy.sql` runs `dw.usp_RunPeriod` for 9–13 March, which fills the warehouse and the reports, then shows the results.
4. Check the `rpt` tables against `3_answer_key/slicedw_legacy_*.csv`. Those numbers come from a Python copy of the procedures, because SQL Server couldn't be run when the data was generated. They should match exactly, apart from a possible one-cent rounding difference in food cost. If a script fails or a number doesn't match, the scripts need a fix.
5. For the Migration Assistant, extract a DACPAC (schema only):

   ```
   sqlpackage /Action:Extract /SourceConnectionString:"<connection string>" /TargetFile:SliceDW.dacpac
   ```

## Inside the database

| Schema | Holds |
|---|---|
| `stg` | Raw data as SSIS landed it from the source systems |
| `cfg` | Stores, menu, the hand-keyed Aloha item map, recipes, royalty terms, the org hierarchy, the ETL run log |
| `adj` | Manual adjustments from the spreadsheet, with an audit trigger |
| `dw` | Facts and dimensions, and the stored procedures |
| `rpt` | Daily sales, royalty invoices, food cost variance, promo cost and region rollups |

The nightly flow: `Nightly_Master.dtsx` runs `LoadTills`, `LoadOnline`, `LoadCommissary` and `LoadAdjustments` into `stg` and `adj`, then calls `dw.usp_RunNightly`, which loads the facts and builds daily sales and promo cost. At period end, `dw.usp_RunPeriod` also loads the commissary data and builds royalty invoices, food cost variance and region rollups.

## T-SQL for the Migration Assistant to fix

The procedures use T-SQL typical of the era that Fabric Warehouse doesn't fully support: a recursive CTE (`usp_BuildRegionRollup`), `FOR XML PATH` (`usp_BuildNetSales`), `SET TRANSACTION ISOLATION LEVEL` and `SET ROWCOUNT`, a cursor (`usp_RunPeriod`), a trigger, synonyms, an indexed view (`rpt.vw_StoreDaySales`), a scalar function, enforced foreign keys, and `MONEY`, `DATETIME`, `DATETIMEOFFSET` and `NVARCHAR` columns. The Migration Assistant's own report is the authority on what needs fixing.

## SliceDW's bugs

The warehouse carries some of the source problems through and adds its own. These are why its numbers are wrong:

| Bug | Where | Effect |
|---|---|---|
| Gift card loads counted as sales | `usp_LoadFactCheckMicros` | Sales overstated |
| Void rows skipped, so voided checks still count | `usp_LoadFactCheckMicros` | Sales overstated |
| No dedupe of re-polled checks | `usp_LoadFactCheckMicros` | Store 1061 overstated |
| Aloha NETTOTAL treated as net, though it includes tax | `usp_LoadFactCheckAloha` | Aloha stores overstated by 13% |
| Aloha dated by close time instead of DOB | `usp_LoadFactCheckAloha` | After-midnight sales land on the wrong day; the last night's are lost |
| Aloha online orders can't be matched to the app, so both count | `usp_DedupOnline` | Aloha stores overstated |
| Status filter checks for `refunded`, so cancelled app orders count | `usp_LoadFactOnline` | Small overstatement everywhere |
| Royalty holiday hard-coded as 3 months; the agreement and `cfg.RoyaltyTerm` say 6 | `usp_CalcRoyalty` | Store 1078 billed when it shouldn't be |
| A marketing credit keyed in twice | `adj.ManualAdjustment` | Store 1055 under-billed by $120 |
| Every shipment line read as cases, and the credit sign ignored | `usp_LoadCommissary` | Aloha stores' cheese use overstated about tenfold |
| Aloha item map incomplete, and MDVEG mapped to the large size | `cfg.AlohaItemMap` | Theoretical usage wrong for Aloha stores |
| Aloha comps include tax | `usp_BuildPromoCost` | Promo cost overstated at Aloha stores |

Same-store sales growth needs a comparison period, so it can only be calculated from a longer data set (see `4_generator/README.md`).
