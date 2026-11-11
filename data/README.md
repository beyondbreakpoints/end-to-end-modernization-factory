# Polar Slice Pizza: hackathon data pack

**Start here.** This pack is everything the team needs to run the AI-Accelerated Legacy-to-Fabric Modernization Factory challenge on the Polar Slice Pizza case. Polar Slice and all its data are fictional.

## The story in brief

Polar Slice is a pizza chain that bought a rival in 2022 and never merged the two sets of systems. Head office's sales figures never match the stores' tills, franchisees are disputing their royalty bills, and nobody can explain where the cheese goes. The data comes from five legacy systems, each with its own quirks, plus a SQL Server warehouse (SliceDW) whose numbers nobody trusts.

The job: move it all into Microsoft Fabric, first reproduce SliceDW's numbers exactly, then show where and why they're wrong.

## What's in the pack

| Folder | What it is | What to do with it |
|---|---|---|
| `1_source_systems/` | Files from the five legacy sources: head office master data, two till systems, the online ordering app and the AS/400 commissary | Load into the Fabric lakehouse (Bronze) |
| `2_legacy_warehouse_slicedw/` | The legacy warehouse: SQL scripts, staging data, SSIS packages and a manual adjustments spreadsheet | Deploy to Azure SQL Database; it feeds the Migration Assistant, the AI dossier and the reconciliation |
| `3_answer_key/` | The correct figures, SliceDW's wrong figures, and a list of every planted problem | **Don't load it into the pipeline.** Use it only to check your results |
| `4_generator/` | The Python scripts that produced all of the above | Rerun to regenerate or to make a bigger data set |

Every folder has its own README with the details.

## The data at a glance

- **Dates:** Monday 9 March to Friday 13 March 2026 (5 business days). Tuesday 10 March is 2-for-1 Tuesday.
- **Stores:** 10 stores in Ontario.

| Store | Location | Till | Owner |
|---|---|---|---|
| 1042 | Toronto, Queen St West | MICROS | Rana Holdings Inc. (F001) |
| 1043 | Toronto, Danforth | MICROS | Kostas Food Group Ltd. (F002) |
| 1055 | Mississauga, Square One | MICROS | Rana Holdings Inc. (F001) |
| 1061 | Hamilton, James St North | MICROS | Steeltown Slices Inc. (F003) |
| 1078 | Oakville, Kerr Village | MICROS | Lakeshore QSR Corp. (F004), opened December 2025 |
| 1090 | Brampton, Bramalea | MICROS | Dhillon Family Foods Ltd. (F005) |
| 3015 | Toronto, Yonge & Eglinton | MICROS | Corporate (pays no royalty) |
| 2207 | Ottawa, Bank St | Aloha | Rideau Pizza Partners (F006) |
| 2214 | Kingston, Princess St | Aloha | Rideau Pizza Partners (F006) |
| 2231 | Barrie, Bayfield | Aloha | Georgian Bay Eats Inc. (F007) |

The three Aloha stores are the ones acquired in 2022.

## Where to start, by workstream

| Workstream | Start with |
|---|---|
| Lakehouse build (Bronze, Silver, Gold) | `1_source_systems/README.md`, then each system's README |
| Warehouse conversion and governance | `2_legacy_warehouse_slicedw/README.md`: deploy SliceDW, extract the DACPAC, run the Migration Assistant, point Purview at it |
| AI dossier | `2_legacy_warehouse_slicedw/sql/02_programmability.sql` (the business rules) and `ssis_packages/` (what loads what) |
| Reconciliation | `3_answer_key/README.md` |

## The planted problems, in one line each

- **Tills:** gift card loads rung up as sales, voids posted after close, checks sent twice.
- **Aloha:** prices include tax, the business day ends at 4 a.m., item codes head office doesn't know.
- **Online app:** every order is also a till sale, some orders were cancelled, some customers have two accounts.
- **Commissary:** cheese shipped in kilograms instead of cases, credits marked only by a minus sign, two stores losing cheese.
- **SliceDW:** twelve bugs of its own, from tax-inclusive Aloha sales to a royalty holiday coded as 3 months instead of 6.

The full list, with counts, is in `3_answer_key/README.md`.
