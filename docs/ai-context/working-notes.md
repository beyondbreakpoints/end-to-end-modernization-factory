# Working notes

This file retains project-operating details from the prior session that do not belong solely to the overview, architecture decisions, backlog, or roadmap.

## Source files and Fabric upload

- The source pack is provided separately from Git. Upload the folders `aloha/`, `as400_commissary/`, `master_data/`, `micros/`, and `online_app/` directly under the lakehouse `Files/` root. Do not add a `polar_slice/` parent folder.
- `docs/onelake-upload.md` describes the supported upload methods (Fabric UI, OneLake File Explorer, and `azcopy`) and verification.
- Fabric Git sync handles Fabric workspace items, not files in OneLake. Keep data upload and item synchronization as separate operational steps.

## Working conventions and cautions

- The integration branch is `NG/Dev`; the final presentation target is `main` via a single PR after the complete workflow.
- Avoid switching the linked Fabric workspace to branches without `fabric/`. Branch changes can remove workspace items that are absent from the selected branch, even though OneLake data itself is not removed.
- The answer key is for checking only. It must remain outside the public repository, commits, notebooks, and pipeline.
- A previous worktree/branch name and past PR numbers in the handoff are historical references, not instructions to reuse them.
- Guide Fabric UI operations one step at a time when user interaction is needed.
- Keep notebook `# META` blocks in Fabric's canonical multi-line, 2-space-indented JSON. The earlier claim that formatting fixed "No default context found" was unverified; the user subsequently identified an incorrect lakehouse item. Verify the actual lakehouse identity, not just its display name, and its default attachment.
- Fabric Python-source parameter cells use `# PARAMETERS CELL ********************`, not ordinary `# CELL` blocks with a `parameters` tag. Silver and Gold now use the native marker. The Silver runner validates every output against its own batch ID; Gold retains its cross-table consistency guard. A reported successful Silver run previously wrote five source-specific UUIDs instead of the runner UUID, exposing the missing parameter propagation.

## Handoff uncertainty

The previous conversation mentioned “item 3” and later asked for step-by-step guidance. The prior assistant interpreted that as the upload step, but the phrase could have referred to Gold. Silver must precede Gold; confirm the intended step if this comes up again.

## Silver implementation handoff

- Five source-specific Silver notebooks and `nb_silver_run_all` are now in `fabric/`; run the orchestrator only after Bronze is available.
- The Silver runner calls master data, MICROS, Aloha, AS/400, then online app so its lookup and POS-matching dependencies exist.
- Silver flags and retains anomalous rows; Gold must explicitly decide business inclusion. `_batch_id` remains Bronze provenance, while `_silver_batch_id` identifies the transformation run.
- Local Python syntax and Fabric metadata were checked; live Spark/Fabric execution and output assertions remain pending.

## Silver menu-mapping fix

- The initial Fabric master-data run failed because the notebook incorrectly required unique menu prices. The source has 19 SKUs but 17 distinct prices. SKU and MICROS item-number uniqueness remain enforced.
- Aloha now uses explicit code-to-SKU mappings, checked against source names and tax-inclusive menu prices, rather than a price-only join. Unknown codes and name/price mismatches are flagged with null SKUs, printed as diagnostics, and stop publication. Mapping must preserve the source row count.
- Local PySpark execution of the master-data and Aloha transformations passed against the source pack, preserving all 7,341 Aloha lines and mapping all 19 item codes. Regression cases also cover unknown codes, name/price mismatches, and comp lines. Delta writes and Fabric orchestration are not exercised by these local tests.
- Run these regressions with Java 17 and PySpark 3.5 installed: `python -m unittest discover -s tests -p test_silver_menu_mapping.py -v`.
- Sync the fixes from `NG/Dev` and rerun `nb_silver_run_all` in Fabric. The earlier failed run may have written `silver.stores`; rerunning overwrites the Silver outputs without changing Bronze.

## Gold milestone 1 handoff

- User reported all Silver notebooks `Succeeded` in Fabric on 2026-11-11, then approved reference inputs plus legacy Gold only and requested a stop for feedback before corrected Gold.
- `nb_gold_run_legacy` invokes `nb_gold_reference_data` and `nb_gold_legacy` after Silver. No extra uploads are needed; embedded references are versioned snapshots of SliceDW's `03_reference_data.sql`.
- Legacy defects are preserved intentionally. Local independent source-based comparisons match every report metric, including 190 food-cost rows with no rounding tolerance. Period legacy net sales are $299,572.90 and invoice amount due is $21,061.48; these are incorrect business results retained as the migration baseline.
- Local tests use Parquet writes in place of Fabric Delta writes. Fabric execution, run-output capture, and deployed SliceDW/external export comparisons remain pending. Details and instructions are in `docs/gold-legacy.md`.
- Do not proceed to corrected Gold before user feedback/confirmation. The one ambiguous Silver Aloha match remains a corrected/reconciliation task.

## Provenance

This context was reconstructed from the user-provided `conversation-summary.md` attachment. The repository did not contain that attachment at the time these notes were added. Treat statements about run status, row counts, branch configuration, and workspace state as reported history; re-check live state before relying on them.