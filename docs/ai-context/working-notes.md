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

## Handoff uncertainty

The previous conversation mentioned “item 3” and later asked for step-by-step guidance. The prior assistant interpreted that as the upload step, but the phrase could have referred to Gold. Silver must precede Gold; confirm the intended step if this comes up again.

## Silver implementation handoff

- Five source-specific Silver notebooks and `nb_silver_run_all` are now in `fabric/`; run the orchestrator only after Bronze is available.
- The Silver runner calls master data, MICROS, Aloha, AS/400, then online app so its lookup and POS-matching dependencies exist.
- Silver flags and retains anomalous rows; Gold must explicitly decide business inclusion. `_batch_id` remains Bronze provenance, while `_silver_batch_id` identifies the transformation run.
- Local Python syntax and Fabric metadata were checked; live Spark/Fabric execution and output assertions remain pending.

## Provenance

This context was reconstructed from the user-provided `conversation-summary.md` attachment. The repository did not contain that attachment at the time these notes were added. Treat statements about run status, row counts, branch configuration, and workspace state as reported history; re-check live state before relying on them.