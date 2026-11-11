# Project overview

## Purpose

Polar Slice Pizza is the fictional case study for the **AI-Accelerated Legacy-to-Fabric Modernization Factory**. The project modernizes five operational source systems and the existing SQL Server warehouse, SliceDW, whose reported results contain known defects. It demonstrates a traceable path from raw source data to curated analytics, reconciliation, and a deployable SQL warehouse.

The intended work order is:

1. Ingest source extracts into Bronze.
2. Normalize and type data in Silver while retaining evidence of anomalies.
3. Build Gold first to reproduce SliceDW, then build corrected business results.
4. Reconcile legacy, corrected, and answer-key results.
5. Deploy the legacy warehouse/dossier through Azure SQL assets.

## Business and data context

- Source systems: MICROS POS, Aloha POS, online ordering app, AS/400 commissary, and master data; SliceDW is the legacy warehouse.
- The reporting window is **2026-03-09 through 2026-03-13**, Monday to Friday. Tuesday, March 10 has a 2-for-1 promotion.
- The business operates 10 Ontario stores: MICROS stores 1042, 1043, 1055, 1061, 1078, 1090, 3015; Aloha stores 2207, 2214, 2231. HST is 13%; timestamps use Eastern time (UTC-04:00 for this data period).
- Till/POS systems are authoritative for completed sales. Every completed app order also appears as a till check, so app and POS sales must not be added together.
- Source-specific anomalies are intentional challenge material. Preserve them and their provenance so the legacy reproduction and corrected views can be explained.

## Repository and runtime

- `data/` contains the source pack (excluding the answer key), legacy SliceDW materials, and generator/pack documentation.
- `fabric/` contains Fabric workspace items: `lh_polarslice` and the Bronze notebooks.
- `docs/onelake-upload.md` documents loading source files to OneLake.
- `sql/` is reserved for the Azure SQL deployment and related dossier work.
- Fabric Git is configured to synchronize `/fabric` from branch `NG/Dev`. Git synchronization moves Fabric items, not the source data files; the user uploads the source folders separately to the lakehouse.
- Lakehouse `lh_polarslice` is schema-enabled. Bronze tables live in `bronze`; Silver and Gold are planned in their own schemas.

## Current state

According to the prior session handoff, Bronze is implemented and was run successfully by the user in Fabric, with all notebook assertions passing. Silver transformations and an ordered runner are now implemented on `NG/Dev`; they still need to be synchronized to and executed in Fabric. The Gold, reconciliation, Azure SQL, and dossier phases remain ahead. Treat this as a handoff snapshot, not a live check of the Fabric workspace or Silver execution.

## Success criteria

The finished project should retain lineage from source files through each layer, reproduce SliceDW results before correcting them, document why corrected values differ, reconcile to the answer key without publishing it, and present the completed work on `main` through a reviewed PR from `NG/Dev`.